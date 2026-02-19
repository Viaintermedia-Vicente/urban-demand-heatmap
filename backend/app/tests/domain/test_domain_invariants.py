from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, func, select

from app.domain.canonical import CanonicalEvent, CanonicalWeatherHour
from app.infra.db.tables import events_table, metadata, weather_observations_table
from app.providers.hub import ProviderHub
from app.services.event_upsert import EventUpsertService
from app.services.weather_upsert import WeatherUpsertService
from app.services.sync_orchestrator import EventSyncRunner, WeatherSyncRunner

MADRID_TZ = ZoneInfo("Europe/Madrid")


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'domain.db'}", future=True)
    metadata.create_all(engine)
    return engine


def canonical_event(**overrides):
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    payload = {
        "source": "providerA",
        "external_id": overrides.get("external_id", "evt-1"),
        "title": overrides.get("title", "Demo Event"),
        "start": overrides.get("start", base),
        "end": overrides.get("end", base + timedelta(hours=2)),
        "lat": overrides.get("lat", 40.4168),
        "lon": overrides.get("lon", -3.7038),
        "venue_name": overrides.get("venue_name"),
    }
    return CanonicalEvent(**payload)


def canonical_weather(**overrides):
    base = datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc)
    payload = {
        "source": overrides.get("source", "providerWx"),
        "lat": overrides.get("lat", 40.4168),
        "lon": overrides.get("lon", -3.7038),
        "observed_at": overrides.get("observed_at", base),
        "temperature_c": overrides.get("temperature_c", 18.0),
    }
    return CanonicalWeatherHour(**payload)


class FakeEventProvider:
    def __init__(self, name: str, items: list[CanonicalEvent], fail: bool = False):
        self.name = name
        self.items = items
        self.fail = fail

    def fetch(self, city: str, past_days: int, future_days: int):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        for item in self.items:
            yield item


class FakeWeatherProvider:
    def __init__(self, name: str, items: list[CanonicalWeatherHour], fail: bool = False):
        self.name = name
        self.items = items
        self.fail = fail

    def fetch(self, lat: float, lon: float, past_days: int, future_days: int):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        for item in self.items:
            yield item


# --- Domain invariants: Events ------------------------------------------------


def test_event_unique_source_external_id(engine):
    service = EventUpsertService(engine)
    events = [canonical_event(external_id="evt-x"), canonical_event(external_id="evt-x")]
    service.upsert_events(events[:1])
    stats = service.upsert_events(events[1:])
    assert stats.get("inserted", 0) == 0
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1


def test_event_cross_provider_dedupe_rule(engine):
    service = EventUpsertService(engine)
    base = datetime(2026, 2, 18, 22, 0, tzinfo=timezone.utc)
    events = [
        CanonicalEvent("providerA", "evt-1", "Mega Show", base, base + timedelta(hours=2), 40.4, -3.7, "WiZink"),
        CanonicalEvent("providerB", "evt-z", "mega show", base, base + timedelta(hours=2), 40.4001, -3.7002, "wizink"),
    ]
    service.upsert_events(events)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1


def test_event_timezone_normalization(engine):
    service = EventUpsertService(engine)
    naive_start = datetime(2026, 3, 1, 22, 0)
    events = [canonical_event(external_id="evt-tz", start=naive_start, end=naive_start + timedelta(hours=1))]
    service.upsert_events(events)
    with engine.begin() as conn:
        stored = conn.execute(
            select(events_table.c.start_dt).where(events_table.c.external_id == "evt-tz")
        ).scalar_one()
    assert stored.tzinfo is not None
    assert stored.tzinfo.key == MADRID_TZ.key


def test_event_last_synced_updates(engine):
    service = EventUpsertService(engine)
    if "last_synced_at" not in events_table.c:
        pytest.fail("events table must include last_synced_at column for sync tracking")
    evt = canonical_event(external_id="evt-last")
    service.upsert_events([evt])
    with engine.begin() as conn:
        first = conn.execute(
            select(events_table.c.last_synced_at).where(events_table.c.external_id == "evt-last")
        ).scalar_one()
    later = canonical_event(external_id="evt-last")
    service.upsert_events([later])
    with engine.begin() as conn:
        second = conn.execute(
            select(events_table.c.last_synced_at).where(events_table.c.external_id == "evt-last")
        ).scalar_one()
    assert second > first


# --- Domain invariants: Weather -----------------------------------------------


def test_weather_unique_observed_at(engine):
    service = WeatherUpsertService(engine)
    hours = [canonical_weather(observed_at=datetime(2026, 2, 18, 8, tzinfo=timezone.utc))]
    service.upsert_hours(hours)
    stats = service.upsert_hours(hours)
    assert stats.get("inserted", 0) == 0


def test_weather_timezone_normalization(engine):
    service = WeatherUpsertService(engine)
    naive = datetime(2026, 2, 18, 9, 0)
    service.upsert_hours([canonical_weather(observed_at=naive)])
    with engine.begin() as conn:
        stored = conn.execute(select(weather_observations_table.c.observed_at)).scalar_one()
    assert stored.tzinfo is not None
    assert stored.tzinfo.key == MADRID_TZ.key


def test_weather_window_stability(engine):
    service = WeatherUpsertService(engine)
    for day in range(3):
        hours = [
            canonical_weather(observed_at=datetime(2026, 2, 18 + day, h, tzinfo=timezone.utc))
            for h in range(24)
        ]
        service.upsert_hours(hours)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 72


# --- Orchestrator resilience --------------------------------------------------


def test_sync_continues_if_one_provider_fails(engine):
    hub = ProviderHub()
    good_events = [canonical_event(external_id="ok-1", title="OK Event")]
    hub.register("events", FakeEventProvider("good", good_events))
    hub.register("events", FakeEventProvider("bad", [], fail=True))
    runner = EventSyncRunner(engine, hub)
    stats = runner.run(city="Madrid", past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1
    assert "errors" in stats and stats["errors"]


# --- Provider hub contracts ---------------------------------------------------


def test_provider_registry_register_and_list():
    hub = ProviderHub()
    hub.register("weather", FakeWeatherProvider("a", []))
    hub.register("weather", FakeWeatherProvider("b", []))
    names = [p.name for p in hub.list("weather")]
    assert names == ["a", "b"]


def test_sync_with_multiple_providers_combines_results(engine):
    hub = ProviderHub()
    hub.register("weather", FakeWeatherProvider("WxA", [canonical_weather(observed_at=datetime(2026, 2, 18, 10, tzinfo=timezone.utc))]))
    hub.register("weather", FakeWeatherProvider("WxB", [canonical_weather(observed_at=datetime(2026, 2, 18, 11, tzinfo=timezone.utc))]))
    runner = WeatherSyncRunner(engine, hub)
    stats = runner.run(lat=40.4, lon=-3.7, past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 2
    assert stats["weather"]["inserted"] == 2

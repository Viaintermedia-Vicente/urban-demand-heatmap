from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, func, select

from app.domain.canonical import CanonicalEvent, CanonicalWeatherHour
from app.hub.event_hub import EventHub
from app.hub.provider_registry import ProviderRegistry
from app.hub.weather_hub import WeatherHub
from app.hub.weather_registry import WeatherProviderRegistry
from app.infra.db.tables import events_table, metadata, weather_observations_table
from app.providers.events.base import ExternalEvent
from app.providers.weather.base import ExternalWeatherHour
from app.services.event_upsert import EventUpsertService
from app.services.weather_upsert import WeatherUpsertService

MADRID_TZ = ZoneInfo("Europe/Madrid")


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'domain.db'}", future=True)
    metadata.create_all(engine)
    return engine


def canonical_event(**overrides):
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    start_at = overrides.get("start_at", overrides.get("start", base))
    end_at = overrides.get("end_at", overrides.get("end", base + timedelta(hours=2)))
    payload = {
        "source": "providerA",
        "external_id": overrides.get("external_id", "evt-1"),
        "title": overrides.get("title", "Demo Event"),
        "start_at": start_at,
        "end_at": end_at,
        "lat": overrides.get("lat", 40.4168),
        "lon": overrides.get("lon", -3.7038),
        "venue_name": overrides.get("venue_name"),
    }
    return CanonicalEvent(**payload)


def external_event(provider: str, external_id: str, *, title: str = "Demo Event", hours_offset: int = 0) -> ExternalEvent:
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    start = base + timedelta(hours=hours_offset)
    return ExternalEvent(
        source=provider,
        external_id=external_id,
        title=title,
        start_at=start,
        end_at=start + timedelta(hours=2),
        category="music",
        subcategory=None,
        status=None,
        url=None,
        venue_name="Demo Venue",
        venue_external_id=f"venue-{provider}",
        venue_source=provider,
        venue_city="Madrid",
        venue_country="ES",
        lat=40.4168,
        lon=-3.7038,
        timezone="Europe/Madrid",
        popularity_score=None,
    )


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


def external_weather_hour(source: str, observed_at: datetime) -> ExternalWeatherHour:
    return ExternalWeatherHour(
        source=source,
        lat=40.4168,
        lon=-3.7038,
        observed_at=observed_at,
        temperature_c=18.0,
    )


class FakeEventProvider:
    def __init__(self, name: str, items: list[ExternalEvent], fail: bool = False):
        self.name = name
        self.items = items
        self.fail = fail

    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: datetime | None = None,
        direction: str = "future",
    ):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        if direction == "past":
            return []
        return list(self.items)


class FakeWeatherProvider:
    def __init__(self, name: str, items: list[ExternalWeatherHour], fail: bool = False):
        self.name = name
        self.items = items
        self.fail = fail

    def fetch_hourly(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        location_name: str | None = None,
    ):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        return list(self.items)


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
    assert stored is not None
    assert stored.hour == (naive_start + timedelta(hours=1)).hour


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
    assert stored is not None
    assert stored.hour == naive.hour + 1


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
    registry = ProviderRegistry()
    registry.register("good", FakeEventProvider("good", [external_event("good", "ok-1")]))
    registry.register("bad", FakeEventProvider("bad", [], fail=True))
    hub = EventHub(registry)

    stats = hub.sync(city="Madrid", past_days=0, future_days=1, session=engine)

    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1
    assert stats["errors"]


# --- Provider registry contracts ---------------------------------------------


def test_provider_registry_register_and_list():
    registry = ProviderRegistry()
    registry.register("a", FakeEventProvider("a", []))
    registry.register("b", FakeEventProvider("b", []))
    assert registry.list() == ["a", "b"]


# --- Weather hub aggregation --------------------------------------------------


def test_sync_with_multiple_providers_combines_results(engine):
    registry = WeatherProviderRegistry()
    base = datetime(2026, 2, 18, 10, tzinfo=timezone.utc)
    registry.register("WxA", FakeWeatherProvider("WxA", [external_weather_hour("WxA", base)]))
    registry.register("WxB", FakeWeatherProvider("WxB", [external_weather_hour("WxB", base + timedelta(hours=1))]))
    hub = WeatherHub(registry)
    stats = hub.sync(lat=40.4, lon=-3.7, start=base.date(), end=(base + timedelta(days=1)).date(), session=engine)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 2
    assert stats["inserted"] == 2


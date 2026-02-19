from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select

from app.domain.canonical import CanonicalEvent, CanonicalWeatherHour
from app.infra.db.tables import events_table, metadata, weather_observations_table
from app.providers.hub import ProviderHub
from app.services.sync_orchestrator import EventSyncRunner, WeatherSyncRunner


class FakeEventProvider:
    def __init__(self, name: str, fail: bool = False, count: int = 1):
        self.name = name
        self.fail = fail
        self.count = count

    def fetch(self, city: str, past_days: int, future_days: int):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        base = datetime(2026, 2, 18, tzinfo=timezone.utc)
        for idx in range(self.count):
            yield CanonicalEvent(
                source=self.name,
                external_id=f"{self.name}-{idx}",
                title=f"Event {idx}",
                start=base + timedelta(hours=idx),
                end=base + timedelta(hours=idx + 2),
                lat=40.4,
                lon=-3.7,
            )


class FakeWeatherProvider:
    def __init__(self, name: str, fail: bool = False, count: int = 1):
        self.name = name
        self.fail = fail
        self.count = count

    def fetch(self, lat: float, lon: float, past_days: int, future_days: int):
        if self.fail:
            raise RuntimeError("weather fail")
        base = datetime(2026, 2, 18, tzinfo=timezone.utc)
        for idx in range(self.count):
            yield CanonicalWeatherHour(
                source=self.name,
                lat=lat,
                lon=lon,
                observed_at=base + timedelta(hours=idx),
                temperature_c=20 + idx,
            )


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}", future=True)
    metadata.create_all(engine)
    return engine


def test_event_sync_combines_providers(engine):
    hub = ProviderHub()
    hub.register("events", FakeEventProvider("A", count=2))
    hub.register("events", FakeEventProvider("B", count=1))
    runner = EventSyncRunner(engine, hub)
    stats = runner.run(city="Madrid", past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 3
    assert stats["events"]["inserted"] == 3


def test_event_sync_handles_provider_failure(engine):
    hub = ProviderHub()
    hub.register("events", FakeEventProvider("A", count=1))
    hub.register("events", FakeEventProvider("B", fail=True))
    runner = EventSyncRunner(engine, hub)
    stats = runner.run(city="Madrid", past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1
    assert "errors" in stats


def test_weather_sync_combines_providers(engine):
    hub = ProviderHub()
    hub.register("weather", FakeWeatherProvider("WxA", count=5))
    hub.register("weather", FakeWeatherProvider("WxB", count=3))
    runner = WeatherSyncRunner(engine, hub)
    stats = runner.run(lat=40.4, lon=-3.7, past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 8
    assert stats["weather"]["inserted"] == 8


def test_weather_sync_continues_on_failure(engine):
    hub = ProviderHub()
    hub.register("weather", FakeWeatherProvider("WxA", count=2))
    hub.register("weather", FakeWeatherProvider("WxB", fail=True))
    runner = WeatherSyncRunner(engine, hub)
    stats = runner.run(lat=40.4, lon=-3.7, past_days=1, future_days=1)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 2
    assert "errors" in stats

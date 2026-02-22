from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select

from app.hub.event_hub import EventHub
from app.hub.provider_registry import ProviderRegistry
from app.hub.weather_hub import WeatherHub
from app.hub.weather_registry import WeatherProviderRegistry
from app.infra.db.tables import events_table, metadata, weather_observations_table
from app.providers.events.base import ExternalEvent
from app.providers.weather.base import ExternalWeatherHour


class FakeEventProvider:
    def __init__(self, name: str, count: int = 1, fail: bool = False) -> None:
        self.name = name
        self.count = count
        self.fail = fail

    def fetch_events(self, *, city: str, days: int, reference: datetime | None = None, direction: str = "future"):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        if direction == "past":
            return []
        reference = reference or datetime(2026, 2, 18, tzinfo=timezone.utc)
        events: list[ExternalEvent] = []
        for idx in range(self.count):
            start = reference + timedelta(hours=idx)
            events.append(
                ExternalEvent(
                    source=self.name,
                    external_id=f"{self.name}-{idx}",
                    title=f"Event {idx}",
                    start_at=start,
                    end_at=start + timedelta(hours=2),
                    category="music",
                    venue_name="Demo Venue",
                    venue_external_id=f"venue-{self.name}",
                    venue_source=self.name,
                    venue_city="Madrid",
                    venue_country="ES",
                    lat=40.4,
                    lon=-3.7,
                    timezone="Europe/Madrid",
                )
            )
        return events


class FakeWeatherProvider:
    def __init__(self, name: str, count: int = 1, fail: bool = False) -> None:
        self.name = name
        self.count = count
        self.fail = fail

    def fetch_hourly(self, *, lat: float, lon: float, start, end, location_name=None):
        if self.fail:
            raise RuntimeError("weather fail")
        base = datetime(2026, 2, 18, tzinfo=timezone.utc)
        payload: list[ExternalWeatherHour] = []
        for idx in range(self.count):
            payload.append(
                ExternalWeatherHour(
                    source=self.name,
                    lat=lat,
                    lon=lon,
                    observed_at=base + timedelta(hours=idx),
                    temperature_c=20 + idx,
                )
            )
        return payload


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}", future=True)
    metadata.create_all(engine)
    return engine


def test_event_sync_combines_providers(engine):
    registry = ProviderRegistry()
    registry.register("A", FakeEventProvider("A", count=2))
    registry.register("B", FakeEventProvider("B", count=1))
    hub = EventHub(registry)
    stats = hub.sync(city="Madrid", past_days=0, future_days=1, session=engine)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 2
    assert stats["inserted"] == 2


def test_event_sync_handles_provider_failure(engine):
    registry = ProviderRegistry()
    registry.register("A", FakeEventProvider("A", count=1))
    registry.register("B", FakeEventProvider("B", fail=True))
    hub = EventHub(registry)
    stats = hub.sync(city="Madrid", past_days=0, future_days=1, session=engine)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1
    assert stats["errors"]


def test_weather_sync_combines_providers(engine):
    registry = WeatherProviderRegistry()
    registry.register("WxA", FakeWeatherProvider("WxA", count=5))
    registry.register("WxB", FakeWeatherProvider("WxB", count=3))
    hub = WeatherHub(registry)
    stats = hub.sync(lat=40.4, lon=-3.7, start=datetime(2026, 2, 18).date(), end=datetime(2026, 2, 19).date(), session=engine)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 5
    assert stats["inserted"] == 5


def test_weather_sync_continues_on_failure(engine):
    registry = WeatherProviderRegistry()
    registry.register("WxA", FakeWeatherProvider("WxA", count=2))
    registry.register("WxB", FakeWeatherProvider("WxB", fail=True))
    hub = WeatherHub(registry)
    stats = hub.sync(lat=40.4, lon=-3.7, start=datetime(2026, 2, 18).date(), end=datetime(2026, 2, 19).date(), session=engine)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 2
    assert stats["errors"]

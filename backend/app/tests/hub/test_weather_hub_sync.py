from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from app.domain.canonical import CanonicalWeatherHour
from app.hub.weather_hub import WeatherHub
from app.hub.weather_registry import WeatherProviderRegistry
from app.infra.db.tables import metadata, weather_observations_table
from app.providers.weather.base import ExternalWeatherHour


class _StaticWeatherProvider:
    def __init__(self, name: str, hours: list[ExternalWeatherHour], fail: bool = False) -> None:
        self.name = name
        self._hours = hours
        self.fail = fail

    def fetch_hourly(self, *, lat: float, lon: float, start: date, end: date, location_name=None):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        return list(self._hours)


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "weather_hub.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def _external_hour(hour: int, source: str = "Wx") -> ExternalWeatherHour:
    observed = datetime(2026, 2, 18, hour, 0, tzinfo=timezone.utc)
    return ExternalWeatherHour(
        source=source,
        lat=40.4168,
        lon=-3.7038,
        observed_at=observed,
        temperature_c=20.0,
        precipitation_mm=0.0,
        cloud_cover_pct=30.0,
        wind_speed_kmh=12.0,
    )


def test_weather_hub_sync_persists(engine):
    registry = WeatherProviderRegistry()
    provider = _StaticWeatherProvider("main", [_external_hour(10), _external_hour(11)])
    registry.register("main", provider)
    hub = WeatherHub(registry)

    stats = hub.sync(lat=40.4, lon=-3.7, start=date(2026, 2, 18), end=date(2026, 2, 19), session=engine)

    assert stats["fetched"] == 2
    assert stats["inserted"] == 2
    assert not stats["errors"]
    with engine.begin() as conn:
        total = conn.execute(select(weather_observations_table.c.id)).all()
    assert len(total) == 2


def test_weather_hub_sync_provider_failure(engine):
    registry = WeatherProviderRegistry()
    good = _StaticWeatherProvider("good", [_external_hour(12)])
    bad = _StaticWeatherProvider("bad", [], fail=True)
    registry.register("good", good)
    registry.register("bad", bad)
    hub = WeatherHub(registry)

    stats = hub.sync(lat=40.4, lon=-3.7, start=date(2026, 2, 18), end=date(2026, 2, 19), session=engine)

    assert stats["inserted"] == 1
    assert stats["errors"]
    assert stats["errors"][0][0] == "bad"


def test_weather_hub_sync_idempotent(engine):
    registry = WeatherProviderRegistry()
    provider = _StaticWeatherProvider("main", [_external_hour(14)])
    registry.register("main", provider)
    hub = WeatherHub(registry)

    first = hub.sync(lat=40.4, lon=-3.7, start=date(2026, 2, 18), end=date(2026, 2, 18), session=engine)
    second = hub.sync(lat=40.4, lon=-3.7, start=date(2026, 2, 18), end=date(2026, 2, 18), session=engine)

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["updated"] >= 1

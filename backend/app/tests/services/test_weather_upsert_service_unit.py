from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from app.domain.canonical import CanonicalWeatherHour
from app.infra.db.tables import metadata, weather_observations_table
from app.services.weather_upsert import WeatherUpsertService


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "weather_service.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def make_hour(observed_hour: int = 10, temp: float = 20.0) -> CanonicalWeatherHour:
    observed = datetime(2026, 2, 18, observed_hour, 0, tzinfo=timezone.utc)
    return CanonicalWeatherHour(
        source="providerWx",
        lat=40.4168,
        lon=-3.7038,
        observed_at=observed,
        temperature_c=temp,
        precipitation_mm=0.5,
        wind_speed_kmh=10.0,
        cloud_cover_pct=50.0,
    )


def test_insert_weather(engine):
    service = WeatherUpsertService(engine)
    stats = service.upsert_hours([make_hour(10), make_hour(11, 22.0)])
    assert stats == {"inserted": 2, "updated": 0, "total": 2}
    with engine.begin() as conn:
        rows = conn.execute(select(weather_observations_table.c.id)).all()
    assert len(rows) == 2


def test_update_weather(engine):
    service = WeatherUpsertService(engine)
    hour = make_hour(12, 18.0)
    service.upsert_hours([hour])
    updated = make_hour(12, 21.0)
    stats = service.upsert_hours([updated])
    assert stats["updated"] == 1
    with engine.begin() as conn:
        stored = conn.execute(
            select(weather_observations_table.c.temperature_c).where(
                weather_observations_table.c.observed_at == updated.observed_at
            )
        ).scalar_one()
    assert stored == 21.0


def test_idempotent_second_run(engine):
    service = WeatherUpsertService(engine)
    hours = [make_hour(14), make_hour(15)]
    service.upsert_hours(hours)
    stats = service.upsert_hours(hours)
    assert stats["inserted"] == 0
    assert stats["updated"] == 2

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select

from app.domain.canonical import CanonicalWeatherHour
from app.infra.db.tables import metadata, weather_observations_table
from app.services.weather_upsert import WeatherUpsertService


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'weather.db'}", future=True)
    metadata.create_all(engine)
    return engine


def sample_hour(offset: int = 0):
    observed = datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc) + timedelta(hours=offset)
    return CanonicalWeatherHour(
        source="providerA",
        lat=40.4,
        lon=-3.7,
        observed_at=observed,
        temperature_c=18.0 + offset,
    )


def test_weather_upsert_idempotent(engine):
    service = WeatherUpsertService(engine)
    hours = [sample_hour(i) for i in range(3)]
    service.upsert_hours(hours)
    stats = service.upsert_hours(hours)
    assert stats["inserted"] == 0
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(weather_observations_table)).scalar()
    assert count == 3


def test_weather_upsert_marks_offline_source(engine):
    service = WeatherUpsertService(engine)
    hours = [sample_hour(0)]
    hours[0].source = "offline"
    service.upsert_hours(hours)
    with engine.begin() as conn:
        stored = conn.execute(select(weather_observations_table.c.source)).scalar_one()
    assert stored == "offline"


def test_weather_upsert_handles_large_window(engine):
    service = WeatherUpsertService(engine)
    hours = [sample_hour(i) for i in range(24 * 3)]
    result = service.upsert_hours(hours)
    assert result["inserted"] == len(hours)

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.deps import get_engine
from app.api.main import create_app
from app.infra.db.tables import metadata, weather_observations_table
from app.jobs.import_csv import import_events_from_csv

TARGET_DATE = "2026-03-01"
TARGET_HOUR = 22
LAT = 40.4168
LON = -3.7038


@pytest.fixture()
def heatmap_client(tmp_path):
    db_path = tmp_path / "heatmap_weather.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)
    metadata.create_all(engine)
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)
    app = create_app(engine=engine)
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()


def insert_weather(engine, temperature, precipitation, wind):
    observed_at = datetime(2026, 3, 1, TARGET_HOUR, tzinfo=timezone.utc)
    with engine.begin() as conn:
        conn.execute(weather_observations_table.delete())
        conn.execute(
            weather_observations_table.insert().values(
                source="test",
                location_name="Madrid",
                lat=LAT,
                lon=LON,
                observed_at=observed_at,
                temperature_c=temperature,
                precipitation_mm=precipitation,
                rain_mm=precipitation,
                snowfall_mm=0.0,
                cloud_cover_pct=30.0,
                wind_speed_kmh=wind,
                wind_gust_kmh=wind,
                wind_dir_deg=90.0,
                humidity_pct=50.0,
                pressure_hpa=1012.0,
                visibility_m=10000.0,
                weather_code=1,
            )
        )


def test_heatmap_weather_influence(heatmap_client):
    client, engine = heatmap_client
    insert_weather(engine, temperature=20.0, precipitation=0.0, wind=5.0)
    good = client.get(
        "/api/heatmap",
        params={"date": TARGET_DATE, "hour": TARGET_HOUR, "lat": LAT, "lon": LON},
    )
    good_score = good.json()["hotspots"][0]["score"]

    insert_weather(engine, temperature=5.0, precipitation=5.0, wind=40.0)
    bad = client.get(
        "/api/heatmap",
        params={"date": TARGET_DATE, "hour": TARGET_HOUR, "lat": LAT, "lon": LON},
    )
    bad_score = bad.json()["hotspots"][0]["score"]

    assert good_score > bad_score

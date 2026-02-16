from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.jobs.import_weather import import_weather


class DummyWeatherClient:
    def __init__(self):
        self._calls = 0

    def fetch_hourly(self, lat, lon, start_date, end_date, location_name=None):
        self._calls += 1
        base = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
        return [
            {
                "source": "open_meteo",
                "location_name": location_name,
                "lat": lat,
                "lon": lon,
                "observed_at": base,
                "temperature_c": 15.0,
                "precipitation_mm": 0.2,
                "rain_mm": 0.2,
                "snowfall_mm": 0.0,
                "cloud_cover_pct": 60.0,
                "wind_speed_kmh": 10.0,
                "wind_gust_kmh": 20.0,
                "wind_dir_deg": 180.0,
                "humidity_pct": 55.0,
                "pressure_hpa": 1015.0,
                "visibility_m": 10000.0,
                "weather_code": 3,
            }
        ]


def test_import_weather_creates_tables_and_is_idempotent(tmp_path):
    db_path = tmp_path / "weather.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    client = DummyWeatherClient()

    import_weather(
        lat=40.4168,
        lon=-3.7038,
        start_date="2026-03-01",
        end_date="2026-03-01",
        location_name="Madrid",
        engine=engine,
        client=client,
    )

    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        assert {row[0] for row in tables} >= {"weather_observations"}
        count1 = conn.execute(text("SELECT COUNT(*) FROM weather_observations")).scalar_one()

    import_weather(
        lat=40.4168,
        lon=-3.7038,
        start_date="2026-03-01",
        end_date="2026-03-01",
        location_name="Madrid",
        engine=engine,
        client=client,
    )

    with engine.connect() as conn:
        count2 = conn.execute(text("SELECT COUNT(*) FROM weather_observations")).scalar_one()
    assert count1 == count2 == 1

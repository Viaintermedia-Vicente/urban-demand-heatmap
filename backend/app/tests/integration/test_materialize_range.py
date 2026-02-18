from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.jobs.import_csv import import_events_from_csv
from app.jobs.materialize_range import materialize_range


def insert_weather(engine, dt):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO weather_observations (
                    source, location_name, lat, lon, observed_at,
                    temperature_c, precipitation_mm, rain_mm, snowfall_mm,
                    cloud_cover_pct, wind_speed_kmh, wind_gust_kmh, wind_dir_deg,
                    humidity_pct, pressure_hpa, visibility_m, weather_code,
                    created_at, updated_at
                ) VALUES (
                    'test', 'Madrid', 40.4168, -3.7038, :obs,
                    19.0, 0.1, 0.1, 0.0,
                    30.0, 10.0, 15.0, 100.0,
                    50.0, 1010.0, 8000.0, 3,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"obs": dt},
        )


def test_materialize_range_multiple_snapshots(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'range.db'}", future=True)
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)

    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for offset in range(3):
        day = start.replace(day=start.day + offset)
        for hour in (18, 20, 22):
            insert_weather(engine, day.replace(hour=hour))

    summary = materialize_range(
        start_date="2026-03-01",
        end_date="2026-03-03",
        hours="18,20,22",
        engine=engine,
    )

    assert summary["inserted"] >= 9
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM event_feature_snapshots")).scalar_one()
    assert count >= 9

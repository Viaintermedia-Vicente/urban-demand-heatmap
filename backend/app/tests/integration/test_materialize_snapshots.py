from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.jobs.import_csv import import_events_from_csv
from app.jobs.materialize_snapshots import materialize_snapshots


def test_materialize_snapshots_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "snapshots.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)

    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)

    # insertar clima mediante repository directo
    observed_at = datetime(2026, 3, 1, 22, tzinfo=timezone.utc)
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
                    20, 0, 0, 0,
                    20, 10, 15, 90,
                    40, 1015, 10000, 1,
                    :now, :now
                )
                """
            ),
            {"obs": observed_at.isoformat(), "now": datetime.now(timezone.utc).isoformat()},
        )

    result1 = materialize_snapshots(
        date_str="2026-03-01",
        hour=22,
        engine=engine,
        lat=40.4168,
        lon=-3.7038,
    )
    result2 = materialize_snapshots(
        date_str="2026-03-01",
        hour=22,
        engine=engine,
        lat=40.4168,
        lon=-3.7038,
    )

    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='event_feature_snapshots'")
        ).fetchall()
        assert tables
        count1 = conn.execute(text("SELECT COUNT(*) FROM event_feature_snapshots")).scalar_one()
        assert count1 > 0
        row = conn.execute(
            text(
                "SELECT score_base, score_weather_factor, score_final FROM event_feature_snapshots LIMIT 1"
            )
        ).fetchone()
    assert round(row[0] * row[1], 4) == round(row[2], 4)
    result_again = materialize_snapshots(
        date_str="2026-03-01",
        hour=22,
        engine=engine,
        lat=40.4168,
        lon=-3.7038,
    )
    with engine.connect() as conn:
        count2 = conn.execute(text("SELECT COUNT(*) FROM event_feature_snapshots")).scalar_one()
    assert count1 == count2
    assert result_again["updated"] >= result_again["inserted"]

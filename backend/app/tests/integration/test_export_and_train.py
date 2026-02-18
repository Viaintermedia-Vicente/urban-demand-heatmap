from __future__ import annotations

import csv

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.jobs.export_training_dataset import export_training_dataset
from app.jobs.import_csv import import_events_from_csv
from app.jobs.materialize_snapshots import materialize_snapshots
from app.jobs.train_baseline import train_baseline

from app.infra.db.snapshots_repository import EventFeatureSnapshotsRepository
from app.infra.db.tables import metadata


def test_export_and_train_pipeline(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dataset.db'}", future=True)
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)

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
                    18, 0.1, 0.1, 0.0,
                    30, 8, 12, 100,
                    45, 1013, 9000, 3,
                    :now, :now
                )
                """
            ),
            {"obs": observed_at.isoformat(), "now": datetime.now(timezone.utc).isoformat()},
        )

    materialize_snapshots(
        date_str="2026-03-01",
        hour=22,
        engine=engine,
        lat=40.4168,
        lon=-3.7038,
    )

    csv_path = tmp_path / "dataset.csv"
    export_training_dataset(
        csv_path,
        start_date="2026-03-01",
        end_date="2026-03-02",
        engine=engine,
    )
    assert csv_path.exists()
    assert csv_path.read_text().count("\n") > 1

    model_path = tmp_path / "model.json"
    metrics = train_baseline(csv_path, model_out=model_path)
    assert model_path.exists()
    assert metrics["rmse"] >= 0


def test_export_training_dataset_multiple_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'many.db'}", future=True)
    metadata.create_all(engine)
    repo = EventFeatureSnapshotsRepository(engine)
    base_target = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
    snapshots = []
    for idx in range(6):
        target = base_target + timedelta(hours=idx)
        snapshots.append(
            {
                "target_at": target,
                "event_id": f"evt-{idx}",
                "event_start_dt": target,
                "event_end_dt": target + timedelta(hours=2),
                "lat": 40.4 + idx * 0.01,
                "lon": -3.7 - idx * 0.01,
                "category": "music",
                "expected_attendance": 1000 + idx * 10,
                "hours_to_start": float(idx),
                "weekday": target.weekday(),
                "month": target.month,
                "temperature_c": 18.0 + idx,
                "precipitation_mm": 0.2,
                "rain_mm": 0.2,
                "snowfall_mm": 0.0,
                "wind_speed_kmh": 12.0,
                "wind_gust_kmh": 18.0,
                "weather_code": 3,
                "humidity_pct": 55.0,
                "pressure_hpa": 1012.0,
                "visibility_m": 9000.0,
                "cloud_cover_pct": 30.0,
                "score_base": 1.0 + idx * 0.05,
                "score_weather_factor": 0.9,
                "score_final": (1.0 + idx * 0.05) * 0.9,
            }
        )
    repo.upsert_many(snapshots)

    csv_path = tmp_path / "many_snapshots.csv"
    result = export_training_dataset(
        csv_path,
        start_date="2026-03-01",
        end_date="2026-03-05",
        engine=engine,
    )
    assert result["rows"] >= 6
    assert csv_path.exists()
    with csv_path.open() as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
    assert len(rows) >= 6
    assert "label_lead_time_min" in rows[0]
    assert "label_attendance_factor" in rows[0]

def test_export_training_dataset_contains_label_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'labels.db'}", future=True)
    metadata.create_all(engine)
    repo = EventFeatureSnapshotsRepository(engine)
    target = datetime(2026, 3, 2, 18, tzinfo=timezone.utc)
    repo.upsert_many(
        [
            {
                "target_at": target,
                "event_id": "evt-label",
                "event_start_dt": target + timedelta(hours=1),
                "event_end_dt": target + timedelta(hours=3),
                "lat": 40.4,
                "lon": -3.7,
                "category": "sports",
                "expected_attendance": 5000,
                "hours_to_start": 1.0,
                "weekday": target.weekday(),
                "month": target.month,
                "temperature_c": 10.0,
                "precipitation_mm": 0.5,
                "rain_mm": 0.5,
                "snowfall_mm": 0.0,
                "wind_speed_kmh": 20.0,
                "wind_gust_kmh": 35.0,
                "weather_code": 2,
                "humidity_pct": 60.0,
                "pressure_hpa": 1008.0,
                "visibility_m": 8000.0,
                "cloud_cover_pct": 80.0,
                "score_base": 1.2,
                "score_weather_factor": 0.85,
                "score_final": 1.02,
            }
        ]
    )
    csv_path = tmp_path / 'labels.csv'
    export_training_dataset(
        csv_path,
        start_date='2026-03-02',
        end_date='2026-03-02',
        engine=engine,
    )
    with csv_path.open() as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
    assert rows, 'dataset must contain at least one row'
    row = rows[0]
    assert 'label_lead_time_min' in row
    assert 'label_attendance_factor' in row


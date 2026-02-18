from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import create_engine

from app.jobs.generate_demo_events import generate_demo_events
from app.jobs.materialize_range import materialize_range
from app.jobs.sync_weather import sync_weather
from app.jobs.export_training_dataset import export_training_dataset
from app.jobs.train_baseline import train_baseline
from app.infra.db.tables import metadata

app = typer.Typer(help="Inflar datos demo: eventos, meteo, snapshots y dataset")
BACKEND_DIR = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_DATASET_PATH = Path(os.getenv("DATASET_OUT", PROJECT_ROOT / "dataset.csv"))
DEFAULT_MODEL_DIR = Path(os.getenv("MODEL_OUT_DIR", PROJECT_ROOT))


def inflate_demo_data(
    *,
    city: str,
    lat: float,
    lon: float,
    past_days: int = 90,
    future_days: int = 30,
    per_day: int = 20,
    hours: str = "0-23",
    engine=None,
    database_url: Optional[str] = None,
    dataset_path: Optional[Path] = None,
    model_dir: Optional[Path] = None,
    reference_date: Optional[date] = None,
) -> dict:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days/future_days deben ser >=0")
    if per_day <= 0:
        raise ValueError("per_day debe ser > 0")
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)

    dataset_path = Path(dataset_path or DEFAULT_DATASET_PATH)
    model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
    reference_date = reference_date or datetime.now(timezone.utc).date()
    start_day = reference_date - timedelta(days=past_days)
    end_day = reference_date + timedelta(days=future_days)

    event_stats = generate_demo_events(
        city=city,
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        per_day=per_day,
        engine=engine,
        reference_date=reference_date,
    )

    weather_stats = sync_weather(
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        engine=engine,
        location_name=city,
        reference=reference_date,
        offline=True,
    )

    materialize_range(
        start_day.isoformat(),
        end_day.isoformat(),
        hours,
        lat=lat,
        lon=lon,
        engine=engine,
    )

    dataset_stats = export_training_dataset(
        dataset_path,
        start_date=start_day.isoformat(),
        end_date=end_day.isoformat(),
        engine=engine,
    )
    rows = dataset_stats.get("rows", 0)
    models_trained = []
    if rows > 50:
        model_dir.mkdir(parents=True, exist_ok=True)
        lead_path = model_dir / "model_lead_time.json"
        att_path = model_dir / "model_attendance_factor.json"
        train_baseline(dataset_path, model_out=lead_path, target_col="label_lead_time_min")
        train_baseline(dataset_path, model_out=att_path, target_col="label_attendance_factor")
        models_trained = [str(lead_path), str(att_path)]

    summary = {
        "events": event_stats,
        "weather": weather_stats,
        "dataset_rows": rows,
        "dataset_path": str(dataset_path),
        "models_trained": models_trained,
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
    }
    print(
        f"[inflate_demo_data] city={city} range={start_day}:{end_day} "
        f"events={event_stats['inserted']} weather_inserted={weather_stats['inserted']} rows={rows}"
    )
    return summary


@app.command()
def cli(
    city: str = typer.Option(..., help="Ciudad"),
    lat: float = typer.Option(..., help="Latitud"),
    lon: float = typer.Option(..., help="Longitud"),
    past_days: int = typer.Option(90, help="Días hacia atrás"),
    future_days: int = typer.Option(30, help="Días hacia adelante"),
    per_day: int = typer.Option(20, help="Eventos por día"),
    hours: str = typer.Option("0-23", help="Horas a materializar"),
    dataset_path: Optional[Path] = typer.Option(None, dir_okay=False, help="Ruta dataset"),
    model_dir: Optional[Path] = typer.Option(None, help="Ruta modelos"),
):
    inflate_demo_data(
        city=city,
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        per_day=per_day,
        hours=hours,
        dataset_path=dataset_path,
        model_dir=model_dir,
    )


if __name__ == "__main__":
    app()

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import create_engine

from app.infra.db.tables import metadata
from app.jobs.export_training_dataset import export_training_dataset
from app.jobs.materialize_range import materialize_range
from app.jobs.sync_events import sync_events
from app.jobs.sync_weather import sync_weather
from app.jobs.train_baseline import train_baseline

app = typer.Typer(help="Ejecuta sync de eventos + meteo sobre una ventana temporal configurable")
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_DATASET_PATH = Path(os.getenv("DATASET_OUT", PROJECT_ROOT / "dataset.csv"))
DEFAULT_MODEL_DIR = Path(os.getenv("MODEL_OUT_DIR", PROJECT_ROOT))


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def run_window_sync(
    *,
    city: str,
    lat: float,
    lon: float,
    base_date: date,
    past_days: int,
    future_days: int,
    hours: str,
    offline_weather: bool = False,
    materialize: bool = False,
    export_dataset: bool = False,
    train_models: bool = False,
    dataset_path: Optional[Path] = None,
    model_dir: Optional[Path] = None,
    engine=None,
    database_url: Optional[str] = None,
) -> dict:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days/future_days deben ser >= 0")
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)

    dataset_path = Path(dataset_path or DEFAULT_DATASET_PATH)
    model_dir = Path(model_dir or DEFAULT_MODEL_DIR)

    start_day = base_date - timedelta(days=past_days)
    end_day = base_date + timedelta(days=future_days)

    weather_stats = sync_weather(
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        engine=engine,
        location_name=city,
        reference=base_date,
        offline=offline_weather,
    )

    event_reference = datetime.combine(base_date, datetime.min.time(), tzinfo=timezone.utc)
    try:
        event_stats = sync_events(
            city=city,
            past_days=past_days,
            future_days=future_days,
            engine=engine,
            reference=event_reference,
        )["events"]
    except Exception as exc:
        print(f"[run_window_sync] WARNING: sync_events failed ({exc}); continuing")
        event_stats = {"inserted": 0, "updated": 0, "skipped": 0}

    snapshot_stats = None
    if materialize:
        snapshot_stats = materialize_range(
            start_day.isoformat(),
            end_day.isoformat(),
            hours,
            lat=lat,
            lon=lon,
            engine=engine,
        )

    dataset_stats = None
    models_trained: list[str] = []
    if export_dataset:
        dataset_stats = export_training_dataset(
            dataset_path,
            start_date=start_day.isoformat(),
            end_date=end_day.isoformat(),
            engine=engine,
        )
        if train_models and dataset_stats.get("rows", 0) > 50:
            model_dir.mkdir(parents=True, exist_ok=True)
            lead_model = model_dir / "model_lead_time.json"
            att_model = model_dir / "model_attendance_factor.json"
            train_baseline(dataset_path, model_out=lead_model, target_col="label_lead_time_min")
            train_baseline(dataset_path, model_out=att_model, target_col="label_attendance_factor")
            models_trained = [str(lead_model), str(att_model)]

    summary = {
        "city": city,
        "base_date": base_date.isoformat(),
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "weather": weather_stats,
        "events": event_stats,
        "snapshots": snapshot_stats,
        "dataset": dataset_stats,
        "models": models_trained,
    }
    print(
        "[run_window_sync] "
        f"base={base_date.isoformat()} range={start_day}:{end_day} "
        f"events={event_stats} weather={weather_stats} "
        f"snapshots={snapshot_stats if snapshot_stats else {}} "
        f"dataset_rows={dataset_stats.get('rows') if dataset_stats else 'N/A'}"
    )
    return summary


@app.command()
def cli(
    city: str = typer.Option(..., help="Ciudad a sincronizar"),
    lat: float = typer.Option(..., help="Latitud"),
    lon: float = typer.Option(..., help="Longitud"),
    base_date: str = typer.Option(..., help="Fecha base YYYY-MM-DD"),
    past_days: int = typer.Option(10, help="Días hacia atrás"),
    future_days: int = typer.Option(10, help="Días hacia adelante"),
    hours: str = typer.Option("0-23", help="Horas a materializar"),
    offline_weather: bool = typer.Option(False, help="Forzar meteo offline"),
    materialize: bool = typer.Option(False, help="Materializar snapshots"),
    export_dataset: bool = typer.Option(False, help="Exportar dataset"),
    train: bool = typer.Option(False, help="Entrenar modelos si hay dataset"),
    dataset_path: Optional[Path] = typer.Option(None, help="Ruta dataset"),
    model_dir: Optional[Path] = typer.Option(None, help="Directorio modelos"),
):
    run_window_sync(
        city=city,
        lat=lat,
        lon=lon,
        base_date=_parse_date(base_date),
        past_days=past_days,
        future_days=future_days,
        hours=hours,
        offline_weather=offline_weather,
        materialize=materialize,
        export_dataset=export_dataset,
        train_models=train,
        dataset_path=dataset_path,
        model_dir=model_dir,
    )


if __name__ == "__main__":
    app()

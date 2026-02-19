from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import create_engine
from zoneinfo import ZoneInfo

from app.hub.event_hub import EventHub
from app.hub.provider_registry import ProviderRegistry
from app.hub.weather_hub import WeatherHub
from app.hub.weather_registry import WeatherProviderRegistry
from app.infra.db.tables import metadata
from app.jobs.export_training_dataset import export_training_dataset
from app.jobs.materialize_range import materialize_range
from app.jobs.train_baseline import train_baseline
from app.jobs.sync_weather import _DemoWeatherProvider
from app.providers.events.base import EventsProvider, ExternalEvent
from app.providers.events.ticketmaster import TicketmasterEventsProvider
from app.providers.weather.base import WeatherProvider
from app.providers.weather.open_meteo import OpenMeteoWeatherProvider

MADRID_TZ = ZoneInfo("Europe/Madrid")
DEFAULT_COUNTRY = os.getenv("DAILY_SYNC_COUNTRY", "ES")
PROJECT_ROOT = Path(__file__).resolve().parents[2].parent
DEFAULT_DATASET_PATH = Path(os.getenv("DATASET_OUT", PROJECT_ROOT / "dataset.csv"))
DEFAULT_MODEL_DIR = Path(os.getenv("MODEL_OUT_DIR", PROJECT_ROOT))

app = typer.Typer(help="Daily sync job for events + weather + optional materialization/training")


def daily_sync(
    *,
    city: str,
    lat: float,
    lon: float,
    past_days: int,
    future_days: int,
    hours: str,
    offline_weather: bool = False,
    materialize: bool = False,
    train: bool = False,
    base_date: Optional[date] = None,
    engine=None,
    database_url: Optional[str] = None,
    dataset_path: Optional[Path] = None,
    model_dir: Optional[Path] = None,
) -> dict:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days/future_days must be >= 0")

    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)

    metadata.create_all(engine)

    today = (base_date or datetime.now(MADRID_TZ).date())
    start_day = today - timedelta(days=past_days)
    end_day = today + timedelta(days=future_days)

    event_hub = _build_event_hub()
    event_stats = event_hub.sync(city=city, past_days=past_days, future_days=future_days, session=engine)

    weather_hub = _build_weather_hub(offline_weather=offline_weather)
    weather_stats = weather_hub.sync(
        lat=lat,
        lon=lon,
        start=start_day,
        end=end_day,
        session=engine,
        location_name=city,
    )

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
    trained_models: list[str] = []
    if train:
        dataset_path = Path(dataset_path or DEFAULT_DATASET_PATH)
        model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        dataset_stats = export_training_dataset(
            dataset_path,
            start_date=start_day.isoformat(),
            end_date=end_day.isoformat(),
            engine=engine,
        )
        if dataset_stats.get("rows", 0) > 50:
            model_dir.mkdir(parents=True, exist_ok=True)
            lead_model = model_dir / "model_lead_time.json"
            att_model = model_dir / "model_attendance_factor.json"
            train_baseline(dataset_path, model_out=lead_model, target_col="label_lead_time_min")
            train_baseline(dataset_path, model_out=att_model, target_col="label_attendance_factor")
            trained_models = [str(lead_model), str(att_model)]

    summary = {
        "city": city,
        "base_date": today.isoformat(),
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "events": event_stats,
        "weather": weather_stats,
        "snapshots": snapshot_stats,
        "dataset": dataset_stats,
        "models": trained_models,
    }
    print(
        f"[daily_sync] base={today} city={city} range={start_day}:{end_day} "
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
    past_days: int = typer.Option(10, help="Días hacia atrás"),
    future_days: int = typer.Option(10, help="Días hacia adelante"),
    hours: str = typer.Option("0-23", help="Horas para materializar"),
    base_date: Optional[str] = typer.Option(None, help="Fecha base YYYY-MM-DD"),
    offline_weather: bool = typer.Option(False, help="Forzar proveedor meteo offline"),
    materialize: bool = typer.Option(False, help="Materializar snapshots"),
    train: bool = typer.Option(False, help="Exportar dataset y entrenar modelos"),
):
    parsed_date = datetime.fromisoformat(base_date).date() if base_date else None
    daily_sync(
        city=city,
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        hours=hours,
        offline_weather=offline_weather,
        materialize=materialize,
        train=train,
        base_date=parsed_date,
    )


def _build_event_hub() -> EventHub:
    registry = ProviderRegistry()
    provider = _resolve_events_provider()
    name = provider.__class__.__name__.lower()
    registry.register(name, provider)
    return EventHub(registry)


def _build_weather_hub(*, offline_weather: bool) -> WeatherHub:
    registry = WeatherProviderRegistry()
    provider = _resolve_weather_provider(offline_weather=offline_weather)
    name = provider.__class__.__name__.lower()
    registry.register(name, provider)
    return WeatherHub(registry)


def _resolve_events_provider() -> EventsProvider:
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if api_key:
        try:
            return TicketmasterEventsProvider(api_key=api_key)
        except Exception as exc:  # pragma: no cover
            print(f"[daily_sync] WARNING: Ticketmaster provider unavailable ({exc}); using demo")
    return _DemoEventsProvider()


def _resolve_weather_provider(*, offline_weather: bool) -> WeatherProvider:
    if offline_weather:
        return _DemoWeatherProvider()
    return OpenMeteoWeatherProvider()


class _DemoEventsProvider(EventsProvider):
    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: Optional[datetime] = None,
        direction: str = "future",
    ) -> list[ExternalEvent]:
        reference = reference or datetime.now(ZoneInfo("UTC"))
        count = max(1, min(5, days))
        records: list[ExternalEvent] = []
        for idx in range(count):
            offset_days = idx if direction == "future" else -(idx + 1)
            start = reference + timedelta(days=offset_days)
            records.append(
                ExternalEvent(
                    source="demo",
                    external_id=f"demo-{direction}-{idx}",
                    title=f"Demo {city} {direction} {idx}",
                    category="music",
                    start_at=start,
                    end_at=start + timedelta(hours=2),
                    venue_name=f"Demo Venue {idx}",
                    venue_external_id=f"demo-venue-{idx}",
                    venue_city=city,
                    venue_country=DEFAULT_COUNTRY,
                    lat=40.4 + 0.01 * idx,
                    lon=-3.7 - 0.01 * idx,
                    url="https://demo.local/event",
                )
            )
        return records


if __name__ == "__main__":
    app()

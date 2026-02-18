from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, Optional

import typer
from sqlalchemy import create_engine

from app.infra.db.tables import metadata
from app.infra.db.weather_repository import WeatherRepository
from app.providers.weather.base import ExternalWeatherHour, WeatherProvider

app = typer.Typer(help="Sync hourly weather observations into the database")
DEFAULT_LAT = float(os.getenv("SYNC_WEATHER_LAT", "40.4168"))
DEFAULT_LON = float(os.getenv("SYNC_WEATHER_LON", "-3.7038"))
DEFAULT_SOURCE = os.getenv("SYNC_WEATHER_SOURCE", "demo")


def sync_weather(
    *,
    lat: float,
    lon: float,
    past_days: int = 0,
    future_days: int = 1,
    provider: Optional[WeatherProvider] = None,
    engine=None,
    database_url: Optional[str] = None,
    location_name: Optional[str] = None,
    reference: Optional[date] = None,
) -> Dict[str, int]:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days and future_days must be >= 0")
    if past_days == 0 and future_days == 0:
        raise ValueError("At least one of past_days/future_days must be > 0")
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)
    repo = WeatherRepository(engine)
    provider = provider or _DemoWeatherProvider()
    reference = reference or datetime.now(timezone.utc).date()
    start_day = reference - timedelta(days=past_days)
    end_day = reference + timedelta(days=future_days)
    observations = provider.fetch_hourly(
        lat=lat,
        lon=lon,
        start=start_day,
        end=end_day,
        location_name=location_name,
    )
    result = repo.upsert_many(_normalize_records(observations))
    _log_summary(lat, lon, result, start_day, end_day)
    return result


@app.command()
def run(
    lat: float = typer.Option(DEFAULT_LAT, help="Latitude"),
    lon: float = typer.Option(DEFAULT_LON, help="Longitude"),
    past_days: int = typer.Option(0, help="Days to backfill"),
    future_days: int = typer.Option(1, help="Days forward"),
    location_name: Optional[str] = typer.Option(None, help="Label for stored observations"),
):
    """CLI entrypoint for weather sync."""
    sync_weather(lat=lat, lon=lon, past_days=past_days, future_days=future_days, location_name=location_name)


def _normalize_records(observations: Iterable[ExternalWeatherHour]):
    for obs in observations:
        observed = obs.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        else:
            observed = observed.astimezone(timezone.utc)
        payload = {
            "source": obs.source or DEFAULT_SOURCE,
            "lat": obs.lat,
            "lon": obs.lon,
            "observed_at": observed,
            "location_name": obs.location_name,
            "temperature_c": obs.temperature_c,
            "precipitation_mm": obs.precipitation_mm,
            "rain_mm": obs.rain_mm,
            "snowfall_mm": obs.snowfall_mm,
            "cloud_cover_pct": obs.cloud_cover_pct,
            "wind_speed_kmh": obs.wind_speed_kmh,
            "wind_gust_kmh": obs.wind_gust_kmh,
            "wind_dir_deg": obs.wind_dir_deg,
            "humidity_pct": obs.humidity_pct,
            "pressure_hpa": obs.pressure_hpa,
            "visibility_m": obs.visibility_m,
            "weather_code": obs.weather_code,
        }
        yield payload


def _log_summary(lat: float, lon: float, stats: Dict[str, int], start: date, end: date):
    db_url = os.getenv("DATABASE_URL", "<engine>")
    print(
        f"[sync_weather] lat={lat} lon={lon} db={db_url} range={start}:{end} "
        f"inserted={stats['inserted']} updated={stats['updated']}"
    )

class _DemoWeatherProvider:
    def fetch_hourly(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        location_name: Optional[str] = None,
    ) -> list[ExternalWeatherHour]:
        hours = int(((end - start).days + 1) * 24)
        records = []
        base = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        for idx in range(hours):
            ts = base + timedelta(hours=idx)
            records.append(
                ExternalWeatherHour(
                    source="demo",
                    lat=lat,
                    lon=lon,
                    observed_at=ts,
                    location_name=location_name or "demo-weather",
                    temperature_c=18 + 5 * ((idx % 24) / 24),
                    precipitation_mm=0.5 if idx % 12 == 0 else 0.0,
                    wind_speed_kmh=10 + (idx % 5),
                    cloud_cover_pct=60.0,
                )
            )
        return records


if __name__ == "__main__":
    app()

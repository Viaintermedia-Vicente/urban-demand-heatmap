from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import typer
from sqlalchemy import create_engine

from app.infra.db.tables import metadata
from app.infra.db.weather_repository import WeatherRepository
from app.infra.weather.open_meteo_client import OpenMeteoClient

app = typer.Typer(help="Importa observaciones meteorológicas horarias desde Open-Meteo o dataset offline")


def import_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    *,
    location_name: Optional[str] = None,
    engine=None,
    database_url: Optional[str] = None,
    client: Optional[OpenMeteoClient] = None,
    offline: bool = False,
) -> dict:
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)
    repo = WeatherRepository(engine)
    client = client or OpenMeteoClient()

    observations = []
    used_offline = offline
    if not offline:
        try:
            observations = client.fetch_hourly(lat, lon, start_date, end_date, location_name=location_name)
        except httpx.HTTPError as exc:
            print(
                f"[import_weather] WARNING: remote provider failed ({exc}); falling back to offline dataset"
            )
            used_offline = True
    if used_offline:
        observations = _generate_offline_observations(lat, lon, start_date, end_date, location_name)

    result = repo.upsert_many(observations)
    db_url = getattr(engine, "url", database_url)
    mode = "offline" if used_offline else "online"
    print(
        f"[import_weather] mode={mode} database={db_url} lat={lat} lon={lon} "
        f"range={start_date}:{end_date} rows={len(observations)} "
        f"inserted={result['inserted']} updated={result['updated']}"
    )
    return {"mode": mode, **result}


@app.command()
def run(
    lat: float = typer.Option(..., help="Latitud decimal"),
    lon: float = typer.Option(..., help="Longitud decimal"),
    start_date: str = typer.Option(..., help="Fecha inicio YYYY-MM-DD"),
    end_date: str = typer.Option(..., help="Fecha fin YYYY-MM-DD"),
    location_name: Optional[str] = typer.Option(None, help="Nombre descriptivo de la localización"),
    offline: bool = typer.Option(False, "--offline", "--from-file", help="Generar dataset sintético"),
):
    """Importa datos meteorológicos entre start_date y end_date (incluido)"""
    import_weather(lat, lon, start_date, end_date, location_name=location_name, offline=offline)


def _generate_offline_observations(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    location_name: Optional[str],
):
    start_day = _parse_date(start_date)
    end_day = _parse_date(end_date)
    current = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    last = datetime.combine(end_day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=23)
    observations = []
    idx = 0
    now = datetime.now(timezone.utc)
    while current <= last:
        temperature = 18 + 6 * math.sin(idx / 6)
        precipitation = 0.6 if idx % 6 == 0 else 0.0
        rain = precipitation
        cloud_cover = max(0.0, min(100.0, 45 + 30 * math.sin(idx / 4)))
        wind = 10 + (idx % 12)
        gust = wind + 4
        obs = {
            "source": "offline",
            "location_name": location_name or "offline-weather",
            "lat": lat,
            "lon": lon,
            "observed_at": current,
            "temperature_c": round(temperature, 2),
            "precipitation_mm": round(precipitation, 2),
            "rain_mm": round(rain, 2),
            "snowfall_mm": 0.0,
            "cloud_cover_pct": round(cloud_cover, 2),
            "wind_speed_kmh": round(wind, 2),
            "wind_gust_kmh": round(gust, 2),
            "wind_dir_deg": float((idx * 20) % 360),
            "humidity_pct": round(55 + 10 * math.sin(idx / 3), 2),
            "pressure_hpa": 1010 + (idx % 5),
            "visibility_m": 20000 - (idx % 4) * 1500,
            "weather_code": 3 if precipitation > 0.5 else 1,
            "created_at": now,
            "updated_at": now,
        }
        observations.append(obs)
        current += timedelta(hours=1)
        idx += 1
    return observations


def _parse_date(value: str):
    return datetime.fromisoformat(value).date()


if __name__ == "__main__":
    app()

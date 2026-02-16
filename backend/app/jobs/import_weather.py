from __future__ import annotations

import os
from typing import Optional

import typer
from sqlalchemy import create_engine

from app.infra.db.tables import metadata
from app.infra.db.weather_repository import WeatherRepository
from app.infra.weather.open_meteo_client import OpenMeteoClient

app = typer.Typer(help="Importa observaciones meteorológicas horarias desde Open-Meteo")


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
    observations = client.fetch_hourly(lat, lon, start_date, end_date, location_name=location_name)
    result = repo.upsert_many(observations)
    db_url = getattr(engine, "url", database_url)
    print(
        f"[import_weather] database={db_url} lat={lat} lon={lon} "
        f"range={start_date}:{end_date} inserted={result['inserted']} updated={result['updated']}"
    )
    return result


@app.command()
def run(
    lat: float = typer.Option(..., help="Latitud decimal"),
    lon: float = typer.Option(..., help="Longitud decimal"),
    start_date: str = typer.Option(..., help="Fecha inicio YYYY-MM-DD"),
    end_date: str = typer.Option(..., help="Fecha fin YYYY-MM-DD"),
    location_name: Optional[str] = typer.Option(None, help="Nombre descriptivo de la localización"),
):
    """Importa datos meteorológicos entre start_date y end_date (incluido)"""
    import_weather(lat, lon, start_date, end_date, location_name=location_name)


if __name__ == "__main__":
    app()

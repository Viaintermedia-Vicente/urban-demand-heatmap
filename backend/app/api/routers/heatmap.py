from __future__ import annotations

from datetime import date as date_type, datetime, time, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Engine

from app.api.deps import get_engine
from app.domain.models import Event as DomainEvent
from app.domain.scoring import compute_hotspots, weather_factor
from app.infra.db.events_repository import EventsRepository
from app.infra.db.weather_repository import WeatherRepository

router = APIRouter(tags=["heatmap"])


@router.get("/heatmap")
def get_heatmap(
    date: date_type,
    hour: int = Query(..., ge=0, le=23),
    lat: float = Query(40.4168, description="Latitud de referencia"),
    lon: float = Query(-3.7038, description="Longitud de referencia"),
    engine: Engine = Depends(get_engine),
):
    repo = EventsRepository(engine)
    weather_repo = WeatherRepository(engine)
    rows = repo.list_events_for_day(date)
    target = datetime.combine(date, time(hour=hour))
    domain_events = [_row_to_domain(row) for row in rows]
    hotspots = compute_hotspots(domain_events, target)
    weather_dt = target.replace(tzinfo=timezone.utc)
    weather = weather_repo.get_observation_at(lat, lon, weather_dt)
    factor = weather_factor(
        weather.get("temperature_c") if weather else None,
        weather.get("precipitation_mm") if weather else None,
        weather.get("wind_speed_kmh") if weather else None,
    )
    adjusted = [
        {
            "lat": hs.lat,
            "lon": hs.lon,
            "score": round(hs.score * factor, 4),
            "radius_m": hs.radius_m,
        }
        for hs in hotspots
    ]
    return {
        "target": weather_dt.isoformat(),
        "weather": _serialize_weather(weather),
        "hotspots": adjusted,
    }


def _row_to_domain(row: dict) -> DomainEvent:
    return DomainEvent(
        id=str(row["id"]),
        title=row["title"],
        category=row["category"],
        start_dt=row["start_dt"],
        end_dt=row["end_dt"],
        lat=row["lat"],
        lon=row["lon"],
        source=row.get("source"),
    )



def _serialize_weather(obs):
    if not obs:
        return None
    keys = [
        "temperature_c",
        "precipitation_mm",
        "rain_mm",
        "snowfall_mm",
        "cloud_cover_pct",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "wind_dir_deg",
        "humidity_pct",
        "pressure_hpa",
        "visibility_m",
        "weather_code",
    ]
    payload = {k: obs.get(k) for k in keys}
    payload["observed_at"] = obs.get("observed_at").isoformat() if obs.get("observed_at") else None
    payload["source"] = obs.get("source")
    return payload

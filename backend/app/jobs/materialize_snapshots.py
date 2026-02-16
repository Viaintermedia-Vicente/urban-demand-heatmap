
from __future__ import annotations

import os
from datetime import datetime, time, timezone
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional

import typer
from sqlalchemy import create_engine

from app.domain.models import Event as DomainEvent
from app.domain.scoring import event_score, weather_factor
from app.infra.db.events_repository import EventsRepository
from app.infra.db.snapshots_repository import EventFeatureSnapshotsRepository
from app.infra.db.tables import metadata
from app.infra.db.weather_repository import WeatherRepository


def _to_utc_naive(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def materialize_snapshots(
    date_str: str,
    hour: int,
    *,
    lat: float = 40.4168,
    lon: float = -3.7038,
    radius_km: float = 5.0,
    engine=None,
    database_url: Optional[str] = None,
) -> dict:
    date_obj = datetime.fromisoformat(date_str).date()
    target_at = datetime.combine(date_obj, time(hour=hour))
    target_naive = _to_utc_naive(target_at)
    target_at_utc = target_naive.replace(tzinfo=timezone.utc)

    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)

    events_repo = EventsRepository(engine)
    weather_repo = WeatherRepository(engine)
    snapshots_repo = EventFeatureSnapshotsRepository(engine)

    events = events_repo.list_events_for_day(date_obj)
    filtered = _filter_events(events, target_naive, lat, lon, radius_km)
    weather = weather_repo.get_observation_at(lat, lon, target_at_utc)
    factor = weather_factor(
        weather.get("temperature_c") if weather else None,
        weather.get("precipitation_mm") if weather else None,
        weather.get("wind_speed_kmh") if weather else None,
    )

    snapshots = []
    for row in filtered:
        start_dt = _to_utc_naive(row["start_dt"])
        end_dt = _to_utc_naive(row.get("end_dt"))
        domain_event = DomainEvent(
            id=row["external_id"],
            title=row["title"],
            category=row["category"],
            start_dt=start_dt,
            end_dt=end_dt,
            lat=row["lat"],
            lon=row["lon"],
            source=row.get("source"),
        )
        base_score = event_score(domain_event, target_naive, domain_event.lat, domain_event.lon)
        final_score = base_score * factor
        hours_to_start = (start_dt - target_naive).total_seconds() / 3600.0
        snapshots.append(
            {
                "target_at": target_at_utc,
                "event_id": row["external_id"],
                "event_start_dt": row["start_dt"],
                "event_end_dt": row["end_dt"],
                "lat": row["lat"],
                "lon": row["lon"],
                "category": row["category"],
                "expected_attendance": row.get("expected_attendance"),
                "hours_to_start": hours_to_start,
                "weekday": target_at_utc.weekday(),
                "month": target_at_utc.month,
                "temperature_c": weather.get("temperature_c") if weather else None,
                "precipitation_mm": weather.get("precipitation_mm") if weather else None,
                "rain_mm": weather.get("rain_mm") if weather else None,
                "snowfall_mm": weather.get("snowfall_mm") if weather else None,
                "wind_speed_kmh": weather.get("wind_speed_kmh") if weather else None,
                "wind_gust_kmh": weather.get("wind_gust_kmh") if weather else None,
                "weather_code": weather.get("weather_code") if weather else None,
                "humidity_pct": weather.get("humidity_pct") if weather else None,
                "pressure_hpa": weather.get("pressure_hpa") if weather else None,
                "cloud_cover_pct": weather.get("cloud_cover_pct") if weather else None,
                "score_base": base_score,
                "score_weather_factor": factor,
                "score_final": final_score,
            }
        )

    result = snapshots_repo.upsert_many(snapshots)
    db_url = getattr(engine, "url", database_url)
    print(
        f"[materialize_snapshots] db={db_url} target={target_at_utc} "
        f"events={len(filtered)} inserted={result['inserted']} updated={result['updated']}"
    )
    return result


def _filter_events(events: List[dict], target_at: datetime, lat: float, lon: float, radius_km: float):
    filtered = []
    normalized_target = _to_utc_naive(target_at)
    for row in events:
        start_dt = _to_utc_naive(row["start_dt"])
        delta_hours = abs((start_dt - normalized_target).total_seconds()) / 3600.0
        if delta_hours > 6:
            continue
        distance = _haversine_km(lat, lon, row["lat"], row["lon"])
        if distance > radius_km:
            continue
        filtered.append(row)
    return filtered


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def materialize_cli(
    date: str = typer.Option(..., help="Fecha YYYY-MM-DD"),
    hour: int = typer.Option(..., help="Hora 0-23"),
    lat: float = typer.Option(40.4168),
    lon: float = typer.Option(-3.7038),
    radius_km: float = typer.Option(5.0),
    database_url: Optional[str] = typer.Option(None, help="DATABASE_URL override"),
):
    materialize_snapshots(date, hour, lat=lat, lon=lon, radius_km=radius_km, database_url=database_url)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "materialize":
        sys.argv.pop(1)
    typer.run(materialize_cli)

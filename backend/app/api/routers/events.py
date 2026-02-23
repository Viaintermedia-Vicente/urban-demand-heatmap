from __future__ import annotations

from datetime import date as date_type, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.engine import Engine

from app.api.deps import get_engine
from app.infra.db.events_repository import EventsRepository
from app.infra.db.tables import events_table, venues_table

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(
    date: date_type,
    from_hour: int = Query(..., ge=0, le=23),
    engine: Engine = Depends(get_engine),
):
    repo = EventsRepository(engine)
    rows = repo.list_events_from_hour(date, from_hour)
    response = []
    for row in rows:
        start_dt = row["start_dt"]
        lat = row.get("lat") if row.get("lat") is not None else row.get("venue_lat")
        lon = row.get("lon") if row.get("lon") is not None else row.get("venue_lon")
        category = _normalize_category(row.get("category"))
        if category is None:
            category = infer_category(row.get("title"))
        if category == "unknown":
            category = None
        subcategory = _normalize_category(row.get("subcategory"))
        response.append(
            {
                "id": row.get("id"),
                "title": row["title"],
                "category": category,
                "subcategory": subcategory,
                "start_dt": start_dt.isoformat() if start_dt else None,
                "end_dt": row.get("end_dt").isoformat() if row.get("end_dt") else None,
                "venue_name": row.get("venue_name"),
                "expected_attendance": row.get("expected_attendance"),
                "lat": lat,
                "lon": lon,
                "url": row.get("url") or row.get("ticket_url") or row.get("source_url"),
                "source": row.get("source"),
            }
        )
    return response


@router.get("/regions")
def list_regions(engine: Engine = Depends(get_engine)):
    """
    Devuelve las regiones disponibles derivadas de las ciudades de los venues.
    """
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                func.lower(venues_table.c.city).label("id"),
                venues_table.c.city.label("label"),
                func.avg(venues_table.c.lat).label("lat"),
                func.avg(venues_table.c.lon).label("lon"),
            )
            .where(venues_table.c.city.is_not(None))
            .group_by(venues_table.c.city)
            .order_by(venues_table.c.city)
        ).mappings().all()
    regions = []
    for row in rows:
        if row["lat"] is None or row["lon"] is None:
            continue
        regions.append(
            {
                "id": row["id"],
                "label": row["label"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            }
        )
    return regions


EARTH_RADIUS_M = 6_371_000


@router.get("/hotspot_events")
def list_hotspot_events(
    date: date_type,
    hour: int = Query(..., ge=0, le=23),
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(300.0, gt=0),
    limit: int = Query(20, ge=1, le=200),
    engine: Engine = Depends(get_engine),
):
    target_local = datetime.combine(date, time(hour=hour)).replace(tzinfo=ZoneInfo("Europe/Madrid"))
    target_utc = target_local.astimezone(timezone.utc)
    candidates = _fetch_active_events(engine)
    target_naive = _to_utc_naive(target_utc)
    results = []
    for row in candidates:
        start = _to_utc_naive(row.get("start_dt"))
        if start is None:
            continue
        end_val = row.get("end_dt")
        end = _to_utc_naive(end_val) if end_val else start + timedelta(hours=3)
        if not (start <= target_naive <= end):
            continue
        distance = _haversine_m(lat, lon, row.get("lat"), row.get("lon"))
        if distance is None or distance > radius_m:
            continue
        results.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "start_dt": _to_iso(row.get("start_dt")),
                "end_dt": _to_iso(row.get("end_dt")),
                "venue_name": row.get("venue_name"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "url": row.get("url"),
                "distance_m": round(distance, 2),
                "source": row.get("source"),
            }
        )
    results.sort(key=lambda item: (item["distance_m"], item["start_dt"] or ""))
    return results[:limit]


def _fetch_active_events(engine: Engine):
    join_stmt = events_table.outerjoin(venues_table, events_table.c.venue_id == venues_table.c.id)
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                events_table.c.id,
                events_table.c.title,
                events_table.c.start_dt,
                events_table.c.end_dt,
                events_table.c.lat,
                events_table.c.lon,
                events_table.c.url,
                events_table.c.source,
                venues_table.c.name.label("venue_name"),
            )
            .select_from(join_stmt)
            .where(events_table.c.is_active.is_(True))
        ).mappings().all()
    return [dict(row) for row in rows]


def _to_iso(dt):
    return dt.isoformat() if dt else None


def infer_category(title: str | None) -> str:
  if not title:
    return None
  t = title.lower()
  if "festival" in t or "concert" in t or "concierto" in t or "music" in t or "música" in t:
    return "music"
  if "teatro" in t or "theatre" in t or "obra" in t:
    return "theatre"
  if "comedia" in t or "comedy" in t or "humor" in t:
    return "comedy"
  return None


def _normalize_category(value: str | None) -> str | None:
  if not value:
    return None
  v = value.strip().lower()
  if not v or v == "unknown":
    return None
  return value


def _to_utc_naive(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _haversine_m(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c

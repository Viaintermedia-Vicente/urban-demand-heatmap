from __future__ import annotations

from datetime import date as date_type, datetime, time
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Engine

from app.api.deps import get_engine
from app.domain.models import Event as DomainEvent
from app.domain.scoring import compute_hotspots
from app.infra.db.events_repository import EventsRepository

router = APIRouter(tags=["heatmap"])


@router.get("/heatmap")
def get_heatmap(
    date: date_type,
    hour: int = Query(..., ge=0, le=23),
    engine: Engine = Depends(get_engine),
):
    repo = EventsRepository(engine)
    rows = repo.list_events_for_day(date)
    target = datetime.combine(date, time(hour=hour))
    domain_events = [_row_to_domain(row) for row in rows]
    hotspots = compute_hotspots(domain_events, target)
    return [
        {
            "lat": hs.lat,
            "lon": hs.lon,
            "score": hs.score,
            "radius_m": hs.radius_m,
        }
        for hs in hotspots
    ]


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

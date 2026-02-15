from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Engine

from app.api.deps import get_engine
from app.infra.db.events_repository import EventsRepository

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
        response.append(
            {
                "title": row["title"],
                "category": row["category"],
                "start_dt": start_dt.isoformat() if start_dt else None,
                "venue_name": row.get("venue_name"),
                "expected_attendance": row.get("expected_attendance"),
            }
        )
    return response

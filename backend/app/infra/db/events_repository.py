from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, insert, or_, select, update, func
from sqlalchemy.engine import Engine

from .tables import events_table, venues_table
from .venues_repository import VenuesRepository


EVENT_COLUMNS = [
    "source",
    "external_id",
    "title",
    "category",
    "subcategory",
    "start_dt",
    "end_dt",
    "timezone",
    "venue_id",
    "lat",
    "lon",
    "status",
    "url",
    "expected_attendance",
    "popularity_score",
    "is_active",
]


class EventsRepository:
    def __init__(self, engine: Engine, venues_repo: Optional[VenuesRepository] = None):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine
        self.venues_repo = venues_repo or VenuesRepository(self.engine)

    def upsert_event(self, event_data: Dict[str, Any]) -> int:
        resolved = {col: event_data.get(col) for col in EVENT_COLUMNS}
        if resolved.get("is_active") is None:
            resolved["is_active"] = True
        if not resolved.get("venue_id"):
            resolved["venue_id"] = self._resolve_venue_id(event_data)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(events_table.c.id).where(
                    (events_table.c.source == resolved["source"])
                    & (events_table.c.external_id == resolved["external_id"])
                )
            ).scalar_one_or_none()
            if existing:
                conn.execute(
                    update(events_table)
                    .where(events_table.c.id == existing)
                    .values(**resolved, updated_at=now, last_synced_at=now)
                )
                return existing
            result = conn.execute(
                insert(events_table).values(**resolved, created_at=now, updated_at=now, last_synced_at=now)
            )
            return result.inserted_primary_key[0]

    def get_event_by_source_external(self, source: str, external_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(events_table).where(
                    (events_table.c.source == source) & (events_table.c.external_id == external_id)
                )
            ).mappings().first()
        return dict(row) if row else None

    def list_events_for_day(
        self,
        day: date,
        city: Optional[str] = None,
        tzinfo=timezone.utc,
    ) -> List[Dict[str, Any]]:
        start, end = self._day_bounds(day, tzinfo)
        join_stmt = events_table.outerjoin(venues_table, events_table.c.venue_id == venues_table.c.id)
        filters = [(events_table.c.start_dt >= start), (events_table.c.start_dt < end)]
        if city:
            filters.append(func.lower(venues_table.c.city) == city.lower())
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    events_table,
                    venues_table.c.name.label("venue_name"),
                    venues_table.c.lat.label("venue_lat"),
                    venues_table.c.lon.label("venue_lon"),
                    venues_table.c.city.label("city"),
                )
                .select_from(join_stmt)
                .where(*filters)
            ).mappings().all()
        return [dict(row) for row in rows]

    def list_events_from_hour(
        self,
        day: date,
        from_hour: int,
        city: Optional[str] = None,
        tzinfo=timezone.utc,
    ) -> List[Dict[str, Any]]:
        day_start_local = datetime.combine(day, time.min, tzinfo=tzinfo)
        hour_start_utc = day_start_local.replace(hour=from_hour).astimezone(timezone.utc)
        if from_hour < 23:
            hour_end_utc = day_start_local.replace(hour=from_hour + 1).astimezone(timezone.utc)
        else:
            hour_end_utc = (day_start_local + timedelta(days=1)).astimezone(timezone.utc)
        default_duration = timedelta(hours=3)
        join_stmt = events_table.outerjoin(venues_table, events_table.c.venue_id == venues_table.c.id)
        filters = [
            events_table.c.start_dt < hour_end_utc,
            or_(
                and_(events_table.c.end_dt.isnot(None), events_table.c.end_dt > hour_start_utc),
                and_(
                    events_table.c.end_dt.is_(None),
                    events_table.c.start_dt > hour_start_utc - default_duration,
                ),
            ),
        ]
        if city:
            filters.append(func.lower(venues_table.c.city) == city.lower())
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    events_table.c.id,
                    events_table.c.title,
                    events_table.c.category,
                    events_table.c.subcategory,
                    events_table.c.start_dt,
                    events_table.c.end_dt,
                    events_table.c.lat,
                    events_table.c.lon,
                    events_table.c.url,
                    events_table.c.source,
                    events_table.c.expected_attendance,
                    venues_table.c.name.label("venue_name"),
                    venues_table.c.lat.label("venue_lat"),
                    venues_table.c.lon.label("venue_lon"),
                    venues_table.c.city.label("city"),
                )
                .select_from(join_stmt)
                .where(*filters)
                .order_by(events_table.c.start_dt)
            ).mappings().all()
        return [dict(row) for row in rows]

    def _resolve_venue_id(self, event_data: Dict[str, Any]) -> Optional[int]:
        venue_source = event_data.get("venue_source", event_data.get("source"))
        venue_external_id = event_data.get("venue_external_id")
        venue_city = event_data.get("venue_city")
        venue_name = event_data.get("venue_name")
        venue_id = None
        if venue_external_id:
            venue_id = self.venues_repo.get_venue_id_by_external(venue_source, venue_external_id)
        if not venue_id and venue_city and venue_name:
            venue = self.venues_repo.get_venue_by_name(venue_city, venue_name)
            if venue:
                venue_id = venue["id"]
        return venue_id

    @staticmethod
    def _day_bounds(day: date, tzinfo=timezone.utc):
        start_local = datetime.combine(day, time.min, tzinfo=tzinfo)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

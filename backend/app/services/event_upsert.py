from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.domain.canonical import CanonicalEvent
from app.infra.db.tables import events_table


class EventUpsertService:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_events(
        self,
        events: Iterable[CanonicalEvent],
        *,
        source: str | None = None,
        today: datetime | None = None,
        deactivate_missing: bool = False,
    ) -> dict:
        event_list = list(events)
        stats = {"inserted": 0, "updated": 0, "total": len(event_list)}

        with self.engine.begin() as conn:
            for event in event_list:
                existing_id = self._locate_event(conn, event)
                now = datetime.now(timezone.utc)
                if existing_id:
                    update_values = self._build_payload(event)
                    conn.execute(
                        update(events_table)
                        .where(events_table.c.id == existing_id)
                        .values(**update_values, updated_at=now, last_synced_at=now, is_active=True)
                    )
                    stats["updated"] += 1
                else:
                    insert_values = {
                        **self._build_payload(event),
                        "source": event.source,
                        "external_id": event.external_id,
                        "created_at": now,
                        "updated_at": now,
                        "last_synced_at": now,
                        "is_active": True,
                    }
                    conn.execute(insert(events_table).values(insert_values))
                    stats["inserted"] += 1
            if deactivate_missing and source and today:
                self.deactivate_missing_events(
                    source=source,
                    active_external_ids=[evt.external_id for evt in event_list],
                    today=today,
                    session=conn,
                )
        return stats

    def _locate_event(self, conn: Connection, event: CanonicalEvent) -> Optional[int]:
        stmt = select(events_table.c.id).where(
            (events_table.c.source == event.source) & (events_table.c.external_id == event.external_id)
        )
        existing = conn.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing
        return self._find_similar_event(conn, event)

    def _find_similar_event(self, conn: Connection, event: CanonicalEvent) -> Optional[int]:
        if not event.title or event.lat is None or event.lon is None:
            return None
        normalized_title = event.title.strip().lower()
        if not normalized_title:
            return None
        tolerance_deg = 0.01
        window = timedelta(minutes=30)
        start_lower = event.start_at - window
        start_upper = event.start_at + window
        stmt = (
            select(events_table.c.id)
            .where(
                func.lower(events_table.c.title) == normalized_title,
                events_table.c.start_dt >= start_lower,
                events_table.c.start_dt <= start_upper,
                func.abs(events_table.c.lat - event.lat) <= tolerance_deg,
                func.abs(events_table.c.lon - event.lon) <= tolerance_deg,
                events_table.c.source != event.source,
            )
            .limit(1)
        )
        return conn.execute(stmt).scalar_one_or_none()

    def _build_payload(self, event: CanonicalEvent) -> dict:
        if event.lat is None or event.lon is None:
            raise ValueError("CanonicalEvent lat/lon are required for persistence")
        raw = event.raw or {}
        timezone_name = self._timezone_name(event.start_at)
        end_dt = event.end_at or event.start_at
        return {
            "title": event.title,
            "category": raw.get("category", "unknown"),
            "subcategory": raw.get("subcategory"),
            "start_dt": event.start_at,
            "end_dt": end_dt,
            "timezone": timezone_name,
            "venue_id": raw.get("venue_id"),
            "lat": event.lat,
            "lon": event.lon,
            "status": raw.get("status"),
            "url": event.url or raw.get("url"),
            "expected_attendance": raw.get("expected_attendance"),
            "popularity_score": raw.get("popularity_score"),
        }

    @staticmethod
    def _timezone_name(dt: datetime) -> str:
        if dt.tzinfo is None:
            return "UTC"
        key = getattr(dt.tzinfo, "key", None)
        if key:
            return key
        return dt.tzinfo.tzname(dt) or "UTC"

    def deactivate_missing_events(
        self,
        *,
        source: str,
        active_external_ids: list[str],
        today: datetime,
        session,
    ) -> int:
        conn = self._ensure_connection(session)
        conditions = [
            events_table.c.source == source,
            events_table.c.start_dt >= today,
            events_table.c.is_active.is_(True),
        ]
        if active_external_ids:
            conditions.append(~events_table.c.external_id.in_(active_external_ids))
        stmt = (
            update(events_table)
            .where(*conditions)
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )
        result = conn.execute(stmt)
        return result.rowcount or 0

    @staticmethod
    def _ensure_connection(session) -> Connection:
        if isinstance(session, Connection):
            return session
        raise ValueError("session must be a sqlalchemy Connection")

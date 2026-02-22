from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.domain.canonical import CanonicalEvent
from app.infra.db.tables import venues_table


class VenueUpsertService:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def ensure_for_events(self, events: Iterable[CanonicalEvent]) -> dict[Tuple[str, str], int]:
        payloads: Dict[Tuple[str, str], dict] = {}
        for event in events:
            payload = self._payload_from_event(event)
            if not payload:
                continue
            payloads[(payload["source"], payload["external_id"])] = payload
        if not payloads:
            return {}
        return self._upsert_payloads(payloads)

    def _upsert_payloads(self, payloads: Dict[Tuple[str, str], dict]) -> dict[Tuple[str, str], int]:
        mapping: dict[Tuple[str, str], int] = {}
        with self.engine.begin() as conn:
            for key, payload in payloads.items():
                existing = self._find_existing(conn, payload["source"], payload["external_id"])
                now = datetime.now(timezone.utc)
                if existing is not None:
                    conn.execute(
                        update(venues_table)
                        .where(venues_table.c.id == existing)
                        .values(**payload, updated_at=now)
                    )
                    mapping[key] = existing
                else:
                    result = conn.execute(
                        insert(venues_table).values(**payload, created_at=now, updated_at=now)
                    )
                    mapping[key] = result.inserted_primary_key[0]
        return mapping

    def _find_existing(self, conn: Connection, source: str, external_id: str) -> Optional[int]:
        stmt = (
            select(venues_table.c.id)
            .where(venues_table.c.source == source, venues_table.c.external_id == external_id)
            .limit(1)
        )
        return conn.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _payload_from_event(event: CanonicalEvent) -> Optional[dict]:
        if not event.venue_name:
            return None
        venue_external_id = event.venue_external_id
        if not venue_external_id:
            return None
        if event.lat is None or event.lon is None:
            return None
        source = event.venue_source or event.source
        city = event.venue_city or "Unknown"
        country = event.venue_country or "??"
        return {
            "source": source,
            "external_id": venue_external_id,
            "name": event.venue_name,
            "lat": event.lat,
            "lon": event.lon,
            "city": city,
            "region": None,
            "country": country,
            "address_line1": None,
            "address_line2": None,
            "postal_code": None,
            "max_capacity": None,
        }

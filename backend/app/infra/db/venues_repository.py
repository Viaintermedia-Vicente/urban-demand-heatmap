from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Engine

from .tables import venues_table


UPSERT_COLUMNS = [
    "source",
    "external_id",
    "name",
    "lat",
    "lon",
    "city",
    "region",
    "country",
    "address_line1",
    "address_line2",
    "postal_code",
    "max_capacity",
]


class VenuesRepository:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_venue(self, venue: Dict[str, Any]) -> int:
        record = {col: venue.get(col) for col in UPSERT_COLUMNS}
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            stmt = select(venues_table.c.id).where(
                self._match_source_external(record["source"], record.get("external_id"))
            )
            existing_id = conn.execute(stmt).scalar_one_or_none()
            if existing_id:
                conn.execute(
                    update(venues_table)
                    .where(venues_table.c.id == existing_id)
                    .values(**record, updated_at=now)
                )
                return existing_id
            result = conn.execute(
                insert(venues_table).values(**record, created_at=now, updated_at=now)
            )
            inserted = result.inserted_primary_key[0]
            return inserted

    def get_venue_id_by_external(self, source: str, external_id: str) -> Optional[int]:
        if not external_id:
            return None
        with self.engine.begin() as conn:
            stmt = select(venues_table.c.id).where(self._match_source_external(source, external_id))
            return conn.execute(stmt).scalar_one_or_none()

    def get_venue_by_name(self, city: str, name: str) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        normalized_name = name.strip().lower()
        with self.engine.begin() as conn:
            stmt = (
                select(venues_table)
                .where(
                    (venues_table.c.city == city)
                    & (func.lower(venues_table.c.name) == normalized_name)
                )
                .limit(1)
            )
            row = conn.execute(stmt).mappings().first()
            return dict(row) if row else None

    def get_venue_by_external(self, source: str, external_id: str) -> Optional[Dict[str, Any]]:
        if not external_id:
            return None
        with self.engine.begin() as conn:
            stmt = select(venues_table).where(
                self._match_source_external(source, external_id)
            )
            row = conn.execute(stmt).mappings().first()
            return dict(row) if row else None

    @staticmethod
    def _match_source_external(source: str, external_id: Optional[str]):
        clause = venues_table.c.source == source
        if external_id is None:
            return clause & venues_table.c.external_id.is_(None)
        return clause & (venues_table.c.external_id == external_id)

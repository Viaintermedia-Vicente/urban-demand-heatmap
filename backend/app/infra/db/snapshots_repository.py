from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from .tables import event_feature_snapshots_table


class EventFeatureSnapshotsRepository:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_many(self, snapshots: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        with self.engine.begin() as conn:
            for snap in snapshots:
                clause = (
                    (event_feature_snapshots_table.c.target_at == snap["target_at"])
                    & (event_feature_snapshots_table.c.event_id == snap["event_id"])
                )
                existing_id = conn.execute(
                    select(event_feature_snapshots_table.c.id).where(clause)
                ).scalar_one_or_none()
                payload = {
                    col.name: snap.get(col.name)
                    for col in event_feature_snapshots_table.columns
                    if col.name not in {"id"}
                }
                payload.setdefault("created_at", now)
                if existing_id:
                    conn.execute(
                        update(event_feature_snapshots_table)
                        .where(event_feature_snapshots_table.c.id == existing_id)
                        .values(**payload)
                    )
                    updated += 1
                else:
                    conn.execute(insert(event_feature_snapshots_table).values(**payload))
                    inserted += 1
        return {"inserted": inserted, "updated": updated}

    def list_by_range(self, start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(event_feature_snapshots_table)
                .where(event_feature_snapshots_table.c.target_at >= start_dt)
                .where(event_feature_snapshots_table.c.target_at <= end_dt)
                .order_by(event_feature_snapshots_table.c.target_at)
            ).mappings().all()
        return [dict(row) for row in rows]

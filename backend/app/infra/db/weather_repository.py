from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import insert, select, update, or_
from sqlalchemy.engine import Engine

from .tables import weather_observations_table


class WeatherRepository:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_many(self, observations: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        with self.engine.begin() as conn:
            for obs in observations:
                key_clause = (
                    (weather_observations_table.c.source == obs["source"])
                    & (weather_observations_table.c.lat == obs["lat"])
                    & (weather_observations_table.c.lon == obs["lon"])
                    & (weather_observations_table.c.observed_at == obs["observed_at"])
                )
                existing_id = conn.execute(
                    select(weather_observations_table.c.id).where(key_clause)
                ).scalar_one_or_none()
                payload = {col.name: obs.get(col.name) for col in weather_observations_table.columns if col.name not in {"id"}}
                payload["updated_at"] = now
                if existing_id:
                    conn.execute(
                        update(weather_observations_table)
                        .where(weather_observations_table.c.id == existing_id)
                        .values(**payload)
                    )
                    updated += 1
                else:
                    payload.setdefault("created_at", now)
                    conn.execute(insert(weather_observations_table).values(**payload))
                    inserted += 1
        return {"inserted": inserted, "updated": updated}

    def get_range(
        self,
        lat: float,
        lon: float,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(weather_observations_table)
                .where(weather_observations_table.c.lat == lat)
                .where(weather_observations_table.c.lon == lon)
                .where(weather_observations_table.c.observed_at >= start_dt)
                .where(weather_observations_table.c.observed_at <= end_dt)
                .order_by(weather_observations_table.c.observed_at)
            ).mappings().all()
        return [dict(row) for row in rows]
    def get_observation_at(self, lat: float, lon: float, observed_at: datetime):
        target_naive = observed_at
        if observed_at.tzinfo is not None:
            target_naive = observed_at.astimezone(timezone.utc).replace(tzinfo=None)
        candidates = [target_naive]
        if observed_at.tzinfo is not None:
            candidates.append(observed_at.astimezone(timezone.utc))
        from datetime import timedelta
        window_start = target_naive - timedelta(minutes=1)
        window_end = target_naive + timedelta(minutes=1)
        with self.engine.begin() as conn:
            stmt = (
                select(weather_observations_table)
                .where(weather_observations_table.c.lat == lat)
                .where(weather_observations_table.c.lon == lon)
                .where(weather_observations_table.c.observed_at >= window_start)
                .where(weather_observations_table.c.observed_at <= window_end)
                .order_by(weather_observations_table.c.observed_at)
                .limit(1)
            )
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None


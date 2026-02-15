from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from .tables import category_rules_table


class CategoryRulesRepository:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_rule(self, rule: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        category = rule["category"]
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(category_rules_table.c.category).where(category_rules_table.c.category == category)
            ).scalar_one_or_none()
            payload = rule.copy()
            payload["updated_at"] = now
            if existing:
                conn.execute(
                    update(category_rules_table)
                    .where(category_rules_table.c.category == category)
                    .values(**payload)
                )
            else:
                conn.execute(
                    insert(category_rules_table).values(**payload)
                )

    def get_rules_map(self) -> Dict[str, Dict[str, Any]]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(category_rules_table)).mappings().all()
            return {row["category"].lower(): dict(row) for row in rows}

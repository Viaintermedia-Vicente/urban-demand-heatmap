from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def run(engine: Optional[Engine] = None, database_url: Optional[str] = None) -> None:
    engine = engine or _resolve_engine(database_url)
    with engine.begin() as conn:
        inspector = inspect(conn)
        columns = {col["name"] for col in inspector.get_columns("events")}
        dialect = conn.dialect.name

        _ensure_last_synced(conn, dialect, columns)
        _ensure_is_active(conn, dialect, columns)
        _ensure_unique_constraint(conn, dialect)


def _ensure_last_synced(conn, dialect: str, columns: set[str]) -> None:
    if "last_synced_at" not in columns:
        if dialect == "sqlite":
            conn.exec_driver_sql(
                "ALTER TABLE events ADD COLUMN last_synced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
        else:
            conn.exec_driver_sql("ALTER TABLE events ADD COLUMN last_synced_at TIMESTAMPTZ")
            conn.exec_driver_sql("UPDATE events SET last_synced_at = NOW() WHERE last_synced_at IS NULL")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN last_synced_at SET DEFAULT NOW()")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN last_synced_at SET NOT NULL")
    else:
        if dialect == "sqlite":
            conn.exec_driver_sql(
                "UPDATE events SET last_synced_at = CURRENT_TIMESTAMP WHERE last_synced_at IS NULL"
            )
        else:
            conn.exec_driver_sql("UPDATE events SET last_synced_at = NOW() WHERE last_synced_at IS NULL")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN last_synced_at SET DEFAULT NOW()")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN last_synced_at SET NOT NULL")


def _ensure_is_active(conn, dialect: str, columns: set[str]) -> None:
    if "is_active" not in columns:
        if dialect == "sqlite":
            conn.exec_driver_sql(
                "ALTER TABLE events ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            )
        else:
            conn.exec_driver_sql("ALTER TABLE events ADD COLUMN is_active BOOLEAN")
            conn.exec_driver_sql("UPDATE events SET is_active = TRUE WHERE is_active IS NULL")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN is_active SET DEFAULT TRUE")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN is_active SET NOT NULL")
    else:
        conn.exec_driver_sql("UPDATE events SET is_active = TRUE WHERE is_active IS NULL")
        if dialect != "sqlite":
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN is_active SET DEFAULT TRUE")
            conn.exec_driver_sql("ALTER TABLE events ALTER COLUMN is_active SET NOT NULL")


def _ensure_unique_constraint(conn, dialect: str) -> None:
    if dialect == "sqlite":
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_events_source_external_id ON events (source, external_id)"
        )
    else:
        conn.exec_driver_sql(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_events_source_external_id'
                      AND conrelid = 'events'::regclass
                ) THEN
                    ALTER TABLE events
                        ADD CONSTRAINT uq_events_source_external_id UNIQUE (source, external_id);
                END IF;
            END;
            $$;
            """
        )


def _resolve_engine(database_url: Optional[str]) -> Engine:
    if not database_url:
        database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return create_engine(database_url, future=True)


if __name__ == "__main__":
    run()

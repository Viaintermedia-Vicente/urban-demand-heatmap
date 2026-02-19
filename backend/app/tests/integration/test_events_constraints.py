from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.infra.db.tables import events_table, metadata


@pytest.fixture()
def sqlite_engine(tmp_path):
    db_path = tmp_path / "events_constraints.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def test_unique_source_external_id_enforced(sqlite_engine):
    payload = {
        "source": "demo",
        "external_id": "evt-1",
        "title": "Demo Event",
        "category": "music",
        "subcategory": None,
        "start_dt": datetime(2026, 3, 1, 20, 0, tzinfo=timezone.utc),
        "end_dt": datetime(2026, 3, 1, 22, 0, tzinfo=timezone.utc),
        "timezone": "UTC",
        "venue_id": None,
        "lat": 40.4168,
        "lon": -3.7038,
        "status": None,
        "url": None,
        "expected_attendance": 1000,
        "popularity_score": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_synced_at": datetime.now(timezone.utc),
        "is_active": True,
    }

    with sqlite_engine.begin() as conn:
        conn.execute(events_table.insert(), payload)

    with pytest.raises(IntegrityError):
        with sqlite_engine.begin() as conn:
            conn.execute(events_table.insert(), payload)

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, update

from app.domain.canonical import CanonicalEvent
from app.infra.db.tables import events_table, metadata
from app.services.event_upsert import EventUpsertService


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'event_service.db'}", future=True)
    metadata.create_all(engine)
    return engine


def make_event(external_id: str = "evt-1", title: str = "Concert", raw_extra: dict | None = None):
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    raw = {"category": "music"}
    if raw_extra:
        raw.update(raw_extra)
    return CanonicalEvent(
        source="providerA",
        external_id=external_id,
        title=title,
        start_at=base,
        end_at=base + timedelta(hours=2),
        lat=40.4168,
        lon=-3.7038,
        raw=raw,
    )


def test_insert_new_event(engine):
    service = EventUpsertService(engine)
    stats = service.upsert_events([make_event("evt-new")])
    assert stats == {"inserted": 1, "updated": 0, "total": 1}
    with engine.begin() as conn:
        stored = conn.execute(select(events_table.c.title)).scalar_one()
    assert stored == "Concert"


def test_update_existing_event(engine):
    service = EventUpsertService(engine)
    service.upsert_events([make_event("evt-2", title="Initial")])
    updated_event = make_event("evt-2", title="Updated", raw_extra={"status": "changed"})
    stats = service.upsert_events([updated_event])
    assert stats["inserted"] == 0
    assert stats["updated"] == 1
    with engine.begin() as conn:
        stored = conn.execute(
            select(events_table.c.title, events_table.c.status).where(events_table.c.external_id == "evt-2")
        ).one()
    assert stored.title == "Updated"
    assert stored.status == "changed"


def test_idempotent_second_run(engine):
    service = EventUpsertService(engine)
    events = [make_event(f"evt-{i}") for i in range(3)]
    service.upsert_events(events)
    stats = service.upsert_events(events)
    assert stats["inserted"] == 0
    assert stats["updated"] == 3
    with engine.begin() as conn:
        count = conn.execute(select(events_table.c.id)).all()
    assert len(count) == 3


def test_reactivate_if_inactive(engine):
    service = EventUpsertService(engine)
    service.upsert_events([make_event("evt-inactive")])
    with engine.begin() as conn:
        conn.execute(
            update(events_table)
            .where(events_table.c.external_id == "evt-inactive")
            .values(is_active=False)
        )
    stats = service.upsert_events([make_event("evt-inactive", title="Revived")])
    assert stats["updated"] == 1
    with engine.begin() as conn:
        row = conn.execute(
            select(events_table.c.is_active, events_table.c.title).where(events_table.c.external_id == "evt-inactive")
        ).one()
    assert row.is_active is True
    assert row.title == "Revived"

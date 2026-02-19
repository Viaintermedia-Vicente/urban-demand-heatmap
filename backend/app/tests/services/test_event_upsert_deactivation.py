from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from app.domain.canonical import CanonicalEvent
from app.infra.db.tables import events_table, metadata
from app.services.event_upsert import EventUpsertService


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "event_deactivation.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def make_event(external_id: str, hours_offset: int = 24, source: str = "providerA") -> CanonicalEvent:
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    start = base + timedelta(hours=hours_offset)
    return CanonicalEvent(
        source=source,
        external_id=external_id,
        title=f"Event {external_id}",
        start_at=start,
        end_at=start + timedelta(hours=2),
        lat=40.4168,
        lon=-3.7038,
    )


def _is_active(engine, external_id: str) -> bool:
    with engine.begin() as conn:
        return (
            conn.execute(
                select(events_table.c.is_active).where(events_table.c.external_id == external_id)
            ).scalar_one()
        )


def test_future_event_gets_deactivated_if_missing(engine):
    service = EventUpsertService(engine)
    future_event = make_event("evt-future", hours_offset=48)
    service.upsert_events([future_event])
    today = datetime(2026, 2, 18, 0, 0, tzinfo=timezone.utc)

    stats = service.upsert_events(
        [],
        source="providerA",
        today=today,
        deactivate_missing=True,
    )

    assert stats["inserted"] == 0
    assert not _is_active(engine, "evt-future")


def test_past_event_not_deactivated(engine):
    service = EventUpsertService(engine)
    past_event = make_event("evt-past", hours_offset=-24)
    service.upsert_events([past_event])
    today = datetime(2026, 2, 18, 0, 0, tzinfo=timezone.utc)

    service.upsert_events([], source="providerA", today=today, deactivate_missing=True)

    assert _is_active(engine, "evt-past")


def test_other_source_not_affected(engine):
    service = EventUpsertService(engine)
    event_a = make_event("evt-a", hours_offset=24, source="sourceA")
    event_b = make_event("evt-b", hours_offset=24, source="sourceB")
    service.upsert_events([event_a, event_b])
    today = datetime(2026, 2, 18, 0, 0, tzinfo=timezone.utc)

    service.upsert_events([], source="sourceA", today=today, deactivate_missing=True)

    assert not _is_active(engine, "evt-a")
    assert _is_active(engine, "evt-b")


def test_reactivation_if_event_returns(engine):
    service = EventUpsertService(engine)
    evt = make_event("evt-return", hours_offset=48)
    service.upsert_events([evt])
    today = datetime(2026, 2, 18, 0, 0, tzinfo=timezone.utc)
    service.upsert_events([], source="providerA", today=today, deactivate_missing=True)
    assert not _is_active(engine, "evt-return")

    service.upsert_events([evt])

    assert _is_active(engine, "evt-return")

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select

from app.domain.canonical import CanonicalEvent
from app.infra.db.tables import events_table, metadata
from app.services.event_upsert import EventUpsertService


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}", future=True)
    metadata.create_all(engine)
    return engine


def sample_event(external_id: str, lat: float = 40.4, lon: float = -3.7, title: str = "Concert"):
    start = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    return CanonicalEvent(
        source="providerA",
        external_id=external_id,
        title=title,
        start_at=start,
        end_at=start + timedelta(hours=2),
        lat=lat,
        lon=lon,
    )


def test_event_upsert_idempotent(engine):
    service = EventUpsertService(engine)
    events = [sample_event(f"evt-{i}") for i in range(3)]
    service.upsert_events(events)
    stats = service.upsert_events(events)
    assert stats["inserted"] == 0
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 3


def test_event_upsert_deduplicates_cross_providers(engine):
    service = EventUpsertService(engine)
    start = datetime(2026, 2, 18, 22, 0, tzinfo=timezone.utc)
    events = [
        CanonicalEvent("providerA", "evt-1", "Mega Show", start, start + timedelta(hours=2), 40.4, -3.7, "WiZink"),
        CanonicalEvent("providerB", "evt-z", "mega show", start, start + timedelta(hours=2), 40.4001, -3.7001, "Wizink"),
    ]
    service.upsert_events(events)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(events_table)).scalar()
    assert count == 1


def test_event_upsert_normalizes_timezone(engine):
    service = EventUpsertService(engine)
    madrid_start = datetime(2026, 2, 18, 20, 0).astimezone(timezone.utc)
    events = [
        CanonicalEvent("providerA", "evt-5", "Hora Local", madrid_start, madrid_start + timedelta(hours=1), 40.4, -3.7, None)
    ]
    service.upsert_events(events)
    with engine.begin() as conn:
        stored = conn.execute(select(events_table.c.start_dt).where(events_table.c.external_id == "evt-5")).scalar_one()
    assert stored.tzinfo is None
    assert stored.hour == 20

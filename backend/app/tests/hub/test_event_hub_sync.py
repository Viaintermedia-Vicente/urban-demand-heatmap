from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from app.domain.canonical import CanonicalEvent
from app.hub.event_hub import EventHub
from app.hub import event_hub as event_hub_module
from app.hub.provider_registry import ProviderRegistry
from app.infra.db.tables import events_table, metadata


class _StaticProvider:
    def __init__(self, name: str, events: list[CanonicalEvent], fail: bool = False) -> None:
        self.name = name
        self._events = events
        self.fail = fail

    def fetch_events(self, *, city: str, days: int, reference: datetime, direction: str = "future"):
        if self.fail:
            raise RuntimeError(f"provider {self.name} failed")
        if direction != "future":
            return []
        return list(self._events)


@pytest.fixture()
def engine(tmp_path):
    db_path = tmp_path / "hub_sync.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def _event(external_id: str, title: str = "Concert") -> CanonicalEvent:
    base = datetime(2026, 2, 18, 20, 0, tzinfo=timezone.utc)
    return CanonicalEvent(
        source="providerA",
        external_id=external_id,
        title=title,
        start_at=base,
        end_at=base + timedelta(hours=2),
        lat=40.4168,
        lon=-3.7038,
    )


def test_hub_sync_persists_events(engine):
    registry = ProviderRegistry()
    provider = _StaticProvider("good", [_event("evt-1"), _event("evt-2")])
    registry.register("A", provider)
    hub = EventHub(registry)

    stats = hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)

    assert stats["fetched"] == 2
    assert stats["inserted"] == 2
    assert not stats["errors"]
    assert stats["provider_stats"][0]["fetched"] == 2
    with engine.begin() as conn:
        count = conn.execute(select(events_table.c.id)).all()
    assert len(count) == 2


def test_hub_sync_handles_provider_failure(engine):
    registry = ProviderRegistry()
    good = _StaticProvider("good", [_event("evt-3")])
    bad = _StaticProvider("bad", [], fail=True)
    registry.register("good", good)
    registry.register("bad", bad)
    hub = EventHub(registry)

    stats = hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)

    assert stats["inserted"] == 1
    assert stats["errors"]
    assert stats["provider_stats"][0]["fetched"] == 1
    assert stats["errors"][0][0] == "bad"


def test_hub_sync_idempotent(engine):
    registry = ProviderRegistry()
    provider = _StaticProvider("good", [_event("evt-9")])
    registry.register("good", provider)
    hub = EventHub(registry)

    first = hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)
    second = hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["updated"] >= 1
    assert second["provider_stats"][0]["fetched"] == 1


def _is_active(engine, external_id: str) -> bool:
    with engine.begin() as conn:
        return (
            conn.execute(
                select(events_table.c.is_active).where(events_table.c.external_id == external_id)
            ).scalar_one()
        )


def test_hub_sync_deactivates_missing_future_events(engine, monkeypatch):
    class _FixedDateTime:
        @staticmethod
        def now(tz=None):
            base = datetime(2026, 2, 18, 0, 0)
            if tz is not None:
                return base.replace(tzinfo=tz)
            return base.replace(tzinfo=timezone.utc)

    monkeypatch.setattr(event_hub_module, "datetime", _FixedDateTime)

    registry = ProviderRegistry()
    provider = _StaticProvider("good", [_event("evt-keep"), _event("evt-drop")])
    registry.register("good", provider)
    hub = EventHub(registry)

    hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)

    provider._events = [_event("evt-keep")]
    hub.sync(city="Madrid", past_days=1, future_days=1, session=engine)

    assert _is_active(engine, "evt-keep") is True
    assert _is_active(engine, "evt-drop") is False

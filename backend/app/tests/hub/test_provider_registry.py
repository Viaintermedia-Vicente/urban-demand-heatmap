from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.hub.event_hub import EventHub
from app.hub.provider_registry import ProviderRegistry
from app.providers.events.base import ExternalEvent, EventsProvider


class _StaticProvider(EventsProvider):
    def __init__(self, events: list[ExternalEvent], *, fail: bool = False) -> None:
        self._events = events
        self._fail = fail
        self.calls: list[tuple[str, int]] = []

    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: datetime | None = None,
        direction: str = "future",
    ) -> list[ExternalEvent]:
        if self._fail:
            raise RuntimeError("provider failure")
        self.calls.append((direction, days))
        if direction == "past":
            return []
        return list(self._events)


def _event(source: str, external_id: str, offset_hours: int = 0) -> ExternalEvent:
    start = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
    return ExternalEvent(
        source=source,
        external_id=external_id,
        title=f"Event {external_id}",
        start_at=start,
    )


def test_registry_register_and_get() -> None:
    registry = ProviderRegistry()
    provider = _StaticProvider([])
    registry.register("demo", provider)

    assert registry.get("demo") is provider
    assert registry.list() == ["demo"]


def test_registry_duplicate_registration_fails() -> None:
    registry = ProviderRegistry()
    provider = _StaticProvider([])
    registry.register("demo", provider)

    with pytest.raises(ValueError):
        registry.register("demo", provider)


def test_hub_combines_multiple_providers() -> None:
    registry = ProviderRegistry()
    provider_a = _StaticProvider([_event("a", "1"), _event("a", "2")])
    provider_b = _StaticProvider([_event("b", "1")])
    registry.register("A", provider_a)
    registry.register("B", provider_b)

    hub = EventHub(registry)
    events = hub.fetch_all(city="Madrid", past_days=1, future_days=2)

    assert len(events) == 3
    assert all(evt.source in {"a", "b"} for evt in events)
    # Both directions invoked when days > 0
    assert ("past", 1) in provider_a.calls
    assert ("future", 2) in provider_a.calls


def test_hub_continues_if_one_provider_fails() -> None:
    registry = ProviderRegistry()
    failing = _StaticProvider([], fail=True)
    healthy = _StaticProvider([_event("ok", "1")])
    registry.register("Failing", failing)
    registry.register("Healthy", healthy)

    hub = EventHub(registry)
    events = hub.fetch_all(city="Madrid", past_days=0, future_days=1)

    assert len(events) == 1
    assert hub.errors  # error tracked
    assert hub.errors[0][0] == "Failing"

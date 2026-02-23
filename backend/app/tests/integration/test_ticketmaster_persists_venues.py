from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, select

from app.hub.event_hub import EventHub
from app.hub.provider_registry import ProviderRegistry
from app.infra.db.tables import events_table, metadata, venues_table
from app.providers.events.base import EventsProvider, ExternalEvent
from app.providers.events.ticketmaster import TicketmasterEventsProvider


class _StaticProvider(EventsProvider):
    def __init__(self, events: list[ExternalEvent]):
        self._events = events

    def fetch_events(self, *, city: str, days: int, reference: datetime | None = None, direction: str = "future"):
        return list(self._events)


def _make_ticketmaster_event() -> ExternalEvent:
    provider = TicketmasterEventsProvider.__new__(TicketmasterEventsProvider)
    payload = {
        "id": "tm-event-1",
        "name": "Ticketmaster Demo",
        "dates": {
            "start": {"dateTime": "2026-03-01T20:00:00Z"},
            "end": {"dateTime": "2026-03-01T22:00:00Z"},
            "status": {"code": "onsale"},
        },
        "_embedded": {
            "venues": [
                {
                    "id": "tm-venue-1",
                    "name": "TM Arena",
                    "city": {"name": "Madrid"},
                    "country": {"countryCode": "ES"},
                    "timezone": "Europe/Madrid",
                    "location": {"latitude": "40.4168", "longitude": "-3.7038"},
                }
            ]
        },
    }
    event = provider._map_event(payload)  # type: ignore[attr-defined]
    return event


def test_ticketmaster_sync_persists_venues(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tm.db'}", future=True)
    metadata.create_all(engine)
    event = _make_ticketmaster_event()
    registry = ProviderRegistry()
    registry.register("ticketmaster", _StaticProvider([event]))
    hub = EventHub(registry)

    hub.sync(city="Madrid", past_days=0, future_days=1, session=engine)

    with engine.begin() as conn:
        event_row = conn.execute(select(events_table)).mappings().one()
        venue_row = conn.execute(select(venues_table)).mappings().one()
    assert event_row["venue_id"] == venue_row["id"]
    assert venue_row["name"] == "TM Arena"

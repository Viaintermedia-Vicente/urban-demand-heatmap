from datetime import datetime, timezone

from app.providers.events.ticketmaster import TicketmasterEventsProvider


def test_ticketmaster_datetime_format():
    dt = datetime(2026, 2, 9, 18, 43, 14, 156741, tzinfo=timezone.utc)
    formatted = TicketmasterEventsProvider._format_ts(dt)
    assert formatted == "2026-02-09T18:43:14Z"
    assert "." not in formatted


def test_ticketmaster_extract_coordinates():
    provider = TicketmasterEventsProvider.__new__(TicketmasterEventsProvider)
    payload = {
        "id": "evt-1",
        "name": "Sample",
        "dates": {
            "start": {"dateTime": "2026-02-19T19:00:00Z"},
            "end": {"dateTime": "2026-02-19T20:00:00Z"},
            "status": {"code": "onsale"}
        },
        "_embedded": {
            "venues": [
                {
                    "name": "Venue",
                    "id": "venue-1",
                    "city": {"name": "Madrid"},
                    "country": {"countryCode": "ES"},
                    "timezone": "Europe/Madrid",
                    "location": {"latitude": "40.4", "longitude": "-3.7"}
                }
            ]
        },
    }
    event = provider._map_event(payload)  # type: ignore[attr-defined]
    assert event.lat == 40.4
    assert event.lon == -3.7


def test_ticketmaster_skip_missing_coordinates():
    provider = TicketmasterEventsProvider.__new__(TicketmasterEventsProvider)
    events = [
        {
            "id": "evt-keep",
            "name": "Valid",
            "dates": {"start": {"dateTime": "2026-02-19T19:00:00Z"}},
            "_embedded": {"venues": [{"location": {"latitude": "40.4", "longitude": "-3.7"}}]},
        },
        {
            "id": "evt-skip",
            "name": "Missing coords",
            "dates": {"start": {"dateTime": "2026-02-20T19:00:00Z"}},
            "_embedded": {"venues": [{"location": {}}]},
        },
    ]
    mapped, stats = provider._process_events(events)  # type: ignore[attr-defined]
    assert len(mapped) == 1
    assert stats["skipped_no_coords"] == 1

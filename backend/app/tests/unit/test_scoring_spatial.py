from datetime import datetime

from app.domain.models import Event
from app.domain import scoring


def make_event():
    return Event(
        id="ev-spatial",
        title="Teatro",
        category="teatro",
        start_dt=datetime(2026, 2, 10, 18, 0, 0),
        end_dt=datetime(2026, 2, 10, 20, 0, 0),
        lat=40.4168,
        lon=-3.7038,
    )


def test_spatial_stronger_at_event_location():
    event = make_event()
    target = event.start_dt
    exact = scoring.event_score(event, target, event.lat, event.lon)
    far = scoring.event_score(event, target, event.lat + 0.05, event.lon + 0.05)
    assert exact > 0
    assert far == 0
    assert exact > far

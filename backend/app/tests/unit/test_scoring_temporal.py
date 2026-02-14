from datetime import datetime, timedelta

from app.domain.models import Event
from app.domain import scoring


def make_event():
    start = datetime(2026, 2, 10, 20, 0, 0)
    return Event(
        id="ev1",
        title="Concierto",
        category="concierto",
        start_dt=start,
        end_dt=start + timedelta(hours=2),
        lat=40.4,
        lon=-3.7,
    )


def test_temporal_pre_has_weight():
    event = make_event()
    target = event.start_dt - timedelta(minutes=30)
    assert scoring.temporal_weight(event, target) > 0


def test_temporal_outside_window_zero():
    event = make_event()
    target = event.end_dt + timedelta(hours=2)
    assert scoring.temporal_weight(event, target) == 0

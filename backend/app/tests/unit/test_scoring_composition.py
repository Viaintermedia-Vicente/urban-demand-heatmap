from datetime import datetime, timedelta

from app.domain.models import Event
from app.domain import scoring


def make_event(event_id: str, lat: float, lon: float) -> Event:
    start = datetime(2026, 2, 10, 19, 0, 0)
    return Event(
        id=event_id,
        title="Demo",
        category="concierto",
        start_dt=start,
        end_dt=start + timedelta(hours=2),
        lat=lat,
        lon=lon,
    )


def test_scores_sum_for_nearby_events():
    e1 = make_event("ev1", 40.4, -3.7)
    e2 = make_event("ev2", 40.4005, -3.7005)
    target = e1.start_dt
    single = scoring.compute_hotspots([e1], target)
    combined = scoring.compute_hotspots([e1, e2], target)
    assert combined[0].score > single[0].score

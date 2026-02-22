from __future__ import annotations

from datetime import datetime, timezone

from app.domain.canonical import CanonicalEvent, CanonicalWeatherHour, MADRID_TZ


def test_canonical_event_normalizes_timezone():
    naive_start = datetime(2026, 2, 18, 20, 0, 0)
    event = CanonicalEvent(
        source="providerA",
        external_id="evt-1",
        title="Sample",
        start_at=naive_start,
        end_at=naive_start,
        lat=40.0,
        lon=-3.0,
    )
    assert event.start_at.tzinfo == MADRID_TZ


def test_canonical_weather_normalizes_timezone():
    naive_obs = datetime(2026, 2, 18, 10, 0, 0)
    hour = CanonicalWeatherHour(
        source="providerA",
        lat=40.0,
        lon=-3.0,
        observed_at=naive_obs,
    )
    assert hour.observed_at.tzinfo == MADRID_TZ


def test_canonical_fields_accept_aware_datetimes():
    aware = datetime(2026, 2, 18, 20, 0, 0, tzinfo=timezone.utc)
    event = CanonicalEvent(
        source="provider",
        external_id="evt-123",
        title="Concert",
        start_at=aware,
        end_at=aware,
        lat=40.0,
        lon=-3.0,
    )
    assert event.start_at.tzinfo == MADRID_TZ
    weather = CanonicalWeatherHour(
        source="provider",
        lat=40.0,
        lon=-3.0,
        observed_at=aware,
    )
    assert weather.observed_at.tzinfo == MADRID_TZ

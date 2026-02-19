from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.canonical import CanonicalEvent, CanonicalWeatherHour


def test_canonical_event_requires_timezone():
    naive_start = datetime(2026, 2, 18, 20, 0, 0)
    with pytest.raises(ValueError):
        CanonicalEvent(
            source="providerA",
            external_id="evt-1",
            title="Sample",
            start=naive_start,
            end=naive_start,
            lat=40.0,
            lon=-3.0,
        )


def test_canonical_weather_requires_timezone():
    naive_obs = datetime(2026, 2, 18, 10, 0, 0)
    with pytest.raises(ValueError):
        CanonicalWeatherHour(
            source="providerA",
            lat=40.0,
            lon=-3.0,
            observed_at=naive_obs,
        )


def test_canonical_fields_accept_aware_datetimes():
    aware = datetime(2026, 2, 18, 20, 0, 0, tzinfo=timezone.utc)
    event = CanonicalEvent(
        source="provider",
        external_id="evt-123",
        title="Concert",
        start=aware,
        end=aware,
        lat=40.0,
        lon=-3.0,
    )
    assert event.start.tzinfo is not None
    weather = CanonicalWeatherHour(
        source="provider",
        lat=40.0,
        lon=-3.0,
        observed_at=aware,
    )
    assert weather.observed_at.tzinfo is not None

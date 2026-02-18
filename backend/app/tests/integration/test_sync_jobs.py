from __future__ import annotations

import os
import subprocess
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select

from app.infra.db.tables import events_table, metadata, venues_table, weather_observations_table
from app.jobs.sync_events import sync_events
from app.jobs.sync_weather import sync_weather
from app.providers.events.base import ExternalEvent, EventsProvider
from app.providers.weather.base import ExternalWeatherHour, WeatherProvider



BACKEND_DIR = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = BACKEND_DIR / "scripts"

class StaticEventsProvider(EventsProvider):
    def __init__(self, events: list[ExternalEvent]):
        self._events = events

    def fetch_events(self, *, city: str, days: int, reference: datetime | None = None, direction: str = "future"):
        return list(self._events)


class RangeEventsProvider(EventsProvider):
    def __init__(self, *, base: datetime, count: int, direction: str = "future"):
        self.base = base
        self.count = count
        self.direction = direction

    def fetch_events(self, *, city: str, days: int, reference: datetime | None = None, direction: str = "future"):
        ref = reference or self.base
        items: list[ExternalEvent] = []
        for idx in range(self.count):
            offset = idx if direction == "future" else -(idx + 1)
            start = ref + timedelta(days=offset)
            items.append(
                ExternalEvent(
                    source="fake",
                    external_id=f"evt-{direction}-{idx}",
                    title=f"Event {idx}",
                    category="music",
                    start_at=start,
                    end_at=start + timedelta(hours=2),
                    venue_name=f"Venue {idx}",
                    venue_external_id=f"venue-{idx}",
                    venue_city=city,
                    lat=40.4 + 0.01 * idx,
                    lon=-3.7 - 0.01 * idx,
                )
            )
        return items


class StaticWeatherProvider(WeatherProvider):
    def __init__(self, hours: list[ExternalWeatherHour]):
        self.hours = hours

    def fetch_hourly(self, *, lat: float, lon: float, start: date, end: date, location_name: str | None = None):
        return list(self.hours)


class RangeWeatherProvider(WeatherProvider):
    def __init__(self, *, base: datetime, count: int):
        self.base = base
        self.count = count

    def fetch_hourly(self, *, lat: float, lon: float, start: date, end: date, location_name: str | None = None):
        items = []
        for idx in range(self.count):
            items.append(
                ExternalWeatherHour(
                    source="fake",
                    lat=lat,
                    lon=lon,
                    observed_at=self.base + timedelta(hours=idx),
                    temperature_c=20.0,
                    precipitation_mm=0.1,
                    wind_speed_kmh=10.0,
                )
            )
        return items


def _make_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}", future=True)
    metadata.create_all(engine)
    return engine


def _count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()



def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_sync_events_upsert_idempotent(tmp_path):
    engine = _make_engine(tmp_path)
    reference = datetime(2026, 3, 1, tzinfo=timezone.utc)
    events = [
        ExternalEvent(
            source="fake",
            external_id=f"evt-{idx}",
            title=f"Show {idx}",
            category="music",
            start_at=reference + timedelta(hours=idx),
            end_at=reference + timedelta(hours=idx + 2),
            venue_name=f"Venue {idx}",
            venue_external_id=f"venue-{idx}",
            venue_city="Madrid",
            lat=40.4 + idx * 0.01,
            lon=-3.6 - idx * 0.01,
        )
        for idx in range(3)
    ]
    provider = StaticEventsProvider(events)

    stats1 = sync_events(
        city="Madrid",
        future_days=3,
        past_days=0,
        provider=provider,
        engine=engine,
        reference=reference,
    )
    assert stats1["events"]["inserted"] == 3
    stats2 = sync_events(
        city="Madrid",
        future_days=3,
        past_days=0,
        provider=provider,
        engine=engine,
        reference=reference,
    )
    assert stats2["events"]["inserted"] == 0
    assert stats2["events"]["updated"] == 3
    with engine.begin() as conn:
        assert _count(conn, events_table) == 3


def test_sync_events_creates_venue_when_missing(tmp_path):
    engine = _make_engine(tmp_path)
    reference = datetime(2026, 3, 1, tzinfo=timezone.utc)
    event = ExternalEvent(
        source="fake",
        external_id="evt-venue",
        title="Venue Linked",
        category="sports",
        start_at=reference,
        end_at=reference + timedelta(hours=2),
        venue_name="Palacio Demo",
        venue_external_id="venue-123",
        venue_city="Madrid",
        lat=40.4,
        lon=-3.7,
    )
    provider = StaticEventsProvider([event])
    stats = sync_events(city="Madrid", future_days=1, provider=provider, engine=engine, reference=reference)
    assert stats["venues"]["inserted"] == 1
    with engine.begin() as conn:
        venue_rows = conn.execute(select(venues_table)).mappings().all()
        assert len(venue_rows) == 1
        event_row = conn.execute(select(events_table)).mappings().first()
        assert event_row["venue_id"] == venue_rows[0]["id"]


def test_sync_weather_upsert_idempotent(tmp_path):
    engine = _make_engine(tmp_path)
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    hours = [
        ExternalWeatherHour(
            source="fake",
            lat=40.4,
            lon=-3.7,
            observed_at=base + timedelta(hours=idx),
            temperature_c=20.0,
        )
        for idx in range(48)
    ]
    provider = StaticWeatherProvider(hours)
    stats1 = sync_weather(lat=40.4, lon=-3.7, past_days=0, future_days=1, provider=provider, engine=engine)
    assert stats1["inserted"] == 48
    stats2 = sync_weather(lat=40.4, lon=-3.7, past_days=0, future_days=1, provider=provider, engine=engine)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == 48
    with engine.begin() as conn:
        assert _count(conn, weather_observations_table) == 48


def test_sync_jobs_work_without_keys(tmp_path):
    engine = _make_engine(tmp_path)
    stats_weather = sync_weather(lat=40.4, lon=-3.7, past_days=0, future_days=1, engine=engine)
    stats_events = sync_events(city="Madrid", future_days=1, engine=engine)
    assert stats_weather["inserted"] > 0
    assert stats_events["events"]["inserted"] > 0


def test_sync_weather_backfill_range(tmp_path):
    engine = _make_engine(tmp_path)
    base = datetime(2026, 3, 8, tzinfo=timezone.utc)
    provider = RangeWeatherProvider(base=base - timedelta(days=7), count=24 * 8)
    sync_weather(
        lat=40.4,
        lon=-3.7,
        past_days=7,
        future_days=1,
        provider=provider,
        engine=engine,
        reference=date(2026, 3, 8),
    )
    with engine.begin() as conn:
        rows = conn.execute(select(weather_observations_table.c.observed_at).order_by(weather_observations_table.c.observed_at)).scalars().all()
        assert rows
        assert _as_utc(rows[0]) < datetime(2026, 3, 8, tzinfo=timezone.utc)


def test_sync_events_backfill_creates_past_events(tmp_path):
    engine = _make_engine(tmp_path)
    reference = datetime(2026, 3, 8, tzinfo=timezone.utc)
    provider = RangeEventsProvider(base=reference, count=3)
    sync_events(
        city="Madrid",
        past_days=3,
        future_days=0,
        provider=provider,
        engine=engine,
        reference=reference,
    )
    with engine.begin() as conn:
        rows = conn.execute(select(events_table.c.start_dt)).scalars().all()
        assert any(_as_utc(row) < reference for row in rows)


def test_cron_scripts_exit_codes(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'cron_events.db'}"
    help_result = subprocess.run(["bash", str(SCRIPTS_DIR / "cron_sync_events.sh"), "--help"], capture_output=True, text=True)
    assert help_result.returncode == 0
    run_result = subprocess.run(["bash", str(SCRIPTS_DIR / "cron_sync_events.sh")], env=env, capture_output=True, text=True)
    assert run_result.returncode == 0, run_result.stderr

    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'cron_weather.db'}"
    weather_result = subprocess.run(["bash", str(SCRIPTS_DIR / "cron_sync_weather.sh")], env=env, capture_output=True, text=True)
    assert weather_result.returncode == 0, weather_result.stderr


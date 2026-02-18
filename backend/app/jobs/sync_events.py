from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional, Tuple

import typer
from sqlalchemy import create_engine

from app.infra.db.events_repository import EventsRepository
from app.infra.db.tables import metadata
from app.infra.db.venues_repository import VenuesRepository
from app.providers.events.base import EventsProvider, ExternalEvent

app = typer.Typer(help="Sync external events into the FinMaster database")
DEFAULT_COUNTRY = os.getenv("SYNC_EVENTS_COUNTRY", "ES")
DEFAULT_DURATION_HOURS = int(os.getenv("SYNC_EVENTS_DEFAULT_DURATION", "2"))


class SyncResults(Dict[str, Dict[str, int]]):
    ...


def sync_events(
    city: str,
    *,
    past_days: int = 0,
    future_days: int = 7,
    provider: Optional[EventsProvider] = None,
    engine=None,
    database_url: Optional[str] = None,
    reference: Optional[datetime] = None,
    country: Optional[str] = None,
) -> Dict[str, Dict[str, int]]:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days and future_days must be >= 0")
    if past_days == 0 and future_days == 0:
        raise ValueError("At least one of past_days/future_days must be > 0")

    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)

    metadata.create_all(engine)
    venues_repo = VenuesRepository(engine)
    events_repo = EventsRepository(engine, venues_repo=venues_repo)
    provider = provider or _DemoEventsProvider()
    reference = reference or datetime.now(timezone.utc)

    stats = {
        "events": {"inserted": 0, "updated": 0, "skipped": 0},
        "venues": {"inserted": 0, "updated": 0, "skipped": 0},
    }

    for direction, days in (("past", past_days), ("future", future_days)):
        if days <= 0:
            continue
        entries = provider.fetch_events(city=city, days=days, reference=reference, direction=direction)
        stats = _process_events(
            entries,
            stats,
            city=city,
            country=country or DEFAULT_COUNTRY,
            direction=direction,
            events_repo=events_repo,
            venues_repo=venues_repo,
            reference=reference,
        )

    _log_summary(city, stats, past_days, future_days)
    return stats


@app.command()
def run(
    city: str = typer.Option(..., help="City to sync"),
    past_days: int = typer.Option(0, help="Days in the past to backfill"),
    future_days: int = typer.Option(7, help="Days forward to fetch"),
    country: Optional[str] = typer.Option(None, help="Country code for inferred venues"),
):
    """CLI entrypoint for syncing external events."""
    sync_events(city, past_days=past_days, future_days=future_days, country=country)


def _process_events(
    events: Iterable[ExternalEvent],
    stats: Dict[str, Dict[str, int]],
    *,
    city: str,
    country: str,
    direction: str,
    events_repo: EventsRepository,
    venues_repo: VenuesRepository,
    reference: datetime,
) -> Dict[str, Dict[str, int]]:
    for event in events:
        if not _event_has_required_fields(event):
            stats["events"]["skipped"] += 1
            continue
        venue_stats, venue_id = _ensure_venue(event, venues_repo, city=city, country=country)
        for key in ("inserted", "updated", "skipped"):
            stats["venues"][key] += venue_stats.get(key, 0)
        payload = _build_event_payload(event, venue_id)
        existed = events_repo.get_event_by_source_external(payload["source"], payload["external_id"])
        events_repo.upsert_event(payload)
        if existed:
            stats["events"]["updated"] += 1
        else:
            stats["events"]["inserted"] += 1
    return stats


def _event_has_required_fields(event: ExternalEvent) -> bool:
    return bool(event.source and event.external_id and event.title and event.start_at and event.lat is not None and event.lon is not None)


def _ensure_venue(
    event: ExternalEvent,
    repo: VenuesRepository,
    *,
    city: str,
    country: str,
) -> Tuple[Dict[str, int], Optional[int]]:
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    venue_id: Optional[int] = None
    if event.venue_name:
        payload = {
            "source": event.venue_source or event.source,
            "external_id": event.venue_external_id,
            "name": event.venue_name,
            "lat": event.lat,
            "lon": event.lon,
            "city": event.venue_city or city,
            "region": None,
            "country": event.venue_country or country,
            "address_line1": None,
            "address_line2": None,
            "postal_code": None,
            "max_capacity": None,
        }
        existed = None
        if payload["external_id"]:
            existed = repo.get_venue_id_by_external(payload["source"], payload["external_id"])
        if existed is None:
            venue = repo.get_venue_by_name(payload["city"], payload["name"])
            existed = venue["id"] if venue else None
        venue_id = repo.upsert_venue(payload)
        if existed:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1
    else:
        stats["skipped"] += 1
    return stats, venue_id


def _build_event_payload(event: ExternalEvent, venue_id: Optional[int]) -> Dict[str, object]:
    start_dt = _ensure_utc(event.start_at)
    end_dt = _ensure_utc(event.end_at or (start_dt + timedelta(hours=DEFAULT_DURATION_HOURS)))
    timezone_name = event.timezone or (start_dt.tzinfo.tzname(None) if start_dt.tzinfo else "UTC")
    category = (event.category or "unknown").lower()
    return {
        "source": event.source,
        "external_id": event.external_id,
        "title": event.title,
        "category": category,
        "subcategory": event.subcategory,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "timezone": timezone_name or "UTC",
        "venue_id": venue_id,
        "lat": event.lat,
        "lon": event.lon,
        "status": event.status,
        "url": event.url,
        "expected_attendance": None,
        "popularity_score": event.popularity_score,
    }


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _log_summary(city: str, stats: Dict[str, Dict[str, int]], past_days: int, future_days: int) -> None:
    db_url = os.getenv("DATABASE_URL", "<engine>")
    print(
        f"[sync_events] city={city} db={db_url} past={past_days} future={future_days} "
        f"events={stats['events']} venues={stats['venues']}"
    )

class _DemoEventsProvider:
    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: Optional[datetime] = None,
        direction: str = "future",
    ) -> list[ExternalEvent]:
        reference = reference or datetime.now(timezone.utc)
        count = max(1, min(5, days))
        records: list[ExternalEvent] = []
        for idx in range(count):
            offset_days = idx if direction == "future" else -(idx + 1)
            start = reference + timedelta(days=offset_days)
            records.append(
                ExternalEvent(
                    source="demo",
                    external_id=f"demo-{direction}-{idx}",
                    title=f"Demo {city} {direction} {idx}",
                    category="music",
                    start_at=start,
                    end_at=start + timedelta(hours=2),
                    venue_name=f"Demo Venue {idx}",
                    venue_external_id=f"demo-venue-{idx}",
                    venue_city=city,
                    venue_country=DEFAULT_COUNTRY,
                    lat=40.4 + 0.01 * idx,
                    lon=-3.7 - 0.01 * idx,
                    url="https://demo.local/event",
                )
            )
        return records


if __name__ == "__main__":
    app()

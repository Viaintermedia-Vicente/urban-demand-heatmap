from __future__ import annotations

import os
from datetime import date, datetime, timedelta, time, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import typer
from sqlalchemy import create_engine

from app.infra.db.events_repository import EventsRepository
from app.infra.db.tables import metadata
from app.infra.db.venues_repository import VenuesRepository

app = typer.Typer(help="Genera eventos demo para poblar la base de datos sin depender de APIs externas")
DEFAULT_TZ = os.getenv("DEMO_EVENTS_TZ", "Europe/Madrid")
DEFAULT_COUNTRY = os.getenv("DEMO_EVENTS_COUNTRY", "ES")
BASE_HOURS = [10, 12, 18, 20, 22]
CATEGORIES = ["music", "sports", "expo", "conference", "community"]


def generate_demo_events(
    *,
    city: str,
    lat: float,
    lon: float,
    past_days: int = 30,
    future_days: int = 7,
    per_day: int = 10,
    timezone_name: str = DEFAULT_TZ,
    engine=None,
    database_url: Optional[str] = None,
    reference_date: Optional[date] = None,
    country: str = DEFAULT_COUNTRY,
) -> Dict[str, int]:
    if past_days < 0 or future_days < 0:
        raise ValueError("past_days y future_days deben ser >= 0")
    if per_day <= 0:
        raise ValueError("per_day debe ser > 0")
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)

    metadata.create_all(engine)
    venues_repo = VenuesRepository(engine)
    events_repo = EventsRepository(engine, venues_repo=venues_repo)

    tz = ZoneInfo(timezone_name)
    today = reference_date or datetime.now(tz).date()
    venue_payload = {
        "source": "demo",
        "external_id": f"demo-venue-{city.lower()}",
        "name": f"Demo Venue - {city}",
        "lat": lat,
        "lon": lon,
        "city": city,
        "region": None,
        "country": country,
        "address_line1": None,
        "address_line2": None,
        "postal_code": None,
        "max_capacity": 20000,
    }
    venue_id = venues_repo.upsert_venue(venue_payload)

    inserted = 0
    updated = 0
    skipped = 0
    total_days = past_days + future_days + 1
    category_count = len(CATEGORIES)

    for offset in range(-past_days, future_days + 1):
        day = today + timedelta(days=offset)
        for idx in range(per_day):
            hour = BASE_HOURS[idx % len(BASE_HOURS)]
            minute = (idx * 7) % 60
            start_local = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=tz)
            end_local = start_local + timedelta(hours=2)
            start_dt = start_local.astimezone(timezone.utc)
            end_dt = end_local.astimezone(timezone.utc)
            event_idx = idx % category_count
            category = CATEGORIES[event_idx]
            lat_variation = lat + ((idx % 5) - 2) * 0.002
            lon_variation = lon + ((idx % 5) - 2) * 0.002
            external_id = f"demo:{city.lower()}:{day.strftime('%Y%m%d')}:{idx}"
            payload = {
                "source": "demo",
                "external_id": external_id,
                "title": f"Demo Event {city} #{offset+per_day+idx}",
                "category": category,
                "subcategory": None,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "timezone": timezone_name,
                "venue_id": venue_id,
                "lat": lat_variation,
                "lon": lon_variation,
                "status": "scheduled",
                "url": f"https://demo.local/{city.lower()}/{external_id.split(':')[-1]}",
                "expected_attendance": 500 + (idx * 25),
                "popularity_score": float(0.5 + (idx % 5) * 0.1),
            }
            existed = events_repo.get_event_by_source_external("demo", external_id)
            events_repo.upsert_event(payload)
            if existed:
                updated += 1
            else:
                inserted += 1
    total_expected = total_days * per_day
    print(
        f"[generate_demo_events] city={city} days={total_days} per_day={per_day} inserted={inserted} updated={updated} expected={total_expected}"
    )
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "expected": total_expected}


@app.command()
def cli(
    city: str = typer.Option(..., help="Ciudad"),
    lat: float = typer.Option(..., help="Latitud"),
    lon: float = typer.Option(..., help="Longitud"),
    past_days: int = typer.Option(30, help="Días hacia atrás"),
    future_days: int = typer.Option(7, help="Días hacia adelante"),
    per_day: int = typer.Option(10, help="Eventos por día"),
    timezone_name: str = typer.Option(DEFAULT_TZ, help="Zona horaria"),
):
    generate_demo_events(
        city=city,
        lat=lat,
        lon=lon,
        past_days=past_days,
        future_days=future_days,
        per_day=per_day,
        timezone_name=timezone_name,
    )


if __name__ == "__main__":
    app()

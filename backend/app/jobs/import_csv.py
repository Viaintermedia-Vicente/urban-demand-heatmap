from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import create_engine

from app.infra.db.category_rules_repository import CategoryRulesRepository
from app.infra.db.events_repository import EventsRepository
from app.infra.db.tables import metadata
from app.infra.db.venues_repository import VenuesRepository
from app.services.attendance import estimate_expected_attendance

DEFAULT_DATA_DIR = Path(os.getenv('IMPORT_DATA_DIR', '/data'))


def import_events_from_csv(
    data_dir: str | Path | None = None,
    *,
    engine=None,
    database_url: Optional[str] = None,
) -> None:
    base_path = _resolve_data_dir(data_dir)
    venues_path = base_path / "venues_seed.csv"
    events_path = base_path / "events_seed.csv"
    category_rules_path = base_path / "category_rules_seed.csv"

    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)
    venues_repo = VenuesRepository(engine)
    events_repo = EventsRepository(engine=engine, venues_repo=venues_repo)
    rules_repo = CategoryRulesRepository(engine)

    rules_count = _import_category_rules(category_rules_path, rules_repo)
    capacity_map, venues_count = _import_venues(venues_path, venues_repo)
    rules_map = rules_repo.get_rules_map()
    events_count = _import_events(events_path, events_repo, capacity_map, rules_map)
    db_url = getattr(engine, "url", database_url or os.getenv("DATABASE_URL"))
    print(
        f"[import_csv] Import complete database={db_url} "
        f"rules={rules_count} venues={venues_count} events={events_count}"
    )


def _resolve_data_dir(data_dir: str | Path | None) -> Path:
    if data_dir is None:
        candidate = DEFAULT_DATA_DIR
    else:
        candidate = Path(data_dir)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"Data directory not found: {candidate}")
    return candidate


def _import_category_rules(path: Path, repo: CategoryRulesRepository) -> int:
    count = 0
    for row in _read_csv(path):
        repo.upsert_rule(
            {
                "category": row["category"].strip().lower(),
                "fill_factor": float(row["fill_factor"]),
                "fallback_attendance": int(row["fallback_attendance"]),
                "default_duration_min": int(row["default_duration_min"]),
                "pre_event_min": int(row["pre_event_min"]),
                "post_event_min": int(row["post_event_min"]),
            }
        )
        count += 1
    return count


def _import_venues(path: Path, repo: VenuesRepository) -> tuple[Dict[str, Optional[int]], int]:
    capacity_by_key: Dict[str, Optional[int]] = {}
    count = 0
    for row in _read_csv(path):
        payload = {
            "source": row["source"],
            "external_id": row["external_id"] or None,
            "name": row["name"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "city": row["city"],
            "region": row["region"] or None,
            "country": row["country"],
            "address_line1": row["address_line1"] or None,
            "address_line2": row["address_line2"] or None,
            "postal_code": row["postal_code"] or None,
            "max_capacity": int(row["max_capacity"]) if row["max_capacity"] else None,
        }
        repo.upsert_venue(payload)
        key = _venue_key(payload["source"], payload["external_id"])
        capacity_by_key[key] = payload["max_capacity"]
        count += 1
    return capacity_by_key, count


def _import_events(
    path: Path,
    repo: EventsRepository,
    capacity_map: Dict[str, Optional[int]],
    rules_map: Dict[str, dict],
) -> int:
    count = 0
    for row in _read_csv(path):
        source = row["source"]
        external_id = row["external_id"]
        venue_external = row.get("venue_external_id") or None
        venue_key = _venue_key(source, venue_external)
        venue_capacity = capacity_map.get(venue_key)
        category = row["category"].strip().lower()
        expected_attendance = estimate_expected_attendance(category, venue_capacity, rules_map)
        try:
            start_dt = _parse_dt(row["start_dt"])
            end_dt = _parse_dt(row["end_dt"])
        except (ValueError, TypeError) as exc:
            print(
                f"[import_csv] WARNING: skipping event {external_id or row.get('title')} due to invalid datetime: {exc}"
            )
            continue
        payload = {
            "source": source,
            "external_id": external_id,
            "title": row["title"],
            "category": category,
            "subcategory": row.get("subcategory") or None,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "timezone": row["timezone"],
            "venue_external_id": venue_external,
            "venue_name": row.get("venue_name"),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "status": row.get("status"),
            "url": row.get("url"),
            "expected_attendance": expected_attendance,
            "popularity_score": None,
        }
        repo.upsert_event(payload)
        count += 1
    return count


def _venue_key(source: str, external_id: Optional[str]) -> str:
    return f"{source}:{external_id or ''}"


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

if __name__ == "__main__":
    import sys
    data_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    import_events_from_csv(data_arg)

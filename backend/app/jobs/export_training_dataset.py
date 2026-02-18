from __future__ import annotations

import csv
import os
from datetime import datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import create_engine

from app.infra.db.snapshots_repository import EventFeatureSnapshotsRepository
from app.infra.db.tables import metadata


def _parse_date(value: str, end: bool = False) -> datetime:
    if len(value) == 10:
        date_val = datetime.fromisoformat(value).date()
        dt = datetime.combine(date_val, time.max if end else time.min)
    else:
        dt = datetime.fromisoformat(value)
    if end:
        return dt.replace(tzinfo=timezone.utc)
    return dt.replace(tzinfo=timezone.utc)


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return r * c


def _compute_label_lead_time(row: dict) -> int:
    lead = 90
    precip = _to_float(row.get("precipitation_mm"))
    wind = _to_float(row.get("wind_speed_kmh"))
    temp = _to_float(row.get("temperature_c"))

    if precip is not None:
        if precip >= 1.0:
            lead = 30
        elif 0.2 <= precip < 1.0:
            lead = 45

    if wind is not None and wind >= 35:
        lead -= 15
    if temp is not None and (temp <= 5 or temp >= 32):
        lead -= 15
    lead = max(15, min(lead, 120))
    return int(lead)


def _compute_label_attendance_factor(row: dict) -> float:
    factor = 1.0
    precip = _to_float(row.get("precipitation_mm"))
    wind = _to_float(row.get("wind_speed_kmh"))
    temp = _to_float(row.get("temperature_c"))
    clouds = _to_float(row.get("cloud_cover_pct"))

    if precip is not None:
        if precip >= 1.0:
            factor -= 0.25
        elif 0.2 <= precip < 1.0:
            factor -= 0.10

    if wind is not None and wind >= 35:
        factor -= 0.10
    if temp is not None and (temp <= 5 or temp >= 32):
        factor -= 0.05
    if clouds is not None and clouds >= 85:
        factor -= 0.03

    factor = max(0.50, min(factor, 1.10))
    return round(factor, 3)


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def export_training_dataset(
    out_path: Path,
    start_date: str,
    end_date: str,
    *,
    center_lat: float = 40.4168,
    center_lon: float = -3.7038,
    limit: Optional[int] = None,
    engine=None,
    database_url: Optional[str] = None,
) -> dict:
    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)
    metadata.create_all(engine)
    repo = EventFeatureSnapshotsRepository(engine)

    start_dt = _parse_date(start_date, end=False)
    end_dt = _parse_date(end_date, end=True)
    rows = repo.list_by_range(start_dt, end_dt)
    total_rows = len(rows)
    if limit is not None and limit >= 0:
        rows = rows[:limit]

    header = [
        "snapshot_id",
        "event_external_id",
        "target_at",
        "hour",
        "dow",
        "category",
        "lat",
        "lon",
        "dist_km",
        "temperature_c",
        "precipitation_mm",
        "rain_mm",
        "snowfall_mm",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "cloud_cover_pct",
        "humidity_pct",
        "pressure_hpa",
        "visibility_m",
        "weather_code",
        "label",
        "label_lead_time_min",
        "label_attendance_factor",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=header)
        writer.writeheader()
        for row in rows:
            target = row["target_at"]
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            label = row.get("expected_attendance")
            if label is None:
                label = row.get("score_final")
            lead_time = _compute_label_lead_time(row)
            attendance_factor = _compute_label_attendance_factor(row)
            dist = _haversine_km(center_lat, center_lon, row["lat"], row["lon"])
            writer.writerow(
                {
                    "snapshot_id": row.get("id"),
                    "event_external_id": row.get("event_id"),
                    "target_at": target.isoformat(),
                    "hour": target.hour,
                    "dow": target.weekday(),
                    "category": row.get("category") or "unknown",
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "dist_km": round(dist, 4),
                    "temperature_c": row.get("temperature_c"),
                    "precipitation_mm": row.get("precipitation_mm"),
                    "rain_mm": row.get("rain_mm"),
                    "snowfall_mm": row.get("snowfall_mm"),
                    "wind_speed_kmh": row.get("wind_speed_kmh"),
                    "wind_gust_kmh": row.get("wind_gust_kmh"),
                    "cloud_cover_pct": row.get("cloud_cover_pct"),
                    "humidity_pct": row.get("humidity_pct"),
                    "pressure_hpa": row.get("pressure_hpa"),
                    "visibility_m": row.get("visibility_m"),
                    "weather_code": row.get("weather_code"),
                    "label": label,
                    "label_lead_time_min": lead_time,
                    "label_attendance_factor": attendance_factor,
                }
            )
    print(
        "[export_training_dataset] "
        f"rows={len(rows)} total={total_rows} start={start_date} end={end_date} "
        f"path={out_path}"
    )
    return {"rows": len(rows), "total": total_rows, "path": str(out_path)}


def export_cli(
    out: Path = typer.Option(..., exists=False, dir_okay=False, writable=True),
    start_date: str = typer.Option(..., help="YYYY-MM-DD"),
    end_date: str = typer.Option(..., help="YYYY-MM-DD"),
    center_lat: float = typer.Option(40.4168),
    center_lon: float = typer.Option(-3.7038),
    limit: Optional[int] = typer.Option(None, help="Limitar filas exportadas"),
    database_url: Optional[str] = typer.Option(None, help="DATABASE_URL override"),
):
    export_training_dataset(
        out,
        start_date,
        end_date,
        center_lat=center_lat,
        center_lon=center_lon,
        limit=limit,
        database_url=database_url,
    )


if __name__ == "__main__":
    typer.run(export_cli)

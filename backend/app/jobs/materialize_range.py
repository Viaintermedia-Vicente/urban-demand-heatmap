from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from time import perf_counter
from typing import List, Optional

import typer
from sqlalchemy import create_engine

from app.jobs.materialize_snapshots import materialize_snapshots


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _parse_hours(value: str) -> List[int]:
    hours: set[int] = set()
    tokens = [t.strip() for t in value.split(",") if t.strip()]
    if not tokens:
        tokens = [value.strip()] if value.strip() else ["0-23"]
    for token in tokens:
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start > end:
                start, end = end, start
            for h in range(start, end + 1):
                hours.add(_validate_hour(h))
        else:
            hours.add(_validate_hour(int(token)))
    return sorted(hours)


def _validate_hour(hour: int) -> int:
    if hour < 0 or hour > 23:
        raise typer.BadParameter("hour must be between 0 and 23")
    return hour


def materialize_range(
    start_date: str,
    end_date: str,
    hours: str = "0-23",
    *,
    lat: float = 40.4168,
    lon: float = -3.7038,
    radius_km: float = 5.0,
    engine=None,
    database_url: Optional[str] = None,
) -> dict:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if end < start:
        start, end = end, start
    hours_list = _parse_hours(hours)
    if not hours_list:
        raise typer.BadParameter("No hours provided")

    if engine is None:
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL required if engine not provided")
        engine = create_engine(database_url, future=True)

    start_time = perf_counter()
    current = start
    total_inserted = 0
    total_updated = 0
    day_count = 0
    while current <= end:
        for hour in hours_list:
            result = materialize_snapshots(
                date_str=current.isoformat(),
                hour=hour,
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                engine=engine,
            )
            total_inserted += result.get("inserted", 0)
            total_updated += result.get("updated", 0)
        day_count += 1
        current += timedelta(days=1)

    total_hours = len(hours_list)
    elapsed = perf_counter() - start_time
    summary = {
        "days": day_count,
        "hours_per_day": total_hours,
        "inserted": total_inserted,
        "updated": total_updated,
        "elapsed_sec": elapsed,
    }
    print(
        f"[materialize_range] days={day_count} hours_per_day={total_hours} "
        f"inserted={total_inserted} updated={total_updated} elapsed={elapsed:.2f}s"
    )
    return summary


def cli(
    start_date: str = typer.Option(..., help="Fecha inicio YYYY-MM-DD"),
    end_date: str = typer.Option(..., help="Fecha fin YYYY-MM-DD"),
    hours: str = typer.Option("0-23", help="Horas a procesar (ej. 18-23 o 18,19,20)"),
    lat: float = typer.Option(40.4168),
    lon: float = typer.Option(-3.7038),
    radius_km: float = typer.Option(5.0),
    database_url: Optional[str] = typer.Option(None, help="DATABASE_URL override"),
):
    materialize_range(
        start_date,
        end_date,
        hours,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        database_url=database_url,
    )


if __name__ == "__main__":
    typer.run(cli)

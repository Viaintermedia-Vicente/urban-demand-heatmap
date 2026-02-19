from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from app.domain.canonical import CanonicalWeatherHour
from app.infra.db.tables import weather_observations_table


class WeatherUpsertService:
    def __init__(self, engine: Engine):
        if engine is None:
            raise ValueError("engine is required")
        self.engine = engine

    def upsert_hours(self, hours: Iterable[CanonicalWeatherHour]) -> dict:
        hour_list = list(hours)
        stats = {"inserted": 0, "updated": 0, "total": len(hour_list)}
        if not hour_list:
            return stats

        with self.engine.begin() as conn:
            for hour in hour_list:
                payload = self._build_payload(hour)
                existing_id = self._find_existing(conn, hour)
                now = datetime.now(timezone.utc)
                if existing_id:
                    conn.execute(
                        update(weather_observations_table)
                        .where(weather_observations_table.c.id == existing_id)
                        .values(**payload, updated_at=now, source=hour.source)
                    )
                    stats["updated"] += 1
                else:
                    insert_payload = {
                        **payload,
                        "source": hour.source,
                        "created_at": now,
                        "updated_at": now,
                    }
                    conn.execute(insert(weather_observations_table).values(insert_payload))
                    stats["inserted"] += 1
        return stats

    def _find_existing(self, conn: Connection, hour: CanonicalWeatherHour) -> Optional[int]:
        stmt = (
            select(weather_observations_table.c.id)
            .where(
                weather_observations_table.c.lat == hour.lat,
                weather_observations_table.c.lon == hour.lon,
                weather_observations_table.c.observed_at == hour.observed_at,
            )
            .limit(1)
        )
        return conn.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _build_payload(hour: CanonicalWeatherHour) -> dict:
        return {
            "lat": hour.lat,
            "lon": hour.lon,
            "observed_at": hour.observed_at,
            "location_name": hour.raw.get("location_name") if hour.raw else None,
            "temperature_c": hour.temperature_c,
            "precipitation_mm": hour.precipitation_mm,
            "rain_mm": hour.raw.get("rain_mm") if hour.raw else None,
            "snowfall_mm": hour.raw.get("snowfall_mm") if hour.raw else None,
            "cloud_cover_pct": hour.cloud_cover_pct,
            "wind_speed_kmh": hour.wind_speed_kmh,
            "wind_gust_kmh": hour.raw.get("wind_gust_kmh") if hour.raw else None,
            "wind_dir_deg": hour.raw.get("wind_dir_deg") if hour.raw else None,
            "humidity_pct": hour.raw.get("humidity_pct") if hour.raw else None,
            "pressure_hpa": hour.raw.get("pressure_hpa") if hour.raw else None,
            "visibility_m": hour.raw.get("visibility_m") if hour.raw else None,
            "weather_code": hour.raw.get("weather_code") if hour.raw else None,
        }

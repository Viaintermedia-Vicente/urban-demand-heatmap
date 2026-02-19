from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy.engine import Engine

from app.domain.canonical import CanonicalWeatherHour
from app.providers.weather.base import ExternalWeatherHour, WeatherProvider
from app.services.weather_upsert import WeatherUpsertService

from .weather_registry import WeatherProviderRegistry


class WeatherHub:
    def __init__(self, registry: WeatherProviderRegistry) -> None:
        self._registry = registry
        self.errors: list[tuple[str, Exception]] = []

    def fetch_all(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        location_name: Optional[str] = None,
    ) -> List[CanonicalWeatherHour]:
        self.errors = []
        combined: List[CanonicalWeatherHour] = []
        for name in self._registry.list():
            provider = self._registry.get(name)
            try:
                hours = provider.fetch_hourly(lat=lat, lon=lon, start=start, end=end, location_name=location_name)
            except Exception as exc:  # pragma: no cover
                self.errors.append((name, exc))
                continue
            combined.extend(self._to_canonical(hours))
        return combined

    def sync(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        session,
        location_name: Optional[str] = None,
    ) -> dict:
        hours = self.fetch_all(lat=lat, lon=lon, start=start, end=end, location_name=location_name)
        engine = self._resolve_engine(session)
        upsert_service = WeatherUpsertService(engine)
        stats = upsert_service.upsert_hours(hours)
        return {
            "providers": self._registry.list(),
            "fetched": len(hours),
            "inserted": stats.get("inserted", 0),
            "updated": stats.get("updated", 0),
            "errors": list(self.errors),
        }

    @staticmethod
    def _to_canonical(payload: list[ExternalWeatherHour]) -> List[CanonicalWeatherHour]:
        canonicals: List[CanonicalWeatherHour] = []
        for hour in payload:
            canonicals.append(
                CanonicalWeatherHour(
                    source=hour.source,
                    lat=hour.lat,
                    lon=hour.lon,
                    observed_at=hour.observed_at,
                    temperature_c=hour.temperature_c,
                    precipitation_mm=hour.precipitation_mm,
                    wind_speed_kmh=hour.wind_speed_kmh,
                    cloud_cover_pct=hour.cloud_cover_pct,
                    raw={
                        "location_name": hour.location_name,
                        "rain_mm": hour.rain_mm,
                        "snowfall_mm": hour.snowfall_mm,
                        "wind_gust_kmh": hour.wind_gust_kmh,
                        "wind_dir_deg": hour.wind_dir_deg,
                        "humidity_pct": hour.humidity_pct,
                        "pressure_hpa": hour.pressure_hpa,
                        "visibility_m": hour.visibility_m,
                        "weather_code": hour.weather_code,
                    },
                )
            )
        return canonicals

    @staticmethod
    def _resolve_engine(session) -> Engine:
        if isinstance(session, Engine):
            return session
        bind = getattr(session, "bind", None)
        if bind is None:
            raise ValueError("session must be an Engine or expose 'bind'")
        return bind

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Protocol


@dataclass
class ExternalWeatherHour:
    source: str
    lat: float
    lon: float
    observed_at: datetime
    location_name: Optional[str] = None
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    snowfall_mm: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_gust_kmh: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    visibility_m: Optional[float] = None
    weather_code: Optional[int] = None


class WeatherProvider(Protocol):
    """Contract for hourly weather providers."""

    def fetch_hourly(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        location_name: Optional[str] = None,
    ) -> list[ExternalWeatherHour]:
        raise NotImplementedError

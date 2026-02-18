from __future__ import annotations

from datetime import date
from typing import Optional

from app.infra.weather.open_meteo_client import OpenMeteoClient

from .base import ExternalWeatherHour, WeatherProvider


class OpenMeteoWeatherProvider(WeatherProvider):
    def __init__(self, client: Optional[OpenMeteoClient] = None):
        self.client = client or OpenMeteoClient()

    def fetch_hourly(
        self,
        *,
        lat: float,
        lon: float,
        start: date,
        end: date,
        location_name: Optional[str] = None,
    ) -> list[ExternalWeatherHour]:
        observations = self.client.fetch_hourly(
            lat,
            lon,
            start.isoformat(),
            end.isoformat(),
            location_name=location_name,
        )
        results: list[ExternalWeatherHour] = []
        for obs in observations:
            results.append(
                ExternalWeatherHour(
                    source=obs.get("source", "open_meteo"),
                    lat=obs["lat"],
                    lon=obs["lon"],
                    observed_at=obs["observed_at"],
                    location_name=obs.get("location_name"),
                    temperature_c=obs.get("temperature_c"),
                    precipitation_mm=obs.get("precipitation_mm"),
                    rain_mm=obs.get("rain_mm"),
                    snowfall_mm=obs.get("snowfall_mm"),
                    cloud_cover_pct=obs.get("cloud_cover_pct"),
                    wind_speed_kmh=obs.get("wind_speed_kmh"),
                    wind_gust_kmh=obs.get("wind_gust_kmh"),
                    wind_dir_deg=obs.get("wind_dir_deg"),
                    humidity_pct=obs.get("humidity_pct"),
                    pressure_hpa=obs.get("pressure_hpa"),
                    visibility_m=obs.get("visibility_m"),
                    weather_code=obs.get("weather_code"),
                )
            )
        return results

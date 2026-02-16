from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import httpx


class OpenMeteoClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    HOURLY_FIELDS = [
        "temperature_2m",
        "precipitation",
        "rain",
        "snowfall",
        "cloudcover",
        "windspeed_10m",
        "windgusts_10m",
        "winddirection_10m",
        "relativehumidity_2m",
        "pressure_msl",
        "visibility",
        "weathercode",
    ]

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def fetch_hourly(
        self,
        lat: float,
        lon: float,
        start_date: str,
        end_date: str,
        *,
        location_name: Optional[str] = None,
    ) -> List[dict]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(self.HOURLY_FIELDS),
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "UTC",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        observations: List[dict] = []
        for idx, ts in enumerate(times):
            observed_at = self._parse_time(ts)
            observations.append(
                {
                    "source": "open_meteo",
                    "location_name": location_name,
                    "lat": lat,
                    "lon": lon,
                    "observed_at": observed_at,
                    "temperature_c": self._get_value(hourly, "temperature_2m", idx),
                    "precipitation_mm": self._get_value(hourly, "precipitation", idx),
                    "rain_mm": self._get_value(hourly, "rain", idx),
                    "snowfall_mm": self._get_value(hourly, "snowfall", idx),
                    "cloud_cover_pct": self._get_value(hourly, "cloudcover", idx),
                    "wind_speed_kmh": self._get_value(hourly, "windspeed_10m", idx),
                    "wind_gust_kmh": self._get_value(hourly, "windgusts_10m", idx),
                    "wind_dir_deg": self._get_value(hourly, "winddirection_10m", idx),
                    "humidity_pct": self._get_value(hourly, "relativehumidity_2m", idx),
                    "pressure_hpa": self._get_value(hourly, "pressure_msl", idx),
                    "visibility_m": self._get_value(hourly, "visibility", idx),
                    "weather_code": self._get_value(hourly, "weathercode", idx, cast=int),
                }
            )
        return observations

    @staticmethod
    def _parse_time(value: str) -> datetime:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        if len(value) == 19:
            value = value + "+00:00"
        return datetime.fromisoformat(value)

    @staticmethod
    def _get_value(hourly: dict, key: str, idx: int, cast=float):
        series = hourly.get(key)
        if series is None:
            return None
        value = series[idx]
        if value is None:
            return None
        return cast(value)

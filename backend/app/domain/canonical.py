
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")


def _to_madrid(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MADRID_TZ)


@dataclass
class CanonicalEvent:
    source: str
    external_id: str
    title: str
    start_at: datetime
    end_at: Optional[datetime] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    venue_name: Optional[str] = None
    venue_external_id: Optional[str] = None
    venue_source: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    url: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    raw: Optional[dict] = None
    _was_naive: bool = field(init=False, repr=False, default=False)

    def __post_init__(self):
        original_start = self.start_at
        self._was_naive = original_start.tzinfo is None
        if not self.source or not self.external_id:
            raise ValueError("source and external_id are required")
        self.start_at = _to_madrid(self.start_at)
        if self.end_at is not None:
            self.end_at = _to_madrid(self.end_at)
        if self.last_synced_at is None:
            self.last_synced_at = datetime.now(MADRID_TZ)
        else:
            self.last_synced_at = _to_madrid(self.last_synced_at)

    @property
    def start(self) -> datetime:
        return self.start_at

    @property
    def end(self) -> Optional[datetime]:
        return self.end_at


@dataclass
class CanonicalWeatherHour:
    source: str
    lat: float
    lon: float
    observed_at: datetime
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    raw: Optional[dict] = None

    def __post_init__(self):
        if not self.source:
            raise ValueError("source is required")
        self.observed_at = _to_madrid(self.observed_at)

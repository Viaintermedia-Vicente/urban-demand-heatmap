from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    category: str
    start_dt: datetime
    end_dt: Optional[datetime]
    lat: float
    lon: float
    source: Optional[str] = None


@dataclass(frozen=True)
class HotspotPoint:
    lat: float
    lon: float
    score: float
    radius_m: Optional[float] = None

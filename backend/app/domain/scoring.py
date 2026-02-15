from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional
import math

from .models import Event, HotspotPoint

# Duraciones estimadas por categoría (horas)
CATEGORY_DURATION_H = {
    "concierto": 2.0,
    "teatro": 2.5,
    "cine": 2.0,
    "feria": 6.0,
    "manifestacion": 3.0,
    "deporte": 3.0,
}

# Radios en metros por categoría
CATEGORY_RADIUS_M = {
    "concierto": 350.0,
    "teatro": 250.0,
    "cine": 200.0,
    "feria": 500.0,
    "manifestacion": 400.0,
    "deporte": 450.0,
}

DEFAULT_DURATION_H = 2.0
DEFAULT_RADIUS_M = 300.0
PRE_WINDOW = timedelta(minutes=60)
POST_WINDOW = timedelta(minutes=60)
# Aproximadamente 0.001 grados ~= 111 m en latitudes medias; sirve para agrupar eventos cercanos
CELL_SIZE_DEG = 0.001


def estimate_end_dt(event: Event) -> datetime:
    if event.end_dt:
        return event.end_dt
    hours = CATEGORY_DURATION_H.get(event.category, DEFAULT_DURATION_H)
    return event.start_dt + timedelta(hours=hours)


def _to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def temporal_weight(event: Event, target: datetime) -> float:
    start = _to_utc_naive(event.start_dt)
    end = _to_utc_naive(estimate_end_dt(event))
    target = _to_utc_naive(target)
    pre_start = start - PRE_WINDOW
    post_end = end + POST_WINDOW

    if target < pre_start or target > post_end:
        return 0.0
    if start <= target <= end:
        return 1.0
    if pre_start <= target < start:
        total = (start - pre_start).total_seconds()
        elapsed = (target - pre_start).total_seconds()
        return max(0.0, min(1.0, elapsed / total))
    # post window
    total = (post_end - end).total_seconds()
    elapsed = (post_end - target).total_seconds()
    return max(0.0, min(1.0, elapsed / total))


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000  # Earth radius meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def spatial_weight(event: Event, lat: float, lon: float) -> float:
    radius = CATEGORY_RADIUS_M.get(event.category, DEFAULT_RADIUS_M)
    distance = _haversine_m(event.lat, event.lon, lat, lon)
    if distance >= radius:
        return 0.0
    return max(0.0, 1.0 - distance / radius)


def event_score(event: Event, target: datetime, lat: float, lon: float) -> float:
    temporal = temporal_weight(event, target)
    if temporal == 0:
        return 0.0
    spatial = spatial_weight(event, lat, lon)
    base_weight = 1.0
    category_boost = {
        "concierto": 1.2,
        "teatro": 1.1,
        "cine": 0.9,
        "feria": 1.3,
    }.get(event.category, 1.0)
    return temporal * spatial * base_weight * category_boost


def compute_hotspots(
    events: Iterable[Event],
    target: datetime,
    categories: Optional[Iterable[str]] = None,
    max_points: int = 20,
) -> List[HotspotPoint]:
    allowed = set(categories) if categories else None
    buckets: dict[tuple[float, float], dict[str, float]] = defaultdict(
        lambda: {"score": 0.0, "lat": 0.0, "lon": 0.0, "count": 0, "radius": DEFAULT_RADIUS_M}
    )

    def quantize(coord: float) -> float:
        return int(coord / CELL_SIZE_DEG) * CELL_SIZE_DEG

    for event in events:
        if allowed and event.category not in allowed:
            continue
        score = event_score(event, target, event.lat, event.lon)
        if score <= 0:
            continue
        key = (quantize(event.lat), quantize(event.lon))
        bucket = buckets[key]
        bucket["score"] += score
        bucket["lat"] += event.lat
        bucket["lon"] += event.lon
        bucket["count"] += 1
        bucket["radius"] = max(bucket["radius"], CATEGORY_RADIUS_M.get(event.category, DEFAULT_RADIUS_M))

    hotspots: List[HotspotPoint] = []
    for key, data in buckets.items():
        count = data["count"] or 1
        hotspots.append(
            HotspotPoint(
                lat=data["lat"] / count,
                lon=data["lon"] / count,
                score=round(data["score"], 4),
                radius_m=data.get("radius", DEFAULT_RADIUS_M),
            )
        )

    hotspots.sort(key=lambda h: h.score, reverse=True)
    return hotspots[:max_points]

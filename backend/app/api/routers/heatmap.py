from __future__ import annotations

import json
import math
import os
from pathlib import Path
from threading import Lock
from datetime import date as date_type, datetime, time, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from app.api.deps import get_engine
from app.domain.models import Event as DomainEvent
from app.domain.scoring import (
    CATEGORY_RADIUS_M,
    CELL_SIZE_DEG,
    DEFAULT_RADIUS_M,
    compute_hotspots,
    event_score,
    weather_factor,
)
from app.infra.db.events_repository import EventsRepository
from app.infra.db.weather_repository import WeatherRepository

router = APIRouter(tags=["heatmap"])

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3]
MODEL_FILENAMES = {
    "lead_time": "model_lead_time.json",
    "attendance_factor": "model_attendance_factor.json",
}
MODEL_CACHE: Dict[str, "LinearModel"] = {}
MODEL_CACHE_LOCK = Lock()


@router.get("/heatmap")
def get_heatmap(
    date: date_type,
    hour: int = Query(..., ge=0, le=23),
    lat: float = Query(40.4168, description="Latitud de referencia"),
    lon: float = Query(-3.7038, description="Longitud de referencia"),
    mode: str = Query("heuristic", pattern="^(heuristic|ml)$"),
    engine: Engine = Depends(get_engine),
):
    repo = EventsRepository(engine)
    weather_repo = WeatherRepository(engine)
    rows = repo.list_events_for_day(date)
    target = datetime.combine(date, time(hour=hour))
    domain_events = [_row_to_domain(row) for row in rows]
    weather_dt = target.replace(tzinfo=timezone.utc)
    weather = weather_repo.get_observation_at(lat, lon, target)
    factor = weather_factor(
        weather.get("temperature_c") if weather else None,
        weather.get("precipitation_mm") if weather else None,
        weather.get("wind_speed_kmh") if weather else None,
    )

    mode = mode.lower()
    if mode == "heuristic":
        hotspots = compute_hotspots(domain_events, target)
        hotspot_payload = [
            {
                "lat": hs.lat,
                "lon": hs.lon,
                "score": round(hs.score * factor, 4),
                "radius_m": hs.radius_m,
                "lead_time_min_pred": None,
                "attendance_factor_pred": None,
            }
            for hs in hotspots
        ]
    else:
        ml_models = _load_ml_models()
        hotspot_payload = _compute_ml_hotspots(
            rows,
            domain_events,
            target,
            lat,
            lon,
            weather,
            ml_models,
        )
        for hs in hotspot_payload:
            hs["score"] = round(hs["score"] * factor, 4)

    return {
        "mode": mode,
        "target": weather_dt.isoformat(),
        "weather": _serialize_weather(weather),
        "hotspots": hotspot_payload,
    }


def _row_to_domain(row: dict) -> DomainEvent:
    return DomainEvent(
        id=str(row["id"]),
        title=row["title"],
        category=row["category"],
        start_dt=row["start_dt"],
        end_dt=row["end_dt"],
        lat=row["lat"],
        lon=row["lon"],
        source=row.get("source"),
    )


def _serialize_weather(obs):
    if not obs:
        return None
    keys = [
        "temperature_c",
        "precipitation_mm",
        "rain_mm",
        "snowfall_mm",
        "cloud_cover_pct",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "wind_dir_deg",
        "humidity_pct",
        "pressure_hpa",
        "visibility_m",
        "weather_code",
    ]
    payload = {k: obs.get(k) for k in keys}
    payload["observed_at"] = obs.get("observed_at").isoformat() if obs.get("observed_at") else None
    payload["source"] = obs.get("source")
    return payload


def _load_ml_models():
    return {
        "lead_time": _get_model("lead_time"),
        "attendance_factor": _get_model("attendance_factor"),
    }


def _get_model(name: str) -> "LinearModel":
    base_dir = _resolve_model_dir()
    cache_key = f"{name}:{base_dir}"
    if cache_key in MODEL_CACHE:
        return MODEL_CACHE[cache_key]
    filename = MODEL_FILENAMES.get(name)
    if not filename:
        raise HTTPException(status_code=500, detail=f"Model '{name}' not configured")
    path = base_dir / filename
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Model file not found: {path}")
    with MODEL_CACHE_LOCK:
        if cache_key in MODEL_CACHE:
            return MODEL_CACHE[cache_key]
        artifact = json.loads(path.read_text())
        MODEL_CACHE[cache_key] = LinearModel(artifact)
        return MODEL_CACHE[cache_key]


def _resolve_model_dir() -> Path:
    env_dir = os.getenv("MODEL_DIR") or os.getenv("HEATMAP_MODEL_DIR")
    base_dir = Path(env_dir) if env_dir else DEFAULT_MODEL_DIR
    return base_dir


WEATHER_FIELDS = [
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
]


def _compute_ml_hotspots(
    rows: List[dict],
    events: List[DomainEvent],
    target: datetime,
    center_lat: float,
    center_lon: float,
    weather: Optional[dict],
    models: Dict[str, "LinearModel"],
    max_points: int = 20,
) -> List[Dict[str, float]]:
    target_naive = _to_utc_naive(target)
    buckets: Dict[Tuple[float, float], Dict[str, float]] = {}
    for row, event in zip(rows, events):
        score = event_score(event, target_naive, event.lat, event.lon)
        if score <= 0:
            continue
        feature_row = _build_feature_row(row, target_naive, center_lat, center_lon, weather)
        lead_pred = _clamp_lead_time(models["lead_time"].predict(feature_row))
        attendance_pred = _clamp_attendance_factor(models["attendance_factor"].predict(feature_row))
        minutes_to_start = _minutes_to_start(row.get("start_dt"), target_naive)
        if minutes_to_start > lead_pred:
            score *= 0.2
        score *= attendance_pred
        if score <= 0:
            continue
        key = _bucket_key(event.lat, event.lon)
        bucket = buckets.setdefault(
            key,
            {
                "score": 0.0,
                "lat_sum": 0.0,
                "lon_sum": 0.0,
                "count": 0,
                "radius": DEFAULT_RADIUS_M,
                "lead_sum": 0.0,
                "attendance_sum": 0.0,
            },
        )
        bucket["score"] += score
        bucket["lat_sum"] += event.lat
        bucket["lon_sum"] += event.lon
        bucket["count"] += 1
        bucket["radius"] = max(bucket["radius"], CATEGORY_RADIUS_M.get(event.category, DEFAULT_RADIUS_M))
        bucket["lead_sum"] += lead_pred
        bucket["attendance_sum"] += attendance_pred

    hotspots: List[Dict[str, float]] = []
    for bucket in buckets.values():
        count = bucket["count"] or 1
        hotspots.append(
            {
                "lat": bucket["lat_sum"] / count,
                "lon": bucket["lon_sum"] / count,
                "score": bucket["score"],
                "radius_m": bucket["radius"],
                "lead_time_min_pred": round(bucket["lead_sum"] / count, 2),
                "attendance_factor_pred": round(bucket["attendance_sum"] / count, 3),
            }
        )
    hotspots.sort(key=lambda item: item["score"], reverse=True)
    return hotspots[:max_points]


def _build_feature_row(row: dict, target: datetime, center_lat: float, center_lon: float, weather: Optional[dict]):
    feature_row = {
        "hour": target.hour,
        "dow": target.weekday(),
        "category": row.get("category") or "unknown",
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "dist_km": _haversine_km(center_lat, center_lon, row.get("lat"), row.get("lon")),
    }
    weather = weather or {}
    for field in WEATHER_FIELDS:
        feature_row[field] = weather.get(field)
    return feature_row


def _bucket_key(lat: float, lon: float) -> Tuple[float, float]:
    def quantize(value: float) -> float:
        return int(value / CELL_SIZE_DEG) * CELL_SIZE_DEG

    return quantize(lat), quantize(lon)


def _minutes_to_start(start_dt: Optional[datetime], target: datetime) -> float:
    if not start_dt:
        return 0.0
    start = _to_utc_naive(start_dt)
    delta = (start - target).total_seconds() / 60.0
    return max(0.0, delta)


def _to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def _clamp_lead_time(value: float) -> float:
    return float(max(15.0, min(120.0, value)))


def _clamp_attendance_factor(value: float) -> float:
    return float(max(0.50, min(1.10, value)))


class LinearModel:
    def __init__(self, artifact: dict):
        self.target_col = artifact.get("target_col", "label")
        self.feature_columns = artifact.get("feature_columns") or []
        self.scales = artifact.get("scales") or [1.0] * len(self.feature_columns)
        self.weights = artifact.get("weights") or [0.0] * len(self.feature_columns)
        self.bias = artifact.get("bias", 0.0)

    def predict(self, feature_row: dict) -> float:
        total = self.bias
        for weight, column, scale in zip(self.weights, self.feature_columns, self.scales):
            if column.startswith("cat_"):
                category = column[4:]
                value = 1.0 if (feature_row.get("category") or "unknown") == category else 0.0
            else:
                raw = feature_row.get(column)
                value = 0.0 if raw in (None, "") else float(raw)
                value = value / scale if scale else value
            total += weight * value
        return total

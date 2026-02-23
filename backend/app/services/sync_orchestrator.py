from __future__ import annotations

from typing import Iterable

from sqlalchemy.engine import Engine

from app.hub.event_hub import EventHub
from app.hub.weather_hub import WeatherHub


class EventSyncRunner:
    def __init__(self, engine: Engine, hub: EventHub):
        self.engine = engine
        self.hub = hub

    def run(self, city: str, past_days: int, future_days: int) -> dict:
        raise NotImplementedError


class WeatherSyncRunner:
    def __init__(self, engine: Engine, hub: WeatherHub):
        self.engine = engine
        self.hub = hub

    def run(self, lat: float, lon: float, past_days: int, future_days: int) -> dict:
        raise NotImplementedError

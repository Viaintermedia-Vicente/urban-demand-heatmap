from __future__ import annotations

import pytest

from app.hub.provider_registry import ProviderRegistry
from app.hub.weather_registry import WeatherProviderRegistry


class DummyProvider:
    def __init__(self, name: str):
        self.name = name


def test_event_registry_register_and_list():
    registry = ProviderRegistry()
    registry.register("events", DummyProvider("a"))
    registry.register("alt", DummyProvider("b"))
    assert registry.list() == ["events", "alt"]


def test_event_registry_get_provider():
    registry = ProviderRegistry()
    provider = DummyProvider("main")
    registry.register("events", provider)
    assert registry.get("events") is provider


def test_event_registry_duplicate_name_raises():
    registry = ProviderRegistry()
    registry.register("events", DummyProvider("dup"))
    with pytest.raises(ValueError):
        registry.register("events", DummyProvider("dup2"))


def test_weather_registry_register_and_get():
    registry = WeatherProviderRegistry()
    provider = DummyProvider("wx")
    registry.register("weather", provider)
    assert registry.get("weather") is provider


def test_weather_registry_list():
    registry = WeatherProviderRegistry()
    registry.register("a", DummyProvider("wx-a"))
    registry.register("b", DummyProvider("wx-b"))
    assert registry.list() == ["a", "b"]

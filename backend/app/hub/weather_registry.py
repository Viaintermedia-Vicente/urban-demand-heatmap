from __future__ import annotations

from typing import Dict, List

from app.providers.weather.base import WeatherProvider


class WeatherProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, WeatherProvider] = {}

    def register(self, name: str, provider: WeatherProvider) -> None:
        if name in self._providers:
            raise ValueError(f"Provider '{name}' already registered")
        self._providers[name] = provider

    def get(self, name: str) -> WeatherProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"Provider '{name}' is not registered") from exc

    def list(self) -> List[str]:
        return list(self._providers.keys())

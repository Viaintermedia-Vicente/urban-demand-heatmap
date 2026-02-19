from __future__ import annotations

from typing import Dict, List

from app.providers.events.base import EventsProvider


class ProviderRegistry:
    """Simple in-memory registry for event providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, EventsProvider] = {}

    def register(self, name: str, provider: EventsProvider) -> None:
        if name in self._providers:
            raise ValueError(f"Provider '{name}' already registered")
        self._providers[name] = provider

    def get(self, name: str) -> EventsProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"Provider '{name}' is not registered") from exc

    def list(self) -> List[str]:
        return list(self._providers.keys())

from __future__ import annotations

from typing import Dict, List, Protocol, TypeVar

T = TypeVar("T")


class ProviderHub:
    def __init__(self):
        self._providers: Dict[str, List[T]] = {}

    def register(self, kind: str, provider: T) -> None:
        raise NotImplementedError

    def list(self, kind: str) -> List[T]:
        raise NotImplementedError

    def get(self, kind: str, name: str) -> T:
        raise NotImplementedError

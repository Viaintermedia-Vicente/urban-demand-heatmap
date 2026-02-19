from __future__ import annotations

import pytest

from app.providers.hub import ProviderHub


class DummyProvider:
    def __init__(self, name: str):
        self.name = name


def test_register_and_list_providers():
    hub = ProviderHub()
    hub.register("events", DummyProvider("a"))
    hub.register("events", DummyProvider("b"))
    providers = hub.list("events")
    assert len(providers) == 2
    assert [p.name for p in providers] == ["a", "b"]


def test_get_provider_by_name():
    hub = ProviderHub()
    provider = DummyProvider("main")
    hub.register("weather", provider)
    assert hub.get("weather", "main") is provider


def test_register_duplicate_name_raises():
    hub = ProviderHub()
    hub.register("weather", DummyProvider("dup"))
    with pytest.raises(ValueError):
        hub.register("weather", DummyProvider("dup"))

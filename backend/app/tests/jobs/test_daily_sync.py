from __future__ import annotations

from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine

from app.jobs import daily_sync as daily_sync_module


class _StubEventHub:
    def __init__(self, calls):
        self.calls = calls

    def sync(self, **kwargs):
        self.calls.append("events")
        return {"providers": ["stub"], "fetched": 0, "inserted": 1, "updated": 0, "errors": []}


class _StubWeatherHub:
    def __init__(self, calls):
        self.calls = calls

    def sync(self, **kwargs):
        self.calls.append("weather")
        return {"providers": ["stub"], "fetched": 0, "inserted": 1, "updated": 0, "errors": []}


def test_daily_sync_calls_hubs_in_order(monkeypatch, tmp_path):
    order: list[str] = []

    monkeypatch.setattr(daily_sync_module, "_build_event_hub", lambda: _StubEventHub(order))
    monkeypatch.setattr(daily_sync_module, "_build_weather_hub", lambda offline_weather=False: _StubWeatherHub(order))

    def fake_materialize(*args, **kwargs):
        order.append("materialize")
        return {"inserted": 0, "updated": 0}

    def fake_export(path, start_date, end_date, engine):
        order.append("export")
        return {"rows": 100}

    trains: list[str] = []

    def fake_train(dataset_path, model_out, target_col):
        trains.append(target_col)
        order.append(f"train:{target_col}")

    monkeypatch.setattr(daily_sync_module, "materialize_range", fake_materialize)
    monkeypatch.setattr(daily_sync_module, "export_training_dataset", fake_export)
    monkeypatch.setattr(daily_sync_module, "train_baseline", fake_train)

    engine = create_engine("sqlite:///:memory:", future=True)
    dataset_path = tmp_path / "dataset.csv"
    model_dir = tmp_path / "models"

    result = daily_sync_module.daily_sync(
        city="Madrid",
        lat=40.4168,
        lon=-3.7038,
        past_days=1,
        future_days=1,
        hours="0-23",
        materialize=True,
        train=True,
        engine=engine,
        dataset_path=dataset_path,
        model_dir=model_dir,
    )

    assert order[:2] == ["events", "weather"]
    assert "materialize" in order
    assert "export" in order
    assert trains == ["label_lead_time_min", "label_attendance_factor"]
    assert result["events"]["inserted"] == 1
    assert result["weather"]["inserted"] == 1


def test_daily_sync_base_date_range(monkeypatch, tmp_path):
    order: list[str] = []

    class _StubHub(_StubEventHub):
        pass

    monkeypatch.setattr(daily_sync_module, "_build_event_hub", lambda: _StubEventHub(order))
    monkeypatch.setattr(daily_sync_module, "_build_weather_hub", lambda offline_weather=False: _StubWeatherHub(order))
    monkeypatch.setattr(daily_sync_module, "materialize_range", lambda *args, **kwargs: {})
    monkeypatch.setattr(daily_sync_module, "export_training_dataset", lambda *args, **kwargs: {"rows": 0})
    monkeypatch.setattr(daily_sync_module, "train_baseline", lambda *args, **kwargs: None)

    engine = create_engine("sqlite:///:memory:", future=True)
    base = "2026-02-10"
    summary = daily_sync_module.daily_sync(
        city="Madrid",
        lat=40.4,
        lon=-3.7,
        past_days=2,
        future_days=3,
        hours="0-23",
        engine=engine,
        base_date=datetime.fromisoformat(base).date(),
    )
    assert summary["start_date"] == "2026-02-08"
    assert summary["end_date"] == "2026-02-13"
    assert summary["base_date"] == base

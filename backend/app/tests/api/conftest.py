from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.deps import get_engine
from app.api.main import create_app
from app.infra.db.tables import metadata
from app.jobs.import_csv import import_events_from_csv


def _build_api_client(tmp_path, monkeypatch, *, create_models: bool):
    db_path = tmp_path / "api_tests.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    metadata.create_all(engine)
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    monkeypatch.delenv("MODEL_DIR", raising=False)
    monkeypatch.delenv("HEATMAP_MODEL_DIR", raising=False)
    if create_models:
        _write_dummy_model(model_dir / "model_lead_time.json", target_col="label_lead_time_min", bias=60)
        _write_dummy_model(
            model_dir / "model_attendance_factor.json",
            target_col="label_attendance_factor",
            bias=0.9,
        )
    monkeypatch.setenv("HEATMAP_MODEL_DIR", str(model_dir))
    app = create_app(engine=engine)
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    metadata.drop_all(engine)


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    yield from _build_api_client(tmp_path, monkeypatch, create_models=True)


@pytest.fixture()
def api_client_no_models(tmp_path, monkeypatch):
    yield from _build_api_client(tmp_path, monkeypatch, create_models=False)


def _write_dummy_model(path: Path, target_col: str, bias: float):
    artifact = {
        "target_col": target_col,
        "feature_columns": ["hour"],
        "scales": [1.0],
        "categories": [],
        "weights": [0.0],
        "bias": bias,
        "metrics": {"mae": 0.0, "rmse": 0.0},
    }
    path.write_text(json.dumps(artifact))

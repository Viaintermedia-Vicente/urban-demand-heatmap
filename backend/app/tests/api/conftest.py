from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api.deps import get_engine
from app.api.main import create_app
from app.infra.db.tables import metadata
from app.jobs.import_csv import import_events_from_csv


@pytest.fixture()
def api_client(tmp_path):
    db_path = tmp_path / "api_tests.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    metadata.create_all(engine)
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=engine)
    app = create_app(engine=engine)
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    metadata.drop_all(engine)

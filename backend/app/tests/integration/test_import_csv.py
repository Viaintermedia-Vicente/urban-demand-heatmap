from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.infra.db.tables import metadata
from app.jobs.import_csv import import_events_from_csv


@pytest.fixture()
def sqlite_engine(tmp_path):
    db_path = tmp_path / "import_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)


def test_csv_import_is_idempotent(sqlite_engine):
    data_dir = Path(__file__).resolve().parents[4] / "data"
    import_events_from_csv(data_dir, engine=sqlite_engine)

    first_counts = _counts(sqlite_engine)
    assert first_counts["venues"] >= 1
    assert first_counts["events"] >= 1

    # Run import again to confirm idempotency
    import_events_from_csv(data_dir, engine=sqlite_engine)
    second_counts = _counts(sqlite_engine)
    assert second_counts == first_counts

    # expected_attendance should be populated and positive
    with sqlite_engine.begin() as conn:
        value = conn.execute(
            text("SELECT MIN(expected_attendance) FROM events")
        ).scalar_one()
        assert value is not None and value > 0


def _counts(engine):
    with engine.begin() as conn:
        venues_total = conn.execute(text("SELECT COUNT(*) FROM venues")).scalar_one()
        events_total = conn.execute(text("SELECT COUNT(*) FROM events")).scalar_one()
    return {"venues": venues_total, "events": events_total}

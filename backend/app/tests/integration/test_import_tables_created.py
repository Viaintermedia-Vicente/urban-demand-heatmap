from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from app.jobs.import_csv import import_events_from_csv


def test_import_creates_sqlite_tables(tmp_path):
    db_path = tmp_path / "tables.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    data_dir = Path(__file__).resolve().parents[4] / "data"

    import_events_from_csv(data_dir, engine=engine)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    table_names = {row[0] for row in rows}
    expected = {"venues", "events", "category_rules"}
    assert expected.issubset(table_names)

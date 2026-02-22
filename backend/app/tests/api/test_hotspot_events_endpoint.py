from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.api.deps import get_engine
from app.api.main import create_app
from app.infra.db.tables import events_table, metadata, venues_table


@pytest.fixture()
def hotspot_client(tmp_path):
    db_path = tmp_path / "hotspot.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    metadata.create_all(engine)
    _seed_events(engine)
    app = create_app(engine=engine)
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    metadata.drop_all(engine)


def _seed_events(engine):
    now = datetime(2026, 2, 18, tzinfo=timezone.utc)
    with engine.begin() as conn:
        v1 = conn.execute(
            insert(venues_table).values(
                source="test",
                external_id="venue-1",
                name="Test Arena",
                lat=40.4168,
                lon=-3.7038,
                city="Madrid",
                region="Madrid",
                country="ES",
                address_line1="Calle 1",
                address_line2=None,
                postal_code="28001",
                max_capacity=None,
                created_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
        v2 = conn.execute(
            insert(venues_table).values(
                source="test",
                external_id="venue-2",
                name="Riverside",
                lat=40.4200,
                lon=-3.7100,
                city="Madrid",
                region="Madrid",
                country="ES",
                address_line1="Calle 2",
                address_line2=None,
                postal_code="28002",
                max_capacity=None,
                created_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
        conn.execute(
            insert(events_table),
            [
                {
                    "source": "test",
                    "external_id": "evt-1",
                    "title": "Morning Show",
                    "category": "music",
                    "subcategory": None,
                    "start_dt": datetime(2026, 3, 1, 20, 0, tzinfo=timezone.utc),
                    "end_dt": datetime(2026, 3, 1, 22, 0, tzinfo=timezone.utc),
                    "timezone": "UTC",
                    "venue_id": v1,
                    "lat": 40.4168,
                    "lon": -3.7038,
                    "status": "confirmed",
                    "url": "https://example.com/evt-1",
                    "expected_attendance": 1000,
                    "popularity_score": 0.5,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "last_synced_at": now,
                },
                {
                    "source": "test",
                    "external_id": "evt-2",
                    "title": "Late Show",
                    "category": "theatre",
                    "subcategory": None,
                    "start_dt": datetime(2026, 3, 1, 19, 0, tzinfo=timezone.utc),
                    "end_dt": datetime(2026, 3, 1, 21, 0, tzinfo=timezone.utc),
                    "timezone": "UTC",
                    "venue_id": v2,
                    "lat": 40.4200,
                    "lon": -3.7100,
                    "status": "confirmed",
                    "url": "https://example.com/evt-2",
                    "expected_attendance": 500,
                    "popularity_score": 0.3,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "last_synced_at": now,
                },
            ],
        )


def test_hotspot_events_returns_empty_when_none(hotspot_client):
    resp = hotspot_client.get(
        "/api/hotspot_events",
        params={
            "date": "2026-03-01",
            "hour": 20,
            "lat": 41.0,
            "lon": -4.0,
            "radius_m": 100,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_hotspot_events_returns_sorted_results(hotspot_client):
    resp = hotspot_client.get(
        "/api/hotspot_events",
        params={
            "date": "2026-03-01",
            "hour": 21,
            "lat": 40.4170,
            "lon": -3.7040,
            "radius_m": 1000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["distance_m"] <= data[1]["distance_m"]
    assert [item["title"] for item in data] == ["Morning Show", "Late Show"]


def test_hotspot_events_validates_inputs(hotspot_client):
    resp = hotspot_client.get(
        "/api/hotspot_events",
        params={
            "date": "2026-03-01",
            "hour": 25,
            "lat": 40.0,
            "lon": -3.7,
        },
    )
    assert resp.status_code == 422
    resp = hotspot_client.get(
        "/api/hotspot_events",
        params={
            "date": "2026-03-01",
            "hour": 20,
            "lat": 40.0,
            "lon": -3.7,
            "radius_m": 0,
        },
    )
    assert resp.status_code == 422

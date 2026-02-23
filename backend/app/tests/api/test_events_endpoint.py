def test_events_endpoint_returns_list(api_client):
    response = api_client.get("/api/events", params={"date": "2026-03-01", "from_hour": 12})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data
    first = data[0]
    assert {"title", "category", "start_dt", "venue_name", "expected_attendance"}.issubset(first.keys())
    assert first["expected_attendance"] is None or first["expected_attendance"] >= 0

def test_heatmap_endpoint_returns_data(api_client):
    response = api_client.get("/api/heatmap", params={"date": "2026-03-01", "hour": 22})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert body.get("hotspots")
    first = body["hotspots"][0]
    assert {"lat", "lon", "score", "radius_m"}.issubset(first.keys())
    assert "weather" in body

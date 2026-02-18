def test_heatmap_endpoint_returns_data(api_client):
    response = api_client.get("/api/heatmap", params={"date": "2026-03-01", "hour": 22})
    assert response.status_code == 200
    body = response.json()
    assert body.get("mode") == "heuristic"
    assert isinstance(body, dict)
    assert body.get("hotspots")
    first = body["hotspots"][0]
    assert {"lat", "lon", "score", "radius_m", "lead_time_min_pred", "attendance_factor_pred"}.issubset(first.keys())
    assert first["lead_time_min_pred"] is None
    assert "weather" in body


def test_heatmap_endpoint_ml_mode_returns_predictions(api_client):
    response = api_client.get(
        "/api/heatmap",
        params={"date": "2026-03-01", "hour": 22, "mode": "ml"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("mode") == "ml"
    assert body.get("hotspots")
    first = body["hotspots"][0]
    assert first["lead_time_min_pred"] is not None
    assert first["attendance_factor_pred"] is not None
    assert "weather" in body


def test_heatmap_endpoint_ml_mode_missing_models_returns_503(api_client_no_models):
    response = api_client_no_models.get(
        "/api/heatmap",
        params={"date": "2026-03-01", "hour": 22, "mode": "ml"},
    )
    assert response.status_code == 503
    body = response.json()
    assert "Model file not found" in body["detail"]


def test_heatmap_endpoint_invalid_mode_returns_422(api_client):
    response = api_client.get(
        "/api/heatmap",
        params={"date": "2026-03-01", "hour": 22, "mode": "invalid"},
    )
    assert response.status_code == 422


def test_food_analysis_success_returns_bounded_estimate(client):
    response = client.post("/v1/food-analysis", json={"food_description": "grilled chicken breast"})

    assert response.status_code == 200
    body = response.json()
    estimate = body["estimate"]

    assert estimate["food_name"] == "grilled chicken breast"
    assert 0 <= estimate["calories"] <= 10_000
    assert 0 <= estimate["protein_grams"] <= 1_000
    assert 0 <= estimate["carbohydrate_grams"] <= 1_000
    assert 0 <= estimate["fat_grams"] <= 1_000
    assert 0 <= estimate["confidence"] <= 1
    assert isinstance(estimate["warnings"], list)


def test_food_analysis_is_deterministic(client):
    payload = {"food_description": "two scrambled eggs"}
    first = client.post("/v1/food-analysis", json=payload).json()
    second = client.post("/v1/food-analysis", json=payload).json()

    assert first == second


def test_food_analysis_rejects_blank_description(client):
    response = client.post("/v1/food-analysis", json={"food_description": "   "})
    assert response.status_code == 422


def test_food_analysis_response_never_exposes_provider_details(client):
    response = client.post("/v1/food-analysis", json={"food_description": "apple"})
    body = response.json()

    serialized = str(body).lower()
    for leaked_term in ("fake", "provider", "copilot", "model"):
        assert leaked_term not in serialized


def test_food_analysis_normalizes_provider_timeout(client):
    response = client.post("/v1/food-analysis", json={"food_description": "__TIMEOUT__ soup"})

    assert response.status_code == 504
    body = response.json()
    assert body["error"]["code"] == "provider_timeout"
    assert "fake" not in str(body).lower()


def test_food_analysis_normalizes_provider_unavailable(client):
    response = client.post("/v1/food-analysis", json={"food_description": "__UNAVAILABLE__ soup"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_unavailable"


def test_food_analysis_rejects_invalid_provider_output(client):
    response = client.post("/v1/food-analysis", json={"food_description": "__INVALID__ soup"})

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "provider_output_invalid"
    assert "fake" not in str(body).lower()

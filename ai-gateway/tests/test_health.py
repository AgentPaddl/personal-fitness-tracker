from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ready(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_healthz_is_public_even_with_no_configuration():
    # /health must remain anonymous and available regardless of app_env or
    # provider configuration; it does not depend on Settings at all.
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

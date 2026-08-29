import azure.functions as func
import httpx

from api.health import health, readiness


def test_health_returns_ok_status():
    req = func.HttpRequest(method="GET", url="/api/health", body=b"")

    response = health(req)

    assert response.status_code == 200
    assert response.get_body() == b'{"status": "ok"}'
    assert response.mimetype == "application/json"


def test_function_app_registers_health_route(monkeypatch):
    import sys

    monkeypatch.setenv("APP_ENV", "development")
    sys.modules.pop("function_app", None)

    import function_app

    assert function_app.app is not None


def test_readiness_returns_ready_when_gateway_readyz_is_200(monkeypatch):
    def _fake_get(url, timeout=None):
        assert url.endswith("/readyz")
        return httpx.Response(200)

    monkeypatch.setattr("api.health.httpx.get", _fake_get)

    req = func.HttpRequest(method="GET", url="/api/readiness", body=b"")
    response = readiness(req)

    assert response.status_code == 200
    assert response.get_body() == b'{"status": "ready"}'


def test_readiness_returns_not_ready_when_gateway_readyz_is_non_200(monkeypatch):
    def _fake_get(url, timeout=None):
        return httpx.Response(503)

    monkeypatch.setattr("api.health.httpx.get", _fake_get)

    req = func.HttpRequest(method="GET", url="/api/readiness", body=b"")
    response = readiness(req)

    assert response.status_code == 503
    assert response.get_body() == b'{"status": "not_ready"}'


def test_readiness_returns_not_ready_when_gateway_is_unreachable(monkeypatch):
    def _fake_get(url, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("api.health.httpx.get", _fake_get)

    req = func.HttpRequest(method="GET", url="/api/readiness", body=b"")
    response = readiness(req)

    assert response.status_code == 503
    assert response.get_body() == b'{"status": "not_ready"}'


def test_readiness_response_never_leaks_gateway_url(monkeypatch):
    def _fake_get(url, timeout=None):
        return httpx.Response(503)

    monkeypatch.setattr("api.health.httpx.get", _fake_get)
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.internal.example")

    req = func.HttpRequest(method="GET", url="/api/readiness", body=b"")
    response = readiness(req)

    assert b"gateway.internal.example" not in response.get_body()

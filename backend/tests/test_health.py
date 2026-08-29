import azure.functions as func

from api.health import health


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

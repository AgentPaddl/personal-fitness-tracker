from fastapi.testclient import TestClient

from app.dependencies import get_provider
from app.main import create_app
from app.providers.base import StructuredGenerationRequest, StructuredGenerationResult, StructuredGenerationProvider


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ready(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_returns_503_when_provider_not_ready(dev_env):
    class _NotReadyProvider(StructuredGenerationProvider):
        async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
            raise NotImplementedError

        async def check_ready(self) -> bool:
            return False

    app = create_app()
    app.dependency_overrides[get_provider] = lambda: _NotReadyProvider()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_not_ready"


def test_healthz_is_public_even_with_no_configuration():
    # /health must remain anonymous and available regardless of app_env or
    # provider configuration; it does not depend on Settings at all.
    response = TestClient(create_app()).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

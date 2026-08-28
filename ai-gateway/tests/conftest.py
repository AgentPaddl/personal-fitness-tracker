import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_provider
from app.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    # Settings/provider are cached with lru_cache; clear between tests so
    # env var overrides in individual tests take effect.
    get_settings.cache_clear()
    get_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_provider.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())

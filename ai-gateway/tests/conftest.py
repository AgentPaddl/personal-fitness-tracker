import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_concurrency_limiter, get_provider
from app.main import create_app


@pytest.fixture(autouse=True)
def _clear_caches():
    # Settings/provider/limiter are cached with lru_cache; clear before and
    # after every test so env var overrides in individual tests take effect
    # and never leak into the next test.
    get_settings.cache_clear()
    get_provider.cache_clear()
    get_concurrency_limiter.cache_clear()
    yield
    get_settings.cache_clear()
    get_provider.cache_clear()
    get_concurrency_limiter.cache_clear()


@pytest.fixture
def dev_env(monkeypatch):
    """Explicit, opt-in development environment for functional tests.

    Nothing in this repo enables this implicitly; every test that needs a
    working gateway must request this fixture (or configure equivalent env
    vars itself), which is the point of finding #1 (fail-closed by default).
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("GATEWAY_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    get_settings.cache_clear()
    get_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_provider.cache_clear()


@pytest.fixture
def client(dev_env) -> TestClient:
    # raise_server_exceptions=False lets tests inspect our normalized error
    # responses instead of Starlette re-raising handled exceptions for
    # server-side logging purposes.
    return TestClient(create_app(), raise_server_exceptions=False)

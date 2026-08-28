"""Smoke test: run the gateway as an independent local process and call it
over a real HTTP connection (not ASGI in-process), proving it can actually
start and serve traffic as a standalone service.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

_GATEWAY_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_ready(base_url: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/healthz", timeout=1.0)
            if response.status_code == 200:
                return
        except httpx.RequestError as exc:
            last_error = exc
        time.sleep(0.1)
    raise TimeoutError(f"Gateway process did not become ready in time: {last_error}")


@pytest.fixture
def running_gateway_process():
    port = _free_port()
    env = {
        **os.environ,
        # Explicit, test-only development configuration for this
        # standalone process; never used outside this smoke test.
        "APP_ENV": "development",
        "GATEWAY_DEV_AUTH_BYPASS": "true",
        "AI_PROVIDER": "fake",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(_GATEWAY_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_ready(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_gateway_process_serves_food_analysis_over_real_http(running_gateway_process):
    base_url = running_gateway_process

    with httpx.Client(base_url=base_url, timeout=5.0) as http_client:
        health_response = http_client.get("/healthz")
        assert health_response.status_code == 200
        assert health_response.json() == {"status": "ok"}

        analysis_response = http_client.post(
            "/v1/food-analysis", json={"food_description": "grilled salmon"}
        )

    assert analysis_response.status_code == 200
    body = analysis_response.json()
    assert "grilled salmon" in body["estimate"]["food_name"]
    assert "fake" not in str(body).lower()

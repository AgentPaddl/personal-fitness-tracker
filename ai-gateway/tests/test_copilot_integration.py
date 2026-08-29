"""Opt-in real GitHub Copilot SDK integration tests.

These tests contact a real Copilot CLI runtime and require local
authentication (see ai-gateway/README.md). They are skipped by default and
must never run in normal CI/local test runs. Enable explicitly with:

    RUN_COPILOT_INTEGRATION_TESTS=1 pytest tests/test_copilot_integration.py

They also require a model-routing configuration, e.g.:

    COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5"}'
"""

from __future__ import annotations

import asyncio
import base64
import os
import struct
import subprocess
import sys
import zlib

import pytest

from app.providers.base import Attachment, GenerationMessage, StructuredGenerationRequest
from app.providers.github_copilot import GitHubCopilotProvider
from tests.test_smoke_process import _GATEWAY_ROOT, _free_port, _wait_until_ready

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_COPILOT_INTEGRATION_TESTS") != "1",
    reason="Opt-in only: set RUN_COPILOT_INTEGRATION_TESTS=1 and authenticate the Copilot CLI locally.",
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "food_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "calories": {"type": "number", "minimum": 0, "maximum": 10_000},
        "protein_grams": {"type": "number", "minimum": 0, "maximum": 1_000},
        "carbohydrate_grams": {"type": "number", "minimum": 0, "maximum": 1_000},
        "fat_grams": {"type": "number", "minimum": 0, "maximum": 1_000},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "food_name",
        "calories",
        "protein_grams",
        "carbohydrate_grams",
        "fat_grams",
        "confidence",
    ],
}


def _model_routes() -> dict[str, str]:
    import json

    raw = os.environ.get("COPILOT_MODEL_ROUTES_JSON", "")
    if not raw:
        pytest.skip("COPILOT_MODEL_ROUTES_JSON is required for the opt-in Copilot integration test.")
    return json.loads(raw)


def test_real_copilot_check_ready():
    async def _run() -> bool:
        provider = GitHubCopilotProvider(model_routes=_model_routes())
        try:
            return await provider.check_ready()
        finally:
            await provider.aclose()

    assert asyncio.run(_run()) is True


def test_real_copilot_food_analysis_german_description():
    async def _run() -> dict:
        provider = GitHubCopilotProvider(model_routes=_model_routes())
        request = StructuredGenerationRequest(
            model_purpose="food_text_v1",
            messages=[
                GenerationMessage(
                    role="system",
                    content=(
                        "You are a nutrition estimation assistant. Given a short food or "
                        "meal description, return a structured nutrition estimate matching "
                        "the requested schema. Values are estimates, not authoritative facts."
                    ),
                ),
                GenerationMessage(
                    role="user",
                    content="Food description: Ein Apfel und eine Scheibe Vollkornbrot mit Butter",
                ),
            ],
            output_json_schema=_SCHEMA,
            timeout_seconds=60.0,
        )
        try:
            result = await provider.generate(request)
        finally:
            await provider.aclose()
        return result.data

    data = asyncio.run(_run())

    assert isinstance(data, dict)
    assert data.get("food_name")


def test_real_local_smoke_backend_to_gateway_to_copilot():
    """The full real local smoke test requested for Phase 3:

    backend GatewayClient -> real HTTP socket -> independent gateway
    process (AI_PROVIDER=copilot) -> GitHubCopilotProvider -> real Copilot
    CLI/model. Uses a German food description. Persists nothing.
    """

    backend_root = _GATEWAY_ROOT.parent / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    from gateway_client import GatewayClient  # noqa: E402  (path set up above)

    routes_json = os.environ.get("COPILOT_MODEL_ROUTES_JSON", "")
    if not routes_json:
        pytest.skip("COPILOT_MODEL_ROUTES_JSON is required for the opt-in Copilot smoke test.")

    port = _free_port()
    env = {
        **os.environ,
        "APP_ENV": "development",
        "GATEWAY_DEV_AUTH_BYPASS": "true",
        "AI_PROVIDER": "copilot",
        "COPILOT_MODEL_ROUTES_JSON": routes_json,
        # Real Copilot calls take tens of seconds (unlike FakeProvider);
        # the gateway's default AI_PROVIDER_TIMEOUT_SECONDS=10 is far too
        # short here and would surface as a false-positive timeout.
        "AI_PROVIDER_TIMEOUT_SECONDS": "90",
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
        _wait_until_ready(base_url, timeout_seconds=30.0)
        client = GatewayClient(base_url=base_url, timeout=100.0)
        try:
            result = client.analyze_food_text("Ein Apfel und eine Scheibe Vollkornbrot mit Butter")
        finally:
            client.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    estimate = result["estimate"]
    assert estimate["food_name"]
    assert "copilot" not in str(result).lower()
    assert "gpt" not in str(result).lower()


def _make_synthetic_png(width: int = 64, height: int = 64) -> bytes:
    """Builds a small, deterministic, non-sensitive test PNG (a solid
    reddish square) using only the stdlib (struct + zlib) - no bundled
    fixture, no user photo, no external dependency.
    """

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw_row = b"\x00" + bytes((200, 60, 40) * width)  # filter byte 0 + RGB pixels
    raw = raw_row * height
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def _image_model_routes() -> dict[str, str]:
    routes = _model_routes()
    if "food_image_v1" not in routes:
        pytest.skip(
            "COPILOT_MODEL_ROUTES_JSON must include a 'food_image_v1' route for the opt-in image test."
        )
    return routes


def test_real_copilot_check_ready_includes_vision_capable_image_route():
    async def _run() -> bool:
        routes = _image_model_routes()
        provider = GitHubCopilotProvider(model_routes=routes, vision_required_purposes=frozenset({"food_image_v1"}))
        try:
            return await provider.check_ready()
        finally:
            await provider.aclose()

    # Fails (rather than silently proceeding) if the configured image
    # model does not report vision support via the SDK's own capabilities.
    assert asyncio.run(_run()) is True


def test_real_copilot_image_analysis_synthetic_food_like_photo():
    async def _run() -> dict:
        routes = _image_model_routes()
        provider = GitHubCopilotProvider(model_routes=routes)
        image_base64 = base64.b64encode(_make_synthetic_png()).decode("ascii")
        request = StructuredGenerationRequest(
            model_purpose="food_image_v1",
            messages=[
                GenerationMessage(
                    role="system",
                    content=(
                        "You are a nutrition estimation assistant. Given a photo of food, "
                        "visually estimate the food and its portion size, and return a "
                        "structured nutrition estimate matching the requested schema."
                    ),
                ),
                GenerationMessage(
                    role="user",
                    content="A photo of the food is attached. Estimate the food and its portion from the image alone.",
                ),
            ],
            output_json_schema=_SCHEMA,
            timeout_seconds=90.0,
            attachments=[Attachment(kind="image", media_type="image/png", data=image_base64)],
        )
        try:
            result = await provider.generate(request)
        finally:
            await provider.aclose()
        return result.data

    data = asyncio.run(_run())

    assert isinstance(data, dict)
    assert data.get("food_name")

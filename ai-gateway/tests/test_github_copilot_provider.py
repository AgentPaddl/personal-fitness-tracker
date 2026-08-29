"""Unit tests for GitHubCopilotProvider using a fake SDK client.

These tests never import a real CopilotClient connection: `CopilotClient` is
monkeypatched with an in-test fake, so no Copilot CLI process is spawned and
no credentials are required. Real/Tool/ToolResult classes from the SDK are
used as-is since they are plain data structures with no I/O.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from copilot.session_events import ModelCallFailureData, ModelCallFailureKind, SessionErrorData
from copilot.tools import ToolResult

from app.errors import (
    ModelUnavailableError,
    ProviderAuthenticationError,
    ProviderOutputInvalidError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RequestValidationFailedError,
)
from app.providers import github_copilot as gc_module
from app.providers.base import Attachment, GenerationMessage, StructuredGenerationRequest
from app.providers.github_copilot import GitHubCopilotProvider

_SCHEMA = {
    "type": "object",
    "properties": {
        "food_name": {"type": "string", "minLength": 1},
        "calories": {"type": "number", "minimum": 0, "maximum": 10_000},
    },
    "required": ["food_name", "calories"],
}


def _request(model_purpose: str = "food_text_v1", timeout_seconds: float = 5.0) -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        model_purpose=model_purpose,
        messages=[
            GenerationMessage(role="system", content="You analyze food."),
            GenerationMessage(role="user", content="Food description: apple"),
        ],
        output_json_schema=_SCHEMA,
        timeout_seconds=timeout_seconds,
    )


class _FakeSession:
    def __init__(
        self,
        tools: list[Any],
        on_send: Callable[["_FakeSession", float], Any],
        disconnect_exc: Exception | None = None,
    ):
        self.tools = tools
        self._on_send = on_send
        self._disconnect_exc = disconnect_exc
        self._handler: Callable[[Any], None] | None = None
        self.disconnected = False
        self.disconnect_attempted = False

    def on(self, handler: Callable[[Any], None]) -> Callable[[], None]:
        self._handler = handler
        return lambda: None

    def emit(self, data: Any) -> None:
        assert self._handler is not None, "no event handler registered"
        self._handler(SimpleNamespace(data=data))

    async def send_and_wait(self, prompt: str, *, attachments: Any = None, timeout: float) -> None:
        self.last_prompt = prompt
        self.last_attachments = attachments
        await self._on_send(self, timeout)

    async def disconnect(self) -> None:
        self.disconnect_attempted = True
        if self._disconnect_exc is not None:
            raise self._disconnect_exc
        self.disconnected = True


class _FakeClient:
    """Stand-in for CopilotClient; captures calls for assertions."""

    def __init__(
        self,
        on_send: Callable[[_FakeSession, float], Any],
        *,
        is_authenticated: bool = True,
        model_ids: tuple[str, ...] = ("gpt-5",),
        vision_model_ids: frozenset[str] = frozenset(),
        disconnect_exc: Exception | None = None,
    ):
        self._on_send = on_send
        self._is_authenticated = is_authenticated
        self._model_ids = model_ids
        self._vision_model_ids = vision_model_ids
        self._disconnect_exc = disconnect_exc
        self.started = False
        self.stopped = False
        self.last_create_session_kwargs: dict[str, Any] | None = None
        self.last_session: _FakeSession | None = None

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def create_session(self, **kwargs: Any) -> _FakeSession:
        self.last_create_session_kwargs = kwargs
        session = _FakeSession(kwargs["tools"], self._on_send, disconnect_exc=self._disconnect_exc)
        self.last_session = session
        return session

    async def get_auth_status(self) -> SimpleNamespace:
        return SimpleNamespace(isAuthenticated=self._is_authenticated)

    async def list_models(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                id=model_id,
                capabilities=SimpleNamespace(supports=SimpleNamespace(vision=model_id in self._vision_model_ids)),
            )
            for model_id in self._model_ids
        ]


def _install_fake_client(monkeypatch, client: _FakeClient) -> None:
    monkeypatch.setattr(gc_module, "CopilotClient", lambda **kwargs: client)


def _provider(model_routes: dict[str, str] | None = None) -> GitHubCopilotProvider:
    return GitHubCopilotProvider(model_routes=model_routes or {"food_text_v1": "gpt-5"})


async def _call_submit_tool(session: _FakeSession, arguments: dict[str, Any]) -> ToolResult:
    tool = session.tools[0]
    invocation = SimpleNamespace(arguments=arguments)
    return await tool.handler(invocation)


def test_generic_request_is_translated_to_session_and_prompt(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    provider = _provider()
    result = asyncio.run(provider.generate(_request()))

    assert result.data == {"food_name": "apple", "calories": 95}
    assert client.last_create_session_kwargs["model"] == "gpt-5"
    assert "apple" in client.last_session.last_prompt
    # Provider stays domain-blind: it must not embed any "food"-specific
    # wording of its own, only forward what the request already contained.
    system_message = client.last_create_session_kwargs["system_message"]["content"]
    assert "You analyze food." in system_message
    assert "submit_structured_result" in system_message


def test_model_routing_resolves_purpose_to_configured_model(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    provider = _provider({"food_text_v1": "gpt-5", "other_purpose": "claude-sonnet-4.5"})
    asyncio.run(provider.generate(_request(model_purpose="other_purpose")))

    assert client.last_create_session_kwargs["model"] == "claude-sonnet-4.5"


def test_unconfigured_purpose_never_substitutes_a_model(monkeypatch):
    client = _FakeClient(lambda session, timeout: None)
    _install_fake_client(monkeypatch, client)

    provider = _provider({"food_text_v1": "gpt-5"})

    with pytest.raises(ModelUnavailableError):
        asyncio.run(provider.generate(_request(model_purpose="unknown_purpose")))

    assert client.last_create_session_kwargs is None


def test_tool_schema_matches_requested_output_schema(monkeypatch):
    captured = {}

    async def on_send(session, timeout):
        captured["schema"] = session.tools[0].parameters
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    asyncio.run(_provider().generate(_request()))

    assert captured["schema"] == _SCHEMA


def test_valid_structured_result_is_returned(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "banana", "calories": 105})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    result = asyncio.run(_provider().generate(_request()))

    assert result.data == {"food_name": "banana", "calories": 105}
    assert client.last_session.disconnected is True


def test_missing_tool_call_is_invalid_structured_output(monkeypatch):
    async def on_send(session, timeout):
        return None  # model answered in prose instead of calling the tool

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderOutputInvalidError):
        asyncio.run(_provider().generate(_request()))

    assert client.last_session.disconnected is True


def test_timeout_is_normalized(monkeypatch):
    async def on_send(session, timeout):
        raise TimeoutError("send_and_wait timed out")

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(_provider().generate(_request()))

    assert client.last_session.disconnected is True


def test_authentication_failure_is_normalized(monkeypatch):
    async def on_send(session, timeout):
        session.emit(
            SessionErrorData(error_type="authentication_error", message="bad credentials", status_code=401)
        )

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderAuthenticationError) as excinfo:
        asyncio.run(_provider().generate(_request()))

    assert "bad credentials" not in str(excinfo.value)


def test_rate_limit_is_normalized(monkeypatch):
    async def on_send(session, timeout):
        session.emit(
            ModelCallFailureData(
                source="model",
                status_code=429,
                error_type="rate_limited",
                error_message="quota exceeded",
                failure_kind=ModelCallFailureKind.API,
            )
        )

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderRateLimitedError):
        asyncio.run(_provider().generate(_request()))


def test_unavailable_runtime_is_normalized(monkeypatch):
    async def on_send(session, timeout):
        raise RuntimeError("the CLI process crashed unexpectedly")

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderUnavailableError) as excinfo:
        asyncio.run(_provider().generate(_request()))

    assert "crashed" not in str(excinfo.value)


def test_exceptions_never_leak_raw_sdk_detail(monkeypatch):
    async def on_send(session, timeout):
        raise RuntimeError("secret internal trace ABC123")

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderUnavailableError) as excinfo:
        asyncio.run(_provider().generate(_request()))

    assert "ABC123" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value)


def test_session_is_disconnected_even_on_failure(monkeypatch):
    async def on_send(session, timeout):
        raise RuntimeError("boom")

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(_provider().generate(_request()))

    assert client.last_session.disconnected is True


def test_disconnect_failure_after_success_still_returns_the_result(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send, disconnect_exc=RuntimeError("disconnect boom"))
    _install_fake_client(monkeypatch, client)

    # The cleanup failure must not mask the successful result.
    result = asyncio.run(_provider().generate(_request()))

    assert result.data == {"food_name": "apple", "calories": 95}
    assert client.last_session.disconnect_attempted is True
    assert client.last_session.disconnected is False


def test_disconnect_failure_does_not_mask_an_already_raised_provider_error(monkeypatch):
    async def on_send(session, timeout):
        raise RuntimeError("original failure")

    client = _FakeClient(on_send, disconnect_exc=RuntimeError("disconnect boom too"))
    _install_fake_client(monkeypatch, client)

    # The original, normalized error must surface, not the disconnect
    # failure and not a raw SDK exception.
    with pytest.raises(ProviderUnavailableError) as excinfo:
        asyncio.run(_provider().generate(_request()))

    assert "disconnect boom too" not in str(excinfo.value)
    assert "original failure" not in str(excinfo.value)
    assert client.last_session.disconnect_attempted is True


def test_client_is_reused_across_generate_calls(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    created_clients: list[_FakeClient] = []

    def factory(**kwargs):
        client = _FakeClient(on_send)
        created_clients.append(client)
        return client

    monkeypatch.setattr(gc_module, "CopilotClient", factory)

    provider = _provider()
    asyncio.run(provider.generate(_request()))
    asyncio.run(provider.generate(_request()))

    assert len(created_clients) == 1
    assert created_clients[0].started is True


def test_aclose_stops_the_underlying_client(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    provider = _provider()
    asyncio.run(provider.generate(_request()))
    asyncio.run(provider.aclose())

    assert client.stopped is True


def test_check_ready_false_when_not_authenticated(monkeypatch):
    client = _FakeClient(lambda session, timeout: None, is_authenticated=False)
    _install_fake_client(monkeypatch, client)

    assert asyncio.run(_provider().check_ready()) is False


def test_check_ready_false_when_configured_model_missing(monkeypatch):
    client = _FakeClient(lambda session, timeout: None, model_ids=("claude-sonnet-4.5",))
    _install_fake_client(monkeypatch, client)

    assert asyncio.run(_provider({"food_text_v1": "gpt-5"}).check_ready()) is False


def test_check_ready_true_when_authenticated_and_model_available(monkeypatch):
    client = _FakeClient(lambda session, timeout: None, model_ids=("gpt-5",))
    _install_fake_client(monkeypatch, client)

    assert asyncio.run(_provider({"food_text_v1": "gpt-5"}).check_ready()) is True


def _request_with_attachments(attachments: list[Attachment]) -> StructuredGenerationRequest:
    request = _request()
    return StructuredGenerationRequest(
        model_purpose=request.model_purpose,
        messages=request.messages,
        output_json_schema=request.output_json_schema,
        timeout_seconds=request.timeout_seconds,
        attachments=attachments,
    )


def test_image_attachment_is_translated_to_sdk_blob_attachment(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    request = _request_with_attachments([Attachment(kind="image", media_type="image/jpeg", data="YmFzZTY0")])
    asyncio.run(_provider().generate(request))

    assert client.last_session.last_attachments == [
        {"type": "blob", "data": "YmFzZTY0", "mimeType": "image/jpeg"}
    ]


def test_no_attachments_passes_none_to_sdk(monkeypatch):
    async def on_send(session, timeout):
        await _call_submit_tool(session, {"food_name": "apple", "calories": 95})

    client = _FakeClient(on_send)
    _install_fake_client(monkeypatch, client)

    asyncio.run(_provider().generate(_request()))

    assert client.last_session.last_attachments is None


def test_unsupported_attachment_kind_is_rejected(monkeypatch):
    client = _FakeClient(lambda session, timeout: None)
    _install_fake_client(monkeypatch, client)

    request = _request_with_attachments([Attachment(kind="video", media_type="video/mp4", data="abc")])

    with pytest.raises(RequestValidationFailedError):
        asyncio.run(_provider().generate(request))

    # Rejected before ever creating a session/spending a model call.
    assert client.last_create_session_kwargs is None


def test_empty_attachment_payload_is_rejected(monkeypatch):
    client = _FakeClient(lambda session, timeout: None)
    _install_fake_client(monkeypatch, client)

    request = _request_with_attachments([Attachment(kind="image", media_type="image/jpeg", data="")])

    with pytest.raises(RequestValidationFailedError):
        asyncio.run(_provider().generate(request))


def test_check_ready_false_when_required_vision_model_lacks_vision_support(monkeypatch):
    client = _FakeClient(
        lambda session, timeout: None,
        model_ids=("gpt-5-mini",),
        vision_model_ids=frozenset(),  # gpt-5-mini not reported as vision-capable
    )
    _install_fake_client(monkeypatch, client)

    provider = GitHubCopilotProvider(
        model_routes={"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"},
        vision_required_purposes=frozenset({"food_image_v1"}),
    )

    assert asyncio.run(provider.check_ready()) is False


def test_check_ready_true_when_required_vision_model_supports_vision(monkeypatch):
    client = _FakeClient(
        lambda session, timeout: None,
        model_ids=("gpt-5-mini",),
        vision_model_ids=frozenset({"gpt-5-mini"}),
    )
    _install_fake_client(monkeypatch, client)

    provider = GitHubCopilotProvider(
        model_routes={"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"},
        vision_required_purposes=frozenset({"food_image_v1"}),
    )

    assert asyncio.run(provider.check_ready()) is True

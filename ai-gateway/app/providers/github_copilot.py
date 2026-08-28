"""GitHubCopilotProvider: the first real StructuredGenerationProvider adapter.

This adapter wraps the official GitHub Copilot SDK for Python
(``github-copilot-sdk``, package import name ``copilot``), which drives the
Copilot CLI in headless/server mode over JSON-RPC. It is intentionally
domain-blind: it only understands generic generation messages, an opaque
``model_purpose`` routing key, a JSON output schema, attachments, and a
timeout. It has no knowledge of "food", nutrition fields, or any other
domain concept - that all lives in the calling use case.

Structured output strategy: this adapter defines a single terminal tool,
``submit_structured_result``, whose parameter schema is exactly the
request's ``output_json_schema``. The session's system message instructs
the model to answer only by calling that tool. ``is_terminal=True`` means a
successful call ends the agent turn immediately (see the SDK's ``Tool``
docstring); a failed/never-called tool is treated as invalid output. The
returned arguments are still passed back untyped - the calling use case is
solely responsible for authoritative Pydantic validation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.session_events import ModelCallFailureData, SessionErrorData
from copilot.tools import Tool, ToolInvocation, ToolResult

from app.errors import (
    GatewayError,
    ModelUnavailableError,
    ProviderAuthenticationError,
    ProviderOutputInvalidError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.base import (
    StructuredGenerationProvider,
    StructuredGenerationRequest,
    StructuredGenerationResult,
)

_SUBMIT_TOOL_NAME = "submit_structured_result"
_SUBMIT_TOOL_DESCRIPTION = (
    "Submit the final structured result. Call this exactly once, with "
    "arguments matching the required schema, instead of answering in prose."
)
_SYSTEM_INSTRUCTIONS_SUFFIX = (
    "\n\nYou must respond only by calling the "
    f"'{_SUBMIT_TOOL_NAME}' tool exactly once with the complete result. "
    "Do not write any other reply."
)


class GitHubCopilotProvider(StructuredGenerationProvider):
    """Adapter around the official GitHub Copilot SDK (``copilot`` package)."""

    def __init__(self, model_routes: dict[str, str], github_token: str | None = None):
        self._model_routes = model_routes
        self._github_token = github_token
        self._client: CopilotClient | None = None
        self._start_lock = asyncio.Lock()

    async def _ensure_client(self) -> CopilotClient:
        # Reuses one long-lived CLI process/connection across requests
        # instead of spawning a fresh one per generation call.
        if self._client is not None:
            return self._client
        async with self._start_lock:
            if self._client is None:
                client = CopilotClient(github_token=self._github_token)
                try:
                    await client.start()
                except Exception as exc:
                    raise _normalize_sdk_exception(exc) from exc
                self._client = client
            return self._client

    def _resolve_model(self, model_purpose: str) -> str:
        try:
            return self._model_routes[model_purpose]
        except KeyError as exc:
            # Never silently substitute another model.
            raise ModelUnavailableError() from exc

    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        model = self._resolve_model(request.model_purpose)
        client = await self._ensure_client()

        system_content = "\n".join(m.content for m in request.messages if m.role == "system")
        user_content = "\n".join(m.content for m in request.messages if m.role == "user")

        result_holder: dict[str, Any] = {}
        failure_holder: dict[str, GatewayError] = {}

        async def _submit_handler(invocation: ToolInvocation) -> ToolResult:
            result_holder["data"] = invocation.arguments
            return ToolResult(result_type="success", text_result_for_llm="Result recorded.")

        submit_tool = Tool(
            name=_SUBMIT_TOOL_NAME,
            description=_SUBMIT_TOOL_DESCRIPTION,
            parameters=request.output_json_schema,
            handler=_submit_handler,
            is_terminal=True,
            skip_permission=True,
        )

        def _on_event(event: Any) -> None:
            data = event.data
            if isinstance(data, SessionErrorData):
                failure_holder.setdefault(
                    "error", _classify_failure(data.status_code, data.error_type, data.message)
                )
            elif isinstance(data, ModelCallFailureData):
                failure_kind = data.failure_kind.value if data.failure_kind else None
                failure_holder.setdefault(
                    "error",
                    _classify_failure(data.status_code, data.error_type or failure_kind, data.error_message),
                )

        try:
            session = await client.create_session(
                model=model,
                on_permission_request=PermissionHandler.approve_all,
                tools=[submit_tool],
                # Whitelist only our terminal tool. Passing an empty list here
                # (instead of omitting the argument) hides *all* tools,
                # including custom ones - not just built-ins - which leaves
                # the model with nothing to call and it falls back to a
                # prose reply. Naming our own tool keeps built-in shell/file
                # tools disabled while still exposing the one tool we need.
                available_tools=[_SUBMIT_TOOL_NAME],
                system_message={"mode": "append", "content": system_content + _SYSTEM_INSTRUCTIONS_SUFFIX}
                if system_content
                else {"mode": "append", "content": _SYSTEM_INSTRUCTIONS_SUFFIX},
            )
        except Exception as exc:
            raise _normalize_sdk_exception(exc) from exc

        try:
            session.on(_on_event)
            try:
                await session.send_and_wait(user_content, timeout=request.timeout_seconds)
            except TimeoutError as exc:
                raise ProviderTimeoutError() from exc
            except Exception as exc:
                raise _normalize_sdk_exception(exc) from exc

            if "error" in failure_holder:
                raise failure_holder["error"]
            if "data" not in result_holder or not isinstance(result_holder["data"], dict):
                # The model never called the terminal tool with usable
                # arguments; treat as invalid structured output, not trusted
                # application data.
                raise ProviderOutputInvalidError()

            return StructuredGenerationResult(data=result_holder["data"])
        finally:
            await session.disconnect()

    async def check_ready(self) -> bool:
        # Metadata-only calls (auth status, model list); never a billed
        # generation request.
        try:
            client = await self._ensure_client()
            auth_status = await client.get_auth_status()
            if not auth_status.isAuthenticated:
                return False
            models = await client.list_models()
            available_ids = {model.id for model in models}
            return all(model_id in available_ids for model_id in self._model_routes.values())
        except Exception:
            return False

    async def aclose(self) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            await client.stop()


def _classify_failure(status_code: int | None, error_type: str | None, message: str | None) -> GatewayError:
    """Map the SDK's own status_code/error_type/message onto a normalized error.

    Based on the real fields exposed by ``SessionErrorData`` and
    ``ModelCallFailureData`` in github-copilot-sdk 1.0.11.
    """

    haystack = " ".join(part.lower() for part in (error_type, message) if part)

    if status_code in (401, 403) or "auth" in haystack or "unauthorized" in haystack or "forbidden" in haystack:
        return ProviderAuthenticationError()
    if status_code == 429 or "rate" in haystack or "quota" in haystack:
        return ProviderRateLimitedError()
    if "model" in haystack and any(term in haystack for term in ("not found", "unavailable", "unsupported")):
        return ModelUnavailableError()
    if status_code == 408 or "timeout" in haystack or "timed out" in haystack:
        return ProviderTimeoutError()
    return ProviderUnavailableError()


def _normalize_sdk_exception(exc: Exception) -> GatewayError:
    """Final normalization boundary for any raw SDK/transport exception."""

    if isinstance(exc, GatewayError):
        return exc
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if not isinstance(status_code, int):
        status_code = None
    return _classify_failure(status_code, type(exc).__name__, str(exc))

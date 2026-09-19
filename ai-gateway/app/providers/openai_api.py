"""Local Azure v1 adapter with a single stateless, bounded SDK request."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import httpx2
from jsonschema import Draft202012Validator, FormatChecker
from openai import APIStatusError, APITimeoutError, AsyncOpenAI

from app.errors import (
    GatewayError, ModelUnavailableError, ProviderAuthenticationError,
    ProviderOutputInvalidError, ProviderRateLimitedError, ProviderTimeoutError,
    ProviderUnavailableError, ServiceNotReadyError,
)
from app.providers.base import (
    GenerationMetadata, StructuredGenerationProvider, StructuredGenerationRequest,
    StructuredGenerationResult, TokenUsage,
)
from app.providers.pricing import PriceTable, resolve_profiles
from app.providers.strict_schema import to_strict_schema

logger = logging.getLogger("app.generation")
diagnostic_logger = logging.getLogger("app.pilot.events.provider")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")


def validate_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or not parsed.hostname.endswith((".openai.azure.com", ".services.ai.azure.com"))
        or parsed.username or parsed.password or parsed.port not in (None, 443)
        or parsed.query or parsed.fragment or parsed.path not in ("", "/", "/openai/v1", "/openai/v1/")
    ):
        raise ValueError("AZURE_OPENAI_ENDPOINT must be an Azure HTTPS resource endpoint.")
    return f"https://{parsed.hostname}/openai/v1/"


def _identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


def _integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _response_diagnostics(status_code: int, headers: Mapping[str, str]) -> dict[str, str | int]:
    result: dict[str, str | int] = {"http_status": status_code}
    for name in ("x-request-id", "apim-request-id", "x-ms-request-id"):
        value = headers.get(name, "")
        if re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}"
                r"|req_[A-Za-z0-9_-]{1,96}", value):
            result[name] = value
    for name in ("retry-after-ms", "x-ms-retry-after-ms", "x-ratelimit-limit-requests",
                 "x-ratelimit-limit-tokens", "x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens"):
        value = headers.get(name, "")
        if re.fullmatch(r"[0-9]{1,9}", value):
            result[name] = int(value)
    for name in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        value = headers.get(name, "")
        if len(value) <= 32 and re.fullmatch(r"(?:[0-9]{1,6}(?:\.[0-9]{1,3})?(?:ms|s|m|h)){1,4}"
                            r"|[0-9]{1,9}(?:\.[0-9]{1,3})?", value):
            result[name] = value
    retry_after = headers.get("retry-after", "")
    if re.fullmatch(r"[0-9]{1,8}", retry_after):
        result["retry-after-seconds"] = int(retry_after)
    elif len(retry_after) <= 64:
        try:
            deadline = parsedate_to_datetime(retry_after)
            if deadline.tzinfo is not None:
                delay = math.ceil(deadline.timestamp() - time.time())
                if 0 <= delay <= 86400:
                    result["retry-after-seconds"] = delay
        except (ValueError, TypeError, OverflowError):
            pass
    return result


def _usage(response: Any) -> TokenUsage | None:
    usage = response.get("usage") if isinstance(response, dict) else None
    if not isinstance(usage, dict):
        return None
    prompt = _integer(usage.get("prompt_tokens"))
    completion = _integer(usage.get("completion_tokens"))
    if prompt is None or completion is None:
        return None
    total = usage.get("total_tokens")
    if total is not None and (_integer(total) is None or total != prompt + completion):
        return None
    prompt_details, completion_details = usage.get("prompt_tokens_details"), usage.get("completion_tokens_details")
    cached_raw = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
    reasoning_raw = completion_details.get("reasoning_tokens") if isinstance(completion_details, dict) else None
    cached, reasoning = _integer(cached_raw), _integer(reasoning_raw)
    if (cached_raw is not None and cached is None) or (reasoning_raw is not None and reasoning is None):
        return None
    if (cached is not None and cached > prompt) or (reasoning is not None and reasoning > completion):
        return None
    return TokenUsage(prompt, completion, cached, reasoning)


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON property.")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number.")
    return number


def _invalid_constant(value: str) -> None:
    raise ValueError("Non-JSON numeric constant.")


class AzureOpenAIProvider(StructuredGenerationProvider):
    def __init__(
        self, *, endpoint: str, api_key: str | None = None, model_routes: dict[str, str],
        max_output_tokens: int = 2000, prices: PriceTable | None = None,
        profile_bindings: dict[str, str] | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
        token_provider: Callable[[], Awaitable[str]] | None = None,
        dispatch_guard: Callable[[], None] | None = None,
    ):
        base_url = validate_endpoint(endpoint)
        if ((token_provider is None and (not isinstance(api_key, str) or not api_key.strip()))
                or token_provider is not None and (api_key is not None or dispatch_guard is None)):
            raise ValueError("Exactly one credential source and an Entra dispatch guard are required.")
        if not model_routes or any(
            not _identifier(purpose) or not _identifier(deployment)
            for purpose, deployment in model_routes.items()
        ):
            raise ValueError("Explicit credentials and valid deployment routes are required.")
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768:
            raise ValueError("Output token limit must be between 1 and 32768.")
        self._profile_bindings = dict(profile_bindings or {})
        self._profiles = resolve_profiles(self._profile_bindings, model_routes, prices, max_output_tokens)
        self._dispatch_guard = dispatch_guard
        self._entra = token_provider is not None
        logging.getLogger("openai._base_client").disabled = True
        self._client = AsyncOpenAI(
            api_key=token_provider if token_provider is not None else api_key, base_url=base_url, max_retries=0,
            organization="", project="",
            http_client=httpx2.AsyncClient(
                transport=transport, follow_redirects=False, trust_env=False,
            ),
        )
        self._routes = dict(model_routes)
        self._max_output_tokens = max_output_tokens
        self._prices = prices.model_copy(deep=True) if prices else None

    async def check_ready(self) -> bool:
        return False

    async def aclose(self) -> None:
        try:
            await asyncio.wait_for(self._client.close(), timeout=1.0)
        except Exception:
            return

    async def generate(self, request: StructuredGenerationRequest) -> StructuredGenerationResult:
        started = time.perf_counter()
        deployment = self._routes.get(request.model_purpose)
        response = None
        accounting = None
        request_id = None
        diagnostics = None
        status = "invalid_request"
        try:
            if os.environ.get("APP_ENV", "production") not in {"development", "test"}:
                from app.config import get_settings
                from app.pilot_release import is_api_artifact, validate_release

                status = "disabled"
                if not is_api_artifact() or not self._entra:
                    raise ServiceNotReadyError()
                try:
                    validate_release(get_settings())
                except Exception:
                    raise ServiceNotReadyError() from None
            from app.pilot import consume_permit, enabled

            profiles = resolve_profiles(self._profile_bindings, self._routes, self._prices, self._max_output_tokens)
            profile = profiles.get(deployment)
            if deployment is None:
                status = "model_unavailable"
                raise ModelUnavailableError()
            limit = request.max_output_tokens
            if limit is not None and (type(limit) is not int or limit < 1):
                raise ProviderOutputInvalidError()
            if not math.isfinite(request.timeout_seconds) or request.timeout_seconds <= 0:
                raise ProviderOutputInvalidError()
            effective_limit = min(limit or self._max_output_tokens, self._max_output_tokens)
            if self._entra:
                if not enabled() or profile is None:
                    raise ServiceNotReadyError()
                self._dispatch_guard()
            if enabled():
                consume_permit(request, deployment=deployment, profile_id=profile.identifier if profile else None,
                               max_output_tokens=effective_limit,
                               price_version=self._prices.version if self._prices else None)
            strict = to_strict_schema(request.output_json_schema)
            Draft202012Validator.check_schema(request.output_json_schema)
            validator = Draft202012Validator(request.output_json_schema, format_checker=FormatChecker())
            strict_validator = Draft202012Validator(strict)
            messages = self._messages(request, profile.image_detail if profile else None)
            parameters = {"reasoning_effort": profile.reasoning_effort, "service_tier": profile.service_tier} if profile else {}
            status = "unavailable"
            async with asyncio.timeout(request.timeout_seconds):
                raw = await self._client.chat.completions.with_raw_response.create(
                    model=deployment, messages=messages, store=False, stream=False, n=1,
                    max_completion_tokens=effective_limit,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "structured_result", "strict": True, "schema": strict,
                    }},
                    timeout=request.timeout_seconds,
                    **parameters,
                )
            request_id = _identifier(raw.request_id)
            diagnostics = _response_diagnostics(raw.status_code, raw.headers)
            status = "invalid_output"
            accounting = json.loads(raw.content, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
            response = raw.parse()
            if profile:
                if (accounting.get("model") != profile.price.model
                        or accounting.get("service_tier") != profile.service_tier):
                    status = "profile_mismatch"
                    raise ModelUnavailableError()
                usage = _usage(accounting)
                if usage and (usage.input_tokens > profile.max_input_tokens or usage.output_tokens > effective_limit):
                    status = "bound_violation"
                    raise ProviderOutputInvalidError()
            status = "invalid_output"
            if len(response.choices) != 1:
                raise ProviderOutputInvalidError()
            choice = response.choices[0]
            if choice.message.refusal or choice.finish_reason == "content_filter":
                status = "refused"
                raise ProviderOutputInvalidError()
            if choice.finish_reason == "length":
                status = "truncated"
                raise ProviderOutputInvalidError()
            if choice.finish_reason != "stop" or choice.message.tool_calls or not choice.message.content:
                raise ProviderOutputInvalidError()
            data = json.loads(
                choice.message.content, object_pairs_hook=_json_object,
                parse_float=_finite_float, parse_constant=_invalid_constant,
            )
            strict_validator.validate(data)
            validator.validate(data)
            status = "success"
        except asyncio.CancelledError:
            self._metadata(deployment, accounting, request_id, started, "cancelled", diagnostics)
            raise
        except (TimeoutError, APITimeoutError):
            error = ProviderTimeoutError()
            error.metadata = self._metadata(deployment, accounting, request_id, started, "timeout", diagnostics)
            raise error from None
        except APIStatusError as exc:
            error_type, status = {
                401: (ProviderAuthenticationError, "authentication_failed"),
                403: (ProviderAuthenticationError, "authentication_failed"),
                404: (ModelUnavailableError, "model_unavailable"),
                408: (ProviderTimeoutError, "timeout"),
                429: (ProviderRateLimitedError, "rate_limited"),
                504: (ProviderTimeoutError, "timeout"),
            }.get(exc.status_code, (ProviderUnavailableError, "unavailable"))
            if exc.status_code == 400 and exc.code == "content_filter":
                error_type, status = ProviderOutputInvalidError, "refused"
            error = error_type()
            diagnostics = _response_diagnostics(exc.status_code, exc.response.headers)
            error.metadata = self._metadata(deployment, accounting, _identifier(exc.request_id), started, status, diagnostics)
            raise error from None
        except Exception as exc:
            if isinstance(exc, GatewayError):
                error = exc
            elif status in {"invalid_request", "invalid_output"}:
                error = ProviderOutputInvalidError()
            else:
                error = ProviderUnavailableError()
            error.metadata = self._metadata(deployment, accounting, request_id, started, status, diagnostics)
            raise error from None
        return StructuredGenerationResult(
            data=data, metadata=self._metadata(deployment, accounting, request_id, started, status, diagnostics),
        )

    def _metadata(self, deployment, response, request_id, started, status, diagnostics=None) -> GenerationMetadata:
        response = response if isinstance(response, dict) else {}
        usage = _usage(response)
        model = _identifier(response.get("model"))
        profile = self._profiles.get(deployment)
        tier = _identifier(response.get("service_tier"))
        cost = self._prices.estimate(deployment, model, usage) if self._prices else None
        if profile and (model != profile.price.model or tier != profile.service_tier):
            cost = None
        metadata = GenerationMetadata(
            provider="azure_openai", requested_deployment=deployment, returned_model=model,
            provider_request_id=request_id, duration_ms=round((time.perf_counter() - started) * 1000, 3),
            status=status, usage=usage, estimated_cost_usd=cost,
            price_version=self._prices.version if self._prices else None,
            profile_id=profile.identifier if profile else None, service_tier=tier,
            response_diagnostics=diagnostics,
        )
        logger.info(
            "generation status=%s duration_ms=%s usage_known=%s input_tokens=%s output_tokens=%s cost_usd=%s price_version=%s",
            status, metadata.duration_ms, metadata.usage_known,
            usage.input_tokens if usage else None, usage.output_tokens if usage else None,
            str(cost) if cost is not None else "unknown",
            metadata.price_version,
        )
        if diagnostics is not None:
            diagnostic_logger.log(logging.INFO if status == "success" else logging.WARNING,
                                  "provider_response status=%s diagnostics=%s", status,
                                  json.dumps(diagnostics, sort_keys=True, separators=(",", ":")))
        return metadata

    @staticmethod
    def _messages(request: StructuredGenerationRequest, image_detail: str | None = None) -> list[dict[str, Any]]:
        messages = [{"role": message.role, "content": message.content} for message in request.messages]
        if not messages or any(message["role"] not in {"system", "user"} for message in messages):
            raise ProviderOutputInvalidError()
        if request.attachments:
            parts = []
            for attachment in request.attachments:
                if attachment.kind != "image" or attachment.media_type not in {"image/jpeg", "image/png"}:
                    raise ProviderOutputInvalidError()
                if len(attachment.data) > 4 * 1024 * 1024:
                    raise ProviderOutputInvalidError()
                if not base64.b64decode(attachment.data, validate=True):
                    raise ProviderOutputInvalidError()
                parts.append({"type": "image_url", "image_url": {
                    "url": f"data:{attachment.media_type};base64,{attachment.data}",
                    **({"detail": image_detail} if image_detail else {}),
                }})
            messages.append({"role": "user", "content": parts})
        return messages
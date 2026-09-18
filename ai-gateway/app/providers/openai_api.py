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
from app.providers.pricing import PriceTable
from app.providers.strict_schema import to_strict_schema

logger = logging.getLogger("app.generation")
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


def _usage(response: Any) -> TokenUsage | None:
    usage = getattr(response, "usage", None)
    prompt = _integer(getattr(usage, "prompt_tokens", None))
    completion = _integer(getattr(usage, "completion_tokens", None))
    if prompt is None or completion is None:
        return None
    total = getattr(usage, "total_tokens", None)
    if total is not None and (_integer(total) is None or total != prompt + completion):
        return None
    cached = _integer(getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None))
    reasoning = _integer(getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None))
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
        self, *, endpoint: str, api_key: str, model_routes: dict[str, str],
        max_output_tokens: int = 2000, prices: PriceTable | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ):
        base_url = validate_endpoint(endpoint)
        if not api_key.strip() or not model_routes or any(
            not _identifier(purpose) or not _identifier(deployment)
            for purpose, deployment in model_routes.items()
        ):
            raise ValueError("Explicit credentials and valid deployment routes are required.")
        if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768:
            raise ValueError("Output token limit must be between 1 and 32768.")
        logging.getLogger("openai._base_client").disabled = True
        self._client = AsyncOpenAI(
            api_key=api_key, base_url=base_url, max_retries=0,
            organization="", project="",
            http_client=httpx2.AsyncClient(
                transport=transport, follow_redirects=False, trust_env=False,
            ),
        )
        self._routes = dict(model_routes)
        self._max_output_tokens = max_output_tokens
        self._prices = prices

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
        request_id = None
        status = "invalid_request"
        try:
            if os.environ.get("APP_ENV", "production") not in {"development", "test"}:
                status = "disabled"
                raise ServiceNotReadyError()
            from app.pilot import consume_permit, enabled

            if enabled():
                consume_permit(request)
            if deployment is None:
                status = "model_unavailable"
                raise ModelUnavailableError()
            limit = request.max_output_tokens
            if limit is not None and (type(limit) is not int or limit < 1):
                raise ProviderOutputInvalidError()
            if not math.isfinite(request.timeout_seconds) or request.timeout_seconds <= 0:
                raise ProviderOutputInvalidError()
            strict = to_strict_schema(request.output_json_schema)
            Draft202012Validator.check_schema(request.output_json_schema)
            validator = Draft202012Validator(request.output_json_schema, format_checker=FormatChecker())
            strict_validator = Draft202012Validator(strict)
            messages = self._messages(request)
            status = "unavailable"
            async with asyncio.timeout(request.timeout_seconds):
                response = await self._client.chat.completions.create(
                    model=deployment, messages=messages, store=False, stream=False, n=1,
                    max_completion_tokens=min(limit or self._max_output_tokens, self._max_output_tokens),
                    response_format={"type": "json_schema", "json_schema": {
                        "name": "structured_result", "strict": True, "schema": strict,
                    }},
                    timeout=request.timeout_seconds,
                )
            request_id = _identifier(getattr(response, "_request_id", None))
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
            self._metadata(deployment, response, request_id, started, "cancelled")
            raise
        except (TimeoutError, APITimeoutError):
            error = ProviderTimeoutError()
            error.metadata = self._metadata(deployment, response, request_id, started, "timeout")
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
            error.metadata = self._metadata(deployment, response, _identifier(exc.request_id), started, status)
            raise error from None
        except Exception as exc:
            if isinstance(exc, GatewayError):
                error = exc
            elif status in {"invalid_request", "invalid_output"}:
                error = ProviderOutputInvalidError()
            else:
                error = ProviderUnavailableError()
            error.metadata = self._metadata(deployment, response, request_id, started, status)
            raise error from None
        return StructuredGenerationResult(
            data=data, metadata=self._metadata(deployment, response, request_id, started, status),
        )

    def _metadata(self, deployment, response, request_id, started, status) -> GenerationMetadata:
        usage = _usage(response)
        model = _identifier(getattr(response, "model", None))
        cost = self._prices.estimate(deployment, model, usage) if self._prices else None
        metadata = GenerationMetadata(
            provider="azure_openai", requested_deployment=deployment, returned_model=model,
            provider_request_id=request_id, duration_ms=round((time.perf_counter() - started) * 1000, 3),
            status=status, usage=usage, estimated_cost_usd=cost,
            price_version=self._prices.version if self._prices else None,
        )
        logger.info(
            "generation status=%s duration_ms=%s usage_known=%s input_tokens=%s output_tokens=%s cost_usd=%s price_version=%s",
            status, metadata.duration_ms, metadata.usage_known,
            usage.input_tokens if usage else None, usage.output_tokens if usage else None,
            str(cost) if cost is not None else "unknown",
            metadata.price_version,
        )
        return metadata

    @staticmethod
    def _messages(request: StructuredGenerationRequest) -> list[dict[str, Any]]:
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
                }})
            messages.append({"role": "user", "content": parts})
        return messages
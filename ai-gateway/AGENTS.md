# Personal AI Gateway agent instructions

These instructions apply to everything under `ai-gateway/`.

## Status

Phase 2 (provider-neutral gateway foundation), Phase 3 (real Copilot SDK provider), Phase 4 (text food analysis), and Phase 5 (image food analysis) are implemented: a domain-blind `StructuredGenerationProvider` adapter interface, a deterministic schema-driven `FakeProvider`, the real `GitHubCopilotProvider` (official GitHub Copilot SDK via the Copilot CLI in headless/server mode), and `FoodAnalysisUseCase` (text and/or image). Phase 6 (`feature/v2-production-hardening`, not yet merged) adds production hardening: real backend-to-gateway authentication (`X-Service-Token`/`GATEWAY_SERVICE_TOKEN`), a fail-fast concurrency limiter, request-correlation IDs, and a `Dockerfile` for Azure Container Apps. Real Azure deployment itself has **not** been performed - see `docs/architecture.md`'s Phase 6 checklist for exactly what remains external/manual.

## Provider decision (final)

- Production provider: the official GitHub Copilot SDK, run through the Copilot CLI in headless/server mode. Implemented as `app/providers/github_copilot.py::GitHubCopilotProvider`.
- `trsdn/github_copilot_openai_api_wrapper` is **not** part of the production architecture and must not be reintroduced without an explicit decision recorded in `docs/architecture.md`.

## Target boundary

- Expose our own authenticated, application-specific server-side API to the Fitness API/domain backend.
- Keep application/domain contracts provider-independent.
- Put each model provider behind the `StructuredGenerationProvider` adapter interface (`app/providers/base.py`).
- The production adapter will wrap the official GitHub Copilot SDK (Copilot CLI, headless/server mode). Treat its transport details as an adapter implementation detail, not as the gateway's public contract.
- Never expose the Copilot CLI process directly to the public internet. Restrict its network reachability to the gateway and protect the gateway with authentication, authorization, rate/size limits, timeouts, and input validation.
- Keep provider routing, model selection, endpoints, and credentials in server-side configuration. Never require the iOS app to know them.
- Never expose provider or model identifiers through the public gateway API surface.

## Contracts and privacy

- Prefer versioned structured JSON contracts and explicit schemas over unstructured model text.
- Model food text/image analysis as structured nutrition estimates. Design responses so users can review and confirm estimates before persistence where appropriate.
- Allow later activity/training assistance and other personal AI services without coupling the core gateway to nutrition-only domain logic.
- Minimize transmission, retention, and logging of health data, food images, prompts, and responses. Do not log secrets or raw sensitive payloads by default.
- Handle provider failures, timeouts, malformed output, and schema-validation failures explicitly; do not silently persist partial results.

## Authentication

- The gateway is never a public, client-facing API - its only caller is our own backend. Fail-closed by default: `GATEWAY_DEV_AUTH_BYPASS` defaults to false and only takes effect when `APP_ENV=development`. Outside that bypass, every `/v1/*` request must present a valid `X-Service-Token` header matching `GATEWAY_SERVICE_TOKEN` (`app/security.py`, constant-time comparison); `GATEWAY_SERVICE_TOKEN` is required (fails closed at startup) when `APP_ENV=production`. `GET /healthz` remains anonymous.
- Never enable `GATEWAY_DEV_AUTH_BYPASS` outside a trusted local environment, and never set `APP_ENV=production` with `AI_PROVIDER=fake` (rejected at startup).
- Copilot's own authentication (separate from the above) is documented in `README.md`: a locally logged-in `copilot` CLI session by default, or an explicit `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`. Never hard-code or commit a token. In a deployed container, only the `COPILOT_GITHUB_TOKEN` mechanism is viable (see `Dockerfile`) - the interactive device-code login has no headless equivalent.

## Concurrency and observability

- `AI_PROVIDER_MAX_CONCURRENCY` (default 2, range 1-20) bounds simultaneous provider calls via `app/concurrency.py::ConcurrencyLimiter` - a fail-fast counter, not a queue. A request that cannot get a slot immediately gets `ServiceSaturatedError` (503 `service_saturated`) rather than waiting or being buffered in memory.
- Every request gets a correlation ID (`X-Request-Id`, forwarded from the backend if present, otherwise minted) logged with path/method/status/latency and echoed back in the response header and in any error envelope's `request_id` field (`app/main.py`'s logging middleware). Never logs the food description, image bytes, or raw provider response.

## Provider abstraction

- `StructuredGenerationProvider` (`app/providers/base.py`) is domain-blind: it only receives generic messages, an opaque `model_purpose` routing key, a JSON output schema, optional attachments, and a timeout. Providers must never branch on domain task names.
- All food-specific instructions, schema selection, and result interpretation belong in `FoodAnalysisUseCase` (or a future use case), never in a provider implementation. `GitHubCopilotProvider` must stay domain-blind too: do not add food-specific prompts/fields to it.
- Model/provider routing is server-side configuration (`FOOD_TEXT_MODEL_PURPOSE`, `FOOD_IMAGE_MODEL_PURPOSE`, `COPILOT_MODEL_ROUTES_JSON`) and must never be exposed through the public API or influence the public request/response shape. A configured model must never be silently substituted.
- Image analysis reuses the same generic `Attachment` (`kind`, `media_type`, `data`) rather than a food-specific type. `GitHubCopilotProvider` translates it into the SDK's inline `BlobAttachment` (base64, no temporary files) and rejects any other attachment `kind` or an empty payload before creating a session. Image requests are routed through `FOOD_IMAGE_MODEL_PURPOSE` (never the text purpose).
- **Readiness (`check_ready()`) capability checks are strict and fail closed** (`_vision_route_is_fully_supported` in `app/providers/github_copilot.py`): for every purpose in `vision_required_purposes`, the mapped model must report, via the SDK's own `list_models()` data (`ModelCapabilities`/`ModelVisionLimits`, `github-copilot-sdk` 1.0.11): `supports.vision == true`; `limits.vision.supported_media_types` present and a superset of `SUPPORTED_IMAGE_MEDIA_TYPES` (`image/jpeg`, `image/png`); `limits.vision.max_prompt_images` present and >= 1; `limits.vision.max_prompt_image_size` **present and** >= `MAX_IMAGE_BYTES`. SDK 1.0.11 does not document a "missing means unlimited" semantic for `max_prompt_image_size` (or any other field here), so a missing/`None` value is treated as unknown/incompatible, not permissive - every required field must be explicitly, affirmatively reported as compatible, or readiness is false. Never silently routes to a different model when a check fails.
- **Image content validation (defense-in-depth):** `ImageAttachment` (`app/schemas/food_analysis.py`) never trusts the declared `media_type` alone. Before base64-decoding, the encoded string's length is checked against the maximum possible base64 length for `MAX_IMAGE_BYTES` (accounting for padding) and rejected immediately if it could not possibly decode within the limit; only then is it strictly base64-decoded (`validate=True`), and the decoded size is checked again as an explicit final guard. After that, `app/image_validation.py` (Pillow) verifies the decoded bytes are a real, undamaged image whose actual format matches the declared `media_type`: it calls `Image.verify()` and then, on a fresh reopen, forces a full pixel decode via `.load()` - `verify()` alone only checks structural well-formedness and lets tail-truncated files (missing scan data/an end marker but with valid headers) through, while `.load()` actually decodes every pixel and fails on those. Pillow's `DecompressionBombError` is caught explicitly (it is not an `OSError` subclass), and `DecompressionBombWarning` is turned into a raised exception via `warnings.simplefilter("error", ...)` so a borderline-oversized image is rejected rather than silently accepted. This repeats the backend's own equivalent check independently, since the gateway must never assume the backend (or any other caller) already validated its input.

## Secrets and validation

- Never commit GitHub/Copilot credentials, OAuth/access/refresh tokens, `.env`, local settings, virtual environments, caches, or build output. Example configuration must contain placeholders only.
- Tests must exercise provider-independent behavior through `FakeProvider`/mocked SDK boundaries and must not require real credentials. The only exception is `tests/test_copilot_integration.py`, which is opt-in only (`RUN_COPILOT_INTEGRATION_TESTS=1`) and must never run in normal CI/local test runs.

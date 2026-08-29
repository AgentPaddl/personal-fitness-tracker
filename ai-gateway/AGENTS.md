# Personal AI Gateway agent instructions

These instructions apply to everything under `ai-gateway/`.

## Status

Phase 2 (provider-neutral gateway foundation), Phase 3 (real Copilot SDK provider), and Phase 4 text food analysis are implemented: a domain-blind `StructuredGenerationProvider` adapter interface, a deterministic schema-driven `FakeProvider`, the real `GitHubCopilotProvider` (official GitHub Copilot SDK via the Copilot CLI in headless/server mode), and the first `FoodAnalysisUseCase`. Image-based food analysis (`feature/v2-ios-food-image-analysis`, not yet merged) extends the same use case to accept an optional generic image `Attachment`, routed to a separate `food_image_v1` model purpose. Production deployment (Azure Container Apps, production authentication mechanism, secret storage) is **not implemented yet** — do not invent that architecture without an explicit task.

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

- Production (deployed) authentication is not decided yet. Fail-closed by default: `GATEWAY_DEV_AUTH_BYPASS` defaults to false and only takes effect when `APP_ENV=development`. The default configuration (no env vars set) refuses every `/v1/*` request. `GET /healthz` remains anonymous.
- Never enable `GATEWAY_DEV_AUTH_BYPASS` outside a trusted local environment, and never set `APP_ENV=production` with `AI_PROVIDER=fake` (rejected at startup).
- Copilot's own authentication (separate from the above) is documented in `README.md`: a locally logged-in `copilot` CLI session by default, or an explicit `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`. Never hard-code or commit a token.

## Provider abstraction

- `StructuredGenerationProvider` (`app/providers/base.py`) is domain-blind: it only receives generic messages, an opaque `model_purpose` routing key, a JSON output schema, optional attachments, and a timeout. Providers must never branch on domain task names.
- All food-specific instructions, schema selection, and result interpretation belong in `FoodAnalysisUseCase` (or a future use case), never in a provider implementation. `GitHubCopilotProvider` must stay domain-blind too: do not add food-specific prompts/fields to it.
- Model/provider routing is server-side configuration (`FOOD_TEXT_MODEL_PURPOSE`, `FOOD_IMAGE_MODEL_PURPOSE`, `COPILOT_MODEL_ROUTES_JSON`) and must never be exposed through the public API or influence the public request/response shape. A configured model must never be silently substituted.
- Image analysis reuses the same generic `Attachment` (`kind`, `media_type`, `data`) rather than a food-specific type. `GitHubCopilotProvider` translates it into the SDK's inline `BlobAttachment` (base64, no temporary files) and rejects any other attachment `kind` or an empty payload before creating a session. Image requests are routed through `FOOD_IMAGE_MODEL_PURPOSE` (never the text purpose).
- **Readiness (`check_ready()`) capability checks are strict and fail closed** (`_vision_route_is_fully_supported` in `app/providers/github_copilot.py`): for every purpose in `vision_required_purposes`, the mapped model must report, via the SDK's own `list_models()` data (`ModelCapabilities`/`ModelVisionLimits`, `github-copilot-sdk` 1.0.11): `supports.vision == true`; `limits.vision.supported_media_types` present and a superset of `SUPPORTED_IMAGE_MEDIA_TYPES` (`image/jpeg`, `image/png`); `limits.vision.max_prompt_images` present and >= 1. `limits.vision.max_prompt_image_size`, if present, must be >= `MAX_IMAGE_BYTES`; if the SDK omits this field entirely, it is treated as "no advertised limit" (not fail-closed), consistent with how every other optional numeric SDK limit is already treated elsewhere. Any other missing/ambiguous capability data (no vision limits object, no media types list, no `max_prompt_images`) fails closed. Never silently routes to a different model when a check fails.
- **Image content validation (defense-in-depth):** `ImageAttachment` (`app/schemas/food_analysis.py`) never trusts the declared `media_type` alone. Before base64-decoding, the encoded string's length is checked against the maximum possible base64 length for `MAX_IMAGE_BYTES` (accounting for padding) and rejected immediately if it could not possibly decode within the limit; only then is it strictly base64-decoded (`validate=True`), and the decoded size is checked again as an explicit final guard. After that, `app/image_validation.py` (Pillow) verifies the decoded bytes are a real, undamaged image whose actual format matches the declared `media_type` - this repeats the backend's own equivalent check independently, since the gateway must never assume the backend (or any other caller) already validated its input.

## Secrets and validation

- Never commit GitHub/Copilot credentials, OAuth/access/refresh tokens, `.env`, local settings, virtual environments, caches, or build output. Example configuration must contain placeholders only.
- Tests must exercise provider-independent behavior through `FakeProvider`/mocked SDK boundaries and must not require real credentials. The only exception is `tests/test_copilot_integration.py`, which is opt-in only (`RUN_COPILOT_INTEGRATION_TESTS=1`) and must never run in normal CI/local test runs.

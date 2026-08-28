# Personal AI Gateway agent instructions

These instructions apply to everything under `ai-gateway/`.

## Status

Phase 2 (provider-neutral gateway foundation) is implemented and has been hardened per independent review: a domain-blind `StructuredGenerationProvider` adapter interface, a deterministic schema-driven `FakeProvider`, and the first `FoodAnalysisUseCase`. The production provider adapter (official GitHub Copilot SDK via the Copilot CLI in headless/server mode) is **not implemented yet**. Do not add real provider integration unless a task explicitly authorizes that phase.

## Provider decision (final)

- Production provider: the official GitHub Copilot SDK, run through the Copilot CLI in headless/server mode.
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

- Production authentication is not implemented yet. Fail-closed by default: `GATEWAY_DEV_AUTH_BYPASS` defaults to false and only takes effect when `APP_ENV=development`. The default configuration (no env vars set) refuses every `/v1/*` request. `GET /healthz` remains anonymous.
- Never enable `GATEWAY_DEV_AUTH_BYPASS` outside a trusted local environment, and never set `APP_ENV=production` with `AI_PROVIDER=fake` (rejected at startup).

## Provider abstraction

- `StructuredGenerationProvider` (`app/providers/base.py`) is domain-blind: it only receives generic messages, an opaque `model_purpose` routing key, a JSON output schema, optional attachments, and a timeout. Providers must never branch on domain task names.
- All food-specific instructions, schema selection, and result interpretation belong in `FoodAnalysisUseCase` (or a future use case), never in a provider implementation.
- Model/provider routing is server-side configuration (e.g. `FOOD_TEXT_MODEL_PURPOSE`) and must never be exposed through the public API or influence the public request/response shape.

## Secrets and validation

- Never commit GitHub/Copilot credentials, OAuth/access/refresh tokens, `.env`, local settings, virtual environments, caches, or build output. Example configuration must contain placeholders only.
- Tests must exercise provider-independent behavior through `FakeProvider` and must not require real credentials. Isolate any opt-in integration test that would exercise a real provider.

# Architecture

## Purpose and current status

This repository contains a private, non-commercial personal fitness and nutrition tracker. The current product is an iOS app, an Azure Functions backend, and a Personal AI Gateway that together implement a working end-to-end food-analysis feature (text and image) against the real GitHub Copilot SDK. Production deployment (an actual Azure rollout) has **not** been performed; Phase 6 (below) prepares the application-level configuration/hardening for it without doing the deployment itself.

## Current monorepo layout

| Path | Current responsibility | Status |
| --- | --- | --- |
| `ios/` | SwiftUI client and local SwiftData persistence | Working application, incl. text/photo/camera food analysis |
| `backend/` | Azure Functions Python 3.13 application API | Working `GET /api/health`, `GET /api/readiness`, `POST /api/food-analysis` (text + image) |
| `ai-gateway/` | Provider-independent server-side AI boundary | Working FastAPI app with the real `GitHubCopilotProvider`; not yet deployed to Azure |
| `docs/` | Architecture and migration documentation | Active documentation |
| `.github/` | Repository-wide agent/Copilot guidance | Active guidance |

The iOS application owns the user experience and local records for workouts, exercise performance, activities, weight, goals, nutrition entries/presets, and backup-related flows. SwiftData is the local persistence layer. Existing behavior and stored user data are compatibility constraints.

The backend currently contains a minimal Azure Functions app whose health function returns HTTP 200 and `{"status": "ok"}`. It does not yet provide the target fitness/nutrition domain API, authentication, or AI orchestration. Its current anonymous authorization setting must not be copied to future sensitive endpoints.

## Provider decision (final)

- **Production provider:** the official GitHub Copilot SDK.
- **Runtime:** the Copilot CLI running in headless/server mode, invoked internally by the gateway's Copilot adapter.
- `trsdn/github_copilot_openai_api_wrapper` is **not** part of the production architecture. It was an early exploration option only and must not be reintroduced without a new explicit decision recorded here.
- AI provider access remains behind the gateway's provider-neutral `StructuredGenerationProvider` abstraction, so the domain backend and iOS client never depend on Copilot-specific transport details.

## Target V2 architecture

```text
iOS client
    |
    | authenticated, versioned fitness/nutrition contracts
    v
Fitness API / domain backend
    |
    | authenticated, provider-neutral AI requests
    v
Personal AI Gateway
    |
    | StructuredGenerationProvider (provider-neutral adapter interface)
    +--> GitHubCopilotProvider (real; official GitHub Copilot SDK)
    |       Copilot CLI in headless/server mode
    +--> FakeProvider (deterministic, used for local development and tests)
    +--> Future provider adapter(s)
```

### iOS client

- Owns SwiftUI presentation, user interaction, and local SwiftData persistence.
- Calls only our authenticated Fitness API; it never calls model providers or the Copilot wrapper directly.
- Contains no GitHub/Copilot credentials, provider tokens, provider base URLs, or provider-specific model routing.
- Presents AI-produced values as estimates and supports review/confirmation before persistence where appropriate.
- Evolves persisted models without destructive migration or loss of existing personal data.

### Fitness API / domain backend

- Owns fitness/nutrition domain rules, application authorization, and application-facing API contracts.
- Validates requests and decides when an approved workflow needs AI assistance.
- Translates use cases into provider-neutral gateway requests; provider transport does not enter domain logic.
- Returns stable, versioned response and error contracts to the iOS client.
- Does not expose sensitive personal endpoints anonymously.

### Personal AI Gateway — Phase 2 foundation implemented

- Provides our authenticated, server-side AI API to the domain backend (FastAPI app under `ai-gateway/`).
- Owns AI schema validation, provider/model routing, timeouts, limits, and normalized errors.
- Uses replaceable provider adapters behind the `StructuredGenerationProvider` interface. The deterministic `FakeProvider` is implemented for local development and tests. `GitHubCopilotProvider` (Phase 3) wraps the official GitHub Copilot SDK via the Copilot CLI in headless/server mode and is implemented for local use; production deployment/authentication is not decided yet.
- Keeps provider-specific transport details behind the adapter boundary; the public gateway API never exposes provider or model identifiers.
- Is not a public proxy. Any future Copilot CLI process must never be exposed directly to the public internet and should be reachable only through controlled server-side networking.

### Provider adapters

- Convert gateway contracts to and from provider-specific formats.
- Contain provider authentication and transport behavior, not fitness/nutrition domain rules.
- Allow provider replacement without changing the iOS contract or core domain logic.
- Treat malformed or schema-invalid provider output as an explicit failure, not trusted application data.

## AI contracts and use cases

Prefer explicit, versioned JSON schemas. Structured contracts should distinguish model estimates from user-confirmed facts and include enough metadata for validation and review without leaking provider internals.

Planned use cases are:

1. Analyze food text into structured nutrition estimates.
2. Analyze food images plus optional context into structured nutrition estimates.
3. Add activity and training assistance.
4. Support other personal AI services through separate application-level contracts.

These are roadmap items, not current capabilities. Persistence of AI output should be an explicit domain action, normally after user review or confirmation.

## Security and privacy assumptions

- Fitness, nutrition, images, prompts, and derived responses are sensitive personal data.
- Provider and wrapper credentials exist only in server-side environment variables or a managed secret store. They never ship in the iOS app, source control, logs, or client-visible responses.
- `.env`, `local.settings.json`, `.venv`, Xcode user data, caches, and build artifacts remain untracked.
- Authentication and authorization are required before exposing personal-data or AI endpoints beyond a trusted local environment.
- Apply least-privilege networking: client traffic terminates at our API, gateway access is limited to authorized backend callers, and the wrapper is internal-only.
- Minimize data sent to providers and define consent, retention, deletion, and export behavior before sending real personal data. Avoid raw sensitive-payload logging by default.
- Apply request size/rate limits, timeouts, output schema validation, and safe error handling at server boundaries.
- AI output is an estimate and is not authoritative health or medical advice.

## Phased roadmap

### Phase 0 — baseline (current)

- Preserve the working SwiftUI/SwiftData app and Azure Functions health endpoint.
- Establish repository, security, agent, and architecture guidance.
- Keep the AI gateway as documentation/configuration scaffolding only.

### Phase 1 — contracts and security design

- Define authentication/authorization and trust boundaries.
- Define versioned domain and gateway JSON schemas, including estimate/confirmation semantics.
- Decide privacy, consent, retention, deletion, observability, and deployment controls.
- Add contract tests before provider integration.

### Phase 2 — provider-neutral gateway foundation (implemented, reviewed, and hardened)

- Implemented the gateway core (FastAPI), configuration, request/response schemas with numeric bounds, normalized errors, and a domain-blind `StructuredGenerationProvider` adapter interface. Concrete providers only ever see generic generation messages, an opaque `model_purpose` routing key, a JSON output schema, optional attachments, and a timeout — never domain task names like "food_analysis_text". All food-specific orchestration (instructions, schema, interpretation) lives in `FoodAnalysisUseCase`.
- Implemented the deterministic, schema-driven `FakeProvider` (derives values purely from the requested JSON schema, with no food-specific knowledge) and the first `FoodAnalysisUseCase`; tests use the fake provider and do not require real credentials.
- Server-side model routing: `FOOD_TEXT_MODEL_PURPOSE` selects a routing key independently of the public contract; changing it never changes the request/response shape and it is never exposed to clients.
- Modularized the Azure Functions backend into blueprints, added an internal `GatewayClient` with distinct timeout/connectivity/upstream-error handling, and a food-analysis backend route that works locally against the gateway's `FakeProvider` path.
- The backend owns its own public request/response contract (`backend/schemas.py`) and explicitly maps the gateway's internal response onto it; unknown fields (provider, model, usage, debug/execution metadata) can never reach the client because only declared fields are ever read and re-serialized.
- Authentication fails closed by default everywhere: the gateway's dev auth bypass requires both `APP_ENV=development` and `GATEWAY_DEV_AUTH_BYPASS=true`; the backend's food-analysis route requires `APP_ENV=development`. Neither is enabled by default. `GET /health` (backend) and `GET /healthz` (gateway) remain anonymous and configuration-independent.
- `AI_PROVIDER=fake` is rejected outright when `APP_ENV=production`, so the fake provider can never silently become a production default; today this means the gateway has no valid production configuration until a real provider adapter exists, which is intentional.
- A final catch-all exception boundary (gateway `app/main.py`, use case `_generate_with_timeout`) normalizes any unexpected/provider exception so raw internals never reach a client.
- Readiness (`GET /readyz`) delegates to a provider's own cheap `check_ready()` check, letting a future real adapter report connectivity without performing a billed generation call.

### Phase 3 — Copilot SDK adapter (implemented for local use)

- Implemented `GitHubCopilotProvider`, wrapping the official GitHub Copilot SDK for Python (`github-copilot-sdk`), which drives the Copilot CLI in headless/server mode. It remains domain-blind: it understands only generic messages, an opaque `model_purpose` routing key, a JSON output schema, and a timeout.
- Structured output uses a terminal tool (`submit_structured_result`, `Tool(is_terminal=True)`) whose parameter schema is supplied by the calling use case; the provider never hard-codes a domain schema, and the use case still authoritatively re-validates whatever the tool call returns.
- Server-side model routing (`COPILOT_MODEL_ROUTES_JSON`) maps each model-routing purpose to a concrete Copilot model id with no default and no silent substitution; `GET /readyz` validates the configured model is actually available via the SDK's `list_models()`/`get_auth_status()` without a billed generation call.
- Local-development authentication uses the Copilot CLI's own documented mechanisms (locally logged-in session via `copilot`/`/login`, or an optional explicit token) — never a hard-coded credential. The production authentication mechanism for a deployed gateway is intentionally not decided yet.
- One long-lived `CopilotClient` (and its underlying CLI process) is reused across requests; only a lightweight SDK session is created and disconnected per request.
- Normalizes provider authentication failure, rate limiting, model unavailability, timeouts, invalid structured output, and unexpected SDK/runtime failures to the gateway's existing error model; a catch-all boundary ensures no raw SDK exception, prompt, or GitHub-specific metadata reaches the public API.
- Unit tests mock the SDK client boundary and require no credentials; an opt-in integration/smoke test (`RUN_COPILOT_INTEGRATION_TESTS=1`) exercises the real CLI and is never run in normal CI/local test runs. `trsdn/github_copilot_openai_api_wrapper` is not part of this plan.
- Remaining for production: Azure Container Apps packaging, a chosen production auth mechanism (server-to-server token vs. another documented option), secret storage, and network isolation for the CLI process.

### Phase 4 — food analysis workflow (text and image analysis; both merged to `main`)

- Implemented the iOS text food-analysis flow: `NutritionView` lets the user type a natural-language description, calls the backend's `POST /api/food-analysis` via a local Swift package (`ios/FoodAnalysisKit`), and presents an editable review sheet (`FoodAnalysisReviewView`) before any persistence.
- The app only ever talks to our own backend's public JSON contract; it has no knowledge of the Personal AI Gateway, GitHub Copilot, model ids, or provider routing.
- `FoodEntry` (existing SwiftData model) is created only after explicit user confirmation of the reviewed values; cancelling/dismissing the review never persists anything. No SwiftData schema change was made.
- **Image analysis (merged):** extends the same flow with photo input, reusing the identical review/persistence UI and the same structured estimate contract.
  - iOS: `PhotosPicker` or camera capture (`UIImagePickerController` bridge) selection, client-side preprocessing (`FoodImagePreprocessor`: EXIF-orientation-corrected resize to a max 1280px side via ImageIO's thumbnail API, deterministic quality/dimension fallback to fit a 3 MiB limit, re-encoded as JPEG, which also strips EXIF/GPS since the source's properties are never copied to the re-encoded output), then upload via `FoodAnalysisService.analyzeImage`.
  - Backend: `POST /api/food-analysis` now also accepts `multipart/form-data` (`image` file field, required; optional `food_description` text field), validated for MIME type (`image/jpeg`, `image/png` only), non-empty payload, and a 3 MiB size cap (chosen to fit the configured vision model's advertised max prompt image size), then forwarded to the gateway as an inline base64 payload over the existing internal JSON contract.
  - Gateway: `FoodAnalysisRequest` now accepts `food_description`, `image`, or both (at least one required); `FoodAnalysisUseCase` builds a generic `Attachment` and routes image requests to a separate, vision-specific model purpose (`FOOD_IMAGE_MODEL_PURPOSE`, default `food_image_v1`) rather than the text purpose, so an image call is never silently sent to a non-vision model.
  - `GitHubCopilotProvider` translates the generic attachment into the SDK's inline `BlobAttachment` (base64, no temporary files) and rejects unsupported attachment kinds/empty payloads before ever creating a session. `check_ready()` additionally verifies, via the SDK's own `list_models()` capability data, that any route required for image analysis actually supports vision (`gpt-5-mini` verified vision-capable via a real Copilot session on 2026-08-29).
  - The output schema, bounds, and review/persistence flow are unchanged from text analysis; no new SwiftData model or migration was introduced.
- Verify privacy controls, failure handling, and observability without sensitive-payload logging.

### Phase 5 — expansion and provider portability (future, not started)

- Add activity/training assistance and other personal AI services as separate domain contracts.
- Add or switch providers through adapters and server-side routing without iOS provider changes.
- Revisit schemas, privacy controls, and data migrations incrementally with each use case.

### Phase 6 — production hardening (`feature/v2-production-hardening`, not yet merged; no real Azure deployment performed)

Adds no new AI capability; hardens the existing text/image food-analysis system for reliable ongoing personal use.

- **Authentication**: the accepted production design is Microsoft Entra ID via MSAL on the iOS native client, then Azure App Service Authentication / Easy Auth on the public backend. The backend does not accept a static shared secret from the app; it only trusts Azure-injected Easy Auth identity headers when `EASY_AUTH_ENABLED=true` and `APP_ENV != development`. A separate server-to-server secret still remains for backend -> gateway (`GATEWAY_SERVICE_TOKEN`, `X-Service-Token`), because the gateway is never a public client-facing API. No GitHub/Copilot credential ever exists in the iOS app or is committed to git.
- **iOS auth**: a real production app must acquire a short-lived Entra access token via MSAL or a supported equivalent, send it as `Authorization: Bearer <token>`, and rely on the backend's App Service Authentication to validate it before the app reaches backend business logic. Until an MSAL integration is configured, the app intentionally keeps a placeholder `EntraAuthService` with no secret material and does not attempt an app-side static API key.
- **Gateway deployment**: a `Dockerfile` (Python 3.13, Copilot CLI runtime pre-fetched at build time, `COPILOT_GITHUB_TOKEN`-based auth since the interactive `/login` flow has no headless equivalent) targets Azure Container Apps but has not been built/deployed here (no Docker available in the authoring environment) - see `ai-gateway/README.md`'s deployment section for the full runtime/memory/networking requirements.
- **Networking**: production `AI_GATEWAY_BASE_URL` must be an explicit, non-`localhost`, `https://` URL (`backend/config.py` fails closed otherwise). Intended topology: `iPhone native client -> Microsoft Entra ID via MSAL -> Azure Functions with App Service Authentication / Easy Auth -> private/restricted gateway -> Copilot CLI runtime (never exposed)`. Only the backend is a public endpoint.
- **Timeout hierarchy**: gateway `AI_PROVIDER_TIMEOUT_SECONDS` (90s recommended) < backend `AI_GATEWAY_TIMEOUT_SECONDS` (100s) < iOS `FoodAnalysisService.timeoutInterval` (110s, raised from 30s) - see `backend/AGENTS.md`'s table.
- **Retry UX**: no automatic/silent retries of an AI request. An explicit "Erneut versuchen" button appears only for retry-eligible failures (connectivity, backend-unavailable, rate-limited, timeout); input/configuration failures are not offered a retry action, since retrying the identical request would just fail the same way.
- **Long-running UX**: the existing spinner is preserved; after 5s it switches to a neutral "Das Essen wird analysiert …" with no fake percentage progress.
- **Observability**: a request-correlation ID (`X-Request-Id`) is minted by the backend (or reused if the caller already sent one), forwarded to the gateway, echoed in response headers, and included in every error envelope's `request_id` field. Structured, content-free logging (path/use-case/status/latency/error-category) at both layers - never the food description, image bytes, raw model response, or credentials.
- **Readiness**: `GET /api/readiness` (new, distinct from `GET /api/health`) checks the gateway is actually reachable; `GET /healthz`/`GET /readyz` (gateway) semantics are unchanged (health = process alive, readiness = real Copilot auth/vision-capable model routing verified without a billed call).
- **Concurrency**: `AI_PROVIDER_MAX_CONCURRENCY` (default 2) is a fail-fast in-memory limiter (`app/concurrency.py`), never an unbounded queue - a request beyond the limit gets an immediate `503 service_saturated`.
- **Preserved unchanged**: the 3 MiB image limit, JPEG/PNG content validation (full decode + decompression-bomb handling), client-side metadata stripping, `food_text_v1`/`food_image_v1` routing, provider domain-neutrality, `submit_structured_result`-only tool exposure, the exactly-once persistence flow, and all existing SwiftData models/schemas (no changes).

#### Personal production checklist

- [ ] Gateway container built and deployed (Azure Container Apps or equivalent)
- [ ] Backend (Azure Functions) deployed
- [ ] Azure App Service Authentication / Easy Auth enabled on the public backend, with Entra ID trust configured and `EASY_AUTH_ENABLED=true`
- [ ] `GATEWAY_SERVICE_TOKEN` configured identically on both backend and gateway
- [ ] Production `AI_GATEWAY_BASE_URL` (explicit HTTPS, non-localhost) configured on the backend
- [ ] Gateway ingress restricted to the backend only (no public gateway exposure)
- [ ] `COPILOT_GITHUB_TOKEN` (server-to-server) configured as a gateway secret
- [ ] `COPILOT_MODEL_ROUTES_JSON` configured for both `food_text_v1` and `food_image_v1`, verified vision-capable via `GET /readyz`
- [ ] Backend `GET /api/health` and `GET /api/readiness` both return healthy/ready against the deployed gateway
- [ ] Gateway `GET /healthz` and `GET /readyz` both return healthy/ready
- [ ] iOS production build configured with the deployed HTTPS backend URL and a real Entra ID access-token provider (MSAL or equivalent) that sends `Authorization: Bearer <token>`
- [ ] Real iPhone smoke test against the deployed stack (text and image, save flow) completed

## Change and validation policy

Changes should be small and reviewable, with explicit acceptance criteria. Build `ios/Trainingsplan.xcodeproj` after Swift changes, with DerivedData outside the repository. After backend changes, run relevant tests and verify the health endpoint. Any SwiftData schema change requires an explicit non-destructive migration plan that preserves existing user data.

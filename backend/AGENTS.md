# Backend agent instructions

These instructions apply to everything under `backend/`.

## Current component

- Azure Functions application targeting Python 3.13, organized as blueprints registered from `function_app.py`.
- `GET /api/health` still returns `{"status": "ok"}` and must keep doing so.
- `POST /api/food-analysis` forwards a food description and/or photo to the Personal AI Gateway through `gateway_client.py`, validates against the backend-owned schemas in `schemas.py`, and returns only the mapped public estimate (never the gateway's raw JSON). It works locally against the gateway's `FakeProvider` path; it does not call any AI provider directly.
  - `Content-Type: application/json` — text-only, unchanged: `{"food_description": "..."}"`.
  - `Content-Type: multipart/form-data` — image analysis: a required `image` file field (`image/jpeg` or `image/png` only, non-empty, ≤3 MiB - see `schemas.SUPPORTED_IMAGE_MIME_TYPES`/`MAX_IMAGE_BYTES`, chosen to fit the currently-configured vision model's advertised max prompt image size) plus an optional `food_description` text field (≤2000 characters). Both branches return the identical `{"estimate": {...}}` envelope. The image is forwarded to the gateway as an inline base64 payload (`GatewayClient.analyze_food_image`) over the existing internal JSON contract, not re-wrapped as multipart again - there is no second internal transport.
  - Image validation errors use their own normalized codes: `image_required`, `image_empty` (400), `unsupported_media_type` (415), `image_content_invalid` (400), `image_too_large` (413). Malformed multipart bodies are caught and mapped to `invalid_request` (400), never an unhandled 500.
  - Content validation (`image_validation.py`, Pillow): the declared MIME type is never trusted on its own. The actual bytes are decoded and verified (`Image.verify()`) and the detected format must match the declared MIME type (`image/jpeg` → `JPEG`, `image/png` → `PNG`); corrupt/truncated images and MIME/content mismatches (e.g. a PNG uploaded as `image/jpeg`) are rejected as `image_content_invalid`. The gateway independently repeats equivalent validation (defense-in-depth) rather than trusting the backend alone.
  - **Memory-bound precision (do not overclaim):** `_read_bounded()` reads at most `MAX_IMAGE_BYTES + 1` bytes from the parsed multipart file stream and rejects anything larger - but this only bounds *this function's own* read call. By the time this code runs, the Azure Functions Python worker has already received and fully buffered the entire raw HTTP request body in memory (`HttpRequest.get_body()`), and werkzeug's multipart parser (`req.files`/`req.form`) has already parsed that whole buffered body before our handler is invoked. So the true worst-case *ingress* memory bound is whatever request-body-size limit the Azure Functions hosting layer itself enforces (documented by Microsoft as a platform-level default, not a value configurable from `host.json` or application code as of this writing) - not `MAX_IMAGE_BYTES`. Our own check only bounds the (already-buffered) data this handler additionally copies/forwards/logs, and prevents a compliant caller's oversized-but-under-the-platform-limit upload from being silently forwarded to the gateway.
  - The uploaded image is never persisted or logged; it exists only in memory for the duration of the one gateway call, and the decoded buffer is released (`del image_bytes`) as soon as the gateway call returns.
- **Authentication (Phase 6):** the route requires either `APP_ENV=development` (local-dev bypass, unchanged) or a valid `X-API-Key` header matching `BACKEND_API_KEY` (`security.py::caller_is_authenticated`, constant-time comparison). `BACKEND_API_KEY` is required (fails closed at startup) when `APP_ENV=production`. This authenticates "this is our own iOS app", not individual end users - there is exactly one user of this private app. See `docs/architecture.md` for why a static shared secret was chosen over Azure Easy Auth/AAD for this use case.
- Every request gets a correlation ID (`X-Request-Id`, reused if the caller already sent one, otherwise minted), echoed back as a response header, included in every error envelope's `request_id` field, forwarded to the gateway, and logged (path/method/use-case/status/latency only - never the food description, image bytes, or gateway response body).
- `function_app.py` calls `config.validate_config()` at import time so invalid configuration - a malformed/out-of-bounds gateway URL/timeout, or (in production) a missing `BACKEND_API_KEY`/`GATEWAY_SERVICE_TOKEN`, a `localhost` gateway URL, or a non-HTTPS gateway URL - fails at startup rather than at first request.
- `GET /api/health` = process alive, nothing more (never reveals the gateway URL or other configuration). `GET /api/readiness` = the gateway is actually reachable right now (calls the gateway's own anonymous `/healthz`, never a billed call, 3s timeout); returns 503 `not_ready` if unreachable.

## Change rules

- Preserve the health response and existing behavior unless a task explicitly changes them.
- Keep fitness/nutrition domain logic and application contracts separate from AI-provider transport. The backend may coordinate with the Personal AI Gateway through our own contract; it must not embed Copilot-wrapper details.
- New endpoints handling personal or AI data require an explicit authentication and authorization design. Do not expose sensitive endpoints anonymously.
- Prefer versioned JSON APIs, explicit schemas, boundary validation, stable error shapes, and provider-neutral domain types.
- Minimize logging of health data, food images, prompts, and model responses. Never log credentials or tokens.
- Read configuration from server-side environment variables or a managed secret store. Never commit `.env`, `local.settings.json`, `.venv`, tokens, credentials, caches, or generated artifacts.
- Keep changes small and supply focused tests for changed behavior.

## Timeout hierarchy

Each layer's timeout must be strictly larger than the one it wraps, so an outer layer never aborts before an inner layer can return its own normalized timeout error. Recommended production values (real Copilot calls observed to take tens of seconds):

| Layer | Setting | Recommended production value |
| --- | --- | --- |
| Gateway provider call | `AI_PROVIDER_TIMEOUT_SECONDS` (gateway) | 90s |
| Backend → gateway HTTP call | `AI_GATEWAY_TIMEOUT_SECONDS` (backend) | 100s |
| iOS `URLSession` request | `FoodAnalysisService.timeoutInterval` | 110s (current default) |

The 10s code defaults on both `AI_PROVIDER_TIMEOUT_SECONDS` and `AI_GATEWAY_TIMEOUT_SECONDS` are tuned for `FakeProvider`/fast local iteration, not real Copilot calls - a real deployment must override both. See `ai-gateway/README.md` for the gateway side of this table.

## Production networking

- `AI_GATEWAY_BASE_URL` must be an explicit, non-`localhost` `https://` URL when `APP_ENV=production` (`config.validate_config()` fails closed otherwise). Local development may keep using `http://127.0.0.1:8000`.
- Intended production topology: `iPhone -> HTTPS Azure Functions (public, authenticated via BACKEND_API_KEY) -> private/restricted gateway (authenticated via GATEWAY_SERVICE_TOKEN, HTTPS) -> Copilot CLI runtime (never exposed)`. Only the Azure Functions backend is a public endpoint; the gateway must never be reachable from the public internet without authentication - restrict it with Container Apps ingress rules/a private endpoint/VNet integration, not just this application-level token.

## Validation

- After Python/backend changes, run the relevant test suite in a clean or ignored virtual environment.
- Verify that the Functions app imports and that the health endpoint still returns HTTP 200 with `{"status": "ok"}`.
- If no automated test covers the change, document and run an appropriate local health check.

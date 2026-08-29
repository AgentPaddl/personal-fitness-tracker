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
  - The uploaded image is never persisted or logged; it exists only in memory for the duration of the one gateway call.
- The route fails closed by default: it only serves requests when `APP_ENV=development` is explicitly set (see `config.py`), returning 403 otherwise. This is a temporary development-only allowance until real authentication is implemented, and is layered on top of the gateway's own independent fail-closed auth.
- `function_app.py` calls `config.validate_config()` at import time so an invalid gateway URL or out-of-bounds timeout fails at startup rather than at first request.

## Change rules

- Preserve the health response and existing behavior unless a task explicitly changes them.
- Keep fitness/nutrition domain logic and application contracts separate from AI-provider transport. The backend may coordinate with the Personal AI Gateway through our own contract; it must not embed Copilot-wrapper details.
- New endpoints handling personal or AI data require an explicit authentication and authorization design. Do not expose sensitive endpoints anonymously.
- Prefer versioned JSON APIs, explicit schemas, boundary validation, stable error shapes, and provider-neutral domain types.
- Minimize logging of health data, food images, prompts, and model responses. Never log credentials or tokens.
- Read configuration from server-side environment variables or a managed secret store. Never commit `.env`, `local.settings.json`, `.venv`, tokens, credentials, caches, or generated artifacts.
- Keep changes small and supply focused tests for changed behavior.

## Validation

- After Python/backend changes, run the relevant test suite in a clean or ignored virtual environment.
- Verify that the Functions app imports and that the health endpoint still returns HTTP 200 with `{"status": "ok"}`.
- If no automated test covers the change, document and run an appropriate local health check.

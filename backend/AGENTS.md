# Backend agent instructions

These instructions apply to everything under `backend/`.

## Current component

- Azure Functions application targeting Python 3.13, organized as blueprints registered from `function_app.py`.
- `GET /api/health` still returns `{"status": "ok"}` and must keep doing so.
- `POST /api/food-analysis` forwards a food description to the Personal AI Gateway through `gateway_client.py`, validates against the backend-owned schemas in `schemas.py`, and returns only the mapped public estimate (never the gateway's raw JSON). It works locally against the gateway's `FakeProvider` path; it does not call any AI provider directly.
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

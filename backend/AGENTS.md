# Backend agent instructions

These instructions apply to everything under `backend/`.

## Current component

- Azure Functions application targeting Python 3.13, organized as blueprints registered from `function_app.py`.
- `GET /api/health` still returns `{"status": "ok"}` and must keep doing so.
- `POST /api/food-analysis` forwards a food description to the Personal AI Gateway through `gateway_client.py` and returns the gateway's structured estimate. It works locally against the gateway's `FakeProvider` path; it does not call any AI provider directly.
- The current function app uses anonymous HTTP authorization. Do not treat that as sufficient for future fitness, nutrition, or AI endpoints. The food-analysis route is a development-time exception explicitly marked as such; add real authentication before any non-local exposure.

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

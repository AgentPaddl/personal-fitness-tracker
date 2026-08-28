# Personal AI Gateway

This is the server-side, provider-independent AI boundary. It exposes a small FastAPI application under `app/` with a provider-neutral `StructuredGenerationProvider` interface, a deterministic `FakeProvider` used for local development and tests, and the first use case: text food analysis.

The production provider adapter targets the official GitHub Copilot SDK, run through the Copilot CLI in headless/server mode. That adapter is **not implemented yet**. `trsdn/github_copilot_openai_api_wrapper` is not part of the production architecture. No provider-specific contract leaks into the public gateway API or the iOS app.

## Local development

```bash
cd ai-gateway
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
APP_ENV=development GATEWAY_DEV_AUTH_BYPASS=true AI_PROVIDER=fake \
  uvicorn app.main:app --reload --port 8000
```

The gateway fails closed by default: it will not start (or will reject all
`/v1/*` requests) unless `APP_ENV=development` and `GATEWAY_DEV_AUTH_BYPASS`
are both set explicitly, as shown above. `GET /healthz` remains anonymous
and available regardless of configuration. See `.env.example` for all
settings, including the server-side `FOOD_TEXT_MODEL_PURPOSE` model-routing
key (never exposed through the public API).

## Tests

```bash
cd ai-gateway
pytest
```

## Configuration

Configuration names are documented in `.env.example`. Copy that file to an untracked `.env` only on the server/development machine and supply real values there. No credentials belong in this repository.

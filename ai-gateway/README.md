# Personal AI Gateway

This is the server-side, provider-independent AI boundary. It exposes a small FastAPI application under `app/` with a provider-neutral `StructuredGenerationProvider` interface and the first use case: text food analysis.

Two providers are implemented:

- **`FakeProvider`** — deterministic, schema-driven, credential-free. Used for local development by default and for all normal automated tests.
- **`GitHubCopilotProvider`** — the real provider, wrapping the official [GitHub Copilot SDK for Python](https://github.com/github/copilot-sdk) (`github-copilot-sdk`), which drives the Copilot CLI in headless/server mode. Both are selected purely through server-side configuration (`AI_PROVIDER`); the public API never exposes which one is active, or any model/provider identifier. `trsdn/github_copilot_openai_api_wrapper` is not part of the production architecture and is not used.

## Local development (FakeProvider — no credentials)

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

## Using the real GitHub Copilot provider

### One-time local authentication

The gateway never stores or requests Copilot/GitHub credentials itself. It
delegates entirely to the Copilot CLI's own documented authentication. To
authenticate locally, run (one time, interactively, outside the gateway):

```bash
cd ai-gateway
source .venv/bin/activate
python -m copilot download-runtime   # first time only: fetches the CLI binary
copilot                              # launches the CLI; it auto-bundles with the SDK
```

Inside the interactive `copilot` session, run the `/login` slash command and
follow the on-screen instructions (opens a GitHub device-code flow in your
browser). This stores your session under `~/.copilot`; the gateway process
picks it up automatically afterwards (`use_logged_in_user` is the SDK
default). No token is ever pasted into this repository, `.env`, or chat.

Alternative (no interactive login): set `COPILOT_GITHUB_TOKEN` (or the
SDK's own `GH_TOKEN`/`GITHUB_TOKEN`) to a fine-grained PAT with the
"Copilot Requests" permission. Still never commit it; use an untracked
`.env` or your shell environment only.

### Model routing configuration

`AI_PROVIDER=copilot` additionally requires `COPILOT_MODEL_ROUTES_JSON`, a
JSON object mapping every configured model-routing purpose (e.g.
`food_text_v1`, from `FOOD_TEXT_MODEL_PURPOSE`) to a concrete Copilot model
id. There is no default mapping and no silent fallback to another model:

```bash
export COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5"}'
```

`GET /readyz` validates that the configured model id is actually returned
by the CLI's `list_models()` and that the CLI reports an authenticated
session, without performing a billed generation call.

### Running the gateway against the real provider

```bash
cd ai-gateway
source .venv/bin/activate
APP_ENV=development GATEWAY_DEV_AUTH_BYPASS=true AI_PROVIDER=copilot \
  COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5"}' \
  uvicorn app.main:app --port 8000
```

### Runtime lifecycle

`GitHubCopilotProvider` starts one long-lived `CopilotClient` (which manages
one Copilot CLI process) lazily on first use and reuses it across requests;
it does not spawn a new CLI process per food-analysis call. Each request
creates a short-lived SDK *session* on top of that shared client and always
disconnects it afterwards (even on error/timeout). The client itself is
stopped on gateway shutdown.

### Structured output strategy

The provider defines a single terminal tool, `submit_structured_result`,
whose parameter schema is exactly the use case's requested JSON schema, and
instructs the model to answer only by calling it once
(`Tool(..., is_terminal=True)` ends the turn on a successful call). The
provider itself never knows this is a "food" schema; `FoodAnalysisUseCase`
owns the schema, instructions, and the authoritative Pydantic validation of
whatever the tool call returns — the provider's output is never trusted
merely because the SDK produced it.

### Opt-in integration/smoke tests

Normal test runs (`pytest`) never contact Copilot. To run the real
integration tests and one real local smoke test (after completing the
one-time login above):

```bash
RUN_COPILOT_INTEGRATION_TESTS=1 \
  COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5"}' \
  pytest tests/test_copilot_integration.py -v
```

This exercises `check_ready()`, a direct provider call with a German food
description, and a full local smoke test
(`backend GatewayClient -> real HTTP socket -> independent gateway process
(AI_PROVIDER=copilot) -> GitHubCopilotProvider -> real Copilot CLI/model`).
Nothing is persisted.

## Tests

```bash
cd ai-gateway
pytest
```

## Configuration

Configuration names are documented in `.env.example`. Copy that file to an untracked `.env` only on the server/development machine and supply real values there. No credentials belong in this repository.

## Remaining work for production (Azure)

This phase only prepares the code to run the real Copilot SDK provider
locally. Not yet decided/implemented: the production authentication
mechanism (device flow vs. server-to-server installation token vs. another
documented option), container packaging for Azure Container Apps, secret
storage (e.g. Key Vault/managed identity), and network isolation for the
Copilot CLI process in a deployed environment.

# Personal AI Gateway

This is the server-side, provider-independent AI boundary. It exposes a small FastAPI application under `app/` with a provider-neutral `StructuredGenerationProvider` interface and the first use case: text food analysis.

Three providers are implemented:

- **`FakeProvider`** — deterministic, schema-driven, credential-free. Used for local development by default and for all normal automated tests.
- **`AzureOpenAIProvider`** - local-only Azure v1 Chat Completions adapter. Text,
  inline JPEG/PNG images and strict structured output, tested through mocked SDK
  HTTP transport. No Copilot fallback; production selection is rejected.
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

## Local Azure API adapter (2026-09-17)

The later pilot admission implementation is documented in the
[operations runbook](../docs/operations-runbook.md#protected-two-person-pilot-local-implementation).
It is opt-in, uses a single Azure Table admission authority, and does not remove
the production guard below. Pilot mode accepts no Copilot/fake fallback and no
development authentication bypass. Offline mocks are not a deployed Table or
Easy Auth integration certification.

This is the first local package from the
[paid API decision](../docs/architecture.md#paid-api-migration-decision-2026-09-17),
not a production switch or authorization for paid/personal-data calls. Existing
Copilot dependencies, container runtime and production routing remain for the
later migration package. The new adapter cannot fall back to them.

Configuration is explicit and server-only:

| Setting | Local Azure behavior |
| --- | --- |
| `AI_PROVIDER` | Set `azure_openai` explicitly. No automatic selection or substitution. |
| `APP_ENV` | Only `development` or `test`; `production` rejects this adapter. Existing gateway authentication still applies. |
| `AZURE_OPENAI_ENDPOINT` | Required Azure HTTPS resource endpoint, such as `https://RESOURCE.openai.azure.com`; normalized to `/openai/v1/`. Only public Azure OpenAI/Foundry resource domains; no credentials, query, fragment, arbitrary proxy or deployment URL. |
| `AZURE_OPENAI_API_KEY` | Required only for a separately authorized real call. Tests inject a non-secret dummy key and mock transport. Never paste real credentials into logs, chat or tracked files. No ambient OpenAI API key fallback. |
| `AZURE_OPENAI_MODEL_ROUTES_JSON` | Required purpose-to-deployment mapping for both configured text/image purposes, e.g. `{"food_text_v1":"text-deployment","food_image_v1":"vision-deployment"}`. Values are deployment names, not a hard-coded model family. Missing, malformed, blank or duplicate mappings fail closed. |
| `AI_PROVIDER_MAX_OUTPUT_TOKENS` | Default 2000, local safety range 1-32768. Request-level caps may lower, never raise it. The chosen deployment must support the configured cap. |
| `AI_PROVIDER_TIMEOUT_SECONDS` | Existing timeout setting, forwarded to SDK and bounded by async deadline; the use case retains its outer timeout. |
| `AZURE_OPENAI_PRICES_JSON` | Optional versioned USD table below. Malformed configured prices fail closed; absence, unmapped deployment or a returned-model mismatch produces unknown cost. |

Price table shape (illustrative server configuration, not a verified account quote):

```json
{
  "version": "azure-eu-standard-2026-09-17",
  "currency": "USD",
  "deployments": {
    "text-deployment": {
      "model": "gpt-4.1-mini-2025-04-14",
      "input_per_million": "0.44",
      "cached_input_per_million": "0.11",
      "output_per_million": "1.76"
    }
  }
}
```

Each price entry binds a deployment to the **exact returned model string**.
Confirm that string and the deployment's region/SKU/rates before relying on the
estimate; the example does not assume what Azure will return. No alias guessing
or default prices. Estimates use `Decimal`: noncached input plus cached input
plus all completion tokens. Reasoning tokens are a subset of completion tokens,
not an additional charge. Missing/inconsistent usage, missing cache breakdown,
missing returned model or unknown price returns `estimated_cost_usd=None`, not
zero. `usage_known` describes valid input/output totals, not necessarily all
optional details. Actual provider billing remains authoritative.

The adapter derives a separate closed, all-required schema from the caller's
schema. It supports the current object/array/scalar, nullable/`anyOf`, and local
`$defs`/`$ref` shapes; unsupported constructs fail before dispatch. Provider-only
schema relaxation removes Azure-unsupported numeric/string/array bounds and
defaults without mutating the original. After parsing strictly (no prose
extraction, duplicate keys, non-finite numbers or repair generation), it validates
both the transport structure and the original JSON schema. `FoodAnalysisUseCase`
still performs authoritative Pydantic validation. Public schemas, estimate
envelope, input modes and refinement prompts are unchanged.

One adapter invocation makes at most one SDK/HTTP attempt: `max_retries=0`,
`n=1`, no redirects, no tools, `store=false`, no streaming or stateful API objects.
Refusals/content filtering, truncation, invalid data, timeouts, authentication,
unavailable deployment and rate limits map to existing public-safe errors.
Missing usage does not invalidate an otherwise valid estimate, but its cost is
unknown. No model/provider fallback or additional repair call occurs.

`StructuredGenerationResult.metadata` and normalized errors carry internal
deployment/model/request identifiers, elapsed time, status, usage and versioned
price estimate when available. Usage is processed before output validation, so
invalid paid output is not silently treated as free. The use case preserves
metadata on its own validation error; success metadata is not serialized into
the public response. External cancellation is re-raised and recorded as unknown
usage; it does not prove provider computation/billing stopped.

Logs contain only status/duration, token counts and cost/price version, alongside
the existing request logs. No inputs, corrections, images, output values or raw
SDK exceptions. The SDK's payload-capable `openai._base_client` logger is disabled
process-wide by this adapter, including DEBUG mode; do not re-enable it. Internal
metadata is not a durable accounting ledger or cross-request idempotency record.

Production protection is independent of readiness: settings/factory reject
`AI_PROVIDER=azure_openai` in production before constructing an SDK client.
Additionally, every `generate()` checks the process's current `APP_ENV`; only
explicit `development` or `test` permits dispatch. Missing/unknown environments
and `production` raise the normalized `service_not_ready` error before handling
input or calling the SDK, including directly constructed or reused adapters.
A production POST with invalid Azure configuration is rejected by the existing
configuration error boundary (`500 internal_error`); even if that factory boundary
is bypassed with an existing adapter, dispatch is rejected (`503 service_not_ready`).
Both paths are tested without a preceding readiness request.

`check_ready()` deliberately returns false without network access: this local
package does not claim a verified account, quota, model/vision capability or
regional deployment. `/readyz` therefore stays 503 for Azure; `/healthz` remains
the existing liveness check. Client shutdown is bounded to one second. Enabling
real readiness, funding, privacy approval, token-input budgeting, distributed
admission activation and API-only rollback belong to later approved work.
The pilot code now includes distributed admission/idempotency and a conservative
full-context cost reserve, but its cloud integration and deployment mapping have
not been verified against an account.

Offline verification with the installed gateway test dependencies:

```bash
RUN_COPILOT_INTEGRATION_TESTS=0 .venv/bin/python -m pytest -q
```

The Azure tests use the real pinned `openai` serializer with `httpx2.MockTransport`;
they never read a real key or contact Azure. Backend regression tests also cover
the mocked Azure path through the existing public mapping. No iOS or persistence
change is needed for this package.

## Using the real GitHub Copilot provider (existing deployment)

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
`food_text_v1`, `food_image_v1` - see below) to a concrete Copilot model
id. There is no default mapping and no silent fallback to another model:

```bash
export COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"}'
```

Available model ids change over time and depend on your Copilot plan; call
`client.list_models()` (or check `GET /readyz`) rather than assuming a
specific id is available. Image analysis (`food_image_v1`) requires a
**vision-capable** model; `/readyz` fails if the configured model does not
report, via the SDK's own `list_models()` capability data: vision support,
`supported_media_types` covering both `image/jpeg` and `image/png`,
`max_prompt_images >= 1`, and an explicit, numeric `max_prompt_image_size`
at least as large as this gateway's own 3 MiB image limit. SDK 1.0.11 does
not document a "missing means unlimited" semantic for `max_prompt_image_size`
(or any other capability field checked here) - a missing/`None` value is
treated as unknown/incompatible, not permissive, and any missing or
ambiguous capability field fails closed rather than assuming compatibility.
It never silently proceeds with, or routes to, a different model. As of
2026-08-29, `gpt-5-mini` is verified to satisfy all of these (its reported
`max_prompt_image_size` is exactly 3145728 bytes = 3 MiB).

`GET /readyz` validates that the configured model id is actually returned
by the CLI's `list_models()` and that the CLI reports an authenticated
session, without performing a billed generation call.

### Running the gateway against the real provider

Real Copilot calls typically take tens of seconds — much longer than
`FakeProvider`. Set `AI_PROVIDER_TIMEOUT_SECONDS` accordingly (the default,
10s, is tuned for the fake provider and will cause spurious
`provider_timeout` errors against a real model):

```bash
cd ai-gateway
source .venv/bin/activate
APP_ENV=development GATEWAY_DEV_AUTH_BYPASS=true AI_PROVIDER=copilot \
  COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"}' \
  AI_PROVIDER_TIMEOUT_SECONDS=90 \
  uvicorn app.main:app --port 8000
```

### Image analysis

`POST /v1/food-analysis` accepts `food_description`, `image`, or both (at
least one is required). `image` is `{"media_type": "image/jpeg" |
"image/png", "data_base64": "..."}` - an inline base64 blob, capped at 3 MiB
decoded and validated as actually-decodable base64. This is the gateway's
own internal contract (the backend's *public* API instead accepts
`multipart/form-data`; see `backend/AGENTS.md`).

Image requests are routed to a separate model purpose,
`FOOD_IMAGE_MODEL_PURPOSE` (default `food_image_v1`), never the text
purpose - a vision-incapable model is never silently used for image input.
`GitHubCopilotProvider` translates the image into the SDK's inline
`BlobAttachment` (base64, no temporary files); attachments of any other
kind, or an empty payload, are rejected before a session is even created.
Nothing about the image (bytes, metadata) is logged or persisted by the
gateway; it exists only for the duration of one generation call.

### Opt-in real image integration test

The same opt-in gate covers a real image-analysis smoke test using a
small, synthetic, deterministically-generated PNG (built in-test via
`struct`/`zlib` - no bundled photo, no user data):

```bash
RUN_COPILOT_INTEGRATION_TESTS=1 \
  COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5-mini", "food_image_v1": "gpt-5-mini"}' \
  pytest tests/test_copilot_integration.py -v
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
  COPILOT_MODEL_ROUTES_JSON='{"food_text_v1": "gpt-5-mini"}' \
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

## Timeout hierarchy

`AI_PROVIDER_TIMEOUT_SECONDS` (gateway) must stay strictly below the backend's `AI_GATEWAY_TIMEOUT_SECONDS`, which must stay strictly below the iOS client's request timeout - otherwise an outer layer aborts before this gateway's own normalized timeout error can ever be returned. Recommended production values: gateway 90s < backend 100s < iOS 110s. See `backend/AGENTS.md` for the full table.

## Concurrency limit

`AI_PROVIDER_MAX_CONCURRENCY` (default 2) caps simultaneous Copilot CLI sessions via a fail-fast in-memory counter (`app/concurrency.py`) - never a queue. A request beyond the limit gets an immediate `503 service_saturated` rather than waiting or being buffered.

## Production deployment (Azure Container Apps)

A `Dockerfile` is provided, targeting Azure Container Apps. It has **not**
been built or deployed in this repository (no Docker available in the
authoring environment) - treat it as a documented starting point that
needs verification before real use, not a proven artifact.

- **Runtime**: Python 3.13, matching local development.
- **Copilot CLI**: fetched at *build* time (`python -m copilot download-runtime`
  in the `Dockerfile`) so the running container has no first-request
  download dependency.
- **Authentication with Copilot**: the interactive `copilot`/`/login`
  device-code flow used for local development has no headless equivalent.
  A deployed container **must** use `COPILOT_GITHUB_TOKEN` (a
  non-interactive, server-to-server GitHub token with the "Copilot
  Requests" permission), injected as a Container Apps secret/environment
  variable - never baked into the image.
- **Persistent storage**: none required. `COPILOT_GITHUB_TOKEN`-based auth
  needs no session persisted across restarts; the CLI's own runtime
  state/logs live under `$HOME` in the container's default ephemeral,
  writable filesystem.
- **Startup/readiness**: the app fails closed at import time
  (`app.config.Settings.validate()`) on any invalid/missing required
  production configuration (`GATEWAY_SERVICE_TOKEN`, a valid
  `COPILOT_MODEL_ROUTES_JSON`, etc.). `GET /readyz` additionally verifies
  real Copilot auth and vision-capable model routing without a billed call.
- **Graceful shutdown**: the FastAPI lifespan hook (`app/main.py`) closes
  the long-lived `CopilotClient`/CLI process on shutdown.
- **Memory**: budget at least 512Mi; image requests hold a decoded payload
  up to `MAX_IMAGE_BYTES` (3 MiB) plus normal Pillow/model-call overhead,
  multiplied by `AI_PROVIDER_MAX_CONCURRENCY` in the worst case.
- **Network isolation**: the gateway is never a public, client-facing API.
  Restrict Container Apps ingress to the backend only (internal ingress /
  a private endpoint / VNet integration) - `GATEWAY_SERVICE_TOKEN` is
  defense-in-depth on top of that network boundary, not a substitute for it.

## Remaining work for production (Azure)

This phase prepares the code and container image to run the real Copilot
SDK provider in production, but does not perform a real deployment. Not
yet done: actually building/pushing the container image, provisioning the
Container Apps environment, configuring secrets (Key Vault/managed
identity vs. plain Container Apps secrets), configuring restricted
ingress/networking, and a real end-to-end smoke test against a deployed
instance.

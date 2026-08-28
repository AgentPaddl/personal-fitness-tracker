# Architecture

## Purpose and current status

This repository contains a private, non-commercial personal fitness and nutrition tracker. The current product consists of an iOS app and a minimal Azure Functions backend. The Personal AI Gateway described below is the target V2 architecture and is **planned, not yet implemented**.

## Current monorepo layout

| Path | Current responsibility | Status |
| --- | --- | --- |
| `ios/` | SwiftUI client and local SwiftData persistence | Working application |
| `backend/` | Azure Functions Python 3.13 application API | Working `GET /api/health` endpoint only |
| `ai-gateway/` | Future provider-independent server-side AI boundary | Placeholder; no AI runtime implemented |
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
    +--> Copilot SDK adapter (production; not implemented yet)
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
- Uses replaceable provider adapters behind the `StructuredGenerationProvider` interface. The deterministic `FakeProvider` is implemented for local development and tests. The production adapter targets the official GitHub Copilot SDK via the Copilot CLI in headless/server mode and is not implemented yet.
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

### Phase 2 — provider-neutral gateway foundation (implemented)

- Implemented the gateway core (FastAPI), configuration, request/response schemas with numeric bounds, normalized errors, and the `StructuredGenerationProvider` adapter interface.
- Implemented the deterministic `FakeProvider` and the first `FoodAnalysisUseCase`; tests use the fake provider and do not require real credentials.
- Modularized the Azure Functions backend into blueprints, added an internal gateway HTTP client, and a food-analysis backend route that works end-to-end against the gateway's `FakeProvider` path locally.
- Gateway authentication is not implemented yet; the request path is structured so authentication can be added without reshaping the contracts, and any bypass is explicitly marked as development-only.
- Provider/model selection remains configurable server-side; only `fake` is currently a valid provider selection.

### Phase 3 — Copilot SDK adapter

- Run the Copilot CLI in headless/server mode as an internal-only process reachable solely by the gateway.
- Implement a `StructuredGenerationProvider` adapter around the official GitHub Copilot SDK without exposing SDK/CLI details to backend domain logic or the iOS client.
- Add opt-in integration checks and operational secret management. `trsdn/github_copilot_openai_api_wrapper` is not part of this plan.

### Phase 4 — food analysis workflow

- Implement text analysis first, then image analysis, using structured nutrition-estimate schemas.
- Add user review/confirmation before appropriate persistence.
- Verify privacy controls, failure handling, and observability without sensitive-payload logging.

### Phase 5 — expansion and provider portability

- Add activity/training assistance and other personal AI services as separate domain contracts.
- Add or switch providers through adapters and server-side routing without iOS provider changes.
- Revisit schemas, privacy controls, and data migrations incrementally with each use case.

## Change and validation policy

Changes should be small and reviewable, with explicit acceptance criteria. Build `ios/Trainingsplan.xcodeproj` after Swift changes, with DerivedData outside the repository. After backend changes, run relevant tests and verify the health endpoint. Any SwiftData schema change requires an explicit non-destructive migration plan that preserves existing user data.

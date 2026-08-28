# Copilot instructions

## Project

This private monorepo is a non-commercial personal iOS fitness and nutrition tracker. Its current stack is a SwiftUI/SwiftData iOS app and an Azure Functions backend using Python 3.13. A provider-independent personal AI gateway is planned but is not implemented yet.

## Working rules

- Preserve existing iOS and backend behavior unless the task and its acceptance criteria explicitly require a change.
- Keep changes small, focused, and reviewable. State clear acceptance criteria and avoid unrelated cleanup.
- Inspect the nearest `AGENTS.md` before changing files under `ios/`, `backend/`, or `ai-gateway/`.
- Never commit secrets, credentials, OAuth/access/refresh tokens, private keys, `.env`, `local.settings.json`, `.venv`, Python caches, Xcode user data, DerivedData, or other build artifacts.
- Treat health, fitness, nutrition, images, and prompts as sensitive personal data. Minimize collection, transfer, retention, and logging.
- After Swift changes, build `ios/Trainingsplan.xcodeproj` with DerivedData outside the repository.
- After backend changes, run relevant tests and verify the health endpoint. Add focused tests when behavior changes.
- Do not implement product features or AI integration unless the task explicitly requests them.

## Data and API safety

- SwiftData is the current local persistence layer. Avoid destructive migrations and preserve existing user data. Prefer additive, explicitly planned schema evolution with migration and rollback considerations.
- The iOS app may call only our authenticated application APIs. It must never contain GitHub or Copilot credentials, provider tokens, provider-specific base URLs, or wrapper credentials.
- Prefer versioned, structured JSON contracts with explicit request and response schemas. Validate data at component boundaries and return actionable errors without leaking secrets.
- AI-generated values are estimates. Where an estimate may be persisted or used as health/fitness data, design for user review and confirmation first.

## Planned AI architecture

Keep domain logic independent of provider-specific transport:

`iOS client -> Fitness API/domain backend -> Personal AI Gateway -> provider adapter(s)`

The production provider adapter targets the official GitHub Copilot SDK, run through the Copilot CLI in headless/server mode. `trsdn/github_copilot_openai_api_wrapper` is not part of the production architecture and must not be reintroduced without an explicit decision. The adapter must remain replaceable behind the gateway's provider-neutral `StructuredGenerationProvider` abstraction and must sit behind our own authenticated, server-side API; never expose it directly to the public internet. Keep provider routing and model selection in server-side configuration rather than hard-coding them in the iOS app.

Initial planned use cases are food text/image analysis into structured nutrition estimates, followed later by activity/training assistance and other personal AI services. Phase 2 implemented the gateway/backend foundation with a deterministic `FakeProvider`. Phase 3 implemented the real `GitHubCopilotProvider` (official GitHub Copilot SDK) for local use; production deployment and authentication are not decided yet.

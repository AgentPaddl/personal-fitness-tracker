# Architecture

## Boundaries

1. The iOS app owns the user experience and local SwiftData persistence.
2. The backend exposes authenticated fitness/nutrition APIs and coordinates durable server-side data.
3. The AI gateway is the only component allowed to communicate with an AI provider. It exposes an application-specific API rather than a provider-specific API.

```text
iOS app -> authenticated backend/API -> personal AI gateway -> AI provider adapter
                                                        -> GitHub Copilot wrapper (initial)
                                                        -> future providers
```

## AI gateway contract

The first adapter is planned for `github_copilot_openai_api_wrapper`. Keep its OpenAI-compatible details behind an adapter interface so the application contract remains stable when the provider changes.

The iOS app must never contain provider base URLs, access tokens, refresh tokens, client secrets, or wrapper credentials. Server secrets come from environment variables locally and a managed secret store in deployment. Log neither prompts containing private health data nor credentials by default.

## Recommended next increments

- Add authentication before exposing personal data outside localhost.
- Define versioned request/response schemas for fitness, nutrition, and AI coaching.
- Add explicit consent, retention, deletion, and export behavior for health-related data.
- Add unit/contract tests before connecting the first AI provider.

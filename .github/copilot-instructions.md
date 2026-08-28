# Repository guidance

- Preserve the monorepo boundaries: `ios/`, `backend/`, `ai-gateway/`, and `docs/`.
- Never add credentials, tokens, private health data, `.env`, `local.settings.json`, or Xcode user state to Git.
- Keep AI-provider details behind the server-side gateway; the iOS app may call only our own authenticated API.
- Prefer small, tested changes. Validate the iOS target and relevant Python tests before considering a change complete.
- Treat fitness and nutrition information as sensitive personal data and minimize collection, logging, and retention.

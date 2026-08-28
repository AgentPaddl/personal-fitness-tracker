# Personal AI Gateway

This directory will contain the server-side provider-independent AI boundary. The initial provider adapter will target `github_copilot_openai_api_wrapper`, but no provider-specific contract should leak into the iOS app.

Configuration names are documented in `.env.example`. Copy that file to an untracked `.env` only on the server/development machine and supply real values there. No credentials belong in this repository.

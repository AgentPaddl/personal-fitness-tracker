# Personal Fitness Tracker

Private monorepo for the iOS fitness and nutrition tracker, its backend, and a provider-independent personal AI gateway.

## Structure

- `ios/` — SwiftUI/SwiftData iOS application
- `backend/` — application API (currently Azure Functions/Python)
- `ai-gateway/` — server-side, provider-independent AI boundary
- `docs/` — architecture and migration notes
- `.github/` — repository and Copilot guidance

## Security

Provider credentials and tokens belong only in server-side environment variables or a managed secret store. Never place credentials in the iOS app, Git history, tracked configuration, or client-visible responses.

## Local validation

Open `ios/Trainingsplan.xcodeproj` in Xcode. For the backend, create a virtual environment and install `backend/requirements.txt`; do not commit the environment or `local.settings.json`.

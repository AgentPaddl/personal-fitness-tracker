# iOS agent instructions

These instructions apply to everything under `ios/`.

## Current component

- SwiftUI application in `ios/Trainingsplan/`.
- SwiftData models provide local persistence for fitness, workout, weight, goal, and nutrition data.
- The Xcode project is `ios/Trainingsplan.xcodeproj`.

## Change rules

- Preserve current screens, navigation, persistence, import/export, and other behavior unless a task explicitly changes them.
- Follow established SwiftUI and SwiftData patterns in the project. Prefer narrowly scoped changes over broad refactors.
- Treat model changes as data migrations. Do not delete or repurpose persisted fields or make destructive schema changes without an explicit migration plan, compatibility review, and task approval. Existing personal data must survive updates.
- Keep domain and presentation logic independent of any AI provider SDK or transport.
- Never add GitHub/Copilot credentials, OAuth tokens, provider secrets, wrapper URLs, or provider-specific model identifiers to the app or its bundled configuration.
- Send sensitive data only to our authenticated application API and only when required by an explicitly approved feature.
- AI-derived nutrition or activity values are estimates; present them for review/confirmation before persistence where appropriate.

## Validation

- After any Swift or Xcode project change, build `ios/Trainingsplan.xcodeproj` using the existing `Trainingsplan` scheme and place DerivedData outside the repository.
- Run relevant tests when available and manually check the changed flow when automated coverage is absent.
- Do not commit DerivedData, Xcode user data, generated archives, or other build output.

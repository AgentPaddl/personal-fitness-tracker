# Migration record

## Selected sources

- iOS: the inner `Trainingsplan.xcodeproj` located beside the complete Swift source folder.
- Backend: `FitnessTrackerBackend`, excluding its nested Git metadata, virtual environment, caches, editor state, and `local.settings.json`.

The original directories remain untouched until the copies build and run successfully from this monorepo. Nested source-repository history is intentionally not copied; the monorepo owns future history.

## Validation checklist

- Confirm Xcode lists the `Trainingsplan` scheme from `ios/Trainingsplan.xcodeproj`.
- Build the iOS app with DerivedData outside the repository.
- Import the Azure Functions app in a clean Python environment.
- Invoke the health handler or run Azure Functions locally and verify a JSON `status: ok` response.
- Confirm Git does not track credentials, local settings, virtual environments, Xcode user data, or build output.

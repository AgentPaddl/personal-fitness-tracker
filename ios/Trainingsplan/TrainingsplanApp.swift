import SwiftUI
import SwiftData

@main
struct TrainingsplanApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    // MSAL's redirect callback (msauth.<bundle-id>://auth,
                    // see Trainingsplan-Info.plist) must be forwarded
                    // exactly this way for interactive sign-in to ever
                    // complete - see MSALEntraTokenAcquirer.handleRedirect.
                    _ = MSALEntraTokenAcquirer.handleRedirect(url: url)
                }
        }
        .modelContainer(for: [
            Exercise.self,
            WorkoutSession.self,
            ExercisePerformance.self,
            WorkoutSet.self,
            Activity.self,
            FoodEntry.self,
            WeightEntry.self,
            UserGoals.self,
            FoodPreset.self
        ])
    }
}

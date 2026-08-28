import SwiftUI
import SwiftData

@main
struct TrainingsplanApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
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

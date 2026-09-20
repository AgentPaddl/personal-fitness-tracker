import Foundation
import SwiftData

@main
struct LegacyFoodStoreWriter {
    @MainActor
    static func main() throws {
        let url = URL(fileURLWithPath: CommandLine.arguments[1])
        let schema = Schema([Exercise.self, WorkoutSession.self, ExercisePerformance.self, WorkoutSet.self,
                             Activity.self, FoodEntry.self, FoodPreset.self, WeightEntry.self, UserGoals.self])
        let container = try ModelContainer(for: schema, configurations: ModelConfiguration(url: url))
        let context = ModelContext(container)
        let date = Date(timeIntervalSince1970: 1_000_000)
        let exercise = Exercise(name: "Legacy exercise", nextWeightIncreaseMarkedAt: date)
        let session = WorkoutSession(startedAt: date)
        let performance = ExercisePerformance(orderIndex: 0, exercise: exercise, workoutSession: session)
        let workoutSet = WorkoutSet(setNumber: 1, weightKg: 60, repetitions: 8, performance: performance)
        context.insert(exercise)
        context.insert(session)
        context.insert(performance)
        context.insert(workoutSet)
        for number in 1...3 {
            context.insert(FoodPreset(name: "Legacy favorite \(number)", calories: number * 100,
                proteinGrams: Double(number), carbsGrams: 20, fatGrams: 3, createdAt: date))
            context.insert(FoodEntry(date: date, name: "Legacy entry \(number)", calories: number * 100,
                proteinGrams: Double(number), carbsGrams: 20, fatGrams: 3, notes: "Synthetic legacy note"))
        }
        try context.save()
        print("Created populated legacy SQLite store from 6eac77e models.")
    }
}
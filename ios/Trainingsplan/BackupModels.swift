import Foundation

struct AppBackup: Codable {
    let exportDate: Date

    let exercises: [ExerciseBackup]
    let workoutSessions: [WorkoutSessionBackup]
    let activities: [ActivityBackup]
    let foodEntries: [FoodEntryBackup]
    let foodPresets: [FoodPresetBackup]
    let weightEntries: [WeightEntryBackup]
    let userGoals: UserGoalsBackup?
}

struct ExerciseBackup: Codable {
    let id: UUID
    let name: String
    let createdAt: Date
    let isArchived: Bool
}

struct WorkoutSessionBackup: Codable {
    let id: UUID
    let startedAt: Date
    let endedAt: Date?
    let durationMinutes: Int?
    let estimatedCalories: Int?
    let bodyWeightKg: Double?
    let isCompleted: Bool
    let performances: [ExercisePerformanceBackup]
}

struct ExercisePerformanceBackup: Codable {
    let exerciseID: UUID?
    let orderIndex: Int
    let sets: [WorkoutSetBackup]
}

struct WorkoutSetBackup: Codable {
    let setNumber: Int
    let weightKg: Double
    let repetitions: Int
}

struct ActivityBackup: Codable {
    let type: String
    let date: Date
    let durationMinutes: Int
    let estimatedCalories: Int
    let bodyWeightKg: Double?
    let notes: String?
}

struct FoodEntryBackup: Codable {
    let date: Date
    let name: String
    let calories: Int
    let proteinGrams: Double
    let carbsGrams: Double
    let fatGrams: Double
    let notes: String?
}

struct FoodPresetBackup: Codable {
    let name: String
    let calories: Int
    let proteinGrams: Double
    let carbsGrams: Double
    let fatGrams: Double
    let createdAt: Date
}

struct WeightEntryBackup: Codable {
    let date: Date
    let weightKg: Double
}

struct UserGoalsBackup: Codable {
    let calorieGoal: Int
    let proteinGoalGrams: Int
    let weeklyActivityGoal: Int
}

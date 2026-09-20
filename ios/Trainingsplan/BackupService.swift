import Foundation
import SwiftData
import FoodAnalysisKit

enum BackupService {

    static func createBackup(
        modelContext: ModelContext
    ) throws -> Data {

        let exercises = try modelContext.fetch(
            FetchDescriptor<Exercise>()
        )

        let workoutSessions = try modelContext.fetch(
            FetchDescriptor<WorkoutSession>()
        )

        let performances = try modelContext.fetch(
            FetchDescriptor<ExercisePerformance>()
        )

        let workoutSets = try modelContext.fetch(
            FetchDescriptor<WorkoutSet>()
        )

        let activities = try modelContext.fetch(
            FetchDescriptor<Activity>()
        )

        let foodEntries = try modelContext.fetch(
            FetchDescriptor<FoodEntry>()
        )

        let foodPresets = try modelContext.fetch(
            FetchDescriptor<FoodPreset>()
        )

        let weightEntries = try modelContext.fetch(
            FetchDescriptor<WeightEntry>()
        )

        let userGoals = try modelContext.fetch(
            FetchDescriptor<UserGoals>()
        )

        let exerciseBackups = exercises.map { exercise in
            ExerciseBackup(
                id: exercise.id,
                name: exercise.name,
                createdAt: exercise.createdAt,
                isArchived: exercise.isArchived,
                nextWeightIncreaseMarkedAtEpochSeconds: exercise.nextWeightIncreaseMarkedAt?.timeIntervalSince1970
            )
        }

        let workoutBackups = workoutSessions.map { session in

            let sessionPerformances = performances
                .filter { $0.workoutSession === session }
                .sorted { $0.orderIndex < $1.orderIndex }

            let performanceBackups = sessionPerformances.map { performance in

                let sets = workoutSets
                    .filter { $0.performance === performance }
                    .sorted { $0.setNumber < $1.setNumber }

                return ExercisePerformanceBackup(
                    exerciseID: performance.exercise?.id,
                    orderIndex: performance.orderIndex,
                    sets: sets.map {
                        WorkoutSetBackup(
                            setNumber: $0.setNumber,
                            weightKg: $0.weightKg,
                            repetitions: $0.repetitions
                        )
                    }
                )
            }

            return WorkoutSessionBackup(
                id: session.id,
                startedAt: session.startedAt,
                endedAt: session.endedAt,
                durationMinutes: session.durationMinutes,
                estimatedCalories: session.estimatedCalories,
                bodyWeightKg: session.bodyWeightKg,
                isCompleted: session.isCompleted,
                performances: performanceBackups
            )
        }

        let activityBackups = activities.map {
            ActivityBackup(
                type: $0.type,
                date: $0.date,
                durationMinutes: $0.durationMinutes,
                estimatedCalories: $0.estimatedCalories,
                bodyWeightKg: $0.bodyWeightKg,
                notes: $0.notes
            )
        }

        let foodEntryBackups = foodEntries.map {
            FoodEntryBackup(
                date: $0.date,
                name: $0.name,
                calories: $0.calories,
                proteinGrams: $0.proteinGrams,
                carbsGrams: $0.carbsGrams,
                fatGrams: $0.fatGrams,
                notes: $0.notes,
                valueOrigin: $0.valueOrigin,
                consumedQuantity: $0.consumedQuantity,
                consumedUnit: $0.consumedUnit
            )
        }

        let foodPresetBackups = foodPresets.map {
            FoodPresetBackup(
                name: $0.name,
                calories: $0.calories,
                proteinGrams: $0.proteinGrams,
                carbsGrams: $0.carbsGrams,
                fatGrams: $0.fatGrams,
                createdAt: $0.createdAt,
                baseQuantity: $0.baseQuantity,
                baseUnit: $0.baseUnit,
                valueOrigin: $0.valueOrigin,
                baseCalories: $0.baseCalories
            )
        }

        let weightBackups = weightEntries.map {
            WeightEntryBackup(
                date: $0.date,
                weightKg: $0.weightKg
            )
        }

        let goalsBackup: UserGoalsBackup?

        if let goals = userGoals.first {
            goalsBackup = UserGoalsBackup(
                calorieGoal: goals.calorieGoal,
                proteinGoalGrams: goals.proteinGoalGrams,
                weeklyActivityGoal: goals.weeklyActivityGoal
            )
        } else {
            goalsBackup = nil
        }

        let backup = AppBackup(
            exportDate: Date(),
            exercises: exerciseBackups,
            workoutSessions: workoutBackups,
            activities: activityBackups,
            foodEntries: foodEntryBackups,
            foodPresets: foodPresetBackups,
            weightEntries: weightBackups,
            userGoals: goalsBackup
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [
            .prettyPrinted,
            .sortedKeys
        ]

        encoder.dateEncodingStrategy = .iso8601

        return try encoder.encode(backup)
    }
    
    static func decodeBackup(from data: Data) throws -> AppBackup {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let backup = try decoder.decode(AppBackup.self, from: data)
        try validateProducts(in: backup)
        return backup
    }

    private static func validateProducts(in backup: AppBackup) throws {
        for preset in backup.foodPresets {
            if let origin = preset.valueOrigin, FoodProductOrigin(rawValue: origin) == nil {
                throw CocoaError(.fileReadCorruptFile)
            }
            if preset.baseQuantity == nil && preset.baseUnit == nil && preset.baseCalories == nil { continue }
            guard let quantity = preset.baseQuantity.flatMap(FoodProductBasis.parseQuantity),
                  let unit = preset.baseUnit.flatMap(FoodProductUnit.init(rawValue:)),
                  let origin = preset.valueOrigin.flatMap(FoodProductOrigin.init(rawValue:)),
                  let calories = FoodProductBasis.parseNumber(preset.baseCalories ?? String(preset.calories)),
                  preset.proteinGrams.isFinite, preset.carbsGrams.isFinite, preset.fatGrams.isFinite,
                  FoodProductBasis(quantity: quantity, unit: unit, origin: origin,
                    nutrition: .init(calories: calories, protein: Decimal(preset.proteinGrams),
                                     carbs: Decimal(preset.carbsGrams), fat: Decimal(preset.fatGrams))) != nil
            else { throw CocoaError(.fileReadCorruptFile) }
        }
        for entry in backup.foodEntries {
            if let origin = entry.valueOrigin, FoodProductOrigin(rawValue: origin) == nil {
                throw CocoaError(.fileReadCorruptFile)
            }
            if entry.consumedQuantity == nil && entry.consumedUnit == nil { continue }
            guard entry.consumedQuantity.flatMap(FoodProductBasis.parseQuantity) != nil,
                  entry.consumedUnit.flatMap(FoodProductUnit.init(rawValue:)) != nil,
                  entry.valueOrigin != nil else { throw CocoaError(.fileReadCorruptFile) }
        }
    }
    
    static func deleteAllData(
        modelContext: ModelContext
    ) throws {
        let workoutSets = try modelContext.fetch(
            FetchDescriptor<WorkoutSet>()
        )

        let performances = try modelContext.fetch(
            FetchDescriptor<ExercisePerformance>()
        )

        let workoutSessions = try modelContext.fetch(
            FetchDescriptor<WorkoutSession>()
        )

        let exercises = try modelContext.fetch(
            FetchDescriptor<Exercise>()
        )

        let activities = try modelContext.fetch(
            FetchDescriptor<Activity>()
        )

        let foodEntries = try modelContext.fetch(
            FetchDescriptor<FoodEntry>()
        )

        let foodPresets = try modelContext.fetch(
            FetchDescriptor<FoodPreset>()
        )

        let weightEntries = try modelContext.fetch(
            FetchDescriptor<WeightEntry>()
        )

        let userGoals = try modelContext.fetch(
            FetchDescriptor<UserGoals>()
        )

        for item in workoutSets {
            modelContext.delete(item)
        }

        for item in performances {
            modelContext.delete(item)
        }

        for item in workoutSessions {
            modelContext.delete(item)
        }

        for item in exercises {
            modelContext.delete(item)
        }

        for item in activities {
            modelContext.delete(item)
        }

        for item in foodEntries {
            modelContext.delete(item)
        }

        for item in foodPresets {
            modelContext.delete(item)
        }

        for item in weightEntries {
            modelContext.delete(item)
        }

        for item in userGoals {
            modelContext.delete(item)
        }

        try modelContext.save()
    }
    
    static func restoreBackup(
        _ backup: AppBackup,
        modelContext: ModelContext
    ) throws {
        try validateProducts(in: backup)
        var exerciseMap: [UUID: Exercise] = [:]

        // 1. Übungen wiederherstellen
        for exerciseBackup in backup.exercises {
            let exercise = Exercise(
                id: exerciseBackup.id,
                name: exerciseBackup.name,
                createdAt: exerciseBackup.createdAt,
                isArchived: exerciseBackup.isArchived,
                nextWeightIncreaseMarkedAt: exerciseBackup.nextWeightIncreaseMarkedAtEpochSeconds.map {
                    Date(timeIntervalSince1970: $0)
                }
            )

            modelContext.insert(exercise)
            exerciseMap[exerciseBackup.id] = exercise
        }

        // 2. Krafttrainings wiederherstellen
        for sessionBackup in backup.workoutSessions {
            let session = WorkoutSession(
                id: sessionBackup.id,
                startedAt: sessionBackup.startedAt,
                endedAt: sessionBackup.endedAt,
                durationMinutes: sessionBackup.durationMinutes,
                estimatedCalories: sessionBackup.estimatedCalories,
                bodyWeightKg: sessionBackup.bodyWeightKg,
                isCompleted: sessionBackup.isCompleted
            )

            modelContext.insert(session)

            for performanceBackup in sessionBackup.performances {
                let exercise: Exercise?

                if let exerciseID = performanceBackup.exerciseID {
                    exercise = exerciseMap[exerciseID]
                } else {
                    exercise = nil
                }

                let performance = ExercisePerformance(
                    orderIndex: performanceBackup.orderIndex,
                    exercise: exercise,
                    workoutSession: session
                )

                modelContext.insert(performance)

                for setBackup in performanceBackup.sets {
                    let workoutSet = WorkoutSet(
                        setNumber: setBackup.setNumber,
                        weightKg: setBackup.weightKg,
                        repetitions: setBackup.repetitions,
                        performance: performance
                    )

                    modelContext.insert(workoutSet)
                }
            }
        }

        // 3. Freie Aktivitäten
        for activityBackup in backup.activities {
            let activity = Activity(
                type: activityBackup.type,
                date: activityBackup.date,
                durationMinutes: activityBackup.durationMinutes,
                estimatedCalories: activityBackup.estimatedCalories,
                bodyWeightKg: activityBackup.bodyWeightKg,
                notes: activityBackup.notes
            )

            modelContext.insert(activity)
        }

        // 4. Ernährung
        for foodBackup in backup.foodEntries {
            let entry = FoodEntry(
                date: foodBackup.date,
                name: foodBackup.name,
                calories: foodBackup.calories,
                proteinGrams: foodBackup.proteinGrams,
                carbsGrams: foodBackup.carbsGrams,
                fatGrams: foodBackup.fatGrams,
                notes: foodBackup.notes,
                valueOrigin: foodBackup.valueOrigin,
                consumedQuantity: foodBackup.consumedQuantity,
                consumedUnit: foodBackup.consumedUnit
            )

            modelContext.insert(entry)
        }

        // 5. Favoriten
        for presetBackup in backup.foodPresets {
            let preset = FoodPreset(
                name: presetBackup.name,
                calories: presetBackup.calories,
                proteinGrams: presetBackup.proteinGrams,
                carbsGrams: presetBackup.carbsGrams,
                fatGrams: presetBackup.fatGrams,
                createdAt: presetBackup.createdAt,
                baseQuantity: presetBackup.baseQuantity,
                baseUnit: presetBackup.baseUnit,
                valueOrigin: presetBackup.valueOrigin,
                baseCalories: presetBackup.baseCalories
            )

            modelContext.insert(preset)
        }

        // 6. Gewicht
        for weightBackup in backup.weightEntries {
            let entry = WeightEntry(
                date: weightBackup.date,
                weightKg: weightBackup.weightKg
            )

            modelContext.insert(entry)
        }

        // 7. Ziele
        if let goalsBackup = backup.userGoals {
            let goals = UserGoals(
                calorieGoal: goalsBackup.calorieGoal,
                proteinGoalGrams: goalsBackup.proteinGoalGrams,
                weeklyActivityGoal: goalsBackup.weeklyActivityGoal
            )

            modelContext.insert(goals)
        }

        try modelContext.save()
    }
}

import Foundation
import SwiftData

@MainActor
enum ExerciseWeightIncreaseMarkerPersistence {
    enum PersistenceError: Error {
        case exerciseNotFound
    }

    static func save(
        _ value: Date?,
        for exercise: Exercise,
        in modelContext: ModelContext,
        persist: (ModelContext) throws -> Void = { try $0.save() }
    ) throws {
        let isolatedContext = ModelContext(modelContext.container)
        isolatedContext.autosaveEnabled = false
        let exerciseID = exercise.persistentModelID

        do {
            let descriptor = FetchDescriptor<Exercise>(
                predicate: #Predicate { $0.persistentModelID == exerciseID }
            )
            guard let storedExercise = try isolatedContext.fetch(descriptor).first else {
                throw PersistenceError.exerciseNotFound
            }

            storedExercise.nextWeightIncreaseMarkedAt = value
            try persist(isolatedContext)
        } catch {
            isolatedContext.rollback()
            throw error
        }
    }
}
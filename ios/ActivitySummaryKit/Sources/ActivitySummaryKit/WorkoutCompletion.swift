import Foundation

public struct WorkoutCompletionDraft: Identifiable, Equatable {
    public let id: UUID
    public let startedAt: Date
    public let capturedFinishAt: Date
    public let bodyWeightKg: Double?
    public let proposedDurationMinutes: Int
    public let proposedCalories: Int

    public init(
        id: UUID = UUID(),
        startedAt: Date,
        capturedFinishAt: Date,
        bodyWeightKg: Double?,
        proposedDurationMinutes: Int,
        proposedCalories: Int
    ) {
        self.id = id
        self.startedAt = startedAt
        self.capturedFinishAt = capturedFinishAt
        self.bodyWeightKg = bodyWeightKg
        self.proposedDurationMinutes = proposedDurationMinutes
        self.proposedCalories = proposedCalories
    }
}

public struct WorkoutCompletionValues: Equatable {
    public let endedAt: Date
    public let durationMinutes: Int
    public let estimatedCalories: Int

    public init(
        endedAt: Date,
        durationMinutes: Int,
        estimatedCalories: Int
    ) {
        self.endedAt = endedAt
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
    }
}

public enum WorkoutCompletion {
    public static let defaultBodyWeightKg = 80.0
    public static let strengthTrainingMET = 5.0

    public static func makeDraft(
        startedAt: Date,
        capturedFinishAt: Date,
        bodyWeightKg: Double?
    ) -> WorkoutCompletionDraft {
        let elapsedMinutes = Int(capturedFinishAt.timeIntervalSince(startedAt) / 60)
        let durationMinutes = max(1, elapsedMinutes)
        let calories = estimatedCalories(
            durationMinutes: durationMinutes,
            bodyWeightKg: bodyWeightKg
        )

        return WorkoutCompletionDraft(
            startedAt: startedAt,
            capturedFinishAt: capturedFinishAt,
            bodyWeightKg: bodyWeightKg,
            proposedDurationMinutes: durationMinutes,
            proposedCalories: calories
        )
    }

    public static func estimatedCalories(
        durationMinutes: Int,
        bodyWeightKg: Double?
    ) -> Int {
        let weight = bodyWeightKg ?? defaultBodyWeightKg
        let calories = strengthTrainingMET * weight * Double(durationMinutes) / 60
        return Int(calories.rounded())
    }

    public static func positiveWholeNumber(from text: String) -> Int? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let value = Int(trimmed), value > 0 else {
            return nil
        }
        return value
    }

    public static func completionValues(
        startedAt: Date,
        durationText: String,
        caloriesText: String
    ) -> WorkoutCompletionValues? {
        guard
            let durationMinutes = positiveWholeNumber(from: durationText),
            let estimatedCalories = positiveWholeNumber(from: caloriesText)
        else {
            return nil
        }

        return WorkoutCompletionValues(
            endedAt: startedAt.addingTimeInterval(Double(durationMinutes) * 60),
            durationMinutes: durationMinutes,
            estimatedCalories: estimatedCalories
        )
    }

    public static func applyWithRollback<Snapshot>(
        snapshot: Snapshot,
        apply: () -> Void,
        save: () throws -> Void,
        restore: (Snapshot) -> Void
    ) throws {
        apply()
        do {
            try save()
        } catch {
            restore(snapshot)
            throw error
        }
    }
}

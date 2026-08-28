import Foundation
import SwiftData

@Model
final class WorkoutSession {
    var id: UUID
    var startedAt: Date
    var endedAt: Date?
    var durationMinutes: Int?
    var estimatedCalories: Int?
    var bodyWeightKg: Double?
    var isCompleted: Bool

    init(
        id: UUID = UUID(),
        startedAt: Date = Date(),
        endedAt: Date? = nil,
        durationMinutes: Int? = nil,
        estimatedCalories: Int? = nil,
        bodyWeightKg: Double? = nil,
        isCompleted: Bool = false
    ) {
        self.id = id
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
        self.bodyWeightKg = bodyWeightKg
        self.isCompleted = isCompleted
    }
}

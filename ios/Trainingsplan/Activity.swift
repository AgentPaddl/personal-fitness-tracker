import Foundation
import SwiftData

@Model
final class Activity {
    var type: String
    var date: Date
    var durationMinutes: Int
    var estimatedCalories: Int
    var bodyWeightKg: Double?
    var notes: String?

    init(
        type: String,
        date: Date = Date(),
        durationMinutes: Int,
        estimatedCalories: Int,
        bodyWeightKg: Double? = nil,
        notes: String? = nil
    ) {
        self.type = type
        self.date = date
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
        self.bodyWeightKg = bodyWeightKg
        self.notes = notes
    }
}

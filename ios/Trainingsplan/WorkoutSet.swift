import Foundation
import SwiftData

@Model
final class WorkoutSet {
    var setNumber: Int
    var weightKg: Double
    var repetitions: Int

    var performance: ExercisePerformance?

    init(
        setNumber: Int,
        weightKg: Double = 0,
        repetitions: Int = 0,
        performance: ExercisePerformance? = nil
    ) {
        self.setNumber = setNumber
        self.weightKg = weightKg
        self.repetitions = repetitions
        self.performance = performance
    }
}

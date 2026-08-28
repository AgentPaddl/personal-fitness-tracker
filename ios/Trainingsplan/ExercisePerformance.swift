import Foundation
import SwiftData

@Model
final class ExercisePerformance {
    var orderIndex: Int

    var exercise: Exercise?
    var workoutSession: WorkoutSession?

    init(
        orderIndex: Int,
        exercise: Exercise? = nil,
        workoutSession: WorkoutSession? = nil
    ) {
        self.orderIndex = orderIndex
        self.exercise = exercise
        self.workoutSession = workoutSession
    }
}

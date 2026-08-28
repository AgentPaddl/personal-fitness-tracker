import Foundation
import SwiftData

@Model
final class UserGoals {
    var calorieGoal: Int
    var proteinGoalGrams: Int
    var weeklyActivityGoal: Int

    init(
        calorieGoal: Int = 2300,
        proteinGoalGrams: Int = 150,
        weeklyActivityGoal: Int = 3
    ) {
        self.calorieGoal = calorieGoal
        self.proteinGoalGrams = proteinGoalGrams
        self.weeklyActivityGoal = weeklyActivityGoal
    }
}

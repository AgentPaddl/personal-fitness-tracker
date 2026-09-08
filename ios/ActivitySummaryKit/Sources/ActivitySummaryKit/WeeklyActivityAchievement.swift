public enum WeeklyActivityAchievement {
    public static func hasEarnedStar(
        weeklyCompletedActivityCount: Int,
        activitiesPerWeekGoal: Int
    ) -> Bool {
        activitiesPerWeekGoal > 0 && weeklyCompletedActivityCount >= activitiesPerWeekGoal
    }
}

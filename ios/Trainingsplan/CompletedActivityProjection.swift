import ActivitySummaryKit
import SwiftData

typealias AppCompletedActivity = CompletedActivitySummary<PersistentIdentifier>

func completedActivitySummaries(
    activities: [Activity],
    workoutSessions: [WorkoutSession]
) -> [AppCompletedActivity] {
    CompletedActivityProjection.project(
        activities: activities.map { activity in
            CompletedFreeActivity(
                id: activity.persistentModelID,
                date: activity.date,
                type: activity.type,
                durationMinutes: activity.durationMinutes,
                estimatedCalories: activity.estimatedCalories
            )
        },
        workoutSessions: workoutSessions.map { workout in
            WorkoutSessionActivity(
                id: workout.persistentModelID,
                startedAt: workout.startedAt,
                endedAt: workout.endedAt,
                durationMinutes: workout.durationMinutes,
                estimatedCalories: workout.estimatedCalories,
                isCompleted: workout.isCompleted
            )
        }
    )
}

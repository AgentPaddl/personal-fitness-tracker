import ActivitySummaryKit
import SwiftData

@MainActor
final class WorkoutSessionDeletionService {
    private let coordinator = WorkoutDeletionCoordinator<PersistentIdentifier>()

    func delete(
        sourceID: CompletedActivitySourceID<PersistentIdentifier>,
        workoutSessions: [WorkoutSession],
        performances: [ExercisePerformance],
        workoutSets: [WorkoutSet],
        modelContext: ModelContext
    ) -> WorkoutDeletionResult {
        guard sourceID.kind == .workoutSession else {
            return .skipped
        }

        guard let session = workoutSessions.first(where: {
            $0.persistentModelID == sourceID.value
        }) else {
            return .skipped
        }

        return delete(
            session: session,
            scope: .completed,
            performances: performances,
            workoutSets: workoutSets,
            modelContext: modelContext
        )
    }

    func discard(
        session: WorkoutSession,
        performances: [ExercisePerformance],
        workoutSets: [WorkoutSet],
        modelContext: ModelContext
    ) -> WorkoutDeletionResult {
        delete(
            session: session,
            scope: .incomplete,
            performances: performances,
            workoutSets: workoutSets,
            modelContext: modelContext
        )
    }

    private func delete(
        session: WorkoutSession,
        scope: WorkoutDeletionScope,
        performances: [ExercisePerformance],
        workoutSets: [WorkoutSet],
        modelContext: ModelContext
    ) -> WorkoutDeletionResult {
        guard
            let plan = WorkoutDeletionPlanner.plan(
                workoutSessionID: session.persistentModelID,
                isCompleted: session.isCompleted,
                scope: scope,
                performances: performances.map { performance in
                    WorkoutDeletionPerformance(
                        id: performance.persistentModelID,
                        workoutSessionID: performance.workoutSession?.persistentModelID,
                        exerciseID: performance.exercise?.persistentModelID
                    )
                },
                sets: workoutSets.map { workoutSet in
                    WorkoutDeletionSet(
                        id: workoutSet.persistentModelID,
                        performanceID: workoutSet.performance?.persistentModelID
                    )
                }
            )
        else {
            return .skipped
        }

        let performancesByID = Dictionary(
            uniqueKeysWithValues: performances.map { ($0.persistentModelID, $0) }
        )
        let setsByID = Dictionary(
            uniqueKeysWithValues: workoutSets.map { ($0.persistentModelID, $0) }
        )

        return coordinator.delete(
            plan: plan,
            deleteSet: { id in
                if let workoutSet = setsByID[id] {
                    modelContext.delete(workoutSet)
                }
            },
            deletePerformance: { id in
                if let performance = performancesByID[id] {
                    modelContext.delete(performance)
                }
            },
            deleteWorkoutSession: { _ in
                modelContext.delete(session)
            },
            persist: {
                try modelContext.save()
            },
            rollback: {
                modelContext.rollback()
            }
        )
    }
}

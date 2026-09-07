import XCTest

@testable import ActivitySummaryKit

final class WorkoutDeletionTests: XCTestCase {
    func testPlanAddressesExactlySelectedWorkoutSession() {
        let plan = makePlan(workoutSessionID: "workout-1")

        XCTAssertEqual(plan.workoutSessionID, "workout-1")
        XCTAssertEqual(plan.performanceIDs, ["performance-1"])
        XCTAssertEqual(plan.setIDs, ["set-1", "set-2"])
    }

    func testPlanLeavesForeignSessionChildrenUnselected() {
        let plan = makePlan(workoutSessionID: "workout-1")

        XCTAssertFalse(plan.performanceIDs.contains("performance-2"))
        XCTAssertFalse(plan.setIDs.contains("set-3"))
    }

    func testExerciseDefinitionsAreNotPartOfDeletionPlan() {
        let performances = [
            WorkoutDeletionPerformance(
                id: "performance-1",
                workoutSessionID: "workout-1",
                exerciseID: "shared-exercise"
            )
        ]

        let plan = WorkoutDeletionPlanner.plan(
            workoutSessionID: "workout-1",
            performances: performances,
            sets: []
        )

        XCTAssertEqual(plan.performanceIDs, ["performance-1"])
        XCTAssertFalse(plan.performanceIDs.contains("shared-exercise"))
        XCTAssertTrue(plan.setIDs.isEmpty)
    }

    func testDeleteRunsChildFirstAndPreservesFreeActivities() {
        let coordinator = WorkoutDeletionCoordinator<String>()
        let freeActivities = ["activity-1", "activity-2"]
        var operations: [String] = []

        let result = coordinator.delete(
            plan: makePlan(workoutSessionID: "workout-1"),
            deleteSet: { operations.append("set:\($0)") },
            deletePerformance: { operations.append("performance:\($0)") },
            deleteWorkoutSession: { operations.append("session:\($0)") },
            persist: { operations.append("persist") },
            rollback: { operations.append("rollback") }
        )

        XCTAssertEqual(result, .deleted)
        XCTAssertEqual(
            operations,
            [
                "set:set-1",
                "set:set-2",
                "performance:performance-1",
                "session:workout-1",
                "persist"
            ]
        )
        XCTAssertEqual(freeActivities, ["activity-1", "activity-2"])
    }

    func testRepeatedDeleteOfCommittedSessionIsSkipped() {
        let coordinator = WorkoutDeletionCoordinator<String>()
        let plan = makePlan(workoutSessionID: "workout-1")
        var persistCount = 0

        let firstResult = coordinator.delete(
            plan: plan,
            deleteSet: { _ in },
            deletePerformance: { _ in },
            deleteWorkoutSession: { _ in },
            persist: { persistCount += 1 },
            rollback: {}
        )
        let repeatedResult = coordinator.delete(
            plan: plan,
            deleteSet: { _ in XCTFail("Repeated deletion must not delete sets") },
            deletePerformance: { _ in XCTFail("Repeated deletion must not delete performances") },
            deleteWorkoutSession: { _ in XCTFail("Repeated deletion must not delete the session") },
            persist: { XCTFail("Repeated deletion must not persist") },
            rollback: { XCTFail("Repeated deletion must not roll back") }
        )

        XCTAssertEqual(firstResult, .deleted)
        XCTAssertEqual(repeatedResult, .skipped)
        XCTAssertEqual(persistCount, 1)
    }

    func testReentrantDeleteWhileDeletionIsRunningIsSkipped() {
        let coordinator = WorkoutDeletionCoordinator<String>()
        let plan = makePlan(workoutSessionID: "workout-1")
        var nestedResult: WorkoutDeletionResult?

        let result = coordinator.delete(
            plan: plan,
            deleteSet: { _ in },
            deletePerformance: { _ in },
            deleteWorkoutSession: { _ in
                nestedResult = coordinator.delete(
                    plan: plan,
                    deleteSet: { _ in },
                    deletePerformance: { _ in },
                    deleteWorkoutSession: { _ in },
                    persist: {},
                    rollback: {}
                )
            },
            persist: {},
            rollback: {}
        )

        XCTAssertEqual(result, .deleted)
        XCTAssertEqual(nestedResult, .skipped)
    }

    func testFailureRollsBackAndLeavesVisibleStatisticsUnchanged() {
        enum TestError: Error {
            case persistenceFailed
        }

        let coordinator = WorkoutDeletionCoordinator<String>()
        let before = CompletedActivityProjection.project(
            activities: [freeActivity()],
            workoutSessions: [workout(id: "workout-1"), workout(id: "workout-2")]
        )
        var visibleItems = before

        let result = coordinator.delete(
            plan: makePlan(workoutSessionID: "workout-1"),
            deleteSet: { _ in },
            deletePerformance: { _ in },
            deleteWorkoutSession: { deletedID in
                visibleItems.removeAll { $0.id.value == deletedID }
            },
            persist: { throw TestError.persistenceFailed },
            rollback: { visibleItems = before }
        )

        XCTAssertEqual(result, .failed)
        XCTAssertEqual(visibleItems.map(\.id), before.map(\.id))
        XCTAssertEqual(
            CompletedActivityProjection.totals(for: visibleItems),
            CompletedActivityProjection.totals(for: before)
        )
    }

    func testFailedDeleteCanBeRetried() {
        enum TestError: Error {
            case persistenceFailed
        }

        let coordinator = WorkoutDeletionCoordinator<String>()
        let plan = makePlan(workoutSessionID: "workout-1")

        let failedResult = coordinator.delete(
            plan: plan,
            deleteSet: { _ in },
            deletePerformance: { _ in },
            deleteWorkoutSession: { _ in },
            persist: { throw TestError.persistenceFailed },
            rollback: {}
        )
        let retryResult = coordinator.delete(
            plan: plan,
            deleteSet: { _ in },
            deletePerformance: { _ in },
            deleteWorkoutSession: { _ in },
            persist: {},
            rollback: {}
        )

        XCTAssertEqual(failedResult, .failed)
        XCTAssertEqual(retryResult, .deleted)
    }

    private func makePlan(workoutSessionID: String) -> WorkoutDeletionPlan<String> {
        WorkoutDeletionPlanner.plan(
            workoutSessionID: workoutSessionID,
            performances: [
                WorkoutDeletionPerformance(
                    id: "performance-1",
                    workoutSessionID: "workout-1",
                    exerciseID: "shared-exercise"
                ),
                WorkoutDeletionPerformance(
                    id: "performance-2",
                    workoutSessionID: "workout-2",
                    exerciseID: "shared-exercise"
                )
            ],
            sets: [
                WorkoutDeletionSet(id: "set-1", performanceID: "performance-1"),
                WorkoutDeletionSet(id: "set-2", performanceID: "performance-1"),
                WorkoutDeletionSet(id: "set-3", performanceID: "performance-2")
            ]
        )
    }

    private func freeActivity() -> CompletedFreeActivity<String> {
        CompletedFreeActivity(
            id: "activity-1",
            date: Date(timeIntervalSince1970: 1_000),
            type: "Yoga",
            durationMinutes: 30,
            estimatedCalories: 100
        )
    }

    private func workout(id: String) -> WorkoutSessionActivity<String> {
        WorkoutSessionActivity(
            id: id,
            startedAt: Date(timeIntervalSince1970: id == "workout-1" ? 2_000 : 3_000),
            endedAt: nil,
            durationMinutes: 30,
            estimatedCalories: 200,
            isCompleted: true
        )
    }
}

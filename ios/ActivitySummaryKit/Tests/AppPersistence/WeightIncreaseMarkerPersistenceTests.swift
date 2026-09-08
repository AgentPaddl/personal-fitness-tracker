import Foundation
import SwiftData
import XCTest
import ActivitySummaryKit

@testable import MarkerAppPersistence

final class WeightIncreaseMarkerPersistenceTests: XCTestCase {
    private let timestamp = Date(timeIntervalSince1970: 1_000_000)

    private enum TestError: Error {
        case saveFailed
    }

    @MainActor
    func testNewExerciseDefaultsToNil() {
        XCTAssertNil(Exercise(name: "Test exercise").nextWeightIncreaseMarkedAt)
    }

    @MainActor
    func testOldBackupWithoutMarkerDecodesAndRestoresNil() throws {
        let data = Data("""
        {
          "exportDate": "2026-09-01T10:00:00Z",
          "exercises": [{
            "id": "A0000000-0000-0000-0000-000000000001",
            "name": "Test exercise",
            "createdAt": "2026-09-01T09:00:00Z",
            "isArchived": false
          }],
          "workoutSessions": [], "activities": [], "foodEntries": [],
          "foodPresets": [], "weightEntries": [], "userGoals": null
        }
        """.utf8)
        let backup = try BackupService.decodeBackup(from: data)
        XCTAssertNil(try XCTUnwrap(backup.exercises.first).nextWeightIncreaseMarkedAtEpochSeconds)

        let container = try makeContainer()
        let context = ModelContext(container)
        try BackupService.restoreBackup(backup, modelContext: context)
        XCTAssertNil(try XCTUnwrap(context.fetch(FetchDescriptor<Exercise>()).first).nextWeightIncreaseMarkedAt)
    }

    @MainActor
    func testBackupRoundtripWithMarkerPreservesIdentityRelationshipsAndHistory() throws {
        try assertBackupRoundtrip(marker: timestamp)
    }

    @MainActor
    func testBackupRoundtripWithNilPreservesIdentityRelationshipsAndHistory() throws {
        try assertBackupRoundtrip(marker: nil)
    }

    @MainActor
    func testBackupRoundtripPreservesExactFractionalSeconds() throws {
        let fractionalTimestamp = Date(timeIntervalSince1970: 1_788_867_123.1234567)
        XCTAssertNotEqual(
            fractionalTimestamp.timeIntervalSince1970,
            fractionalTimestamp.timeIntervalSince1970.rounded()
        )
        try assertBackupRoundtrip(marker: fractionalTimestamp)
    }

    @MainActor
    func testBackupEncodesOnlyMarkerAsNumberAndKeepsExistingDateFormats() throws {
        let marker = Date(timeIntervalSince1970: 1_788_867_123.1234567)
        let fixture = try makeFixture(marker: marker)
        fixture.exercise.createdAt = timestamp
        fixture.session.endedAt = timestamp.addingTimeInterval(60)
        try fixture.context.save()

        let data = try BackupService.createBackup(modelContext: fixture.context)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let exerciseJSON = try XCTUnwrap((json["exercises"] as? [[String: Any]])?.first)
        let sessionJSON = try XCTUnwrap((json["workoutSessions"] as? [[String: Any]])?.first)
        let encodedMarker = try XCTUnwrap(exerciseJSON["nextWeightIncreaseMarkedAtEpochSeconds"] as? NSNumber)

        XCTAssertEqual(encodedMarker.doubleValue, marker.timeIntervalSince1970)
        XCTAssertNil(exerciseJSON["nextWeightIncreaseMarkedAt"])
        XCTAssertEqual(exerciseJSON["createdAt"] as? String, "1970-01-12T13:46:40Z")
        XCTAssertEqual(sessionJSON["startedAt"] as? String, "1970-01-12T13:46:40Z")
        XCTAssertEqual(sessionJSON["endedAt"] as? String, "1970-01-12T13:47:40Z")
        XCTAssertNotNil(ISO8601DateFormatter().date(from: try XCTUnwrap(json["exportDate"] as? String)))
    }

    @MainActor
    func testRepeatedTogglesSurviveLaterMainContextSaveWithoutSavingPendingEditsEarly() throws {
        for finalActive in [true, false] {
            let fixture = try makeFixture(marker: nil)
            let marker = WeightIncreaseMarker()
            fixture.exercise.name = "Pending name"
            fixture.workoutSet.weightKg = 65
            fixture.workoutSet.repetitions = 9
            fixture.session.durationMinutes = 42
            let sequence = finalActive ? [true, false, true, false, true] : [true, false, true, false]
            var expectedMarker: Date?

            for (index, active) in sequence.enumerated() {
                let moment = Date(timeIntervalSince1970: 1_788_867_123.125 + Double(index))
                expectedMarker = active ? moment : nil
                XCTAssertTrue(try marker.setActive(
                    active,
                    currentValue: fixture.exercise.nextWeightIncreaseMarkedAt,
                    now: { moment },
                    persist: {
                        try ExerciseWeightIncreaseMarkerPersistence.save($0, for: fixture.exercise, in: fixture.context)
                    },
                    publish: { fixture.exercise.nextWeightIncreaseMarkedAt = $0 }
                ))

                let reader = ModelContext(fixture.context.container)
                let savedExercise = try XCTUnwrap(reader.fetch(FetchDescriptor<Exercise>()).first)
                let savedSet = try XCTUnwrap(reader.fetch(FetchDescriptor<WorkoutSet>()).first)
                let savedSession = try XCTUnwrap(reader.fetch(FetchDescriptor<WorkoutSession>()).first)
                XCTAssertEqual(savedExercise.nextWeightIncreaseMarkedAt, expectedMarker)
                XCTAssertEqual(savedExercise.name, "Test exercise")
                XCTAssertEqual(savedSet.weightKg, 60)
                XCTAssertEqual(savedSet.repetitions, 8)
                XCTAssertNil(savedSession.durationMinutes)
                XCTAssertFalse(savedSession.isCompleted)
                XCTAssertEqual(fixture.exercise.name, "Pending name")
                XCTAssertEqual(fixture.workoutSet.weightKg, 65)
                XCTAssertEqual(fixture.workoutSet.repetitions, 9)
                XCTAssertEqual(fixture.session.durationMinutes, 42)
            }

            try fixture.context.save()

            let reader = ModelContext(fixture.context.container)
            let savedExercise = try XCTUnwrap(reader.fetch(FetchDescriptor<Exercise>()).first)
            let savedSet = try XCTUnwrap(reader.fetch(FetchDescriptor<WorkoutSet>()).first)
            let savedSession = try XCTUnwrap(reader.fetch(FetchDescriptor<WorkoutSession>()).first)
            XCTAssertEqual(savedExercise.nextWeightIncreaseMarkedAt, expectedMarker)
            XCTAssertEqual(savedExercise.nextWeightIncreaseMarkedAt != nil, finalActive)
            XCTAssertEqual(savedExercise.name, "Pending name")
            XCTAssertEqual(savedSet.weightKg, 65)
            XCTAssertEqual(savedSet.repetitions, 9)
            XCTAssertEqual(savedSession.durationMinutes, 42)
            XCTAssertFalse(savedSession.isCompleted)
        }
    }

    @MainActor
    func testActivationAndDeactivationPersistAcrossContexts() throws {
        let fixture = try makeFixture(marker: nil)
        let marker = WeightIncreaseMarker()

        for active in [true, false] {
            try marker.setActive(
                active,
                currentValue: fixture.exercise.nextWeightIncreaseMarkedAt,
                now: { timestamp },
                persist: {
                    try ExerciseWeightIncreaseMarkerPersistence.save($0, for: fixture.exercise, in: fixture.context)
                },
                publish: { fixture.exercise.nextWeightIncreaseMarkedAt = $0 }
            )
            let reader = ModelContext(fixture.context.container)
            let saved = try XCTUnwrap(reader.fetch(FetchDescriptor<Exercise>()).first)
            XCTAssertEqual(saved.nextWeightIncreaseMarkedAt, active ? timestamp : nil)
            XCTAssertEqual(fixture.exercise.nextWeightIncreaseMarkedAt, saved.nextWeightIncreaseMarkedAt)
            XCTAssertFalse(fixture.session.isCompleted)
        }
    }

    @MainActor
    func testSaveFailureRollsBackOnlyIsolatedContextAndKeepsUnsavedSetEdits() throws {
        for original in [nil, timestamp] as [Date?] {
            let fixture = try makeFixture(marker: original)
            fixture.workoutSet.weightKg = 65
            fixture.workoutSet.repetitions = 9
            fixture.exercise.name = "Unsaved name"
            var failedContext: ModelContext?

            XCTAssertThrowsError(try WeightIncreaseMarker().setActive(
                original == nil,
                currentValue: fixture.exercise.nextWeightIncreaseMarkedAt,
                now: { timestamp },
                persist: { value in
                    try ExerciseWeightIncreaseMarkerPersistence.save(value, for: fixture.exercise, in: fixture.context) {
                        failedContext = $0
                        XCTAssertTrue($0.hasChanges)
                        throw TestError.saveFailed
                    }
                },
                publish: { fixture.exercise.nextWeightIncreaseMarkedAt = $0 }
            ))

            XCTAssertFalse(try XCTUnwrap(failedContext).hasChanges)
            XCTAssertEqual(fixture.exercise.nextWeightIncreaseMarkedAt, original)
            XCTAssertEqual(fixture.exercise.name, "Unsaved name")
            XCTAssertEqual(fixture.workoutSet.weightKg, 65)
            XCTAssertEqual(fixture.workoutSet.repetitions, 9)
            XCTAssertFalse(fixture.session.isCompleted)
            XCTAssertTrue(fixture.context.hasChanges)

            let reader = ModelContext(fixture.context.container)
            let savedExercise = try XCTUnwrap(reader.fetch(FetchDescriptor<Exercise>()).first)
            let savedSet = try XCTUnwrap(reader.fetch(FetchDescriptor<WorkoutSet>()).first)
            XCTAssertEqual(savedExercise.nextWeightIncreaseMarkedAt, original)
            XCTAssertEqual(savedExercise.name, "Test exercise")
            XCTAssertEqual(savedSet.weightKg, 60)
            XCTAssertEqual(savedSet.repetitions, 8)
        }
    }

    @MainActor
    func testSuccessfulSaveDoesNotPersistOtherPendingChanges() throws {
        let fixture = try makeFixture(marker: nil)
        fixture.workoutSet.weightKg = 65
        fixture.exercise.name = "Unsaved name"

        try ExerciseWeightIncreaseMarkerPersistence.save(timestamp, for: fixture.exercise, in: fixture.context)
        fixture.exercise.nextWeightIncreaseMarkedAt = timestamp

        let reader = ModelContext(fixture.context.container)
        let savedExercise = try XCTUnwrap(reader.fetch(FetchDescriptor<Exercise>()).first)
        XCTAssertEqual(savedExercise.nextWeightIncreaseMarkedAt, timestamp)
        XCTAssertEqual(savedExercise.name, "Test exercise")
        XCTAssertEqual(try reader.fetch(FetchDescriptor<WorkoutSet>()).first?.weightKg, 60)
        XCTAssertEqual(fixture.exercise.name, "Unsaved name")
        XCTAssertEqual(fixture.workoutSet.weightKg, 65)
        XCTAssertFalse(fixture.session.isCompleted)
    }

    @MainActor
    func testCommittedMarkerSurvivesLaterTrainingContextRollback() throws {
        let fixture = try makeFixture(marker: nil)
        try ExerciseWeightIncreaseMarkerPersistence.save(timestamp, for: fixture.exercise, in: fixture.context)
        fixture.exercise.nextWeightIncreaseMarkedAt = timestamp
        fixture.workoutSet.weightKg = 65

        fixture.context.rollback()

        XCTAssertEqual(fixture.exercise.nextWeightIncreaseMarkedAt, timestamp)
        let reader = ModelContext(fixture.context.container)
        XCTAssertEqual(try reader.fetch(FetchDescriptor<Exercise>()).first?.nextWeightIncreaseMarkedAt, timestamp)
    }

    @MainActor
    func testSharedExerciseOccurrencesObserveTheSameMarker() throws {
        let fixture = try makeFixture(marker: nil)
        let secondSession = WorkoutSession()
        let secondPerformance = ExercisePerformance(orderIndex: 0, exercise: fixture.exercise, workoutSession: secondSession)
        fixture.context.insert(secondSession)
        fixture.context.insert(secondPerformance)
        try fixture.context.save()

        try ExerciseWeightIncreaseMarkerPersistence.save(timestamp, for: fixture.exercise, in: fixture.context)
        fixture.exercise.nextWeightIncreaseMarkedAt = timestamp
        XCTAssertTrue(fixture.performance.exercise === secondPerformance.exercise)
        XCTAssertEqual(secondPerformance.exercise?.nextWeightIncreaseMarkedAt, timestamp)
        XCTAssertFalse(secondSession.isCompleted)
        XCTAssertFalse(fixture.session.isCompleted)
    }

    @MainActor
    func testDiscardPreservesExistingAndNewlySetMarkers() throws {
        for initiallyMarked in [false, true] {
            let fixture = try makeFixture(marker: initiallyMarked ? timestamp : nil)
            if !initiallyMarked {
                try ExerciseWeightIncreaseMarkerPersistence.save(timestamp, for: fixture.exercise, in: fixture.context)
                fixture.exercise.nextWeightIncreaseMarkedAt = timestamp
            }

            let result = WorkoutSessionDeletionService().discard(
                session: fixture.session,
                performances: [fixture.performance],
                workoutSets: [fixture.workoutSet],
                modelContext: fixture.context
            )
            XCTAssertEqual(result, .deleted)
            try assertOnlyMarkedExerciseRemains(in: fixture.context)
        }
    }

    @MainActor
    func testDeletingCompletedWorkoutPreservesMarker() throws {
        let fixture = try makeFixture(marker: timestamp)
        fixture.session.isCompleted = true
        try fixture.context.save()

        let result = WorkoutSessionDeletionService().delete(
            sourceID: .init(kind: .workoutSession, value: fixture.session.persistentModelID),
            workoutSessions: [fixture.session],
            performances: [fixture.performance],
            workoutSets: [fixture.workoutSet],
            modelContext: fixture.context
        )
        XCTAssertEqual(result, .deleted)
        try assertOnlyMarkedExerciseRemains(in: fixture.context)
    }

    @MainActor
    func testWeightChangeAndCompletionDoNotClearMarker() throws {
        let fixture = try makeFixture(marker: timestamp)
        fixture.workoutSet.weightKg = 70
        let values = try XCTUnwrap(WorkoutCompletion.completionValues(
            startedAt: fixture.session.startedAt,
            durationText: "30",
            caloriesText: "150"
        ))
        try WorkoutCompletion.applyWithRollback(
            snapshot: fixture.session.isCompleted,
            apply: {
                fixture.session.endedAt = values.endedAt
                fixture.session.durationMinutes = values.durationMinutes
                fixture.session.estimatedCalories = values.estimatedCalories
                fixture.session.isCompleted = true
            },
            save: { try fixture.context.save() },
            restore: { fixture.session.isCompleted = $0 }
        )
        let reader = ModelContext(fixture.context.container)
        XCTAssertEqual(try reader.fetch(FetchDescriptor<Exercise>()).first?.nextWeightIncreaseMarkedAt, timestamp)
    }

    @MainActor
    private func makeContainer() throws -> ModelContainer {
        let schema = Schema([
            Exercise.self, WorkoutSession.self, ExercisePerformance.self, WorkoutSet.self,
            Activity.self, FoodEntry.self, FoodPreset.self, WeightEntry.self, UserGoals.self
        ])
        return try ModelContainer(for: schema, configurations: [ModelConfiguration(isStoredInMemoryOnly: true)])
    }

    @MainActor
    private func makeFixture(marker: Date?) throws -> (
        context: ModelContext, exercise: Exercise, session: WorkoutSession,
        performance: ExercisePerformance, workoutSet: WorkoutSet
    ) {
        let context = ModelContext(try makeContainer())
        context.autosaveEnabled = false
        let exercise = Exercise(name: "Test exercise", nextWeightIncreaseMarkedAt: marker)
        let session = WorkoutSession(startedAt: timestamp)
        let performance = ExercisePerformance(orderIndex: 0, exercise: exercise, workoutSession: session)
        let workoutSet = WorkoutSet(setNumber: 1, weightKg: 60, repetitions: 8, performance: performance)
        context.insert(exercise)
        context.insert(session)
        context.insert(performance)
        context.insert(workoutSet)
        try context.save()
        return (context, exercise, session, performance, workoutSet)
    }

    @MainActor
    private func assertBackupRoundtrip(marker: Date?) throws {
        let fixture = try makeFixture(marker: marker)
        let data = try BackupService.createBackup(modelContext: fixture.context)
        let backup = try BackupService.decodeBackup(from: data)
        XCTAssertEqual(backup.exercises.first?.nextWeightIncreaseMarkedAtEpochSeconds, marker?.timeIntervalSince1970)
        try BackupService.deleteAllData(modelContext: fixture.context)
        try BackupService.restoreBackup(backup, modelContext: fixture.context)

        let restoredExercise = try XCTUnwrap(fixture.context.fetch(FetchDescriptor<Exercise>()).first)
        let restoredSession = try XCTUnwrap(fixture.context.fetch(FetchDescriptor<WorkoutSession>()).first)
        let restoredPerformance = try XCTUnwrap(fixture.context.fetch(FetchDescriptor<ExercisePerformance>()).first)
        let restoredSet = try XCTUnwrap(fixture.context.fetch(FetchDescriptor<WorkoutSet>()).first)
        XCTAssertEqual(restoredExercise.id, backup.exercises.first?.id)
        XCTAssertEqual(restoredExercise.nextWeightIncreaseMarkedAt, marker)
        XCTAssertTrue(restoredPerformance.exercise === restoredExercise)
        XCTAssertTrue(restoredPerformance.workoutSession === restoredSession)
        XCTAssertTrue(restoredSet.performance === restoredPerformance)
        XCTAssertEqual(restoredSet.weightKg, 60)
        XCTAssertEqual(restoredSet.repetitions, 8)
        XCTAssertFalse(restoredSession.isCompleted)
    }

    @MainActor
    private func assertOnlyMarkedExerciseRemains(in context: ModelContext) throws {
        let reader = ModelContext(context.container)
        XCTAssertEqual(try reader.fetch(FetchDescriptor<Exercise>()).count, 1)
        XCTAssertEqual(try reader.fetch(FetchDescriptor<Exercise>()).first?.nextWeightIncreaseMarkedAt, timestamp)
        XCTAssertTrue(try reader.fetch(FetchDescriptor<WorkoutSession>()).isEmpty)
        XCTAssertTrue(try reader.fetch(FetchDescriptor<ExercisePerformance>()).isEmpty)
        XCTAssertTrue(try reader.fetch(FetchDescriptor<WorkoutSet>()).isEmpty)
    }
}
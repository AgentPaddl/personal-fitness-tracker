import XCTest

@testable import ActivitySummaryKit

final class WorkoutCompletionTests: XCTestCase {
    private let startedAt = Date(timeIntervalSince1970: 1_000_000)

    func testTenElapsedSecondsProposesOneMinute() {
        let draft = makeDraft(elapsedSeconds: 10)

        XCTAssertEqual(draft.proposedDurationMinutes, 1)
    }

    func testExactlyOneMinuteProposesOneMinute() {
        let draft = makeDraft(elapsedSeconds: 60)

        XCTAssertEqual(draft.proposedDurationMinutes, 1)
    }

    func testFortyEightElapsedMinutesProposesFortyEightMinutes() {
        let draft = makeDraft(elapsedSeconds: 48 * 60)

        XCTAssertEqual(draft.proposedDurationMinutes, 48)
    }

    func testFutureStartCannotProduceZeroDuration() {
        let draft = WorkoutCompletion.makeDraft(
            startedAt: startedAt.addingTimeInterval(60),
            capturedFinishAt: startedAt,
            bodyWeightKg: 70
        )

        XCTAssertEqual(draft.proposedDurationMinutes, 1)
    }

    func testMissingWeightUsesEightyKilograms() {
        XCTAssertEqual(
            WorkoutCompletion.estimatedCalories(durationMinutes: 60, bodyWeightKg: nil),
            400
        )
    }

    func testCaloriesUseTheProposedDuration() {
        let draft = WorkoutCompletion.makeDraft(
            startedAt: startedAt,
            capturedFinishAt: startedAt.addingTimeInterval(30 * 60),
            bodyWeightKg: 60
        )

        XCTAssertEqual(draft.proposedDurationMinutes, 30)
        XCTAssertEqual(draft.proposedCalories, 150)
    }

    func testInvalidDurationsAreRejected() {
        for value in ["", "abc", "-1", "0", "1.5"] {
            XCTAssertNil(WorkoutCompletion.positiveWholeNumber(from: value))
        }
    }

    func testPositiveWholeNumberDurationIsValid() {
        XCTAssertEqual(WorkoutCompletion.positiveWholeNumber(from: " 48 "), 48)
    }

    func testInvalidCaloriesAreRejected() {
        for value in ["", "abc", "-1", "0", "1.5"] {
            XCTAssertNil(
                WorkoutCompletion.completionValues(
                    startedAt: startedAt,
                    durationText: "30",
                    caloriesText: value
                )
            )
        }
    }

    func testDurationCorrectionRecalculatesCalories() {
        let calories = WorkoutCompletion.estimatedCalories(
            durationMinutes: 48,
            bodyWeightKg: 75
        )

        XCTAssertEqual(calories, 300)
    }

    func testSuccessfulCompletionValuesAreInternallyConsistent() throws {
        let values = try XCTUnwrap(
            WorkoutCompletion.completionValues(
                startedAt: startedAt,
                durationText: "48",
                caloriesText: "300"
            )
        )

        XCTAssertEqual(values.durationMinutes, 48)
        XCTAssertEqual(values.estimatedCalories, 300)
        XCTAssertEqual(values.endedAt, startedAt.addingTimeInterval(48 * 60))
    }

    func testSaveFailureRestoresSnapshot() {
        struct State: Equatable {
            var endedAt: Date?
            var durationMinutes: Int?
            var estimatedCalories: Int?
            var isCompleted: Bool
        }
        enum TestError: Error {
            case saveFailed
        }

        let original = State(
            endedAt: nil,
            durationMinutes: nil,
            estimatedCalories: nil,
            isCompleted: false
        )
        var state = original

        XCTAssertThrowsError(
            try WorkoutCompletion.applyWithRollback(
                snapshot: original,
                apply: {
                    state = State(
                        endedAt: startedAt.addingTimeInterval(60),
                        durationMinutes: 1,
                        estimatedCalories: 7,
                        isCompleted: true
                    )
                },
                save: { throw TestError.saveFailed },
                restore: { state = $0 }
            )
        )
        XCTAssertEqual(state, original)
    }

    private func makeDraft(elapsedSeconds: TimeInterval) -> WorkoutCompletionDraft {
        WorkoutCompletion.makeDraft(
            startedAt: startedAt,
            capturedFinishAt: startedAt.addingTimeInterval(elapsedSeconds),
            bodyWeightKg: 70
        )
    }
}

import XCTest

@testable import ActivitySummaryKit

final class CompletedActivityProjectionTests: XCTestCase {
    private let timeZone = TimeZone(identifier: "Europe/Berlin")!

    func testOneActivityAndTwoCompletedWorkoutsProduceThreeUniqueItems() {
        let activity = freeActivity(id: "activity", date: date(2026, 9, 2, 12))
        let firstWorkout = workout(id: "workout-1", startedAt: date(2026, 9, 3, 9), endedAt: date(2026, 9, 3, 10))
        let secondWorkout = workout(id: "workout-2", startedAt: date(2026, 9, 4, 9), endedAt: date(2026, 9, 4, 10))

        let items = CompletedActivityProjection.project(
            activities: [activity],
            workoutSessions: [firstWorkout, secondWorkout]
        )

        XCTAssertEqual(items.count, 3)
        XCTAssertEqual(Set(items.map(\.id)).count, 3)
        XCTAssertEqual(items.filter { $0.id.kind == .workoutSession }.count, 2)
    }

    func testIncompleteWorkoutIsExcluded() {
        let incomplete = workout(
            id: "incomplete",
            startedAt: date(2026, 9, 2, 9),
            endedAt: nil,
            isCompleted: false
        )

        let items = CompletedActivityProjection.project(
            activities: [],
            workoutSessions: [incomplete]
        )

        XCTAssertTrue(items.isEmpty)
    }

    func testCompletedWorkoutAppearsExactlyOnceAndIsLabelledStrengthTraining() {
        let completed = workout(id: "workout", startedAt: date(2026, 9, 2, 9), endedAt: date(2026, 9, 2, 10))

        let items = CompletedActivityProjection.project(
            activities: [],
            workoutSessions: [completed]
        )

        XCTAssertEqual(items.count, 1)
        XCTAssertEqual(items.first?.title, "Krafttraining")
        XCTAssertEqual(items.first?.id.kind, .workoutSession)
    }

    func testCompletedWorkoutUsesEndedAtForItsWeek() {
        let sunday = date(2026, 9, 6, 23, 30)
        let monday = date(2026, 9, 7, 0, 30)
        let completed = workout(id: "cross-week", startedAt: sunday, endedAt: monday)
        let items = CompletedActivityProjection.project(activities: [], workoutSessions: [completed])
        let calendar = CompletedActivityProjection.mondayThroughSundayCalendar(timeZone: timeZone)

        XCTAssertTrue(
            CompletedActivityProjection.items(items, inWeekContaining: monday, calendar: calendar).count == 1
        )
        XCTAssertTrue(
            CompletedActivityProjection.items(items, inWeekContaining: sunday, calendar: calendar).isEmpty
        )
    }

    func testLegacyCompletedWorkoutFallsBackToStartedAt() {
        let startedAt = date(2026, 9, 3, 9)
        let completed = workout(id: "legacy", startedAt: startedAt, endedAt: nil)

        let item = CompletedActivityProjection.project(
            activities: [],
            workoutSessions: [completed]
        ).first

        XCTAssertEqual(item?.date, startedAt)
    }

    func testLocalWeekIncludesMondayThroughSundayOnly() {
        let calendar = CompletedActivityProjection.mondayThroughSundayCalendar(timeZone: timeZone)
        let reference = date(2026, 9, 2, 12)
        let activities = [
            freeActivity(id: "previous-sunday", date: date(2026, 8, 30, 23, 59)),
            freeActivity(id: "monday", date: date(2026, 8, 31, 0, 0)),
            freeActivity(id: "sunday", date: date(2026, 9, 6, 23, 59)),
            freeActivity(id: "next-monday", date: date(2026, 9, 7, 0, 0))
        ]
        let items = CompletedActivityProjection.project(activities: activities, workoutSessions: [])

        let weeklyItems = CompletedActivityProjection.items(
            items,
            inWeekContaining: reference,
            calendar: calendar
        )

        XCTAssertEqual(Set(weeklyItems.map { $0.id.value }), ["monday", "sunday"])
    }

    func testMissingWorkoutCaloriesRemainUnavailableAndContributeZero() {
        let completed = workout(
            id: "workout",
            startedAt: date(2026, 9, 2, 9),
            endedAt: date(2026, 9, 2, 10),
            estimatedCalories: nil
        )
        let items = CompletedActivityProjection.project(activities: [], workoutSessions: [completed])

        XCTAssertNil(items.first?.estimatedCalories)
        XCTAssertEqual(
            CompletedActivityProjection.totals(for: items),
            CompletedActivityTotals(count: 1, estimatedCalories: 0)
        )
    }

    func testProjectionSortsNewestFirst() {
        let activities = [
            freeActivity(id: "oldest", date: date(2026, 9, 1, 12)),
            freeActivity(id: "newest", date: date(2026, 9, 3, 12))
        ]
        let middle = workout(id: "middle", startedAt: date(2026, 9, 2, 9), endedAt: date(2026, 9, 2, 10))

        let items = CompletedActivityProjection.project(
            activities: activities,
            workoutSessions: [middle]
        )

        XCTAssertEqual(items.map { $0.id.value }, ["newest", "middle", "oldest"])
    }

    private func freeActivity(
        id: String,
        date: Date,
        calories: Int = 200
    ) -> CompletedFreeActivity<String> {
        CompletedFreeActivity(
            id: id,
            date: date,
            type: "Wandern",
            durationMinutes: 60,
            estimatedCalories: calories
        )
    }

    private func workout(
        id: String,
        startedAt: Date,
        endedAt: Date?,
        estimatedCalories: Int? = 300,
        isCompleted: Bool = true
    ) -> WorkoutSessionActivity<String> {
        WorkoutSessionActivity(
            id: id,
            startedAt: startedAt,
            endedAt: endedAt,
            durationMinutes: 45,
            estimatedCalories: estimatedCalories,
            isCompleted: isCompleted
        )
    }

    private func date(
        _ year: Int,
        _ month: Int,
        _ day: Int,
        _ hour: Int,
        _ minute: Int = 0
    ) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        return calendar.date(
            from: DateComponents(
                year: year,
                month: month,
                day: day,
                hour: hour,
                minute: minute
            )
        )!
    }
}

import XCTest

@testable import ActivitySummaryKit

final class WeeklyActivityAchievementTests: XCTestCase {
    func testBelowGoalDoesNotEarnStar() {
        XCTAssertFalse(earned(count: 2, goal: 3))
    }

    func testMeetingGoalEarnsStar() {
        XCTAssertTrue(earned(count: 3, goal: 3))
    }

    func testExceedingGoalStillReturnsSingleEarnedState() {
        XCTAssertTrue(earned(count: 4, goal: 3))
        XCTAssertEqual(earned(count: 4, goal: 3), earned(count: 3, goal: 3))
        XCTAssertTrue(earned(count: Int.max, goal: 3))
    }

    func testZeroGoalNeverEarnsStar() {
        XCTAssertFalse(earned(count: 0, goal: 0))
        XCTAssertFalse(earned(count: 3, goal: 0))
    }

    func testNegativeGoalNeverEarnsStar() {
        XCTAssertFalse(earned(count: 3, goal: -1))
        XCTAssertFalse(earned(count: 0, goal: Int.min))
    }

    func testNegativeCountDoesNotEarnStar() {
        XCTAssertFalse(earned(count: -1, goal: 3))
    }

    func testCountReductionRemovesStarWithoutRememberingPreviousResult() {
        XCTAssertTrue(earned(count: 3, goal: 3))
        XCTAssertFalse(earned(count: 2, goal: 3))
    }

    func testIncreasingGoalRemovesStar() {
        XCTAssertTrue(earned(count: 3, goal: 3))
        XCTAssertFalse(earned(count: 3, goal: 4))
    }

    func testDecreasingGoalEarnsStar() {
        XCTAssertFalse(earned(count: 3, goal: 4))
        XCTAssertTrue(earned(count: 3, goal: 3))
    }

    private func earned(count: Int, goal: Int) -> Bool {
        WeeklyActivityAchievement.hasEarnedStar(
            weeklyCompletedActivityCount: count,
            activitiesPerWeekGoal: goal
        )
    }
}

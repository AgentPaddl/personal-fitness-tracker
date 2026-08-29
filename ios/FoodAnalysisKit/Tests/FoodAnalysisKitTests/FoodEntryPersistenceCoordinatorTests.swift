import XCTest

@testable import FoodAnalysisKit

final class FoodEntryPersistenceCoordinatorTests: XCTestCase {
    func testSuccessfulSaveInsertsOnceAndCommits() {
        let coordinator = FoodEntryPersistenceCoordinator()
        var insertCount = 0
        var persistCount = 0
        var rollbackCount = 0

        let result = coordinator.save(
            insert: { insertCount += 1 },
            persist: { persistCount += 1 },
            rollback: { rollbackCount += 1 }
        )

        XCTAssertEqual(result, .saved)
        XCTAssertEqual(insertCount, 1)
        XCTAssertEqual(persistCount, 1)
        XCTAssertEqual(rollbackCount, 0)
        XCTAssertTrue(coordinator.hasCommitted)
        XCTAssertFalse(coordinator.isSaving)
    }

    func testFailedSaveRollsBackAndLeavesNothingCommitted() {
        struct SaveError: Error {}
        let coordinator = FoodEntryPersistenceCoordinator()
        var insertCount = 0
        var rollbackCount = 0

        let result = coordinator.save(
            insert: { insertCount += 1 },
            persist: { throw SaveError() },
            rollback: { rollbackCount += 1 }
        )

        XCTAssertEqual(result, .failed)
        XCTAssertEqual(insertCount, 1)
        XCTAssertEqual(rollbackCount, 1)
        XCTAssertFalse(coordinator.hasCommitted)
        XCTAssertFalse(coordinator.isSaving)
    }

    func testRetryAfterFailureCanSucceed() {
        struct SaveError: Error {}
        let coordinator = FoodEntryPersistenceCoordinator()
        var attempt = 0
        var insertCount = 0
        var rollbackCount = 0

        func attemptSave() -> FoodEntrySaveResult {
            attempt += 1
            return coordinator.save(
                insert: { insertCount += 1 },
                persist: {
                    if attempt == 1 { throw SaveError() }
                },
                rollback: { rollbackCount += 1 }
            )
        }

        XCTAssertEqual(attemptSave(), .failed)
        XCTAssertEqual(attemptSave(), .saved)

        XCTAssertEqual(insertCount, 2)
        XCTAssertEqual(rollbackCount, 1)
        XCTAssertTrue(coordinator.hasCommitted)
    }

    func testDuplicateConfirmationAfterSuccessIsSkippedAndDoesNotPersistAgain() {
        let coordinator = FoodEntryPersistenceCoordinator()
        var insertCount = 0
        var persistCount = 0

        let first = coordinator.save(
            insert: { insertCount += 1 },
            persist: { persistCount += 1 },
            rollback: {}
        )
        let second = coordinator.save(
            insert: { insertCount += 1 },
            persist: { persistCount += 1 },
            rollback: {}
        )

        XCTAssertEqual(first, .saved)
        XCTAssertEqual(second, .skipped)
        XCTAssertEqual(insertCount, 1)
        XCTAssertEqual(persistCount, 1)
    }

    func testReentrantCallWhileSavingIsSkipped() {
        let coordinator = FoodEntryPersistenceCoordinator()
        var insertCount = 0
        var persistCount = 0
        var nestedResult: FoodEntrySaveResult?

        let result = coordinator.save(
            insert: { insertCount += 1 },
            persist: {
                persistCount += 1
                // Simulates a rapid duplicate tap arriving while the first
                // save is still in flight.
                nestedResult = coordinator.save(
                    insert: { insertCount += 1 },
                    persist: { persistCount += 1 },
                    rollback: {}
                )
            },
            rollback: {}
        )

        XCTAssertEqual(result, .saved)
        XCTAssertEqual(nestedResult, .skipped)
        XCTAssertEqual(insertCount, 1)
        XCTAssertEqual(persistCount, 1)
    }
}

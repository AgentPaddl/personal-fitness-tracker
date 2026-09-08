import XCTest

@testable import ActivitySummaryKit

final class WeightIncreaseMarkerTests: XCTestCase {
    private enum TestError: Error {
        case saveFailed
    }

    @MainActor
    func testActivatingPersistsCurrentTimeBeforePublishing() throws {
        let marker = WeightIncreaseMarker()
        let timestamp = Date(timeIntervalSince1970: 1_000_000)
        var stored: Date?
        var displayed: Date?

        XCTAssertTrue(try marker.setActive(
            true,
            currentValue: displayed,
            now: { timestamp },
            persist: { value in
                XCTAssertTrue(marker.isSaving)
                XCTAssertNil(displayed)
                stored = value
            },
            publish: { value in
                XCTAssertEqual(stored, timestamp)
                displayed = value
            }
        ))
        XCTAssertEqual(displayed, timestamp)
        XCTAssertFalse(marker.isSaving)
    }

    @MainActor
    func testDeactivatingPersistsAndPublishesNil() throws {
        let marker = WeightIncreaseMarker()
        var stored: Date? = Date(timeIntervalSince1970: 1_000_000)
        var displayed = stored

        try marker.setActive(
            false,
            currentValue: displayed,
            persist: { stored = $0 },
            publish: { displayed = $0 }
        )

        XCTAssertNil(stored)
        XCTAssertNil(displayed)
    }

    @MainActor
    func testSaveFailurePreservesPreviousValueAndAllowsRetry() throws {
        for original in [nil, Date(timeIntervalSince1970: 1_000_000)] as [Date?] {
            let marker = WeightIncreaseMarker()
            var displayed = original
            var didPublish = false

            XCTAssertThrowsError(try marker.setActive(
                original == nil,
                currentValue: displayed,
                persist: { _ in throw TestError.saveFailed },
                publish: {
                    didPublish = true
                    displayed = $0
                }
            ))
            XCTAssertEqual(displayed, original)
            XCTAssertFalse(didPublish)
            XCTAssertFalse(marker.isSaving)
            XCTAssertTrue(try marker.setActive(
                original == nil,
                currentValue: displayed,
                persist: { _ in },
                publish: { displayed = $0 }
            ))
        }
    }

    @MainActor
    func testReentrantChangeIsSkippedDuringSave() throws {
        let marker = WeightIncreaseMarker()
        let timestamp = Date(timeIntervalSince1970: 1_000_000)
        var saveCount = 0
        var displayed: Date?

        try marker.setActive(
            true,
            currentValue: nil,
            now: { timestamp },
            persist: { _ in
                saveCount += 1
                XCTAssertFalse(try marker.setActive(
                    false,
                    currentValue: timestamp,
                    persist: { _ in saveCount += 1 },
                    publish: { displayed = $0 }
                ))
            },
            publish: { displayed = $0 }
        )

        XCTAssertEqual(saveCount, 1)
        XCTAssertEqual(displayed, timestamp)
    }

    @MainActor
    func testRepeatedStateDoesNotSaveOrReplaceTimestamp() throws {
        let marker = WeightIncreaseMarker()
        for original in [nil, Date(timeIntervalSince1970: 1_000_000)] as [Date?] {
            XCTAssertFalse(try marker.setActive(
                original != nil,
                currentValue: original,
                persist: { _ in XCTFail("Unchanged state must not save") },
                publish: { _ in XCTFail("Unchanged state must not publish") }
            ))
        }
    }

    @MainActor
    func testRapidSequentialChangesStayConsistent() throws {
        let marker = WeightIncreaseMarker()
        var stored: Date?
        var displayed: Date?
        var saveCount = 0

        for index in 0..<100 {
            let active = index.isMultiple(of: 2)
            try marker.setActive(
                active,
                currentValue: displayed,
                now: { Date(timeIntervalSince1970: Double(index)) },
                persist: {
                    saveCount += 1
                    stored = $0
                },
                publish: { displayed = $0 }
            )
            XCTAssertEqual(stored, displayed)
            XCTAssertEqual(displayed != nil, active)
        }

        XCTAssertEqual(saveCount, 100)
        XCTAssertNil(displayed)
    }
}
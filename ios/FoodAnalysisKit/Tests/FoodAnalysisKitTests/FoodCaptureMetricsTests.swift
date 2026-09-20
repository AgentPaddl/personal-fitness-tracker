import Foundation
import XCTest
@testable import FoodAnalysisKit

final class FoodCaptureMetricsTests: XCTestCase {
    func testLocalReuseDoesNotConsumeOrFinishPendingAICapture() async {
        await MainActor.run {
            var now: Double = 0
            let metrics = FoodCaptureMetrics(clock: { now })
            let initial = metrics.begin()
            now = 2
            metrics.startOperation(UUID(), correction: false)
            now = 3
            let reuse = metrics.beginLocalCapture(kind: .productReuse)
            now = 5
            metrics.setActive(false)
            now = 15
            metrics.setActive(true)
            metrics.manualCorrection(captureID: reuse)
            metrics.saveResult(.failed, captureID: reuse)
            now = 18
            metrics.saveResult(.saved, captureID: reuse)
            metrics.finish(.discarded, captureID: reuse)
            XCTAssertEqual(metrics.currentID, initial)
            now = 20
            metrics.endOperation(succeeded: true)
            now = 22
            metrics.finish(.productSaved)
            let capture = metrics.archive.captures[0]
            let local = metrics.archive.captures[1]
            XCTAssertEqual(capture.activeSeconds, 7)
            XCTAssertEqual(capture.inactiveSeconds, 15)
            XCTAssertEqual(capture.operations[0].waitSeconds, 18)
            XCTAssertEqual(capture.operations[0].activeWaitSeconds, 3)
            XCTAssertEqual(capture.outcome, .productSaved)
            XCTAssertEqual(local.activeSeconds, 5)
            XCTAssertEqual(local.inactiveSeconds, 10)
            XCTAssertEqual(local.manualCorrectionRounds, 1)
            XCTAssertEqual(local.saveFailures, 1)
            XCTAssertEqual(local.outcome, .saved)
            XCTAssertTrue(local.operations.isEmpty)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 1)
            XCTAssertFalse(metrics.hasActiveCaptures)
        }
    }

    func testLocalCancellationRecoveryAndDeletionGuard() async throws {
        try await MainActor.run {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            let url = directory.appendingPathComponent("metrics.json")
            defer { try? FileManager.default.removeItem(at: directory) }
            let metrics = FoodCaptureMetrics(fileURL: url)
            let identifier = metrics.beginLocalCapture(kind: .productCreation)
            XCTAssertFalse(metrics.storageFailed)
            XCTAssertThrowsError(try metrics.deleteMeasurements())
            let recovered = FoodCaptureMetrics(fileURL: url)
            let record = try XCTUnwrap(recovered.archive.captures.first)
            XCTAssertEqual(record.outcome, .incomplete)
            XCTAssertFalse(record.timingComplete)
            metrics.finish(.discarded, captureID: identifier)
            metrics.saveResult(.skipped, captureID: identifier)
            XCTAssertEqual(metrics.archive.captures[0].outcome, .discarded)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 0)
            try metrics.deleteMeasurements()
        }
    }

    func testCaptureKindsAndLegacyArchiveCompatibility() async throws {
        try await MainActor.run {
            let metrics = FoodCaptureMetrics()
            metrics.begin()
            metrics.finish(.productSaved)
            metrics.begin(kind: .productReuse)
            metrics.saveResult(.saved)
            XCTAssertEqual(metrics.archive.captures.map(\.effectiveKind), [.aiCapture, .productReuse])
            XCTAssertTrue(metrics.archive.captures[1].operations.isEmpty)
            var legacy = metrics.archive
            legacy.captures[0].kind = nil
            let decoded = try JSONDecoder().decode(FoodCaptureMetrics.Archive.self,
                from: JSONEncoder().encode(legacy))
            XCTAssertEqual(decoded.captures[0].effectiveKind, .aiCapture)
            XCTAssertEqual(decoded.captures[1].effectiveKind, .productReuse)
        }
    }

    func testDeletingActiveCaptureIsRejectedAndFailedImportDoesNotBecomeKnown() async throws {
        try await MainActor.run {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: directory) }
            let url = directory.appendingPathComponent("metrics.json")
            let metrics = FoodCaptureMetrics(fileURL: url)
            let identifier = UUID()
            metrics.startOperation(identifier, correction: false)
            XCTAssertThrowsError(try metrics.deleteMeasurements())
            XCTAssertNotNil(metrics.currentID)
            metrics.endOperation(succeeded: true)
            metrics.finish(.discarded)
            try FileManager.default.removeItem(at: url)
            try FileManager.default.createDirectory(at: url, withIntermediateDirectories: false)
            let receipt = FoodCaptureMetrics.CostReceipt(costs: [.init(operationID: identifier, knownUSD: 1)])
            XCTAssertThrowsError(try metrics.importCosts(JSONEncoder().encode(receipt)))
            XCTAssertEqual(metrics.costSummary.knownOperations, 0)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 1)
            XCTAssertTrue(metrics.storageFailed)
        }
    }

    func testCostReceiptValidationIsAtomicAndDoesNotRetainAdditionalContent() async throws {
        try await MainActor.run {
            let metrics = FoodCaptureMetrics()
            let identifier = UUID()
            metrics.startOperation(identifier, correction: false)
            metrics.endOperation(succeeded: true)
            metrics.finish(.discarded)
            let valid = FoodOperationCost(operationID: identifier, knownUSD: 0)
            for costs in [[valid, valid], [valid, .init(operationID: UUID(), knownUSD: 1)],
                          [.init(operationID: identifier, knownUSD: -1)]] {
                let receipt = FoodCaptureMetrics.CostReceipt(costs: costs)
                XCTAssertThrowsError(try metrics.importCosts(JSONEncoder().encode(receipt)))
                XCTAssertTrue(metrics.archive.costs.isEmpty)
            }
            let receipt: [String: Any] = ["schemaVersion": 2, "costs": []]
            XCTAssertThrowsError(try metrics.importCosts(JSONSerialization.data(withJSONObject: receipt)))
            XCTAssertThrowsError(try metrics.importCosts(Data(repeating: 32, count: 1_000_001)))
            let extraContent: [String: Any] = [
                "schemaVersion": 1, "privateText": "synthetic-sensitive-content",
                "costs": [["operationID": identifier.uuidString, "knownUSD": 0,
                           "foodName": "synthetic-sensitive-content"]]
            ]
            try metrics.importCosts(JSONSerialization.data(withJSONObject: extraContent))
            XCTAssertEqual(metrics.costSummary.knownOperations, 1)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 0)
            let exported = String(data: try metrics.export(), encoding: .utf8)!
            XCTAssertFalse(exported.contains("synthetic-sensitive-content"))
            XCTAssertFalse(exported.contains("foodName"))
            XCTAssertFalse(exported.contains("privateText"))
        }
    }

    func testActiveCaptureAndWaitExcludeBackgroundAndSaveFailure() async throws {
        try await MainActor.run {
            var now: Double = 0
            let metrics = FoodCaptureMetrics(clock: { now })
            let review = metrics.begin()
            now = 3
            metrics.startOperation(UUID(), correction: false)
            now = 5
            metrics.setActive(false)
            now = 15
            metrics.setActive(true)
            now = 18
            metrics.endOperation(succeeded: true)
            metrics.manualCorrection()
            now = 20
            metrics.saveResult(.failed)
            XCTAssertEqual(metrics.archive.captures[0].outcome, .inProgress)
            now = 22
            metrics.saveResult(.saved)
            metrics.saveResult(.skipped)
            metrics.finish(.discarded)
            let record = try XCTUnwrap(metrics.archive.captures.first)
            XCTAssertEqual(record.id, review)
            XCTAssertEqual(record.activeSeconds, 12)
            XCTAssertEqual(record.inactiveSeconds, 10)
            XCTAssertEqual(record.operations[0].waitSeconds, 15)
            XCTAssertEqual(record.operations[0].activeWaitSeconds, 5)
            XCTAssertEqual(record.manualCorrectionRounds, 1)
            XCTAssertEqual(record.saveFailures, 1)
            XCTAssertEqual(record.outcome, .saved)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 1)
        }
    }

    func testCostsIncludeDiscardedAbortedAndRetriedOperationsWithoutDoubleCounting() async throws {
        try await MainActor.run {
            let metrics = FoodCaptureMetrics()
            let initial = UUID()
            let correction = UUID()
            metrics.startOperation(initial, correction: false)
            metrics.endOperation(succeeded: false)
            metrics.finish(.technicalAbort)
            metrics.startOperation(initial, correction: false)
            metrics.endOperation(succeeded: true)
            metrics.startOperation(correction, correction: true)
            metrics.endOperation(succeeded: false)
            metrics.finish(.discarded)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 2)
            let receipt = FoodCaptureMetrics.CostReceipt(costs: [.init(operationID: initial, knownUSD: Decimal(string: "0.00825")!)])
            let data = try JSONEncoder().encode(receipt)
            try metrics.importCosts(data)
            try metrics.importCosts(data)
            XCTAssertEqual(metrics.costSummary.knownUSD, Decimal(string: "0.00825"))
            XCTAssertEqual(metrics.costSummary.knownOperations, 1)
            XCTAssertEqual(metrics.costSummary.unknownOperations, 1)
            let export = try XCTUnwrap(JSONSerialization.jsonObject(with: metrics.export()) as? [String: Any])
            XCTAssertEqual(Set(export.keys), ["archive", "costSummary"])
            let encoded = String(data: try metrics.export(), encoding: .utf8)!
            for forbidden in ["foodName", "calories", "protein", "image", "description", "correctionText", "token"] {
                XCTAssertFalse(encoded.contains(forbidden))
            }
            let unknown = FoodCaptureMetrics.CostReceipt(costs: [.init(operationID: UUID(), knownUSD: 0)])
            XCTAssertThrowsError(try metrics.importCosts(JSONEncoder().encode(unknown)))
            let conflicting = FoodCaptureMetrics.CostReceipt(costs: [.init(operationID: initial, knownUSD: 0)])
            XCTAssertThrowsError(try metrics.importCosts(JSONEncoder().encode(conflicting)))
        }
    }

    func testInterruptedCaptureIsRecoveredAsIncompleteWithoutInventedDuration() async throws {
        try await MainActor.run {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: directory) }
            let url = directory.appendingPathComponent("metrics.json")
            var now: Double = 0
            let metrics = FoodCaptureMetrics(fileURL: url, clock: { now })
            metrics.startOperation(UUID(), correction: false)
            now = 7
            metrics.setActive(false)
            let recovered = FoodCaptureMetrics(fileURL: url, clock: { 1000 })
            XCTAssertEqual(recovered.archive.captures[0].outcome, .incomplete)
            XCTAssertFalse(recovered.archive.captures[0].timingComplete)
            XCTAssertFalse(recovered.archive.captures[0].operations[0].waitComplete)
            XCTAssertEqual(recovered.archive.captures[0].activeSeconds, 7)
            XCTAssertEqual(recovered.costSummary.unknownOperations, 1)
            XCTAssertNil(recovered.archive.captures[0].endedAt)
            try recovered.deleteMeasurements()
            XCTAssertFalse(FileManager.default.fileExists(atPath: url.path))
        }
    }

    func testCorruptStorageIsNotOverwrittenOrExportedAsEmpty() async throws {
        try await MainActor.run {
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: url) }
            let corrupt = Data("broken".utf8)
            try corrupt.write(to: url)
            let metrics = FoodCaptureMetrics(fileURL: url)
            metrics.begin()
            XCTAssertTrue(metrics.storageFailed)
            XCTAssertThrowsError(try metrics.export())
            XCTAssertEqual(try Data(contentsOf: url), corrupt)
        }
    }
}
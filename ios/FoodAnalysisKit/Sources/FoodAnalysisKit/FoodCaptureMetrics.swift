import Combine
import Foundation

public struct FoodCaptureMeasurement: Codable, Equatable, Identifiable {
    public enum Outcome: String, Codable { case inProgress, saved, discarded, technicalAbort, incomplete }
    public struct Operation: Codable, Equatable, Identifiable {
        public let id: UUID
        public let isCorrection: Bool
        public var sends = 1
        public var completedResponses = 0
        public var technicalAborts = 0
        public var waitSeconds: Double = 0
        public var activeWaitSeconds: Double = 0
        public var waitComplete = false
    }

    public let id: UUID
    public let startedAt: Date
    public var endedAt: Date?
    public var outcome: Outcome = .inProgress
    public var activeSeconds: Double = 0
    public var inactiveSeconds: Double = 0
    public var timingComplete = true
    public var manualCorrectionRounds = 0
    public var saveFailures = 0
    public var operations: [Operation] = []
}

public struct FoodOperationCost: Codable, Equatable {
    public let operationID: UUID
    public let knownUSD: Decimal

    public init(operationID: UUID, knownUSD: Decimal) {
        self.operationID = operationID
        self.knownUSD = knownUSD
    }
}

@MainActor
public final class FoodCaptureMetrics: ObservableObject {
    public struct Archive: Codable {
        public var schemaVersion = 1
        public var captures: [FoodCaptureMeasurement] = []
        public var costs: [FoodOperationCost] = []
    }
    public struct CostReceipt: Codable {
        public let schemaVersion: Int
        public let costs: [FoodOperationCost]

        public init(costs: [FoodOperationCost]) {
            schemaVersion = 1
            self.costs = costs
        }
    }
    public struct CostSummary: Codable {
        public let knownUSD: Decimal
        public let knownOperations: Int
        public let unknownOperations: Int
    }
    private struct Export: Encodable {
        let archive: Archive
        let costSummary: CostSummary
    }

    @Published public private(set) var storageFailed = false
    public private(set) var archive = Archive()
    @Published public private(set) var currentID: UUID?
    private let fileURL: URL?
    private let clock: () -> Double
    private let date: () -> Date
    private var lastTick: Double?
    private var active = true
    private var pendingOperation: UUID?
    private var readable = true

    public init(fileURL: URL? = nil, clock: @escaping () -> Double = FoodCaptureMetrics.monotonicTime,
                date: @escaping () -> Date = Date.init) {
        self.fileURL = fileURL
        self.clock = clock
        self.date = date
        if let fileURL, FileManager.default.fileExists(atPath: fileURL.path) {
            do {
                archive = try JSONDecoder().decode(Archive.self, from: Data(contentsOf: fileURL))
                guard archive.schemaVersion == 1 else { throw CocoaError(.coderInvalidValue) }
                for index in archive.captures.indices where archive.captures[index].outcome == .inProgress {
                    archive.captures[index].outcome = .incomplete
                    archive.captures[index].timingComplete = false
                }
                persist()
            } catch {
                storageFailed = true
                readable = false
            }
        }
    }

    nonisolated public static func monotonicTime() -> Double {
        Double(clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW)) / 1_000_000_000
    }

    public static func local() -> FoodCaptureMetrics {
        let directory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("LocalProductMetrics", isDirectory: true)
        return FoodCaptureMetrics(fileURL: directory.appendingPathComponent("captures-v1.json"))
    }

    @discardableResult
    public func begin() -> UUID {
        if let currentID { return currentID }
        let identifier = UUID()
        currentID = identifier
        lastTick = clock()
        archive.captures.append(FoodCaptureMeasurement(id: identifier, startedAt: date()))
        persist()
        return identifier
    }

    public func setActive(_ value: Bool) {
        checkpoint()
        active = value
        persist()
    }

    public func startOperation(_ identifier: UUID, correction: Bool) {
        let hasCaptureStart = currentID != nil
        begin()
        checkpoint()
        guard let index = currentIndex else { return }
        if !hasCaptureStart { archive.captures[index].timingComplete = false }
        if let operation = archive.captures[index].operations.firstIndex(where: { $0.id == identifier }) {
            archive.captures[index].operations[operation].sends += 1
            archive.captures[index].operations[operation].waitComplete = false
        } else {
            archive.captures[index].operations.append(.init(id: identifier, isCorrection: correction))
        }
        pendingOperation = identifier
        persist()
    }

    public func endOperation(succeeded: Bool) {
        checkpoint()
        if let index = currentIndex, let operation = archive.captures[index].operations.firstIndex(where: { $0.id == pendingOperation }) {
            archive.captures[index].operations[operation].waitComplete = true
            if succeeded { archive.captures[index].operations[operation].completedResponses += 1 }
            else { archive.captures[index].operations[operation].technicalAborts += 1 }
        }
        pendingOperation = nil
        persist()
    }

    public func manualCorrection() {
        guard let index = currentIndex else { return }
        archive.captures[index].manualCorrectionRounds += 1
        persist()
    }

    public func saveResult(_ result: FoodEntrySaveResult) {
        switch result {
        case .saved: finish(.saved)
        case .failed:
            if let index = currentIndex { archive.captures[index].saveFailures += 1 }
            checkpoint()
            persist()
        case .skipped: break
        }
    }

    public func finish(_ outcome: FoodCaptureMeasurement.Outcome) {
        checkpoint()
        guard let index = currentIndex else { return }
        if pendingOperation != nil {
            endOperation(succeeded: false)
            archive.captures[index].timingComplete = false
        }
        archive.captures[index].outcome = outcome
        archive.captures[index].endedAt = date()
        if outcome == .incomplete { archive.captures[index].timingComplete = false }
        currentID = nil
        lastTick = nil
        persist()
    }

    public var costSummary: CostSummary {
        let identifiers = Set(archive.captures.flatMap { $0.operations.map(\.id) })
        let known = archive.costs.filter { identifiers.contains($0.operationID) }
        return CostSummary(knownUSD: known.reduce(Decimal.zero) { $0 + $1.knownUSD },
                           knownOperations: known.count, unknownOperations: identifiers.count - known.count)
    }

    public func importCosts(_ data: Data) throws {
        guard readable, data.count <= 1_000_000 else { throw CocoaError(.fileReadCorruptFile) }
        let receipt = try JSONDecoder().decode(CostReceipt.self, from: data)
        let identifiers = Set(archive.captures.flatMap { $0.operations.map(\.id) })
        guard receipt.schemaVersion == 1,
              Set(receipt.costs.map(\.operationID)).count == receipt.costs.count,
              receipt.costs.allSatisfy({ identifiers.contains($0.operationID) && !$0.knownUSD.isNaN && $0.knownUSD >= 0 })
        else { throw CocoaError(.coderInvalidValue) }
        for item in receipt.costs {
            if let previous = archive.costs.first(where: { $0.operationID == item.operationID }), previous != item {
                throw CocoaError(.coderInvalidValue)
            }
        }
        let previousCosts = archive.costs
        for item in receipt.costs where !archive.costs.contains(where: { $0.operationID == item.operationID }) {
            archive.costs.append(item)
        }
        persist()
        if storageFailed {
            archive.costs = previousCosts
            throw CocoaError(.fileWriteUnknown)
        }
    }

    public func export() throws -> Data {
        checkpoint()
        persist()
        guard !storageFailed else { throw CocoaError(.fileReadCorruptFile) }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(Export(archive: archive, costSummary: costSummary))
    }

    public func deleteMeasurements() throws {
        guard currentID == nil else { throw CocoaError(.fileWriteUnknown) }
        if let fileURL, FileManager.default.fileExists(atPath: fileURL.path) {
            try FileManager.default.removeItem(at: fileURL)
        }
        archive = Archive()
        currentID = nil
        pendingOperation = nil
        lastTick = nil
        readable = true
        storageFailed = false
    }

    private var currentIndex: Int? { archive.captures.firstIndex { $0.id == currentID } }

    private func checkpoint() {
        guard let index = currentIndex, let previous = lastTick else { return }
        let now = clock()
        let elapsed = now - previous
        lastTick = now
        guard elapsed.isFinite, elapsed >= 0 else {
            archive.captures[index].timingComplete = false
            return
        }
        if active { archive.captures[index].activeSeconds += elapsed }
        else { archive.captures[index].inactiveSeconds += elapsed }
        if let operation = archive.captures[index].operations.firstIndex(where: { $0.id == pendingOperation }) {
            archive.captures[index].operations[operation].waitSeconds += elapsed
            if active { archive.captures[index].operations[operation].activeWaitSeconds += elapsed }
        }
    }

    private func persist() {
        guard readable else { return }
        guard let fileURL else { return }
        do {
            var directory = fileURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try directory.setResourceValues(values)
            let data = try JSONEncoder().encode(archive)
#if os(iOS)
            try data.write(to: fileURL, options: [.atomic, .completeFileProtection])
#else
            try data.write(to: fileURL, options: .atomic)
#endif
            storageFailed = false
        } catch { storageFailed = true }
    }
}
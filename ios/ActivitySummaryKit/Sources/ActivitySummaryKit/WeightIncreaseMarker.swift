import Foundation

@MainActor
public final class WeightIncreaseMarker {
    public private(set) var isSaving = false

    public init() {}

    @discardableResult
    public func setActive(
        _ isActive: Bool,
        currentValue: Date?,
        now: () -> Date = Date.init,
        persist: (Date?) throws -> Void,
        publish: (Date?) -> Void
    ) throws -> Bool {
        guard !isSaving, isActive != (currentValue != nil) else {
            return false
        }

        isSaving = true
        defer { isSaving = false }

        let value = isActive ? now() : nil
        try persist(value)
        publish(value)
        return true
    }
}
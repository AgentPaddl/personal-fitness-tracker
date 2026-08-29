/// Result of one `FoodEntryPersistenceCoordinator.save` attempt.
public enum FoodEntrySaveResult: Equatable, Sendable {
    /// The entry was inserted and the underlying store save succeeded.
    case saved
    /// The store save threw; the caller's `rollback` closure was invoked
    /// so no pending/persisted object remains, and a retry is allowed.
    case failed
    /// No-op: a save was already in flight, or this instance already
    /// committed once. Guarantees a duplicate confirmation (e.g. a rapid
    /// double tap) can never persist the same review twice.
    case skipped
}

/// Coordinates a single insert-then-save persistence attempt with rollback
/// on failure, and guarantees at most one successful commit per instance.
///
/// Deliberately generic over plain closures rather than a concrete
/// persistence framework type (e.g. SwiftData's `ModelContext`), so this
/// orchestration - the part that actually matters for correctness - can be
/// unit tested without a persistence stack. Callers own construction of the
/// object to insert and the `ModelContext` calls themselves.
public final class FoodEntryPersistenceCoordinator {
    public private(set) var isSaving = false
    public private(set) var hasCommitted = false

    public init() {}

    /// - Parameters:
    ///   - insert: Inserts the new object into the persistence context.
    ///   - persist: Attempts to commit the store (e.g. `ModelContext.save()`).
    ///   - rollback: Undoes `insert` if `persist` throws (e.g.
    ///     `ModelContext.delete(_:)` on the same object).
    @discardableResult
    public func save(
        insert: () -> Void,
        persist: () throws -> Void,
        rollback: () -> Void
    ) -> FoodEntrySaveResult {
        guard !isSaving, !hasCommitted else { return .skipped }

        isSaving = true
        defer { isSaving = false }

        insert()
        do {
            try persist()
            hasCommitted = true
            return .saved
        } catch {
            rollback()
            return .failed
        }
    }
}

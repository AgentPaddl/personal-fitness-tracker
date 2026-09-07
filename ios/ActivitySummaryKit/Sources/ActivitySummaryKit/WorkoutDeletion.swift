public struct WorkoutDeletionPerformance<ID: Hashable>: Equatable {
    public let id: ID
    public let workoutSessionID: ID?
    public let exerciseID: ID?

    public init(id: ID, workoutSessionID: ID?, exerciseID: ID?) {
        self.id = id
        self.workoutSessionID = workoutSessionID
        self.exerciseID = exerciseID
    }
}

public struct WorkoutDeletionSet<ID: Hashable>: Equatable {
    public let id: ID
    public let performanceID: ID?

    public init(id: ID, performanceID: ID?) {
        self.id = id
        self.performanceID = performanceID
    }
}

public struct WorkoutDeletionPlan<ID: Hashable>: Equatable {
    public let workoutSessionID: ID
    public let performanceIDs: [ID]
    public let setIDs: [ID]

    public init(workoutSessionID: ID, performanceIDs: [ID], setIDs: [ID]) {
        self.workoutSessionID = workoutSessionID
        self.performanceIDs = performanceIDs
        self.setIDs = setIDs
    }
}

public enum WorkoutDeletionPlanner {
    public static func plan<ID: Hashable>(
        workoutSessionID: ID,
        performances: [WorkoutDeletionPerformance<ID>],
        sets: [WorkoutDeletionSet<ID>]
    ) -> WorkoutDeletionPlan<ID> {
        let performanceIDs = performances
            .filter { $0.workoutSessionID == workoutSessionID }
            .map(\.id)
        let selectedPerformanceIDs = Set(performanceIDs)
        let setIDs = sets
            .filter { performanceID in
                guard let id = performanceID.performanceID else {
                    return false
                }
                return selectedPerformanceIDs.contains(id)
            }
            .map(\.id)

        return WorkoutDeletionPlan(
            workoutSessionID: workoutSessionID,
            performanceIDs: performanceIDs,
            setIDs: setIDs
        )
    }
}

public enum WorkoutDeletionResult: Equatable {
    case deleted
    case failed
    case skipped
}

public final class WorkoutDeletionCoordinator<ID: Hashable> {
    private var isDeleting = false
    private var deletedSessionIDs: Set<ID> = []

    public init() {}

    public func delete(
        plan: WorkoutDeletionPlan<ID>,
        deleteSet: (ID) -> Void,
        deletePerformance: (ID) -> Void,
        deleteWorkoutSession: (ID) -> Void,
        persist: () throws -> Void,
        rollback: () -> Void
    ) -> WorkoutDeletionResult {
        guard !isDeleting, !deletedSessionIDs.contains(plan.workoutSessionID) else {
            return .skipped
        }

        isDeleting = true
        defer { isDeleting = false }

        plan.setIDs.forEach(deleteSet)
        plan.performanceIDs.forEach(deletePerformance)
        deleteWorkoutSession(plan.workoutSessionID)

        do {
            try persist()
            deletedSessionIDs.insert(plan.workoutSessionID)
            return .deleted
        } catch {
            rollback()
            return .failed
        }
    }
}

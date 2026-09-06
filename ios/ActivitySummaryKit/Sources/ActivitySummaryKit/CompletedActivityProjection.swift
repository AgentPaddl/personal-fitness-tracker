import Foundation

public enum CompletedActivitySourceKind: Hashable {
    case activity
    case workoutSession
}

public struct CompletedActivitySourceID<ID: Hashable>: Hashable {
    public let kind: CompletedActivitySourceKind
    public let value: ID

    public init(kind: CompletedActivitySourceKind, value: ID) {
        self.kind = kind
        self.value = value
    }
}

public struct CompletedActivitySummary<ID: Hashable>: Identifiable {
    public let id: CompletedActivitySourceID<ID>
    public let date: Date
    public let title: String
    public let durationMinutes: Int
    public let estimatedCalories: Int?

    public init(
        id: CompletedActivitySourceID<ID>,
        date: Date,
        title: String,
        durationMinutes: Int,
        estimatedCalories: Int?
    ) {
        self.id = id
        self.date = date
        self.title = title
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
    }
}

public struct CompletedFreeActivity<ID: Hashable> {
    public let id: ID
    public let date: Date
    public let type: String
    public let durationMinutes: Int
    public let estimatedCalories: Int

    public init(
        id: ID,
        date: Date,
        type: String,
        durationMinutes: Int,
        estimatedCalories: Int
    ) {
        self.id = id
        self.date = date
        self.type = type
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
    }
}

public struct WorkoutSessionActivity<ID: Hashable> {
    public let id: ID
    public let startedAt: Date
    public let endedAt: Date?
    public let durationMinutes: Int?
    public let estimatedCalories: Int?
    public let isCompleted: Bool

    public init(
        id: ID,
        startedAt: Date,
        endedAt: Date?,
        durationMinutes: Int?,
        estimatedCalories: Int?,
        isCompleted: Bool
    ) {
        self.id = id
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.durationMinutes = durationMinutes
        self.estimatedCalories = estimatedCalories
        self.isCompleted = isCompleted
    }
}

public struct CompletedActivityTotals: Equatable {
    public let count: Int
    public let estimatedCalories: Int

    public init(count: Int, estimatedCalories: Int) {
        self.count = count
        self.estimatedCalories = estimatedCalories
    }
}

public enum CompletedActivityProjection {
    public static func project<ID: Hashable>(
        activities: [CompletedFreeActivity<ID>],
        workoutSessions: [WorkoutSessionActivity<ID>]
    ) -> [CompletedActivitySummary<ID>] {
        let activityItems = activities.map { activity in
            CompletedActivitySummary(
                id: CompletedActivitySourceID(kind: .activity, value: activity.id),
                date: activity.date,
                title: activity.type,
                durationMinutes: activity.durationMinutes,
                estimatedCalories: activity.estimatedCalories
            )
        }

        let workoutItems = workoutSessions.compactMap { workout -> CompletedActivitySummary<ID>? in
            guard workout.isCompleted else {
                return nil
            }

            return CompletedActivitySummary(
                id: CompletedActivitySourceID(kind: .workoutSession, value: workout.id),
                date: workout.endedAt ?? workout.startedAt,
                title: "Krafttraining",
                durationMinutes: workout.durationMinutes ?? 0,
                estimatedCalories: workout.estimatedCalories
            )
        }

        return (activityItems + workoutItems).sorted { $0.date > $1.date }
    }

    public static func mondayThroughSundayCalendar(
        timeZone: TimeZone = .current
    ) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        calendar.firstWeekday = 2
        calendar.minimumDaysInFirstWeek = 4
        return calendar
    }

    public static func items<ID: Hashable>(
        _ items: [CompletedActivitySummary<ID>],
        inWeekContaining date: Date,
        calendar: Calendar
    ) -> [CompletedActivitySummary<ID>] {
        let day = calendar.startOfDay(for: date)
        let daysSinceMonday = (calendar.component(.weekday, from: day) + 5) % 7
        guard
            let monday = calendar.date(byAdding: .day, value: -daysSinceMonday, to: day),
            let nextMonday = calendar.date(byAdding: .day, value: 7, to: monday)
        else {
            return []
        }

        return items.filter { $0.date >= monday && $0.date < nextMonday }
    }

    public static func totals<ID: Hashable>(
        for items: [CompletedActivitySummary<ID>]
    ) -> CompletedActivityTotals {
        CompletedActivityTotals(
            count: items.count,
            estimatedCalories: items.reduce(0) { result, item in
                result + (item.estimatedCalories ?? 0)
            }
        )
    }
}

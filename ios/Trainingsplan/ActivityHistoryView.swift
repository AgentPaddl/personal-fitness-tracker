import SwiftUI
import SwiftData
import ActivitySummaryKit

struct ActivityHistoryView: View {
    @Environment(\.modelContext) private var modelContext

    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]

    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]
    
    @State private var selectedActivityToEdit: Activity?

    var body: some View {
        List {
            if completedActivities.isEmpty {
                Text("Noch keine Aktivitäten")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(completedActivities) { item in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Label(item.title, systemImage: icon(for: item))

                            Spacer()

                            Text(
                                item.date,
                                format: .dateTime.day().month().year()
                            )
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .fontWeight(.semibold)

                        if let calories = item.estimatedCalories {
                            Text("\(item.durationMinutes) Min. · ca. \(calories) kcal")
                                .foregroundStyle(.secondary)
                        } else {
                            Text("\(item.durationMinutes) Min. · Keine Schätzung")
                                .foregroundStyle(.secondary)
                        }

                        if let weight = bodyWeight(for: item) {
                            Text("Körpergewicht: \(weight, specifier: "%.1f") kg")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 3)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        if let activity = activity(for: item) {
                            selectedActivityToEdit = activity
                        }
                    }
                    .swipeActions {
                        if let activity = activity(for: item) {
                            Button(role: .destructive) {
                                deleteActivity(activity)
                            } label: {
                                Label("Löschen", systemImage: "trash")
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Aktivitätshistorie")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $selectedActivityToEdit) { activity in
            EditActivityView(activity: activity)
        }
    }

    private var completedActivities: [AppCompletedActivity] {
        completedActivitySummaries(
            activities: activities,
            workoutSessions: workoutSessions
        )
    }

    private func activity(for item: AppCompletedActivity) -> Activity? {
        guard item.id.kind == .activity else {
            return nil
        }

        return activities.first { $0.persistentModelID == item.id.value }
    }

    private func workout(for item: AppCompletedActivity) -> WorkoutSession? {
        guard item.id.kind == .workoutSession else {
            return nil
        }

        return workoutSessions.first { $0.persistentModelID == item.id.value }
    }

    private func icon(for item: AppCompletedActivity) -> String {
        item.id.kind == .workoutSession ? "dumbbell.fill" : "figure.walk"
    }

    private func bodyWeight(for item: AppCompletedActivity) -> Double? {
        activity(for: item)?.bodyWeightKg ?? workout(for: item)?.bodyWeightKg
    }

    private func deleteActivity(_ activity: Activity) {
        modelContext.delete(activity)

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Löschen der Aktivität:", error)
        }
    }
}

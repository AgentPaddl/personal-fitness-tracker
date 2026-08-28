import SwiftUI
import SwiftData

struct ActivityHistoryView: View {
    @Environment(\.modelContext) private var modelContext

    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]

    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]
    
    @State private var selectedActivityToEdit: Activity?

    var body: some View {
        List {
            if historyItems.isEmpty {
                Text("Noch keine Aktivitäten")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(historyItems) { item in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Label(item.title, systemImage: item.icon)

                            Spacer()

                            Text(
                                item.date,
                                format: .dateTime.day().month().year()
                            )
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .fontWeight(.semibold)

                        Text("\(item.durationMinutes) Min. · ca. \(item.calories) kcal")
                            .foregroundStyle(.secondary)

                        if let weight = item.bodyWeightKg {
                            Text("Körpergewicht: \(weight, specifier: "%.1f") kg")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 3)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        if case .activity(let activity) = item.source {
                            selectedActivityToEdit = activity
                        }
                    }
                    .swipeActions {
                        if case .activity(let activity) = item.source {
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

    private var historyItems: [ActivityHistoryItem] {
        let activityItems = activities.map { activity in
            ActivityHistoryItem(
                title: activity.type,
                icon: "figure.walk",
                date: activity.date,
                durationMinutes: activity.durationMinutes,
                calories: activity.estimatedCalories,
                bodyWeightKg: activity.bodyWeightKg,
                source: .activity(activity)
            )
        }

        let workoutItems = workoutSessions
            .filter { $0.isCompleted }
            .map { workout in
                ActivityHistoryItem(
                    title: "Krafttraining",
                    icon: "dumbbell.fill",
                    date: workout.startedAt,
                    durationMinutes: workout.durationMinutes ?? 0,
                    calories: workout.estimatedCalories ?? 0,
                    bodyWeightKg: workout.bodyWeightKg,
                    source: .workout(workout)
                )
            }

        return (activityItems + workoutItems)
            .sorted { $0.date > $1.date }
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

private struct ActivityHistoryItem: Identifiable {
    let id = UUID()

    let title: String
    let icon: String
    let date: Date
    let durationMinutes: Int
    let calories: Int
    let bodyWeightKg: Double?
    let source: ActivityHistorySource
}

private enum ActivityHistorySource {
    case activity(Activity)
    case workout(WorkoutSession)
}

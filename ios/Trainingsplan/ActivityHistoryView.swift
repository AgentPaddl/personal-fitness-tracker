import SwiftUI
import SwiftData
import ActivitySummaryKit

struct ActivityHistoryView: View {
    @Environment(\.modelContext) private var modelContext

    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]

    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]

    @Query(sort: \ExercisePerformance.orderIndex)
    private var performances: [ExercisePerformance]

    @Query(sort: \WorkoutSet.setNumber)
    private var workoutSets: [WorkoutSet]
    
    @State private var selectedActivityToEdit: Activity?
    @State private var workoutPendingDeletion: AppCompletedActivity?
    @State private var workoutDeleteError: String?
    @State private var workoutDeletionService = WorkoutSessionDeletionService()

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
                        } else if item.id.kind == .workoutSession {
                            Button(role: .destructive) {
                                workoutPendingDeletion = item
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
        .confirmationDialog(
            "Krafttraining löschen?",
            isPresented: workoutDeleteConfirmationIsPresented,
            presenting: workoutPendingDeletion
        ) { item in
            Button("Krafttraining löschen", role: .destructive) {
                deleteWorkout(item)
            }
            Button("Abbrechen", role: .cancel) {}
        } message: { _ in
            Text("Das Training wird einschließlich seiner Sätze dauerhaft aus Verlauf und Wochenstatistik entfernt.")
        }
        .alert(
            "Krafttraining konnte nicht gelöscht werden",
            isPresented: workoutDeleteErrorIsPresented
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(workoutDeleteError ?? "Bitte versuche es erneut.")
        }
    }

    private var completedActivities: [AppCompletedActivity] {
        completedActivitySummaries(
            activities: activities,
            workoutSessions: workoutSessions
        )
    }

    private var workoutDeleteErrorIsPresented: Binding<Bool> {
        Binding(
            get: { workoutDeleteError != nil },
            set: { isPresented in
                if !isPresented {
                    workoutDeleteError = nil
                }
            }
        )
    }

    private var workoutDeleteConfirmationIsPresented: Binding<Bool> {
        Binding(
            get: { workoutPendingDeletion != nil },
            set: { isPresented in
                if !isPresented {
                    workoutPendingDeletion = nil
                }
            }
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

    private func deleteWorkout(_ item: AppCompletedActivity) {
        let result = workoutDeletionService.delete(
            sourceID: item.id,
            workoutSessions: workoutSessions,
            performances: performances,
            workoutSets: workoutSets,
            modelContext: modelContext
        )

        switch result {
        case .deleted:
            workoutPendingDeletion = nil
        case .failed:
            workoutDeleteError = "Das Krafttraining wurde nicht gelöscht. Deine Daten bleiben erhalten. Bitte versuche es erneut."
        case .skipped:
            break
        }
    }
}

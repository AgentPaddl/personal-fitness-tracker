import SwiftUI
import SwiftData
import ActivitySummaryKit

struct TrainingView: View {
    @Environment(\.modelContext) private var modelContext
    
    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]

    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]

    @Query(sort: \ExercisePerformance.orderIndex)
    private var performances: [ExercisePerformance]

    @Query(sort: \WorkoutSet.setNumber)
    private var workoutSets: [WorkoutSet]
    
    @Query(sort: \WeightEntry.date, order: .reverse)
    private var weightEntries: [WeightEntry]
    
    @State private var activityType = ""
    @State private var durationText = ""
    @State private var caloriesText = ""
    @State private var selectedActivityToEdit: Activity?
    @State private var workoutPendingDeletion: AppCompletedActivity?
    @State private var workoutDeleteError: String?
    @State private var workoutDeletionService = WorkoutSessionDeletionService()
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Krafttraining") {
                    NavigationLink {
                        WorkoutSessionView()
                    } label: {
                        Label("Krafttraining starten", systemImage: "dumbbell.fill")
                    }
                }
                Section("Aktivität hinzufügen") {
                    TextField("Aktivität, z. B. Yoga", text: $activityType)
                    
                    TextField("Dauer in Minuten", text: $durationText)
                        .keyboardType(.numberPad)
                    
                    TextField("Geschätzte Kalorien", text: $caloriesText)
                        .keyboardType(.numberPad)
                    
                    Button("Aktivität speichern") {
                        saveActivity()
                    }
                    .disabled(!canSave)
                }
                
                Section("Letzte Aktivitäten") {
                    if completedActivities.isEmpty {
                        Text("Noch keine Aktivitäten")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(recentActivities) { item in
                            VStack(alignment: .leading, spacing: 5) {
                                HStack {
                                    Text(item.title)
                                        .fontWeight(.semibold)
                                    
                                    Spacer()
                                    
                                    Text(item.date, format: .dateTime.day().month().year())
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                
                                if let calories = item.estimatedCalories {
                                    Text("\(item.durationMinutes) Min. · ca. \(calories) kcal")
                                        .foregroundStyle(.secondary)
                                } else {
                                    Text("\(item.durationMinutes) Min. · Keine Schätzung")
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selectedActivityToEdit = activity(for: item)
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
                        
                        NavigationLink {
                            ActivityHistoryView()
                        } label: {
                            Text("Alle Aktivitäten anzeigen")
                        }
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Training")
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
        
    }
    
    private var completedActivities: [AppCompletedActivity] {
        completedActivitySummaries(
            activities: activities,
            workoutSessions: workoutSessions
        )
    }

    private var recentActivities: [AppCompletedActivity] {
        Array(completedActivities.prefix(5))
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
    
    private var canSave: Bool {
        !activityType.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        parsedDuration != nil &&
        parsedCalories != nil
    }
    
    private var parsedDuration: Int? {
        guard let value = Int(durationText), value > 0 else {
            return nil
        }
        
        return value
    }
    
    private var parsedCalories: Int? {
        guard let value = Int(caloriesText), value >= 0 else {
            return nil
        }
        
        return value
    }
    
    private var latestWeight: Double? {
        weightEntries.first?.weightKg
    }
    
    private func saveActivity() {
        guard
            let duration = parsedDuration,
            let calories = parsedCalories
        else {
            return
        }
        
        let activity = Activity(
            type: activityType.trimmingCharacters(in: .whitespacesAndNewlines),
            date: Date(),
            durationMinutes: duration,
            estimatedCalories: calories,
            bodyWeightKg: latestWeight
        )
        
        modelContext.insert(activity)
        
        do {
            try modelContext.save()
            
            activityType = ""
            durationText = ""
            caloriesText = ""
        } catch {
            print("Fehler beim Speichern der Aktivität:", error)
        }
    }
    private func activity(for item: AppCompletedActivity) -> Activity? {
        guard item.id.kind == .activity else {
            return nil
        }

        return activities.first { $0.persistentModelID == item.id.value }
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

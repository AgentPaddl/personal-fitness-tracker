import SwiftUI
import SwiftData

struct TrainingView: View {
    @Environment(\.modelContext) private var modelContext
    
    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]
    
    @Query(sort: \WeightEntry.date, order: .reverse)
    private var weightEntries: [WeightEntry]
    
    @State private var activityType = ""
    @State private var durationText = ""
    @State private var caloriesText = ""
    @State private var selectedActivityToEdit: Activity?
    
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
                    if activities.isEmpty {
                        Text("Noch keine Aktivitäten")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(recentActivities) { activity in
                            VStack(alignment: .leading, spacing: 5) {
                                HStack {
                                    Text(activity.type)
                                        .fontWeight(.semibold)
                                    
                                    Spacer()
                                    
                                    Text(activity.date, format: .dateTime.day().month().year())
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                
                                Text("\(activity.durationMinutes) Min. · ca. \(activity.estimatedCalories) kcal")
                                    .foregroundStyle(.secondary)
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selectedActivityToEdit = activity
                            }
                        }
                        .onDelete(perform: deleteActivities)
                        
                        if activities.count > 5 {
                            NavigationLink {
                                ActivityHistoryView()
                            } label: {
                                Text("Alle Aktivitäten anzeigen")
                            }
                        }
                    }
                }
            }
            .navigationTitle("Training")
            .sheet(item: $selectedActivityToEdit) { activity in
                EditActivityView(activity: activity)
            }
        }
        
    }
    
    private var recentActivities: [Activity] {
        Array(activities.prefix(5))
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
    private func deleteActivities(at offsets: IndexSet) {
        for index in offsets {
            let activity = recentActivities[index]
            modelContext.delete(activity)
        }

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Löschen der Aktivität:", error)
        }
    }
}

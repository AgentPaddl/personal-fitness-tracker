import SwiftUI
import SwiftData

struct WorkoutFinishView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let session: WorkoutSession
    let durationMinutes: Int
    let estimatedCalories: Int
    let onSaved: () -> Void

    @State private var caloriesText = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Training") {
                    LabeledContent("Dauer") {
                        Text("\(durationMinutes) Min.")
                    }

                    if let bodyWeight = session.bodyWeightKg {
                        LabeledContent("Körpergewicht") {
                            Text("\(bodyWeight, specifier: "%.1f") kg")
                        }
                    }
                }

                Section("Kalorienverbrauch") {
                    TextField("Kalorien", text: $caloriesText)
                        .keyboardType(.numberPad)

                    Text("Lokaler Schätzwert. Du kannst ihn vor dem Speichern ändern.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Training abschließen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        saveWorkout()
                    }
                    .disabled(parsedCalories == nil)
                }
            }
            .onAppear {
                caloriesText = String(estimatedCalories)
            }
        }
    }

    private var parsedCalories: Int? {
        guard let value = Int(caloriesText), value >= 0 else {
            return nil
        }

        return value
    }

    private func saveWorkout() {
        guard let calories = parsedCalories else {
            return
        }

        let endDate = Date()

        session.endedAt = endDate
        session.durationMinutes = durationMinutes
        session.estimatedCalories = calories
        session.isCompleted = true

        do {
            try modelContext.save()
            onSaved()
            dismiss()
        } catch {
            print("Fehler beim Abschließen des Trainings:", error)
        }
    }
}

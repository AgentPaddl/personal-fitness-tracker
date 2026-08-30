import SwiftUI
import SwiftData

struct EditActivityView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let activity: Activity

    @State private var activityType = ""
    @State private var durationText = ""
    @State private var caloriesText = ""
    @State private var notes = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Aktivität bearbeiten") {
                    TextField("Aktivität", text: $activityType)

                    TextField("Dauer in Minuten", text: $durationText)
                        .keyboardType(.numberPad)

                    TextField("Geschätzte Kalorien", text: $caloriesText)
                        .keyboardType(.numberPad)

                    TextField("Kommentar (optional)", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }

                Section {
                    if let weight = activity.bodyWeightKg {
                        LabeledContent("Körpergewicht") {
                            Text("\(weight, specifier: "%.1f") kg")
                        }
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .dismissesKeyboardOnBackgroundTap()
            .navigationTitle("Bearbeiten")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        saveChanges()
                    }
                    .disabled(!canSave)
                }
            }
            .onAppear {
                loadActivity()
            }
        }
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

    private func loadActivity() {
        activityType = activity.type
        durationText = String(activity.durationMinutes)
        caloriesText = String(activity.estimatedCalories)
        notes = activity.notes ?? ""
    }

    private func saveChanges() {
        guard
            let duration = parsedDuration,
            let calories = parsedCalories
        else {
            return
        }

        activity.type = activityType.trimmingCharacters(
            in: .whitespacesAndNewlines
        )
        activity.durationMinutes = duration
        activity.estimatedCalories = calories

        let cleanedNotes = notes.trimmingCharacters(
            in: .whitespacesAndNewlines
        )

        activity.notes = cleanedNotes.isEmpty ? nil : cleanedNotes

        do {
            try modelContext.save()
            dismiss()
        } catch {
            print("Fehler beim Bearbeiten der Aktivität:", error)
        }
    }
}

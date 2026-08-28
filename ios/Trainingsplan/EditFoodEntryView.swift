import SwiftUI
import SwiftData

struct EditFoodEntryView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let entry: FoodEntry

    @State private var name = ""
    @State private var calories = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var notes = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Eintrag bearbeiten") {
                    TextField("Bezeichnung", text: $name)

                    TextField("Kalorien", text: $calories)
                        .keyboardType(.numberPad)

                    TextField("Protein in g", text: $protein)
                        .keyboardType(.decimalPad)

                    TextField("Kohlenhydrate in g", text: $carbs)
                        .keyboardType(.decimalPad)

                    TextField("Fett in g", text: $fat)
                        .keyboardType(.decimalPad)

                    TextField("Kommentar (optional)", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }
            }
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
                loadEntry()
            }
        }
    }

    private var canSave: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        parsedCalories != nil &&
        parsedProtein != nil &&
        parsedCarbs != nil &&
        parsedFat != nil
    }

    private var parsedCalories: Int? {
        Int(calories)
    }

    private var parsedProtein: Double? {
        parseDecimal(protein)
    }

    private var parsedCarbs: Double? {
        parseDecimal(carbs)
    }

    private var parsedFat: Double? {
        parseDecimal(fat)
    }

    private func parseDecimal(_ text: String) -> Double? {
        Double(text.replacingOccurrences(of: ",", with: "."))
    }

    private func loadEntry() {
        name = entry.name
        calories = String(entry.calories)
        protein = String(entry.proteinGrams)
        carbs = String(entry.carbsGrams)
        fat = String(entry.fatGrams)
        notes = entry.notes ?? ""
    }

    private func saveChanges() {
        guard
            let calories = parsedCalories,
            let protein = parsedProtein,
            let carbs = parsedCarbs,
            let fat = parsedFat
        else {
            return
        }

        entry.name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        entry.calories = calories
        entry.proteinGrams = protein
        entry.carbsGrams = carbs
        entry.fatGrams = fat

        let cleanedNotes = notes.trimmingCharacters(
            in: .whitespacesAndNewlines
        )

        entry.notes = cleanedNotes.isEmpty ? nil : cleanedNotes

        do {
            try modelContext.save()
            dismiss()
        } catch {
            print("Fehler beim Bearbeiten des Ernährungseintrags:", error)
        }
    }
}

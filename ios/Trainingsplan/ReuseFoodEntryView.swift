import SwiftUI
import SwiftData

struct ReuseFoodEntryView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    
    let sourceEntry: FoodEntry
    
    @State private var name = ""
    @State private var calories = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var notes = ""
    @State private var selectedScale: Double = 1.0
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Eintrag") {
                    TextField("Bezeichnung", text: $name)
                    
                    TextField("Kalorien", text: $calories)
                        .keyboardType(.numberPad)
                    
                    TextField("Protein in g", text: $protein)
                        .keyboardType(.decimalPad)
                    
                    TextField("Kohlenhydrate in g", text: $carbs)
                        .keyboardType(.decimalPad)
                    
                    TextField("Fett in g", text: $fat)
                        .keyboardType(.decimalPad)
                    
                    TextField("Kommentar", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Portion")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        
                        HStack {
                            scaleButton(0.5)
                            scaleButton(0.75)
                            scaleButton(1.0)
                            scaleButton(1.25)
                            scaleButton(1.5)
                        }
                    }
                }
            }
            .navigationTitle("Wiederverwenden")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Heute hinzufügen") {
                        save()
                    }
                    .disabled(!canSave)
                }
            }
            .onAppear {
                loadSourceEntry()
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
    
    private func loadSourceEntry() {
        selectedScale = 1.0
        
        name = sourceEntry.name
        calories = String(sourceEntry.calories)
        protein = String(sourceEntry.proteinGrams)
        carbs = String(sourceEntry.carbsGrams)
        fat = String(sourceEntry.fatGrams)
        notes = sourceEntry.notes ?? ""
    }
    
    private func save() {
        guard
            let calories = parsedCalories,
            let protein = parsedProtein,
            let carbs = parsedCarbs,
            let fat = parsedFat
        else {
            return
        }
        
        let newEntry = FoodEntry(
            date: Date(),
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            calories: calories,
            proteinGrams: protein,
            carbsGrams: carbs,
            fatGrams: fat,
            notes: notes.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? nil
            : notes.trimmingCharacters(in: .whitespacesAndNewlines)
        )
        
        modelContext.insert(newEntry)
        
        do {
            try modelContext.save()
            dismiss()
        } catch {
            print("Fehler beim Wiederverwenden des Eintrags:", error)
        }
    }
    @ViewBuilder
    private func scaleButton(_ scale: Double) -> some View {
        if selectedScale == scale {
            Button {
                applyScale(scale)
            } label: {
                Text("\(scale, specifier: "%g")×")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
        } else {
            Button {
                applyScale(scale)
            } label: {
                Text("\(scale, specifier: "%g")×")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
    }
    private func applyScale(_ scale: Double) {
        selectedScale = scale

        calories = String(
            Int((Double(sourceEntry.calories) * scale).rounded())
        )

        protein = String(
            (sourceEntry.proteinGrams * scale * 10).rounded() / 10
        )

        carbs = String(
            (sourceEntry.carbsGrams * scale * 10).rounded() / 10
        )

        fat = String(
            (sourceEntry.fatGrams * scale * 10).rounded() / 10
        )
    }
}

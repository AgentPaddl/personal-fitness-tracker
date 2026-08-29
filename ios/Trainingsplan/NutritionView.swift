import SwiftUI
import SwiftData
import FoodAnalysisKit

struct NutritionView: View {
    @Environment(\.modelContext) private var modelContext

    @Query(sort: \FoodEntry.date, order: .reverse)
    private var foodEntries: [FoodEntry]
    @Query(sort: \FoodPreset.name)
    private var foodPresets: [FoodPreset]

    @Query
    private var userGoals: [UserGoals]

    @State private var name = ""
    @State private var calories = ""
    @State private var protein = ""
    @State private var carbs = ""
    @State private var fat = ""
    @State private var notes = ""
    @State private var selectedEntryToEdit: FoodEntry?
    @StateObject private var foodAnalysisViewModel = FoodAnalysisViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section("Favoriten") {
                    if foodPresets.isEmpty {
                        Text("Noch keine Favoriten angelegt")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(foodPresets) { preset in
                            Button {
                                addPreset(preset)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(preset.name)
                                            .foregroundStyle(.primary)

                                        Text("\(preset.calories) kcal · \(preset.proteinGrams, specifier: "%.0f") g Protein")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }

                                    Spacer()

                                    Image(systemName: "plus.circle")
                                }
                            }
                        }
                        .onDelete(perform: deletePresets)
                    }
                }
                Section("Heute") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(totalCalories) / \(calorieGoal) kcal")
                            .font(.title2)
                            .fontWeight(.semibold)

                        Text("\(totalProtein, specifier: "%.0f") / \(proteinGoal) g Protein")
                            .foregroundStyle(.secondary)
                    }

                    if todaysEntries.isEmpty {
                        Text("Noch keine Ernährungseinträge")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(todaysEntries) { entry in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(entry.name)
                                    .fontWeight(.semibold)

                                Text("\(entry.calories) kcal · \(entry.proteinGrams, specifier: "%.0f") g Protein")
                                    .foregroundStyle(.secondary)

                                Text("\(entry.carbsGrams, specifier: "%.0f") g Carbs · \(entry.fatGrams, specifier: "%.0f") g Fett")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selectedEntryToEdit = entry
                            }
                            .swipeActions(edge: .leading) {
                                Button {
                                    createPreset(from: entry)
                                } label: {
                                    Label("Favorit", systemImage: "star")
                                }
                            }
                        }
                        .onDelete(perform: deleteFoodEntries)
                    }
                }

                Section("KI-Analyse (Text)") {
                    Text("Beschreibe dein Essen in natürlicher Sprache. Das Ergebnis ist eine Schätzung, die du vor dem Speichern prüfen und anpassen kannst.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    TextField(
                        "z. B. Ein Apfel und eine Scheibe Vollkornbrot mit Butter",
                        text: $foodAnalysisViewModel.descriptionText,
                        axis: .vertical
                    )
                    .lineLimit(1...4)
                    .disabled(foodAnalysisViewModel.isAnalyzing)

                    if foodAnalysisViewModel.isAnalyzing {
                        HStack {
                            ProgressView()
                            Text("Analysiere…")
                                .foregroundStyle(.secondary)
                        }
                    } else {
                        Button("Analysieren") {
                            Task { await foodAnalysisViewModel.analyze() }
                        }
                        .disabled(
                            foodAnalysisViewModel.descriptionText
                                .trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        )
                    }

                    if let errorMessage = foodAnalysisViewModel.errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }

                Section("Eintrag hinzufügen") {
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

                    Button("Speichern") {
                        saveFoodEntry()
                    }
                    .disabled(!canSave)
                }
            }
            .navigationTitle("Ernährung")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        NutritionHistoryView()
                    } label: {
                        Image(systemName: "clock.arrow.circlepath")
                    }
                }
            }
            .sheet(item: $selectedEntryToEdit) { entry in
                EditFoodEntryView(entry: entry)
            }
            .sheet(item: $foodAnalysisViewModel.reviewDraft) { draft in
                FoodAnalysisReviewView(draft: draft) {
                    foodAnalysisViewModel.descriptionText = ""
                }
            }
        }
    }

    private var todaysEntries: [FoodEntry] {
        foodEntries.filter {
            Calendar.current.isDateInToday($0.date)
        }
    }

    private var totalCalories: Int {
        todaysEntries.reduce(0) { $0 + $1.calories }
    }

    private var totalProtein: Double {
        todaysEntries.reduce(0) { $0 + $1.proteinGrams }
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
    private var calorieGoal: Int {
        userGoals.first?.calorieGoal ?? 2300
    }

    private var proteinGoal: Int {
        userGoals.first?.proteinGoalGrams ?? 150
    }

    private func parseDecimal(_ text: String) -> Double? {
        Double(text.replacingOccurrences(of: ",", with: "."))
    }

    private func saveFoodEntry() {
        guard
            let calories = parsedCalories,
            let protein = parsedProtein,
            let carbs = parsedCarbs,
            let fat = parsedFat
        else {
            return
        }

        let entry = FoodEntry(
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

        modelContext.insert(entry)

        do {
            try modelContext.save()

            name = ""
            self.calories = ""
            self.protein = ""
            self.carbs = ""
            self.fat = ""
            self.notes = ""
        } catch {
            print("Fehler beim Speichern des Ernährungseintrags:", error)
        }
    }
    private func addPreset(_ preset: FoodPreset) {
        let entry = FoodEntry(
            date: Date(),
            name: preset.name,
            calories: preset.calories,
            proteinGrams: preset.proteinGrams,
            carbsGrams: preset.carbsGrams,
            fatGrams: preset.fatGrams
        )

        modelContext.insert(entry)

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Hinzufügen des Favoriten:", error)
        }
    }

    private func deleteFoodEntries(at offsets: IndexSet) {
        for index in offsets {
            let entry = todaysEntries[index]
            modelContext.delete(entry)
        }

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Löschen des Ernährungseintrags:", error)
        }
    }
private func createPreset(from entry: FoodEntry) {
    let alreadyExists = foodPresets.contains {
        $0.name.caseInsensitiveCompare(entry.name) == .orderedSame &&
        $0.calories == entry.calories &&
        $0.proteinGrams == entry.proteinGrams &&
        $0.carbsGrams == entry.carbsGrams &&
        $0.fatGrams == entry.fatGrams
    }

    guard !alreadyExists else {
        return
    }

    let preset = FoodPreset(
        name: entry.name,
        calories: entry.calories,
        proteinGrams: entry.proteinGrams,
        carbsGrams: entry.carbsGrams,
        fatGrams: entry.fatGrams
    )

    modelContext.insert(preset)

    do {
        try modelContext.save()
    } catch {
        print("Fehler beim Speichern des Favoriten:", error)
    }
}
    private func deletePresets(at offsets: IndexSet) {
        for index in offsets {
            let preset = foodPresets[index]
            modelContext.delete(preset)
        }

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Löschen des Favoriten:", error)
        }
    }
}

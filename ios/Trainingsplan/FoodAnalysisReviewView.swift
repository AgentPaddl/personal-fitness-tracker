import SwiftUI
import SwiftData
import FoodAnalysisKit

/// Review/confirmation sheet for a text food-analysis AI estimate.
///
/// Nothing is persisted until the user taps "Übernehmen"; dismissing or
/// cancelling never touches SwiftData. Values are pre-filled from the
/// estimate but remain fully editable before the user confirms.
struct FoodAnalysisReviewView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    @State var draft: FoodAnalysisReviewDraft
    var onSaved: (() -> Void)?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Label(
                        "KI-Schätzung – bitte prüfen und bei Bedarf anpassen, bevor du speicherst.",
                        systemImage: "sparkles"
                    )
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                }

                Section("Ergebnis prüfen") {
                    TextField("Bezeichnung", text: $draft.name)

                    TextField("Kalorien", text: $draft.calories)
                        .keyboardType(.numberPad)

                    TextField("Protein in g", text: $draft.protein)
                        .keyboardType(.decimalPad)

                    TextField("Kohlenhydrate in g", text: $draft.carbs)
                        .keyboardType(.decimalPad)

                    TextField("Fett in g", text: $draft.fat)
                        .keyboardType(.decimalPad)
                }

                if draft.confidence < 1 || !draft.warnings.isEmpty {
                    Section("Hinweise zur Schätzung") {
                        Text("Konfidenz: \(Int((draft.confidence * 100).rounded())) %")
                            .font(.caption)
                            .foregroundStyle(.secondary)

                        ForEach(draft.warnings, id: \.self) { warning in
                            Text(warning)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("KI-Schätzung")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button("Übernehmen") {
                        save()
                    }
                    .disabled(draft.validated() == nil)
                }
            }
        }
    }

    private func save() {
        guard let input = draft.validated() else { return }

        let entry = FoodEntry(
            date: Date(),
            name: input.name,
            calories: input.calories,
            proteinGrams: input.proteinGrams,
            carbsGrams: input.carbsGrams,
            fatGrams: input.fatGrams
        )

        modelContext.insert(entry)

        do {
            try modelContext.save()
            onSaved?()
            dismiss()
        } catch {
            print("Fehler beim Speichern der KI-Schätzung:", error)
        }
    }
}

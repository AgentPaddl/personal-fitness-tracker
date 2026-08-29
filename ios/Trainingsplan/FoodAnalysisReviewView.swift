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

    @State private var isSaving = false
    @State private var saveErrorMessage: String?
    @State private var persistenceCoordinator = FoodEntryPersistenceCoordinator()

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
                        .disabled(isSaving)

                    TextField("Kalorien", text: $draft.calories)
                        .keyboardType(.numberPad)
                        .disabled(isSaving)

                    TextField("Protein in g", text: $draft.protein)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving)

                    TextField("Kohlenhydrate in g", text: $draft.carbs)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving)

                    TextField("Fett in g", text: $draft.fat)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving)
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

                if let saveErrorMessage {
                    Section {
                        Text(saveErrorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
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
                    .disabled(isSaving)
                }

                ToolbarItem(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView()
                    } else {
                        Button("Übernehmen") {
                            save()
                        }
                        .disabled(draft.validated() == nil)
                    }
                }
            }
        }
    }

    private func save() {
        guard let input = draft.validated() else { return }

        isSaving = true
        saveErrorMessage = nil

        let entry = FoodEntry(
            date: Date(),
            name: input.name,
            calories: input.calories,
            proteinGrams: input.proteinGrams,
            carbsGrams: input.carbsGrams,
            fatGrams: input.fatGrams
        )

        let result = persistenceCoordinator.save(
            insert: { modelContext.insert(entry) },
            persist: { try modelContext.save() },
            rollback: { modelContext.delete(entry) }
        )

        isSaving = false

        switch result {
        case .saved:
            onSaved?()
            dismiss()
        case .failed:
            saveErrorMessage = "Der Eintrag konnte nicht gespeichert werden. Bitte versuche es erneut."
        case .skipped:
            // Already saved once from this review, or a save is already
            // in flight (rapid duplicate tap); nothing further to do.
            break
        }
    }
}

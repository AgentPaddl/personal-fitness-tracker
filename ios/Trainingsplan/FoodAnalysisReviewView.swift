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

    @ObservedObject var session: FoodAnalysisReviewSession
    var onSaved: (() -> Void)?

    @State private var isSaving = false
    @State private var saveErrorMessage: String?

    private var draft: FoodAnalysisReviewDraft {
        get { session.currentDraft }
        nonmutating set { session.currentDraft = newValue }
    }

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
                    TextField("Bezeichnung", text: $session.currentDraft.name)
                        .disabled(isSaving || session.isRefining)

                    TextField("Kalorien", text: $session.currentDraft.calories)
                        .keyboardType(.numberPad)
                        .disabled(isSaving || session.isRefining)

                    TextField("Protein in g", text: $session.currentDraft.protein)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving || session.isRefining)

                    TextField("Kohlenhydrate in g", text: $session.currentDraft.carbs)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving || session.isRefining)

                    TextField("Fett in g", text: $session.currentDraft.fat)
                        .keyboardType(.decimalPad)
                        .disabled(isSaving || session.isRefining)
                }

                Section("Konfidenz") {
                    Text("\(Int((session.confidence * 100).rounded())) %")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if !session.assumptions.isEmpty {
                    Section("Annahmen") {
                        ForEach(session.assumptions, id: \.self) { assumption in
                            Text(assumption)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                if !session.warnings.isEmpty {
                    Section("Hinweise") {
                        ForEach(session.warnings, id: \.self) { warning in
                            Text(warning)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Section("Schätzung verbessern") {
                    Text("Ergänze Kontext, um die aktuell sichtbare Schätzung neu berechnen zu lassen.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    ZStack(alignment: .topLeading) {
                        if session.correctionText.isEmpty {
                            Text("Zum Beispiel: Es waren 250 g Reis oder ich habe nur die Hälfte gegessen.")
                                .foregroundStyle(.tertiary)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 8)
                                .allowsHitTesting(false)
                        }

                        TextEditor(text: $session.correctionText)
                            .frame(minHeight: 90)
                            .scrollContentBackground(.hidden)
                            .disabled(isSaving || session.isRefining || session.isRefinementLimitReached)
                            .accessibilityLabel("Zusätzlicher Kontext")
                            .accessibilityHint("Beschreibe Mengen, Zutaten oder wie viel du gegessen hast.")
                    }

                    HStack {
                        Text("\(session.successfulRefinementCount) von \(FoodAnalysisReviewSession.maximumSuccessfulRefinements) Überarbeitungen verwendet")
                        Spacer()
                        Text("\(session.correctionText.count)/\(FoodAnalysisReviewSession.correctionCharacterLimit)")
                            .foregroundStyle(
                                session.correctionText.count > FoodAnalysisReviewSession.correctionCharacterLimit
                                    ? Color.red
                                    : Color.secondary
                            )
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)

                    if session.correctionText.count > FoodAnalysisReviewSession.correctionCharacterLimit {
                        Text("Bitte kürze den zusätzlichen Kontext auf höchstens 1000 Zeichen.")
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                    if session.isRefinementLimitReached {
                        Text("Die maximal drei Überarbeitungen wurden verwendet. Du kannst die Werte weiterhin manuell bearbeiten und übernehmen.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if let refinementErrorMessage = session.refinementErrorMessage {
                        Text(refinementErrorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                    Button {
                        Task {
                            await session.refine()
                        }
                    } label: {
                        if session.isRefining {
                            HStack {
                                ProgressView()
                                Text("Wird neu berechnet …")
                            }
                        } else {
                            Text("Neu berechnen")
                        }
                    }
                    .disabled(!session.canRefine || isSaving)
                    .accessibilityLabel("Schätzung neu berechnen")
                }

                if let saveErrorMessage {
                    Section {
                        Text(saveErrorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
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
                        .disabled(!session.canConfirmCurrentDraft)
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

        let result = session.persistenceCoordinator.save(
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

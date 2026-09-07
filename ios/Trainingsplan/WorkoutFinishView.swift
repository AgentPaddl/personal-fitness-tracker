import SwiftUI
import SwiftData
import ActivitySummaryKit

struct WorkoutFinishView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let session: WorkoutSession
    let draft: WorkoutCompletionDraft
    let onSaved: () -> Void

    @State private var durationText: String
    @State private var caloriesText: String
    @State private var isSaving = false
    @State private var saveError: String?

    init(
        session: WorkoutSession,
        draft: WorkoutCompletionDraft,
        onSaved: @escaping () -> Void
    ) {
        self.session = session
        self.draft = draft
        self.onSaved = onSaved
        _durationText = State(initialValue: String(draft.proposedDurationMinutes))
        _caloriesText = State(initialValue: String(draft.proposedCalories))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Training") {
                    TextField("Dauer in Minuten", text: $durationText)
                        .keyboardType(.numberPad)

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

                if let saveError {
                    Section {
                        Text(saveError)
                            .foregroundStyle(.red)
                    }
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
                    .disabled(isSaving)
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        saveWorkout()
                    } label: {
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("Speichern")
                        }
                    }
                    .disabled(completionValues == nil || isSaving)
                }
            }
            .onChange(of: durationText) {
                guard let duration = WorkoutCompletion.positiveWholeNumber(from: durationText) else {
                    return
                }
                caloriesText = String(
                    WorkoutCompletion.estimatedCalories(
                        durationMinutes: duration,
                        bodyWeightKg: draft.bodyWeightKg
                    )
                )
            }
        }
    }

    private var completionValues: WorkoutCompletionValues? {
        WorkoutCompletion.completionValues(
            startedAt: draft.startedAt,
            durationText: durationText,
            caloriesText: caloriesText
        )
    }

    private func saveWorkout() {
        guard let values = completionValues, !isSaving else {
            return
        }

        isSaving = true
        saveError = nil
        defer { isSaving = false }

        let snapshot = WorkoutSessionCompletionSnapshot(session: session)

        do {
            try WorkoutCompletion.applyWithRollback(
                snapshot: snapshot,
                apply: {
                    session.endedAt = values.endedAt
                    session.durationMinutes = values.durationMinutes
                    session.estimatedCalories = values.estimatedCalories
                    session.isCompleted = true
                },
                save: {
                    try modelContext.save()
                },
                restore: { previous in
                    previous.restore(session: session)
                }
            )
            onSaved()
            dismiss()
        } catch {
            print("Fehler beim Abschließen des Trainings:", error)
            saveError = "Das Training konnte nicht gespeichert werden. Bitte versuche es erneut."
        }
    }
}

private struct WorkoutSessionCompletionSnapshot {
    let endedAt: Date?
    let durationMinutes: Int?
    let estimatedCalories: Int?
    let isCompleted: Bool

    init(session: WorkoutSession) {
        endedAt = session.endedAt
        durationMinutes = session.durationMinutes
        estimatedCalories = session.estimatedCalories
        isCompleted = session.isCompleted
    }

    func restore(session: WorkoutSession) {
        session.endedAt = endedAt
        session.durationMinutes = durationMinutes
        session.estimatedCalories = estimatedCalories
        session.isCompleted = isCompleted
    }
}

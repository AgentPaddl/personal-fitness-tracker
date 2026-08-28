import SwiftUI
import SwiftData

struct ExercisePickerView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    @Query(sort: \Exercise.name)
    private var exercises: [Exercise]

    @State private var newExerciseName = ""

    let onSelect: (Exercise) -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Neue Übung") {
                    TextField("z. B. Bankdrücken", text: $newExerciseName)

                    Button("Übung anlegen und auswählen") {
                        createExercise()
                    }
                    .disabled(cleanedName.isEmpty)
                }

                Section("Vorhandene Übungen") {
                    if activeExercises.isEmpty {
                        Text("Noch keine Übungen angelegt")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(activeExercises) { exercise in
                            Button {
                                selectExercise(exercise)
                            } label: {
                                Text(exercise.name)
                                    .foregroundStyle(.primary)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Übung hinzufügen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }
            }
        }
    }

    private var activeExercises: [Exercise] {
        exercises.filter { !$0.isArchived }
    }

    private var cleanedName: String {
        newExerciseName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func createExercise() {
        let exercise = Exercise(name: cleanedName)

        modelContext.insert(exercise)

        do {
            try modelContext.save()
            selectExercise(exercise)
        } catch {
            print("Fehler beim Anlegen der Übung:", error)
        }
    }

    private func selectExercise(_ exercise: Exercise) {
        onSelect(exercise)
        dismiss()
    }
}

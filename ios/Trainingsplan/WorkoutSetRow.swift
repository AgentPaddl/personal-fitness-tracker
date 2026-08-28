import SwiftUI
import SwiftData

struct WorkoutSetRow: View {
    @Environment(\.modelContext) private var modelContext

    @Bindable var workoutSet: WorkoutSet

    var body: some View {
        HStack {
            Text("Satz \(workoutSet.setNumber)")
                .frame(width: 55, alignment: .leading)

            TextField(
                "kg",
                value: $workoutSet.weightKg,
                format: .number
            )
            .keyboardType(.decimalPad)
            .multilineTextAlignment(.trailing)
            .textFieldStyle(.roundedBorder)

            Text("kg")

            TextField(
                "Wdh.",
                value: $workoutSet.repetitions,
                format: .number
            )
            .keyboardType(.numberPad)
            .multilineTextAlignment(.trailing)
            .textFieldStyle(.roundedBorder)

            Text("Wdh.")
        }
        .onChange(of: workoutSet.weightKg) {
            save()
        }
        .onChange(of: workoutSet.repetitions) {
            save()
        }
    }

    private func save() {
        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Speichern des Satzes:", error)
        }
    }
}

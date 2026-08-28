import SwiftUI
import SwiftData

struct ExerciseHistoryView: View {
    let exercise: Exercise

    @Query(sort: \ExercisePerformance.orderIndex)
    private var performances: [ExercisePerformance]

    @Query(sort: \WorkoutSet.setNumber)
    private var workoutSets: [WorkoutSet]

    var body: some View {
        List {
            if completedPerformances.isEmpty {
                Text("Noch keine abgeschlossenen Trainings")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(completedPerformances) { performance in
                    Section {
                        ForEach(sets(for: performance)) { workoutSet in
                            HStack {
                                Text("Satz \(workoutSet.setNumber)")

                                Spacer()

                                Text(
                                    "\(workoutSet.weightKg, specifier: "%.1f") kg × \(workoutSet.repetitions)"
                                )
                            }
                        }
                    } header: {
                        if let date = performance.workoutSession?.startedAt {
                            Text(
                                date,
                                format: .dateTime
                                    .day()
                                    .month()
                                    .year()
                            )
                        }
                    }
                }
            }
        }
        .navigationTitle(exercise.name)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var completedPerformances: [ExercisePerformance] {
        performances
            .filter {
                $0.exercise === exercise &&
                $0.workoutSession?.isCompleted == true
            }
            .sorted {
                ($0.workoutSession?.startedAt ?? .distantPast) >
                ($1.workoutSession?.startedAt ?? .distantPast)
            }
    }

    private func sets(for performance: ExercisePerformance) -> [WorkoutSet] {
        workoutSets
            .filter { $0.performance === performance }
            .sorted { $0.setNumber < $1.setNumber }
    }
}

import SwiftUI
import SwiftData

struct WorkoutSessionView: View {
    @Environment(\.modelContext) private var modelContext
    
    @Query(sort: \WeightEntry.date, order: .reverse)
    private var weightEntries: [WeightEntry]
    
    @Query(sort: \ExercisePerformance.orderIndex)
    private var performances: [ExercisePerformance]
    
    @Query(sort: \WorkoutSet.setNumber)
    private var workoutSets: [WorkoutSet]
    
    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]
    
    @State private var session: WorkoutSession?
    @State private var showExercisePicker = false
    @State private var showFinishWorkout = false
    @State private var finishDuration = 0
    @State private var finishCalories = 0
    
    var body: some View {
        Form {
            if let session {
                Section("Laufendes Training") {
                    LabeledContent("Gestartet") {
                        Text(
                            session.startedAt,
                            format: .dateTime.hour().minute()
                        )
                    }
                    
                    if let bodyWeight = session.bodyWeightKg {
                        LabeledContent("Körpergewicht") {
                            Text("\(bodyWeight, specifier: "%.1f") kg")
                        }
                    }
                }
                
                Section("Übungen") {
                    if currentSessionPerformances.isEmpty {
                        Text("Noch keine Übungen hinzugefügt")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(currentSessionPerformances) { performance in
                            VStack(alignment: .leading, spacing: 8) {
                                if let exercise = performance.exercise {
                                    NavigationLink {
                                        ExerciseHistoryView(exercise: exercise)
                                    } label: {
                                        Text(exercise.name)
                                            .fontWeight(.semibold)
                                    }
                                } else {
                                    Text("Unbekannte Übung")
                                        .fontWeight(.semibold)
                                }
                                
                                ForEach(sets(for: performance)) { workoutSet in
                                    WorkoutSetRow(workoutSet: workoutSet)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    
                    Button {
                        showExercisePicker = true
                    } label: {
                        Label("Übung hinzufügen", systemImage: "plus")
                    }
                }
                
                Section {
                    Button("Training abschließen") {
                        prepareWorkoutFinish()
                    }
                    .disabled(currentSessionPerformances.isEmpty)
                }
            } else {
                Section {
                    Button {
                        startWorkout()
                    } label: {
                        Label("Training starten", systemImage: "play.fill")
                    }
                }
                
                Section {
                    Text("Beim Start werden Startzeit und dein zuletzt gespeichertes Körpergewicht übernommen.")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .scrollDismissesKeyboard(.interactively)
        .dismissesKeyboardOnBackgroundTap()
        .navigationTitle("Krafttraining")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            restoreOpenWorkoutIfNeeded()
        }
        
        .sheet(isPresented: $showExercisePicker) {
            ExercisePickerView { exercise in
                addExercise(exercise)
            }
        }
        
        .sheet(isPresented: $showFinishWorkout) {
            if let session {
                WorkoutFinishView(
                    session: session,
                    durationMinutes: finishDuration,
                    estimatedCalories: finishCalories
                ) {
                    self.session = nil
                }
            }
        }
    }
    
    private var latestWeight: Double? {
        weightEntries.first?.weightKg
    }
    
    private func startWorkout() {
        let newSession = WorkoutSession(
            startedAt: Date(),
            bodyWeightKg: latestWeight,
            isCompleted: false
        )
        
        modelContext.insert(newSession)
        
        do {
            try modelContext.save()
            session = newSession
        } catch {
            print("Fehler beim Starten des Trainings:", error)
        }
    }
    private func addExercise(_ exercise: Exercise) {
        guard let session else {
            return
        }
        
        let nextOrderIndex = currentSessionPerformances.count
        
        let performance = ExercisePerformance(
            orderIndex: nextOrderIndex,
            exercise: exercise,
            workoutSession: session
        )
        
        modelContext.insert(performance)
        
        let previousSets = lastSets(for: exercise)
        
        for setNumber in 1...3 {
            let previousSet = previousSets.first {
                $0.setNumber == setNumber
            }
            
            let newSet = WorkoutSet(
                setNumber: setNumber,
                weightKg: previousSet?.weightKg ?? 0,
                repetitions: previousSet?.repetitions ?? 0,
                performance: performance
            )
            
            modelContext.insert(newSet)
        }
        
        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Hinzufügen der Übung:", error)
        }
    }
    
    private var currentSessionPerformances: [ExercisePerformance] {
        guard let session else {
            return []
        }
        
        return performances
            .filter { $0.workoutSession === session }
            .sorted { $0.orderIndex < $1.orderIndex }
    }
    
    private func sets(for performance: ExercisePerformance) -> [WorkoutSet] {
        workoutSets
            .filter { $0.performance === performance }
            .sorted { $0.setNumber < $1.setNumber }
    }
    private func lastSets(for exercise: Exercise) -> [WorkoutSet] {
        let previousPerformances = performances
            .filter {
                $0.exercise === exercise &&
                $0.workoutSession?.isCompleted == true
            }
            .sorted {
                ($0.workoutSession?.startedAt ?? .distantPast) >
                ($1.workoutSession?.startedAt ?? .distantPast)
            }
        
        guard let lastPerformance = previousPerformances.first else {
            return []
        }
        
        return sets(for: lastPerformance)
    }
    private func prepareWorkoutFinish() {
        guard let session else {
            return
        }
        
        let duration = max(
            1,
            Int(Date().timeIntervalSince(session.startedAt) / 60)
        )
        
        finishDuration = duration
        finishCalories = estimateCalories(
            durationMinutes: duration,
            bodyWeightKg: session.bodyWeightKg
        )
        
        showFinishWorkout = true
    }
    private func estimateCalories(
        durationMinutes: Int,
        bodyWeightKg: Double?
    ) -> Int {
        let weight = bodyWeightKg ?? 80
        
        let metValue = 5.0
        
        let calories =
        metValue *
        weight *
        Double(durationMinutes) /
        60.0
        
        return Int(calories.rounded())
    }
    private func restoreOpenWorkoutIfNeeded() {
        guard session == nil else {
            return
        }

        if let openSession = workoutSessions.first(where: { !$0.isCompleted }) {
            session = openSession
        }
    }
}

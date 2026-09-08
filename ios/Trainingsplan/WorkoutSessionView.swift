import SwiftUI
import SwiftData
import ActivitySummaryKit

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
    @State private var completionDraft: WorkoutCompletionDraft?
    @State private var sessionPendingDiscard: WorkoutSession?
    @State private var discardError: String?
    @State private var deletionService = WorkoutSessionDeletionService()
    @State private var weightIncreaseMarker = WeightIncreaseMarker()
    @State private var isSavingMarker = false
    @State private var markerSaveError: String?
    
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
                                    Toggle(isOn: Binding(
                                        get: { exercise.nextWeightIncreaseMarkedAt != nil },
                                        set: { setWeightIncreaseMarker($0, for: exercise) }
                                    )) {
                                        HStack(alignment: .firstTextBaseline) {
                                            if exercise.nextWeightIncreaseMarkedAt != nil {
                                                Image(systemName: "arrow.up.circle.fill")
                                                    .foregroundStyle(Color.accentColor)
                                                    .accessibilityHidden(true)
                                            }
                                            Text("Beim nächsten Mal mehr Gewicht")
                                                .fixedSize(horizontal: false, vertical: true)
                                        }
                                    }
                                    .disabled(isSavingMarker)
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

                Section {
                    Button("Training verwerfen", role: .destructive) {
                        sessionPendingDiscard = session
                    }
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
        
        .sheet(item: $completionDraft) { draft in
            if let session {
                WorkoutFinishView(
                    session: session,
                    draft: draft
                ) {
                    self.session = nil
                }
            }
        }
        .confirmationDialog(
            "Training verwerfen?",
            isPresented: discardConfirmationIsPresented,
            presenting: sessionPendingDiscard
        ) { session in
            Button("Training verwerfen", role: .destructive) {
                discardWorkout(session)
            }
            Button("Abbrechen", role: .cancel) {}
        } message: { _ in
            Text("Das begonnene Training und alle eingetragenen Übungen und Sätze werden dauerhaft gelöscht.")
        }
        .alert(
            "Training konnte nicht verworfen werden",
            isPresented: discardErrorIsPresented
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(discardError ?? "Bitte versuche es erneut.")
        }
        .alert(
            "Erinnerung konnte nicht gespeichert werden",
            isPresented: Binding(
                get: { markerSaveError != nil },
                set: { if !$0 { markerSaveError = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(markerSaveError ?? "Bitte versuche es erneut.")
        }
    }

    private func setWeightIncreaseMarker(_ isActive: Bool, for exercise: Exercise) {
        guard !isSavingMarker else { return }
        isSavingMarker = true
        defer { isSavingMarker = false }

        do {
            try weightIncreaseMarker.setActive(
                isActive,
                currentValue: exercise.nextWeightIncreaseMarkedAt,
                persist: { value in
                    try ExerciseWeightIncreaseMarkerPersistence.save(
                        value,
                        for: exercise,
                        in: modelContext
                    )
                },
                publish: { exercise.nextWeightIncreaseMarkedAt = $0 }
            )
        } catch {
            markerSaveError = "Die Erinnerung wurde nicht geändert. Bitte versuche es erneut."
        }
    }
    
    private var latestWeight: Double? {
        weightEntries.first?.weightKg
    }

    private var discardConfirmationIsPresented: Binding<Bool> {
        Binding(
            get: { sessionPendingDiscard != nil },
            set: { isPresented in
                if !isPresented {
                    sessionPendingDiscard = nil
                }
            }
        )
    }

    private var discardErrorIsPresented: Binding<Bool> {
        Binding(
            get: { discardError != nil },
            set: { isPresented in
                if !isPresented {
                    discardError = nil
                }
            }
        )
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

        let finishMoment = Date()
        completionDraft = WorkoutCompletion.makeDraft(
            startedAt: session.startedAt,
            capturedFinishAt: finishMoment,
            bodyWeightKg: session.bodyWeightKg
        )
    }

    private func discardWorkout(_ session: WorkoutSession) {
        let result = deletionService.discard(
            session: session,
            performances: performances,
            workoutSets: workoutSets,
            modelContext: modelContext
        )

        switch result {
        case .deleted:
            sessionPendingDiscard = nil
            self.session = nil
        case .failed:
            discardError = "Das Training wurde nicht verworfen. Deine Eingaben bleiben erhalten. Bitte versuche es erneut."
        case .skipped:
            break
        }
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

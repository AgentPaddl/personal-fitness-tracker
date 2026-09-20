import SwiftUI
import SwiftData
import PhotosUI
import AVFoundation
import UIKit
import FoodAnalysisKit
import UniformTypeIdentifiers

struct NutritionView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.scenePhase) private var scenePhase

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
    @StateObject private var foodAnalysisViewModel = FoodAnalysisViewModel(
        tokenProvider: EntraAuthServiceFactory.configuredProviderOrNil()
    )
    @State private var photoPickerItem: PhotosPickerItem?
    @State private var isPhotoPickerPresented = false
    @State private var isLoadingPickedPhoto = false
    @State private var isCameraSheetPresented = false
    @State private var isCaptureSurfaceVisible = false
    @State private var showsLongRunningAnalysisHint = false
    @State private var confirmsNewAnalysis = false
    @State private var confirmsAnalysisRetry = false
    private let isCameraHardwareAvailable = UIImagePickerController.isSourceTypeAvailable(.camera)

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

                Section("KI-Analyse (Text & Foto)") {
#if PILOT_ACCEPTANCE
                    Menu {
                        ForEach(PilotAcceptanceFixture.allCases, id: \.rawValue) { fixture in
                            Button(fixture.rawValue) {
                                do {
                                    let directory = URL.cachesDirectory.appendingPathComponent("PilotAcceptance")
                                    let prepared = try fixture.prepare(in: directory)
                                    foodAnalysisViewModel.descriptionText = fixture.foodDescription
                                    foodAnalysisViewModel.setPickedImage(rawData: try fixture.source(in: directory))
                                    guard foodAnalysisViewModel.selectedImage == prepared else {
                                        foodAnalysisViewModel.removeSelectedImage()
                                        throw FoodImagePreprocessingError.encodeFailed
                                    }
                                } catch {
                                    foodAnalysisViewModel.removeSelectedImage()
                                    foodAnalysisViewModel.errorMessage = "Abnahmebild nicht verifiziert."
                                }
                            }
                        }
                    } label: {
                        Label("Abnahmebild", systemImage: "photo.badge.checkmark")
                    }
                    .disabled(foodAnalysisViewModel.isAnalyzing || isLoadingPickedPhoto)
#endif
                    Text("Beschreibe dein Essen oder wähle ein Foto - oder beides. Das Ergebnis ist eine Schätzung, die du vor dem Speichern prüfen und anpassen kannst.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    TextField(
                        "z. B. Ein Apfel und eine Scheibe Vollkornbrot mit Butter",
                        text: $foodAnalysisViewModel.descriptionText,
                        axis: .vertical
                    )
                    .lineLimit(1...4)
                    .disabled(foodAnalysisViewModel.isAnalyzing)

                    if let selectedImage = foodAnalysisViewModel.selectedImage,
                        let uiImage = UIImage(data: selectedImage.data)
                    {
                        HStack {
                            Image(uiImage: uiImage)
                                .resizable()
                                .scaledToFill()
                                .frame(width: 60, height: 60)
                                .clipShape(RoundedRectangle(cornerRadius: 8))

                            Spacer()

                            Button("Entfernen", role: .destructive) {
                                foodAnalysisViewModel.removeSelectedImage()
                            }
                            .disabled(foodAnalysisViewModel.isAnalyzing)
                        }
                    } else {
                        HStack {
                            Button {
                                foodAnalysisViewModel.metrics.begin()
                                isPhotoPickerPresented = true
                            } label: {
                                Label("Foto auswählen", systemImage: "photo")
                            }
                            .buttonStyle(.borderless)
                            .disabled(foodAnalysisViewModel.isAnalyzing || isLoadingPickedPhoto)
                            .photosPicker(isPresented: $isPhotoPickerPresented, selection: $photoPickerItem,
                                          matching: .images, photoLibrary: .shared())

                            if isCameraHardwareAvailable {
                                Button {
                                    requestCameraCapture()
                                } label: {
                                    Label("Foto aufnehmen", systemImage: "camera")
                                }
                                .buttonStyle(.borderless)
                                .disabled(foodAnalysisViewModel.isAnalyzing || isLoadingPickedPhoto)
                            }
                        }
                    }

                    if isLoadingPickedPhoto {
                        HStack {
                            ProgressView()
                            Text("Foto wird geladen…")
                                .foregroundStyle(.secondary)
                        }
                    }

                    if foodAnalysisViewModel.isAnalyzing {
                        HStack {
                            ProgressView()
                            Text(showsLongRunningAnalysisHint ? "Das Essen wird analysiert …" : "Analysiere…")
                                .foregroundStyle(.secondary)
                        }
                        .task {
                            // Neutral, non-percentage hint for a real Copilot
                            // call (typically tens of seconds) - avoids
                            // implying false progress.
                            try? await Task.sleep(nanoseconds: 5_000_000_000)
                            if foodAnalysisViewModel.isAnalyzing {
                                showsLongRunningAnalysisHint = true
                            }
                        }
                        Button("Anfrage abbrechen", role: .cancel) {
                            foodAnalysisViewModel.interruptAnalysis()
                        }
                    } else {
                        Button(foodAnalysisViewModel.requiresNewOperationConfirmation ? "Neue Berechnung …" : "Analysieren") {
                            showsLongRunningAnalysisHint = false
                            if foodAnalysisViewModel.requiresNewOperationConfirmation {
                                confirmsNewAnalysis = true
                            } else {
                                Task { await foodAnalysisViewModel.analyze() }
                            }
                        }
                        .disabled(!foodAnalysisViewModel.canAnalyze || isLoadingPickedPhoto)
                    }

                    if let errorMessage = foodAnalysisViewModel.errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)

                        if foodAnalysisViewModel.canRetryOperation {
                            Button("Dieselbe Anfrage erneut senden …") {
                                confirmsAnalysisRetry = true
                            }
                            .disabled(foodAnalysisViewModel.isAnalyzing)
                        }
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
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Ernährung")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    FoodCaptureMetricsMenu(metrics: foodAnalysisViewModel.metrics)
                }
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
            .sheet(item: $foodAnalysisViewModel.reviewDraft, onDismiss: {
                foodAnalysisViewModel.closeReviewSession()
            }) { _ in
                if let session = foodAnalysisViewModel.reviewSession {
                    FoodAnalysisReviewView(session: session) {
                        foodAnalysisViewModel.clearAfterSave()
                    }
                }
            }
            .onChange(of: photoPickerItem) { _, newItem in
                guard let newItem else { return }
                foodAnalysisViewModel.metrics.begin()
                isLoadingPickedPhoto = true
                Task {
                    defer {
                        isLoadingPickedPhoto = false
                        photoPickerItem = nil
                    }
                    if let data = try? await newItem.loadTransferable(type: Data.self) {
                        foodAnalysisViewModel.setPickedImage(rawData: data)
                    } else {
                        foodAnalysisViewModel.errorMessage = FoodAnalysisViewModel.userMessage(
                            for: .imageProcessingFailed
                        )
                        foodAnalysisViewModel.metrics.finish(.technicalAbort)
                    }
                }
            }
            .fullScreenCover(isPresented: $isCameraSheetPresented) {
                CameraCaptureView(
                    onCapture: { data in
                        foodAnalysisViewModel.setPickedImage(rawData: data)
                        isCameraSheetPresented = false
                    },
                    onCancel: {
                        isCameraSheetPresented = false
                    }
                )
                .ignoresSafeArea()
            }
            .confirmationDialog("Neue Berechnung starten?", isPresented: $confirmsNewAnalysis, titleVisibility: .visible) {
                Button("Neue Berechnung starten") {
                    Task { await foodAnalysisViewModel.analyze(confirmNewOperation: true) }
                }
                Button("Abbrechen", role: .cancel) {}
            } message: {
                Text("Der vorherige Vorgang könnte beim KI-Anbieter bereits Ressourcen verbraucht haben. Eine neue Berechnung kann dort erneut Verbrauch und Kosten verursachen. Ein fehlendes Ergebnis wird dadurch nicht wiederhergestellt.")
            }
            .confirmationDialog("Dieselbe Anfrage erneut senden?", isPresented: $confirmsAnalysisRetry, titleVisibility: .visible) {
                Button("Mit derselben Vorgangs-ID senden") {
                    Task { await foodAnalysisViewModel.retryOperation() }
                }
                Button("Abbrechen", role: .cancel) {}
            } message: {
                Text("Inhalt und Vorgangs-ID bleiben gleich. Ein bereits angenommenes Ergebnis kann nicht abgerufen werden. Ohne aktivierten serverseitigen Wiederholungsschutz ist erneuter Verbrauch beim KI-Anbieter möglich.")
            }
            .onChange(of: scenePhase) { _, phase in
                foodAnalysisViewModel.metrics.setActive(phase == .active && isCaptureSurfaceVisible)
                if phase == .background {
                    confirmsNewAnalysis = false
                    confirmsAnalysisRetry = false
                }
            }
            .onAppear {
                isCaptureSurfaceVisible = true
                foodAnalysisViewModel.metrics.setActive(scenePhase == .active)
            }
            .onDisappear {
                if !isCameraSheetPresented && !isPhotoPickerPresented
                    && foodAnalysisViewModel.reviewSession == nil && selectedEntryToEdit == nil {
                    isCaptureSurfaceVisible = false
                    foodAnalysisViewModel.metrics.setActive(false)
                    if !foodAnalysisViewModel.isAnalyzing && !isLoadingPickedPhoto {
                        foodAnalysisViewModel.leaveCapture()
                    }
                }
            }
        }
    }

    /// Only checks/requests camera *permission* here, in direct response to
    /// the user tapping "Foto aufnehmen" - never proactively on view load.
    private func requestCameraCapture() {
        foodAnalysisViewModel.metrics.begin()
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: isCameraHardwareAvailable,
            authorizationStatus: CameraAuthorizationStatus(AVCaptureDevice.authorizationStatus(for: .video))
        )
        switch decision {
        case .presentCamera:
            isCameraSheetPresented = true
        case .requestPermission:
            AVCaptureDevice.requestAccess(for: .video) { granted in
                DispatchQueue.main.async {
                    if granted {
                        isCameraSheetPresented = true
                    } else {
                        foodAnalysisViewModel.errorMessage = FoodAnalysisViewModel.userMessage(for: .permissionDenied)
                    }
                }
            }
        case .unavailable(let reason):
            foodAnalysisViewModel.errorMessage = FoodAnalysisViewModel.userMessage(for: reason)
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

extension CameraAuthorizationStatus {
    /// Maps AVFoundation's status onto `FoodAnalysisKit`'s
    /// AVFoundation-independent enum, isolating that dependency to this
    /// one call site in the app layer.
    init(_ status: AVAuthorizationStatus) {
        switch status {
        case .authorized: self = .authorized
        case .notDetermined: self = .notDetermined
        case .denied: self = .denied
        case .restricted: self = .restricted
        @unknown default: self = .restricted
        }
    }
}

private struct FoodCaptureMetricsMenu: View {
    @ObservedObject var metrics: FoodCaptureMetrics
    @State private var document: BackupDocument?
    @State private var exporting = false
    @State private var importing = false
    @State private var confirmingDeletion = false
    @State private var errorMessage: String?

    var body: some View {
        Menu {
            if metrics.storageFailed {
                Label("Messdaten unvollständig", systemImage: "exclamationmark.triangle")
            }
            Button {
                do {
                    document = BackupDocument(data: try metrics.export())
                    exporting = true
                } catch { errorMessage = "Die Messdaten konnten nicht exportiert werden." }
            } label: {
                Label("Messdaten exportieren", systemImage: "square.and.arrow.up")
            }
            Button { importing = true } label: {
                Label("Kostenbeleg importieren", systemImage: "square.and.arrow.down")
            }
            Button(role: .destructive) { confirmingDeletion = true } label: {
                Label("Messdaten löschen", systemImage: "trash")
            }
            .disabled(metrics.currentID != nil)
        } label: {
            Image(systemName: metrics.storageFailed ? "exclamationmark.triangle" : "chart.bar.xaxis")
        }
        .accessibilityLabel("Lokale Produktmessung")
        .help("Lokale Produktmessung")
        .fileExporter(isPresented: $exporting, document: document, contentType: .json,
                      defaultFilename: "produktmessung-v1.json") { result in
            if case .failure = result { errorMessage = "Die Messdaten konnten nicht exportiert werden." }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { result in
            do {
                let url = try result.get()
                let access = url.startAccessingSecurityScopedResource()
                defer { if access { url.stopAccessingSecurityScopedResource() } }
                let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize
                guard let size, size <= 1_000_000 else { throw CocoaError(.fileReadTooLarge) }
                try metrics.importCosts(Data(contentsOf: url))
            } catch { errorMessage = "Der Kostenbeleg konnte nicht zugeordnet werden. Messdaten wurden nicht ersetzt." }
        }
        .confirmationDialog("Lokale Messdaten löschen?", isPresented: $confirmingDeletion, titleVisibility: .visible) {
            Button("Messdaten löschen", role: .destructive) {
                do { try metrics.deleteMeasurements() }
                catch { errorMessage = "Die Messdaten konnten nicht gelöscht werden." }
            }
            Button("Abbrechen", role: .cancel) {}
        }
        .alert("Produktmessung", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("OK") { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }
}

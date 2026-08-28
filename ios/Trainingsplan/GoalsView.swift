import SwiftUI
import SwiftData
import UniformTypeIdentifiers

struct GoalsView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext
    
    @Query
    private var userGoals: [UserGoals]
    
    @State private var calorieGoal = ""
    @State private var proteinGoal = ""
    @State private var activityGoal = ""
    @State private var backupDocument: BackupDocument?
    @State private var showExporter = false
    @State private var exportError: String?
    @State private var showImporter = false
    @State private var pendingBackup: AppBackup?
    @State private var showImportConfirmation = false
    @State private var importMessage: String?
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Tägliche Ernährung") {
                    TextField("Kalorienziel", text: $calorieGoal)
                        .keyboardType(.numberPad)
                    
                    TextField("Proteinziel in g", text: $proteinGoal)
                        .keyboardType(.numberPad)
                }
                
                Section("Bewegung") {
                    TextField("Aktivitäten pro Woche", text: $activityGoal)
                        .keyboardType(.numberPad)
                    
                    Text("Eine Woche läuft von Montag bis Sonntag.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Section("Daten") {
                    Button {
                        exportBackup()
                    } label: {
                        Label("Backup exportieren", systemImage: "square.and.arrow.up")
                    }
                    
                    Button {
                        showImporter = true
                    } label: {
                        Label("Backup importieren", systemImage: "square.and.arrow.down")
                    }
                }
            }
            .navigationTitle("Ziele")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") {
                        saveGoals()
                    }
                    .disabled(!canSave)
                }
            }
            .onAppear {
                loadGoals()
            }
            .fileExporter(
                isPresented: $showExporter,
                document: backupDocument,
                contentType: .json,
                defaultFilename: backupFilename
            ){ result in
                switch result {
                case .success:
                    break
                    
                case .failure(let error):
                    exportError = error.localizedDescription
                }
            }
            .fileImporter(
                isPresented: $showImporter,
                allowedContentTypes: [.json],
                allowsMultipleSelection: false
            ) { result in
                handleImportSelection(result)
            }
            .confirmationDialog(
                "Backup wiederherstellen?",
                isPresented: $showImportConfirmation,
                titleVisibility: .visible
            ) {
                Button("Aktuelle Daten ersetzen", role: .destructive) {
                    restorePendingBackup()
                }
                
                Button("Abbrechen", role: .cancel) {
                    pendingBackup = nil
                }
            } message: {
                Text(
                    "Alle aktuell in der App gespeicherten Daten werden gelöscht und durch den Inhalt des Backups ersetzt."
                )
            }
            .alert(
                "Backup",
                isPresented: Binding(
                    get: { importMessage != nil },
                    set: { if !$0 { importMessage = nil } }
                )
            ) {
                Button("OK") {
                    importMessage = nil
                }
            } message: {
                Text(importMessage ?? "")
            }
            .alert("Backup-Fehler", isPresented: Binding(
                get: { exportError != nil },
                set: { if !$0 { exportError = nil } }
            )) {
                Button("OK") {
                    exportError = nil
                }
            } message: {
                Text(exportError ?? "Unbekannter Fehler")
            }
        }
    }
    
    private var canSave: Bool {
        guard
            let calories = Int(calorieGoal),
            let protein = Int(proteinGoal),
            let activities = Int(activityGoal)
        else {
            return false
        }
        
        return calories > 0 && protein > 0 && activities > 0
    }
    
    private var backupFilename: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        
        return "FitnessTracker_Backup_\(formatter.string(from: Date()))"
    }
    
    private func loadGoals() {
        guard let goals = userGoals.first else {
            return
        }
        
        calorieGoal = String(goals.calorieGoal)
        proteinGoal = String(goals.proteinGoalGrams)
        activityGoal = String(goals.weeklyActivityGoal)
    }
    
    private func saveGoals() {
        guard
            let goals = userGoals.first,
            let calories = Int(calorieGoal),
            let protein = Int(proteinGoal),
            let activities = Int(activityGoal)
        else {
            return
        }
        
        goals.calorieGoal = calories
        goals.proteinGoalGrams = protein
        goals.weeklyActivityGoal = activities
        
        do {
            try modelContext.save()
            dismiss()
        } catch {
            print("Fehler beim Speichern der Ziele:", error)
        }
    }
    private func exportBackup() {
        do {
            let data = try BackupService.createBackup(
                modelContext: modelContext
            )
            
            backupDocument = BackupDocument(data: data)
            showExporter = true
        } catch {
            exportError = error.localizedDescription
            print("Fehler beim Erstellen des Backups:", error)
        }
    }
    private func handleImportSelection(
        _ result: Result<[URL], Error>
    ) {
        do {
            guard let url = try result.get().first else {
                return
            }

            let hasAccess = url.startAccessingSecurityScopedResource()

            defer {
                if hasAccess {
                    url.stopAccessingSecurityScopedResource()
                }
            }

            let data = try Data(contentsOf: url)

            let backup = try BackupService.decodeBackup(
                from: data
            )

            pendingBackup = backup
            showImportConfirmation = true

        } catch {
            importMessage = "Backup konnte nicht gelesen werden: \(error.localizedDescription)"
        }
    }
    private func restorePendingBackup() {
        guard let backup = pendingBackup else {
            return
        }

        do {
            try BackupService.deleteAllData(
                modelContext: modelContext
            )

            try BackupService.restoreBackup(
                backup,
                modelContext: modelContext
            )

            pendingBackup = nil

            loadGoals()

            importMessage = "Backup wurde erfolgreich wiederhergestellt."

        } catch {
            pendingBackup = nil

            importMessage =
                "Backup konnte nicht vollständig wiederhergestellt werden: \(error.localizedDescription)"
        }
    }
}

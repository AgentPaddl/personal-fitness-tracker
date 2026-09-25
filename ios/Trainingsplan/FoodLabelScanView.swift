import SwiftUI
import AVFoundation
import FoodAnalysisKit

struct FoodLabelScanView: View {
    @Environment(\.dismiss) private var dismiss
    let replacesExistingValues: Bool
    let onSelected: (FoodLabelColumn) -> Void
    @State private var cameraPresented = false
    @State private var photo: Data?
    @State private var scanID = UUID()
    @State private var columns: [FoodLabelColumn] = []
    @State private var selectedID: Int?
    @State private var reading = false
    @State private var errorMessage: String?
    @State private var permissionTask: Task<Void, Never>?
    @State private var pendingReplacement: FoodLabelColumn?
    @State private var confirmsReplacement = false

    private var selected: FoodLabelColumn? { FoodLabelRecognition.selectedColumn(from: columns, id: selectedID) }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    if let photo, let image = UIImage(data: photo) {
                        Image(uiImage: image)
                            .resizable().scaledToFit().frame(maxHeight: 320)
                            .accessibilityLabel("Fotografierte Nährwerttabelle")
                    }
                    Button(action: requestCamera) {
                        Label(photo == nil ? "Foto aufnehmen" : "Erneut aufnehmen", systemImage: "camera")
                    }
                    .disabled(reading || permissionTask != nil)
                    if reading { ProgressView("Etikett wird gelesen") }
                }
                if !columns.isEmpty {
                    Section("Bezugsspalte") {
                        if columns.count > 1 {
                            Picker("Spalte", selection: $selectedID) {
                                Text("Spalte wählen").tag(nil as Int?)
                                ForEach(columns) { column in
                                    Text("\(column.id + 1): \(column.heading)").tag(Optional(column.id))
                                }
                            }
                        } else if let column = columns.first {
                            LabeledContent("Spalte", value: column.heading)
                        }
                        if let selected {
                            LabeledContent("Bezugsmenge", value: display(selected.quantity, unit: selected.unit?.title ?? ""))
                            LabeledContent("Kalorien", value: display(selected.calories, unit: "kcal"))
                            LabeledContent("Eiweiß", value: display(selected.protein, unit: "g"))
                            LabeledContent("Kohlenhydrate", value: display(selected.carbs, unit: "g"))
                            LabeledContent("Fett", value: display(selected.fat, unit: "g"))
                        }
                    }
                }
                if let errorMessage {
                    Section {
                        Text(errorMessage).foregroundStyle(.red)
                        Button("Manuell fortfahren") { dismiss() }
                    }
                }
            }
            .navigationTitle("Etikett prüfen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") { permissionTask?.cancel(); dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Werte übernehmen") {
                        guard let selected, selected.hasValues, !reading else { return }
                        if replacesExistingValues {
                            pendingReplacement = selected
                            confirmsReplacement = true
                        } else {
                            onSelected(selected)
                            dismiss()
                        }
                    }
                    .disabled(selected?.hasValues != true || reading)
                }
            }
            .alert("Vorhandene Werte ersetzen?", isPresented: $confirmsReplacement, presenting: pendingReplacement) { column in
                Button("Werte ersetzen", role: .destructive) {
                    onSelected(column)
                    pendingReplacement = nil
                    dismiss()
                }
                Button("Abbrechen", role: .cancel) { pendingReplacement = nil }
            } message: { _ in
                Text("Alle Nährwerte und die Bezugsmenge werden ersetzt, auch durch offene Felder. Der Name bleibt unverändert.")
            }
            .sheet(isPresented: $cameraPresented) {
                CameraCaptureView(onCapture: { data in
                    pendingReplacement = nil
                    photo = data
                    columns = []
                    selectedID = nil
                    errorMessage = nil
                    reading = true
                    cameraPresented = false
                    scanID = UUID()
                }, onCancel: { cameraPresented = false })
            }
            .task(id: scanID) {
                guard let photo else { return }
                do {
                    let tokens = try await FoodLabelTextRecognizer.recognize(photo)
                    try Task.checkCancellation()
                    columns = FoodLabelRecognition.columns(from: tokens)
                    selectedID = columns.count == 1 ? columns.first?.id : nil
                    if !columns.contains(where: \.hasValues) {
                        errorMessage = "Keine eindeutigen Nährwerte erkannt. Die Angaben bleiben offen."
                    }
                } catch is CancellationError {
                    return
                } catch {
                    guard !Task.isCancelled else { return }
                    errorMessage = "Das Etikett konnte auf diesem Gerät nicht gelesen werden."
                }
                reading = false
            }
            .onDisappear {
                if !cameraPresented {
                    permissionTask?.cancel()
                    photo = nil
                    columns = []
                    pendingReplacement = nil
                }
            }
        }
    }

    private func display(_ value: Decimal?, unit: String) -> String {
        guard let value else { return "Offen" }
        return NSDecimalNumber(decimal: value).stringValue.replacingOccurrences(of: ".", with: ",") + " " + unit
    }

    private func requestCamera() {
        errorMessage = nil
        let decision = CameraCaptureAvailability.decide(
            isCameraHardwareAvailable: UIImagePickerController.isSourceTypeAvailable(.camera),
            authorizationStatus: CameraAuthorizationStatus(AVCaptureDevice.authorizationStatus(for: .video)))
        switch decision {
        case .presentCamera:
            cameraPresented = true
        case .requestPermission:
            permissionTask = Task {
                let granted = await AVCaptureDevice.requestAccess(for: .video)
                guard !Task.isCancelled else { return }
                permissionTask = nil
                if granted { cameraPresented = true }
                else { errorMessage = "Kein Kamerazugriff. Manuelles Anlegen bleibt möglich." }
            }
        case .unavailable(let reason):
            switch reason {
            case .hardwareUnavailable: errorMessage = "Auf diesem Gerät ist keine Kamera verfügbar."
            case .permissionDenied: errorMessage = "Kamerazugriff wurde abgelehnt. Manuelles Anlegen bleibt möglich."
            case .permissionRestricted: errorMessage = "Kamerazugriff ist eingeschränkt. Manuelles Anlegen bleibt möglich."
            }
        }
    }
}
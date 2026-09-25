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
    @State private var recognition: FoodLabelTextRecognizer.Result?
    @State private var issues: [FoodLabelIssue] = []

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
                            ForEach(Array(issues.filter { $0.columnID == selected.id && $0.reason == .nonExactValue }.enumerated()), id: \.offset) { _, issue in
                                Text(issueDescription(issue)).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                if let recognition {
                    Section {
                        DisclosureGroup("Lokale Erkennungsdiagnose") {
                            diagnosticImage(recognition)
                            LabeledContent("Bild für OCR", value: "\(recognition.image.width) × \(recognition.image.height)")
                            LabeledContent("Textbereiche / Wörter", value: "\(recognition.lines.count) / \(recognition.tokens.count)")
                            LabeledContent("Bereiche mit geringer Sicherheit", value: "\(recognition.lowConfidenceCount)")
                            LabeledContent("Am Bildrand begrenzte Wörter", value: "\(recognition.clippedWordCount)")
                            ForEach(Array(issues.enumerated()), id: \.offset) { _, issue in
                                Text(issueDescription(issue)).font(.caption)
                            }
                            if issues.isEmpty { Text("Keine offenen Parserfelder.").font(.caption) }
                            Text(recognition.lines.joined(separator: "\n")).font(.caption.monospaced())
                        }
                    }
                    .privacySensitive()
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
                    recognition = nil
                    issues = []
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
                    let result = try await FoodLabelTextRecognizer.inspect(photo)
                    try Task.checkCancellation()
                    recognition = result
                    let analysis = FoodLabelRecognition.analyze(result.tokens)
                    columns = analysis.columns
                    issues = analysis.issues
                    selectedID = columns.count == 1 ? columns.first?.id : nil
                    if !columns.contains(where: \.hasValues) {
                        if result.lines.isEmpty {
                            errorMessage = "Vision hat keinen Text erkannt. Die Angaben bleiben offen."
                        } else if result.tokens.isEmpty {
                            errorMessage = "Text erkannt, aber keine Wortpositionen verfügbar. Die Angaben bleiben offen."
                        } else {
                            errorMessage = "Text erkannt, aber keine Nährwerte eindeutig zugeordnet. Die Angaben bleiben offen."
                        }
                    }
                } catch is CancellationError {
                    return
                } catch let failure as FoodLabelTextRecognizer.Failure {
                    guard !Task.isCancelled else { return }
                    switch failure {
                    case .unsupported: errorMessage = "Die deutsche Texterkennung ist auf diesem Gerät nicht verfügbar."
                    case .invalidImage: errorMessage = "Das Kamerabild konnte nicht für die Texterkennung vorbereitet werden."
                    case .tooMuchText: errorMessage = "Das Bild enthält zu viele Textbereiche für diese Prüfung."
                    }
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
                    recognition = nil
                    issues = []
                }
            }
        }
    }

    private func display(_ value: Decimal?, unit: String) -> String {
        guard let value else { return "Offen" }
        return NSDecimalNumber(decimal: value).stringValue.replacingOccurrences(of: ".", with: ",") + " " + unit
    }

    private func diagnosticImage(_ result: FoodLabelTextRecognizer.Result) -> some View {
        Canvas { context, size in
            context.draw(Image(decorative: result.image, scale: 1), in: CGRect(origin: .zero, size: size))
            for token in result.tokens {
                let rect = CGRect(x: token.x * size.width, y: token.y * size.height,
                                  width: token.width * size.width, height: token.height * size.height)
                context.stroke(Path(rect), with: .color(.orange), lineWidth: 1)
            }
        }
        .aspectRatio(CGFloat(result.image.width) / CGFloat(result.image.height), contentMode: .fit)
        .frame(maxHeight: 420)
        .accessibilityLabel("Normalisiertes Kamerabild mit erkannten Wortbereichen")
    }

    private func issueDescription(_ issue: FoodLabelIssue) -> String {
        let fields = ["calories": "Kalorien", "protein": "Eiweiß", "carbs": "Kohlenhydrate", "fat": "Fett", "basis": "Bezugsmenge"]
        let prefix = issue.columnID.map { "Spalte \($0 + 1), " } ?? ""
        let field = issue.field.flatMap { fields[$0] }.map { $0 + ": " } ?? ""
        let reason: String
        switch issue.reason {
        case .noText: reason = "Keine OCR-Wörter vorhanden."
        case .invalidInput: reason = "Ungültige Wortgeometrie oder Eingabegrenze überschritten."
        case .noNutrientLabels: reason = "Keine unterstützte Nährwertbeschriftung erkannt."
        case .missingOrConflictingHeader: reason = "Keine eindeutige Bezugsüberschrift oberhalb der Nährwerte erkannt."
        case .tooManyColumns: reason = "Mehr als sechs Bezugsspalten erkannt."
        case .missingRow: reason = "Keine passende beschriftete Zeile mit erforderlichem Kontext erkannt."
        case .repeatedRows: reason = "Mehrere passende Beschriftungen; Zuordnung bleibt offen."
        case .missingValueOrUnit: reason = "Zahl und explizite Einheit nicht eindeutig derselben Zelle zugeordnet."
        case .ambiguousValues: reason = "Mehrere Werte ohne eindeutige Zuordnung."
        case .ambiguousOCRNumber: reason = "Widersprüchliche Zahlenlesarten oder angeschnittene Angabe. Die Angabe bleibt offen."
        case .nonExactValue: reason = "Ungleichheitsangabe auf dem Etikett. Kein exakter Wert speicherbar; bitte im Editor manuell prüfen und ergänzen."
        case .outsideColumn: reason = "Kein Wert eindeutig innerhalb dieser Bezugsspalte."
        case .outOfRange: reason = "Wert außerhalb des zulässigen Bereichs."
        }
        return prefix + field + reason
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
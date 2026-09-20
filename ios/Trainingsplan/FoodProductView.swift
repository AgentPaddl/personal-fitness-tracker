import SwiftUI
import SwiftData
import FoodAnalysisKit

struct FoodProductEditorView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    private let onSaved: () -> Void
    @State private var session: FoodProductEditorSession
    @State private var measuredValues: [String]?
    @State private var name: String
    @State private var calories: String
    @State private var protein: String
    @State private var carbs: String
    @State private var fat: String
    @State private var quantity = ""
    @State private var unit: FoodProductUnit?
    @State private var origin: FoodProductOrigin
    @State private var packagingConfirmed = false
    @State private var saveError: String?

    init(draft: FoodAnalysisReviewDraft? = nil, session: FoodProductEditorSession,
         onSaved: @escaping () -> Void = {}) {
        _name = State(initialValue: draft?.name ?? "")
        _calories = State(initialValue: draft?.calories ?? "")
        _protein = State(initialValue: draft?.protein ?? "")
        _carbs = State(initialValue: draft?.carbs ?? "")
        _fat = State(initialValue: draft?.fat ?? "")
        _origin = State(initialValue: draft == nil ? .manual : .aiEstimate)
        _measuredValues = State(initialValue: draft.map { [$0.name, $0.calories, $0.protein, $0.carbs, $0.fat] })
        _session = State(initialValue: session)
        self.onSaved = onSaved
    }

    private var basis: FoodProductBasis? {
        guard !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let amount = FoodProductBasis.parseQuantity(quantity), let unit,
              origin != .packaging || packagingConfirmed,
              let calories = FoodProductBasis.parseNumber(calories),
              let protein = FoodProductBasis.parseNumber(protein),
              let carbs = FoodProductBasis.parseNumber(carbs),
              let fat = FoodProductBasis.parseNumber(fat) else { return nil }
        return FoodProductBasis(quantity: amount, unit: unit, origin: origin,
                                nutrition: .init(calories: calories, protein: protein, carbs: carbs, fat: fat))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Produkt") {
                    TextField("Name", text: $name)
                    Picker("Herkunft", selection: $origin) {
                        ForEach(FoodProductOrigin.allCases) { Text($0.title).tag($0) }
                    }
                }
                Section("Bezug der Nährwerte") {
                    TextField("Bezugsmenge ergänzen", text: $quantity).keyboardType(.decimalPad)
                    Picker("Einheit", selection: $unit) {
                        Text("Einheit wählen").tag(nil as FoodProductUnit?)
                        ForEach(FoodProductUnit.allCases) { Text($0.title).tag(Optional($0)) }
                    }
                }
                Section("Werte für die Bezugsmenge") {
                    TextField("Kalorien", text: $calories).keyboardType(.decimalPad)
                    TextField("Protein in g", text: $protein).keyboardType(.decimalPad)
                    TextField("Kohlenhydrate in g", text: $carbs).keyboardType(.decimalPad)
                    TextField("Fett in g", text: $fat).keyboardType(.decimalPad)
                    if origin == .packaging {
                        Toggle("Werte und Bezugsmenge mit Etikett abgeglichen", isOn: $packagingConfirmed)
                    }
                }
                if let saveError { Text(saveError).foregroundStyle(.red) }
            }
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("Produkt prüfen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        recordEdits()
                        session.close(cancelled: true)
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Produkt speichern") { saveProduct() }.disabled(basis == nil)
                }
            }
            .onChange(of: [name, calories, protein, carbs, fat, quantity, unit?.rawValue ?? "", origin.rawValue]) { _, _ in
                packagingConfirmed = false
            }
            .onDisappear {
                recordEdits()
                session.close()
            }
        }
    }

    private func saveProduct() {
        guard let basis else { return }
        recordEdits()
        let result = session.saveProduct(name: name, basis: basis, in: modelContext)
        switch result {
        case .saved: onSaved(); dismiss()
        case .failed: saveError = "Das Produkt konnte nicht gespeichert werden."
        case .skipped: break
        }
    }

    private func recordEdits() {
        let values = [name, calories, protein, carbs, fat]
        if let measuredValues, measuredValues != values {
            session.recordCorrection()
        }
        measuredValues = values
    }
}

struct FoodProductPortionView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    let preset: FoodPreset
    let metrics: FoodCaptureMetrics
    let captureID: UUID
    @State private var quantity: String
    @State private var measuredQuantity: String
    @State private var persistence = FoodProductPersistence()
    @State private var saveError: String?

    init(preset: FoodPreset, metrics: FoodCaptureMetrics, captureID: UUID) {
        self.preset = preset
        self.metrics = metrics
        self.captureID = captureID
        _quantity = State(initialValue: preset.baseQuantity ?? "")
        _measuredQuantity = State(initialValue: preset.baseQuantity ?? "")
    }

    private var nutrition: FoodProductNutrition? {
        guard let basis = preset.productBasis, let amount = FoodProductBasis.parseQuantity(quantity) else { return nil }
        return basis.scaled(to: amount, unit: basis.unit)
    }

    var body: some View {
        NavigationStack {
            Form {
                if let basis = preset.productBasis {
                    Section(preset.name) {
                        LabeledContent("Herkunft", value: basis.origin.title)
                        LabeledContent("Produktbasis", value: "\(preset.baseQuantity ?? "") \(basis.unit.title)")
                        TextField("Menge in \(basis.unit.title)", text: $quantity).keyboardType(.decimalPad)
                    }
                    if let nutrition {
                        Section("Diese Portion") {
                            LabeledContent("Kalorien", value: "\(nutrition.roundedCalories) kcal")
                            LabeledContent("Protein", value: "\(NSDecimalNumber(decimal: nutrition.protein).stringValue) g")
                            LabeledContent("Kohlenhydrate", value: "\(NSDecimalNumber(decimal: nutrition.carbs).stringValue) g")
                            LabeledContent("Fett", value: "\(NSDecimalNumber(decimal: nutrition.fat).stringValue) g")
                        }
                    }
                }
                if let saveError { Text(saveError).foregroundStyle(.red) }
            }
            .navigationTitle("Portion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") {
                        recordQuantityEdit()
                        metrics.finish(.discarded, captureID: captureID)
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Heute hinzufügen") { savePortion() }.disabled(nutrition == nil)
                }
            }
            .onDisappear { recordQuantityEdit() }
        }
    }

    private func savePortion() {
        guard let amount = FoodProductBasis.parseQuantity(quantity) else { return }
        recordQuantityEdit()
        let result = persistence.savePortion(of: preset, quantity: amount, in: modelContext)
        metrics.saveResult(result, captureID: captureID)
        switch result {
        case .saved: dismiss()
        case .failed: saveError = "Die Portion konnte nicht gespeichert werden."
        case .skipped: break
        }
    }

    private func recordQuantityEdit() {
        if quantity != measuredQuantity,
           FoodProductBasis.parseQuantity(quantity) != FoodProductBasis.parseQuantity(measuredQuantity) {
            metrics.manualCorrection(captureID: captureID)
        }
        measuredQuantity = quantity
    }
}
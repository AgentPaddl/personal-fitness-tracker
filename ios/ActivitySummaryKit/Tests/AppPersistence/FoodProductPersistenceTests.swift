import Foundation
import ImageIO
import SwiftData
import XCTest
import FoodAnalysisKit
@testable import MarkerAppPersistence

final class FoodProductPersistenceTests: XCTestCase {
    private struct LabelImageCase: Decodable {
        let id: String
        let file: String
        let expected: [String: String]
        let required: [String]
        let expectedIssues: [String: String]?
    }

    func testLocalLabelCorpusWithExplicitPrivateImages() async throws {
        guard let manifest = ProcessInfo.processInfo.environment["PFT_LABEL_CASES"] else {
            throw XCTSkip("Explicit local image cases required; no image is bundled or downloaded.")
        }
        let cases = try JSONDecoder().decode([LabelImageCase].self, from: Data(manifest.utf8))
        XCTAssertFalse(cases.isEmpty)
        for imageCase in cases {
            let data = try Data(contentsOf: URL(fileURLWithPath: imageCase.file))
            let original = try await FoodLabelTextRecognizer.inspect(data)
            let jpeg = NSMutableData()
            let destination = try XCTUnwrap(CGImageDestinationCreateWithData(jpeg, "public.jpeg" as CFString, 1, nil))
            CGImageDestinationAddImage(destination, original.image, [kCGImageDestinationLossyCompressionQuality: 0.9] as CFDictionary)
            XCTAssertTrue(CGImageDestinationFinalize(destination))
            for (variant, result) in [("original", original), ("jpeg", try await FoodLabelTextRecognizer.inspect(jpeg as Data))] {
                let prefix = "\(imageCase.id)/\(variant)"
                let invalid = result.tokens.filter {
                    ![$0.x, $0.y, $0.width, $0.height].allSatisfy(\.isFinite)
                        || $0.x < 0 || $0.y < 0 || $0.width <= 0 || $0.height <= 0
                        || $0.x + $0.width > 1.001 || $0.y + $0.height > 1.001
                        || $0.text.isEmpty || $0.text.count > 200
                }
                let analysis = FoodLabelRecognition.analyze(result.tokens)
                XCTAssertTrue(analysis.columns.count <= 1, "\(prefix): unexpected extra reference column")
                let reasons = analysis.issues.map { "\($0.field ?? "input"):\($0.reason.rawValue)" }.joined(separator: ",")
                print("\(prefix): lines=\(result.lines.count), words=\(result.tokens.count), invalid=\(invalid.count), lowConfidence=\(result.lowConfidenceCount), columns=\(analysis.columns.count), issues=\(reasons)")
                for token in invalid {
                    print("\(prefix): invalidBox=\([token.x, token.y, token.width, token.height]), characters=\(token.text.count)")
                }
                let column = FoodLabelRecognition.selectedColumn(from: analysis.columns, id: nil)
                for (field, reason) in imageCase.expectedIssues ?? [:] {
                    XCTAssertTrue(analysis.issues.contains { $0.field == field && $0.reason.rawValue == reason },
                        "\(prefix): \(field) rejection reason mismatch")
                }
                let values: [String: Decimal?] = ["basis": column?.quantity, "calories": column?.calories,
                    "protein": column?.protein, "carbs": column?.carbs, "fat": column?.fat]
                for field in ["basis", "calories", "protein", "carbs", "fat"] {
                    let actual = values[field] ?? nil
                    let reference = imageCase.expected[field].flatMap { Decimal(string: $0) }
                    let state = actual == nil ? "open" : actual == reference ? "correct" : "incorrect"
                    print("\(prefix): \(field)=\(state)")
                    XCTAssertTrue(actual == nil || actual == reference, "\(prefix): \(field) incorrectly assigned")
                    if imageCase.required.contains(field) {
                        XCTAssertNotNil(actual, "\(prefix): \(field) missing")
                    }
                    if ProcessInfo.processInfo.environment["PFT_LABEL_TRACE"] == "YES", let reference {
                        let expression = try NSRegularExpression(pattern: #"[0-9]+(?:[,.][0-9]+)?"#)
                        let numberSeen = result.tokens.contains { token in
                            expression.matches(in: token.text, range: NSRange(token.text.startIndex..., in: token.text)).contains { match in
                                guard let range = Range(match.range, in: token.text) else { return false }
                                return FoodProductBasis.parseNumber(String(token.text[range])) == reference
                            }
                        }
                        print("\(prefix): \(field) referenceDigitsPresent=\(numberSeen)")
                    }
                }
                if let unit = column?.unit {
                    XCTAssertTrue(unit.rawValue == imageCase.expected["unit"], "\(prefix): incorrect reference unit")
                }
                if imageCase.required.contains("basis") {
                    XCTAssertNotNil(column?.unit, "\(prefix): reference unit missing")
                }
                if ProcessInfo.processInfo.environment["PFT_LABEL_TRACE"] == "YES" {
                    let headerPunctuation = result.tokens.filter {
                        $0.text.range(of: #"^[0-9]+\s*(g|ml):$"#, options: [.regularExpression, .caseInsensitive]) != nil
                    }.count
                    let joinedEnergy = result.tokens.filter {
                        $0.text.range(of: #"kj/[0-9]"#, options: [.regularExpression, .caseInsensitive]) != nil
                    }.count
                    print("\(prefix): headerWithColon=\(headerPunctuation), joinedEnergy=\(joinedEnergy), clipped=\(result.clippedWordCount)")
                    let labels = ["calories": ["energie", "brennwert", "calories"], "fat": ["fett", "fat"],
                        "carbs": ["kohlenhydrate", "carbohydrate"], "protein": ["eiweiss", "protein"],
                        "excluded": ["zucker", "sugar", "salz", "salt", "saturates", "fettsauren", "ballaststoffe"],
                        "basis": ["pro", "portion", "serving"], "unit": ["g", "ml", "kcal", "kj"]]
                    for token in result.tokens {
                        let normalized = token.text.lowercased().folding(options: .diacriticInsensitive, locale: Locale(identifier: "de_DE"))
                            .replacingOccurrences(of: "ß", with: "ss")
                        let categories = labels.filter { $0.value.contains(normalized) }.map(\.key).sorted()
                        let alternateCategories = labels.filter { entry in
                            (token.alternatives ?? []).contains { alternative in
                                entry.value.contains(alternative.lowercased().folding(options: .diacriticInsensitive,
                                    locale: Locale(identifier: "de_DE")).replacingOccurrences(of: "ß", with: "ss"))
                            }
                        }.map(\.key).sorted()
                        let number = normalized.range(of: "[0-9]", options: .regularExpression) != nil
                        guard !categories.isEmpty || !alternateCategories.isEmpty || number else { continue }
                        print("\(prefix): categories=\(categories), alternatives=\(alternateCategories), line=\(token.lineID ?? -1), slope=\(token.lineSlope ?? 0), numeric=\(number), ambiguous=\(token.numberIsAmbiguous == true), box=\([token.x, token.y, token.width, token.height])")
                    }
                }
            }
        }
    }

    func testLocalLabelCameraPipelineWithExplicitPrivateImage() async throws {
        guard let filePath = ProcessInfo.processInfo.environment["PFT_LABEL_IMAGE_PATH"] else {
            throw XCTSkip("Explicit local regression image required; no image is bundled or downloaded.")
        }
        let original = try Data(contentsOf: URL(fileURLWithPath: filePath))
        let first = try await FoodLabelTextRecognizer.inspect(original)
        XCTAssertTrue(first.image.width == 2250 && first.image.height == 3000, "Unexpected normalized dimensions")
        let jpeg = NSMutableData()
        let destination = try XCTUnwrap(CGImageDestinationCreateWithData(jpeg, "public.jpeg" as CFString, 1, nil))
        CGImageDestinationAddImage(destination, first.image, [kCGImageDestinationLossyCompressionQuality: 0.9] as CFDictionary)
        XCTAssertTrue(CGImageDestinationFinalize(destination), "In-memory JPEG conversion failed")
        for (imageKind, input) in [("HEIC", original), ("JPEG", jpeg as Data)] {
            let result = try await FoodLabelTextRecognizer.inspect(input)
            XCTAssertFalse(result.lines.isEmpty, "Vision returned no text")
            XCTAssertTrue(result.tokens.allSatisfy {
                $0.x >= 0 && $0.y >= 0 && $0.width > 0 && $0.height > 0
                    && $0.x + $0.width <= 1.001 && $0.y + $0.height <= 1.001
            }, "Unexpected word geometry")
            let analysis = FoodLabelRecognition.analyze(result.tokens)
            XCTAssertTrue(analysis.columns.count == 1, "Expected one unambiguous reference column")
            guard let column = FoodLabelRecognition.selectedColumn(from: analysis.columns, id: nil) else {
                XCTFail("No reviewable column")
                return
            }
            XCTAssertTrue(column.quantity == 100 && column.unit == .grams, "Reference basis mismatch")
            XCTAssertTrue(column.calories == 381, "Energy does not match the manually reviewed reference")
            let fatReason = analysis.issues.filter { $0.field == "fat" }.map { $0.reason.rawValue }.joined(separator: ",")
            if imageKind == "HEIC" {
                XCTAssertTrue(column.fat == Decimal(string: "4.9"), "HEIC: fat missing or mismatched; \(fatReason)")
            } else {
                XCTAssertTrue(column.fat == nil || column.fat == Decimal(string: "4.9"), "JPEG: incorrect fat value")
                if column.fat == nil {
                    XCTAssertTrue(analysis.issues.contains { $0.field == "fat" && $0.reason == .missingRow }, "Missing JPEG label must be diagnosed")
                }
            }
            XCTAssertTrue(column.carbs == Decimal(string: "71.6"), "Carbohydrates do not match the manually reviewed reference")
            XCTAssertTrue(column.protein == nil || column.protein == Decimal(string: "12.7"), "Incorrect protein value")
            XCTAssertTrue(column.hasValues, "Partial results must remain reviewable")
        }
    }

    @MainActor
    func testLocalLabelScanSavesOnlyProductAndNeverAddsAnAIOperation() throws {
        let context = ModelContext(try container())
        let metrics = FoodCaptureMetrics()
        let editor = FoodProductEditorSession(metrics: metrics)
        var tokens = [FoodLabelText(text: "100g", x: 0.60, y: 0.10, width: 0.08, height: 0.025)]
        for (index, pair) in [("Energie", "200kcal"), ("Eiweiss", "10g"),
                              ("Kohlenhydrate", "20g"), ("Fett", "8g")].enumerated() {
            let position = 0.20 + Double(index) * 0.06
            tokens.append(.init(text: pair.0, x: 0.10, y: position, width: 0.25, height: 0.025))
            tokens.append(.init(text: pair.1, x: 0.60, y: position, width: 0.08, height: 0.025))
        }
        let columns = FoodLabelRecognition.columns(from: tokens)
        let column = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 0)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
        let nutrition = try FoodProductNutrition(calories: XCTUnwrap(column.calories),
            protein: XCTUnwrap(column.protein), carbs: XCTUnwrap(column.carbs), fat: XCTUnwrap(column.fat))
        let basis = try XCTUnwrap(FoodProductBasis(quantity: XCTUnwrap(column.quantity),
            unit: XCTUnwrap(column.unit), origin: .manual, nutrition: nutrition))
        XCTAssertEqual(editor.saveProduct(name: "Synthetic label", basis: basis, in: context), .saved)
        editor.close()
        let products = try context.fetch(FetchDescriptor<FoodPreset>())
        XCTAssertEqual(products.count, 1)
        XCTAssertEqual(products.first?.valueOrigin, FoodProductOrigin.manual.rawValue)
        XCTAssertEqual(products.first?.productBasis, basis)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
        XCTAssertEqual(metrics.archive.captures.count, 1)
        XCTAssertEqual(metrics.archive.captures.first?.id, editor.id)
        XCTAssertEqual(metrics.archive.captures.first?.kind, .productCreation)
        XCTAssertEqual(metrics.archive.captures.first?.outcome, .productSaved)
        XCTAssertEqual(metrics.archive.captures.first?.operations.count, 0)
    }

    @MainActor
    func testEditorSessionSupportsAIReviewWithoutInstrumentation() throws {
        let context = ModelContext(try container())
        let captureID = UUID()
        let editor = FoodProductEditorSession(metrics: nil, captureID: captureID)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .aiEstimate,
            nutrition: .init(calories: 200, protein: 10, carbs: 20, fat: 8)))
        XCTAssertEqual(editor.id, captureID)
        editor.recordCorrection()
        XCTAssertEqual(editor.saveProduct(name: "Synthetic", basis: basis, in: context), .saved)
        editor.close()
        XCTAssertEqual(editor.saveProduct(name: "Duplicate", basis: basis, in: context), .skipped)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
    }

    @MainActor
    func testEditorSessionMeasuresOnlyPersistedSuccessOnceAcrossDismissal() throws {
        let context = ModelContext(try container())
        let metrics = FoodCaptureMetrics()
        var presented: FoodProductEditorSession? = FoodProductEditorSession(metrics: metrics)
        let editor = try XCTUnwrap(presented)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .manual,
            nutrition: .init(calories: 200, protein: 10, carbs: 20, fat: 8)))
        XCTAssertEqual(metrics.archive.captures.first?.id, editor.id)
        XCTAssertEqual(editor.saveProduct(name: "Synthetic", basis: basis, in: context, save: { isolated in
            XCTAssertEqual(metrics.archive.captures.first?.outcome, .inProgress)
            try isolated.save()
            XCTAssertEqual(metrics.archive.captures.first?.outcome, .inProgress)
        }), .saved)
        let completed = metrics.archive.captures
        presented = nil
        editor.close()
        editor.close(cancelled: true)
        editor.recordCorrection()
        XCTAssertEqual(editor.saveProduct(name: "Duplicate", basis: basis, in: context), .skipped)
        XCTAssertEqual(metrics.archive.captures, completed)
        XCTAssertEqual(completed.count, 1)
        XCTAssertEqual(completed.first?.kind, .productCreation)
        XCTAssertEqual(completed.first?.outcome, .productSaved)
        XCTAssertEqual(completed.first?.timingComplete, true)
        XCTAssertEqual(completed.first?.operations.count, 0)
        XCTAssertFalse(metrics.hasActiveCaptures)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
    }

    @MainActor
    func testEditorSessionFailureRemainsOpenAndRetryReportsProductSaved() throws {
        let context = ModelContext(try container())
        let metrics = FoodCaptureMetrics()
        let editor = FoodProductEditorSession(metrics: metrics)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .manual,
            nutrition: .init(calories: 200, protein: 10, carbs: 20, fat: 8)))
        XCTAssertEqual(editor.saveProduct(name: "Synthetic", basis: basis, in: context,
            save: { _ in throw CocoaError(.fileWriteUnknown) }), .failed)
        XCTAssertEqual(metrics.archive.captures.first?.outcome, .inProgress)
        XCTAssertNil(metrics.archive.captures.first?.endedAt)
        XCTAssertEqual(metrics.archive.captures.first?.saveFailures, 1)
        XCTAssertTrue(metrics.localCaptureIDs.contains(editor.id))
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 0)
        editor.recordCorrection()
        XCTAssertEqual(editor.saveProduct(name: "Synthetic", basis: basis, in: context), .saved)
        editor.close()
        XCTAssertEqual(metrics.archive.captures.count, 1)
        XCTAssertEqual(metrics.archive.captures.first?.outcome, .productSaved)
        XCTAssertEqual(metrics.archive.captures.first?.manualCorrectionRounds, 1)
        XCTAssertEqual(metrics.archive.captures.first?.saveFailures, 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 1)
    }

    @MainActor
    func testEditorSessionCancellationAndDismissalNeverReportSuccess() throws {
        for failedSave in [false, true] {
            for cancelled in [false, true] {
                let context = ModelContext(try container())
                let metrics = FoodCaptureMetrics()
                let editor = FoodProductEditorSession(metrics: metrics)
                let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .manual,
                    nutrition: .init(calories: 200, protein: 10, carbs: 20, fat: 8)))
                if failedSave {
                    XCTAssertEqual(editor.saveProduct(name: "Synthetic", basis: basis, in: context,
                        save: { _ in throw CocoaError(.fileWriteUnknown) }), .failed)
                } else {
                    XCTAssertEqual(editor.saveProduct(name: " ", basis: basis, in: context), .skipped)
                }
                editor.close(cancelled: cancelled)
                let completed = metrics.archive.captures
                editor.close()
                editor.close(cancelled: true)
                XCTAssertEqual(editor.saveProduct(name: "Late save", basis: basis, in: context), .skipped)
                XCTAssertEqual(metrics.archive.captures, completed)
                XCTAssertEqual(completed.count, 1)
                XCTAssertEqual(completed.first?.outcome, cancelled ? .discarded : .incomplete)
                XCTAssertEqual(completed.first?.timingComplete, cancelled)
                XCTAssertEqual(completed.first?.saveFailures, failedSave ? 1 : 0)
                XCTAssertFalse(metrics.hasActiveCaptures)
                XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 0)
                XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
            }
        }
    }

    @MainActor
    func testEditorSessionKeepsOriginalAIReviewOpenOnDismissal() throws {
        let context = ModelContext(try container())
        let metrics = FoodCaptureMetrics()
        let captureID = metrics.begin()
        let dismissed = FoodProductEditorSession(metrics: metrics, captureID: captureID)
        dismissed.close(cancelled: true)
        dismissed.close()
        XCTAssertEqual(metrics.currentID, captureID)
        XCTAssertEqual(metrics.archive.captures.first?.outcome, .inProgress)
        let reopened = FoodProductEditorSession(metrics: metrics, captureID: captureID)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .aiEstimate,
            nutrition: .init(calories: 200, protein: 10, carbs: 20, fat: 8)))
        XCTAssertEqual(reopened.saveProduct(name: "Synthetic", basis: basis, in: context), .saved)
        reopened.close()
        metrics.finish(.incomplete, captureID: captureID)
        XCTAssertEqual(metrics.archive.captures.count, 1)
        XCTAssertEqual(metrics.archive.captures.first?.kind, .aiCapture)
        XCTAssertEqual(metrics.archive.captures.first?.outcome, .productSaved)
        XCTAssertNil(metrics.currentID)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
    }

    @MainActor
    func testMalformedProductBackupIsRejectedBeforeAnyWrites() throws {
        let context = ModelContext(try container())
        context.insert(FoodEntry(name: "Existing", calories: 1, proteinGrams: 0, carbsGrams: 0, fatGrams: 0))
        try context.save()
        let original = try BackupService.createBackup(modelContext: context)
        for fields in [["baseQuantity": "0", "baseUnit": "g", "valueOrigin": "packaging"],
                       ["baseQuantity": "100", "baseUnit": "kg", "valueOrigin": "packaging"],
                       ["baseQuantity": "100", "valueOrigin": "packaging"],
                       ["baseQuantity": "100", "baseUnit": "g", "valueOrigin": "invented"]] {
            var json = try XCTUnwrap(JSONSerialization.jsonObject(with: original) as? [String: Any])
            var preset: [String: Any] = ["name": "Invalid", "calories": 100, "proteinGrams": 1,
                "carbsGrams": 2, "fatGrams": 3, "createdAt": "2026-09-01T10:00:00Z"]
            for (key, value) in fields { preset[key] = value }
            json["foodPresets"] = [preset]
            XCTAssertThrowsError(try BackupService.decodeBackup(from: JSONSerialization.data(withJSONObject: json)))
            XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 1)
            XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodPreset>()), 0)
        }
    }

    @MainActor
    func testEditingValuesInvalidatesPackagingOriginButNotesDoNot() {
        let entry = FoodEntry(name: "Synthetic", calories: 100, proteinGrams: 1, carbsGrams: 2, fatGrams: 3,
                              valueOrigin: "packaging", consumedQuantity: "100", consumedUnit: "g")
        entry.notes = "Synthetic note"
        entry.invalidateOriginIfEdited(name: "Synthetic", calories: 100, protein: 1, carbs: 2, fat: 3)
        XCTAssertEqual(entry.valueOrigin, "packaging")
        entry.invalidateOriginIfEdited(name: "Synthetic", calories: 101, protein: 1, carbs: 2, fat: 3)
        XCTAssertEqual(entry.valueOrigin, "manual")
        XCTAssertNil(entry.consumedQuantity)
        XCTAssertNil(entry.consumedUnit)
    }

    @MainActor
    func testUpgradeOfPopulatedOriginalStorePreservesFoodAndWorkoutRelationships() throws {
        let location = try XCTUnwrap(ProcessInfo.processInfo.environment["PFT_LEGACY_STORE_URL"])
        let url = URL(fileURLWithPath: location)
        XCTAssertTrue(FileManager.default.fileExists(atPath: location))
        let schema = Schema([Exercise.self, WorkoutSession.self, ExercisePerformance.self, WorkoutSet.self,
                             Activity.self, FoodEntry.self, FoodPreset.self, WeightEntry.self, UserGoals.self])
        let container = try ModelContainer(for: schema, configurations: ModelConfiguration(url: url))
        let context = ModelContext(container)
        let presets = try context.fetch(FetchDescriptor<FoodPreset>(sortBy: [SortDescriptor(\.name)]))
        let entries = try context.fetch(FetchDescriptor<FoodEntry>(sortBy: [SortDescriptor(\.name)]))
        XCTAssertEqual(presets.count, 3)
        XCTAssertEqual(entries.count, 3)
        for index in 0..<3 {
            XCTAssertEqual(presets[index].name, "Legacy favorite \(index + 1)")
            XCTAssertEqual(presets[index].calories, (index + 1) * 100)
            XCTAssertEqual(presets[index].createdAt, Date(timeIntervalSince1970: 1_000_000))
            XCTAssertNil(presets[index].baseQuantity)
            XCTAssertNil(presets[index].baseUnit)
            XCTAssertNil(presets[index].valueOrigin)
            XCTAssertNil(presets[index].baseCalories)
            XCTAssertNil(entries[index].valueOrigin)
            XCTAssertNil(entries[index].consumedQuantity)
            XCTAssertEqual(entries[index].notes, "Synthetic legacy note")
            XCTAssertEqual(entries[index].calories, (index + 1) * 100)
        }
        let performance = try XCTUnwrap(context.fetch(FetchDescriptor<ExercisePerformance>()).first)
        let workoutSet = try XCTUnwrap(context.fetch(FetchDescriptor<WorkoutSet>()).first)
        XCTAssertEqual(performance.exercise?.name, "Legacy exercise")
        XCTAssertEqual(performance.exercise?.nextWeightIncreaseMarkedAt, Date(timeIntervalSince1970: 1_000_000))
        XCTAssertNotNil(performance.workoutSession)
        XCTAssertTrue(workoutSet.performance === performance)
        XCTAssertEqual(workoutSet.weightKg, 60)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .milliliters, origin: .packaging,
            nutrition: .init(calories: 40, protein: 1, carbs: 5, fat: 2)))
        XCTAssertEqual(FoodProductPersistence().saveProduct(name: "New product", basis: basis, in: context), .saved)
        let reader = ModelContext(container)
        let product = try XCTUnwrap(reader.fetch(FetchDescriptor<FoodPreset>()).first { $0.name == "New product" })
        XCTAssertEqual(product.productBasis, basis)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodEntry>()), 3)
        XCTAssertEqual(FoodProductPersistence().savePortion(of: product, quantity: 250, in: reader), .saved)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodEntry>()), 4)
        let backup = try BackupService.decodeBackup(from: BackupService.createBackup(modelContext: reader))
        XCTAssertEqual(backup.foodPresets.count, 4)
        XCTAssertEqual(backup.foodEntries.count, 4)
        XCTAssertEqual(backup.workoutSessions.first?.performances.first?.sets.first?.repetitions, 8)
    }

    @MainActor
    private func container() throws -> ModelContainer {
        let schema = Schema([Exercise.self, WorkoutSession.self, ExercisePerformance.self, WorkoutSet.self,
                             Activity.self, FoodEntry.self, FoodPreset.self, WeightEntry.self, UserGoals.self])
        return try ModelContainer(for: schema, configurations: ModelConfiguration(isStoredInMemoryOnly: true))
    }

    @MainActor
    func testProductSaveCreatesNoEntryAndPortionSaveDoesNotChangeBasis() throws {
        let container = try container()
        let context = ModelContext(container)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 100, unit: .grams, origin: .packaging,
            nutrition: .init(calories: Decimal(string: "123.4")!, protein: 10, carbs: 15, fat: 4)))
        let creation = FoodProductPersistence()
        XCTAssertEqual(creation.saveProduct(name: "Synthetic product", basis: basis, in: context), .saved)
        XCTAssertEqual(creation.saveProduct(name: "Duplicate", basis: basis, in: context), .skipped)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 0)
        let preset = try XCTUnwrap(context.fetch(FetchDescriptor<FoodPreset>()).first)
        XCTAssertEqual(preset.productBasis, basis)
        let portion = FoodProductPersistence()
        XCTAssertEqual(portion.savePortion(of: preset, quantity: 250, in: context), .saved)
        XCTAssertEqual(portion.savePortion(of: preset, quantity: 300, in: context), .skipped)
        let entries = try context.fetch(FetchDescriptor<FoodEntry>())
        XCTAssertEqual(entries.count, 1)
        XCTAssertEqual(entries[0].calories, 309)
        XCTAssertEqual(entries[0].proteinGrams, 25)
        XCTAssertEqual(entries[0].valueOrigin, "packaging")
        XCTAssertEqual(entries[0].consumedQuantity, "250")
        XCTAssertEqual(preset.productBasis, basis)
        let exported = try BackupService.createBackup(modelContext: context)
        let restored = ModelContext(try self.container())
        try BackupService.restoreBackup(BackupService.decodeBackup(from: exported), modelContext: restored)
        XCTAssertEqual(try restored.fetch(FetchDescriptor<FoodPreset>()).first?.productBasis, basis)
        XCTAssertEqual(try restored.fetch(FetchDescriptor<FoodEntry>()).first?.consumedQuantity, "250")
        XCTAssertEqual(try restored.fetch(FetchDescriptor<FoodEntry>()).first?.valueOrigin, "packaging")
        XCTAssertEqual(FoodProductPersistence().savePortion(of: preset, quantity: 100, in: context), .saved)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 2)
        XCTAssertEqual(try context.fetch(FetchDescriptor<FoodEntry>()).first { $0.consumedQuantity == "100" }?.calories, 123)
        XCTAssertEqual(preset.productBasis, basis)
    }

    @MainActor
    func testFailureRollsBackAndRetryDoesNotSaveUnrelatedEdits() throws {
        let context = ModelContext(try container())
        let unrelated = FoodEntry(name: "Uncommitted", calories: 1, proteinGrams: 0, carbsGrams: 0, fatGrams: 0)
        context.autosaveEnabled = false
        context.insert(unrelated)
        let basis = try XCTUnwrap(FoodProductBasis(quantity: 1, unit: .piece, origin: .aiEstimate,
            nutrition: .init(calories: 10, protein: 0, carbs: 0, fat: 0)))
        let creation = FoodProductPersistence()
        XCTAssertEqual(creation.saveProduct(name: "Synthetic", basis: basis, in: context,
            save: { _ in throw CocoaError(.fileWriteUnknown) }), .failed)
        let reader = ModelContext(context.container)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodPreset>()), 0)
        XCTAssertEqual(creation.saveProduct(name: "Synthetic", basis: basis, in: context), .saved)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodEntry>()), 0)
        XCTAssertTrue(context.hasChanges)
        let preset = try XCTUnwrap(reader.fetch(FetchDescriptor<FoodPreset>()).first)
        let portion = FoodProductPersistence()
        XCTAssertEqual(portion.savePortion(of: preset, quantity: 2, in: context,
            save: { _ in throw CocoaError(.fileWriteUnknown) }), .failed)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodEntry>()), 0)
        XCTAssertEqual(portion.savePortion(of: preset, quantity: 2, in: context), .saved)
        XCTAssertEqual(try reader.fetchCount(FetchDescriptor<FoodEntry>()), 1)
    }

    @MainActor
    func testLegacyBackupWithoutProductFieldsRetainsFixedPortion() throws {
        let data = Data("""
        {"exportDate":"2026-09-01T10:00:00Z","exercises":[],"workoutSessions":[],"activities":[],
         "foodEntries":[{"date":"2026-09-01T10:00:00Z","name":"Old meal","calories":42,"proteinGrams":1,"carbsGrams":2,"fatGrams":3}],
         "foodPresets":[{"createdAt":"2026-09-01T10:00:00Z","name":"Old favorite","calories":42,"proteinGrams":1,"carbsGrams":2,"fatGrams":3}],
         "weightEntries":[],"userGoals":null}
        """.utf8)
        let context = ModelContext(try container())
        try BackupService.restoreBackup(BackupService.decodeBackup(from: data), modelContext: context)
        let preset = try XCTUnwrap(context.fetch(FetchDescriptor<FoodPreset>()).first)
        XCTAssertNil(preset.productBasis)
        XCTAssertNil(preset.valueOrigin)
        XCTAssertEqual(preset.calories, 42)
        XCTAssertEqual(FoodProductPersistence().savePortion(of: preset, quantity: 100, in: context), .skipped)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<FoodEntry>()), 1)
    }
}
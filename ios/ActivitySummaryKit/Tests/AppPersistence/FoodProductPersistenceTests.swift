import Foundation
import SwiftData
import XCTest
import FoodAnalysisKit
@testable import MarkerAppPersistence

final class FoodProductPersistenceTests: XCTestCase {
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
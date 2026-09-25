import XCTest
@testable import FoodAnalysisKit

final class FoodLabelRecognitionTests: XCTestCase {
    private func token(_ text: String, _ x: Double, _ y: Double, width: Double = 0.08) -> FoodLabelText {
        .init(text: text, x: x, y: y, width: width, height: 0.025)
    }

    private func table() -> [FoodLabelText] {
        [token("pro", 0.48, 0.10), token("100", 0.58, 0.10), token("g", 0.67, 0.10, width: 0.02),
         token("Brennwert", 0.10, 0.20), token("840kJ", 0.43, 0.20), token("200kcal", 0.60, 0.20),
         token("Fett", 0.10, 0.26), token("4,5g", 0.60, 0.26),
         token("gesättigte Fettsäuren", 0.10, 0.31, width: 0.30), token("1,2g", 0.60, 0.31),
         token("Kohlenhydrate", 0.10, 0.37), token("30g", 0.60, 0.37),
         token("Eiweiß", 0.10, 0.43), token("8,2g", 0.60, 0.43)]
    }

    func testVerticalEnglishPanelsKeepServingBasisAndIgnoreSugarPercentages() {
        func word(_ text: String, _ x: Double, _ y: Double, _ lineID: Int) -> FoodLabelText {
            FoodLabelText(text: text, x: x, y: y, width: 0.08, height: 0.03, lineID: lineID, lineSlope: 0)
        }
        let panels = [word("Calories", 0.15, 0.20, 1), word("Sugar", 0.40, 0.20, 2), word("Fat", 0.65, 0.20, 3),
            word("160", 0.15, 0.26, 4), word("0g", 0.40, 0.26, 5), word("3g", 0.65, 0.26, 6),
            word("8%", 0.15, 0.30, 7), word("0%", 0.40, 0.30, 8), word("4%", 0.65, 0.30, 9)]
        for hasMass in [true, false] {
            let reference = [word("Serving", 0.30, 0.1, 0)] + (hasMass ? [word("40g", 0.42, 0.1, 0)] : [])
            let analysis = FoodLabelRecognition.analyze(reference + panels)
            XCTAssertEqual(analysis.columns.first?.quantity, hasMass ? 40 : nil)
            XCTAssertEqual(analysis.columns.first?.unit, hasMass ? .grams : nil)
            XCTAssertEqual(analysis.columns.first?.calories, 160)
            XCTAssertEqual(analysis.columns.first?.fat, 3)
            XCTAssertNil(analysis.columns.first?.carbs)
            XCTAssertTrue(analysis.columns.first?.heading.contains("Portion") == true)
            let mixed = FoodLabelRecognition.analyze(reference + panels + [word("per", 0.7, 0.1, 10), word("100g", 0.8, 0.1, 10)])
            XCTAssertTrue(mixed.columns.isEmpty)
            let bareReference = FoodLabelRecognition.analyze(reference + panels + [word("100g", 0.8, 0.1, 10)])
            XCTAssertTrue(bareReference.columns.isEmpty)
            let saturated = FoodLabelRecognition.analyze(reference + panels + [word("Saturated", 0.54, 0.20, 3)])
            XCTAssertNil(saturated.columns.first?.fat)
            XCTAssertEqual(saturated.columns.first?.calories, 160)
        }
    }

    func testVisionReadingOrderCannotOverrideCompleteGeometricRow() {
        let input = [token("100g", 0.6, 0.12),
            FoodLabelText(text: "Carbohydrate", x: 0.1, y: 0.32, width: 0.2, height: 0.025, lineID: 10, lineSlope: 0),
            FoodLabelText(text: "2g", x: 0.6, y: 0.345, width: 0.08, height: 0.025, lineID: 11, lineSlope: 0),
            FoodLabelText(text: "24g", x: 0.6, y: 0.32, width: 0.08, height: 0.025, lineID: 12, lineSlope: 0)]
        XCTAssertEqual(FoodLabelRecognition.columns(from: input).first?.carbs, 24)
    }

    func testInvalidVisionMetadataIsRejected() {
        for word in [
            FoodLabelText(text: "Fat", x: 0.1, y: 0.2, width: 0.1, height: 0.03, lineID: Int.max),
            FoodLabelText(text: "Fat", x: 0.1, y: 0.2, width: 0.1, height: 0.03, lineSlope: .nan),
            FoodLabelText(text: "Fat", x: 0.1, y: 0.2, width: 0.1, height: 0.03, alternatives: Array(repeating: "Fat", count: 9))
        ] {
            XCTAssertEqual(FoodLabelRecognition.analyze([word]).issues.first?.reason, .invalidInput)
        }
    }

    func testVisionReadingOrderCannotBorrowValueFromAboveLabel() {
        let input = [token("100g", 0.6, 0.12),
            FoodLabelText(text: "Carbohydrate", x: 0.1, y: 0.32, width: 0.2, height: 0.025, lineID: 10),
            FoodLabelText(text: "2g", x: 0.6, y: 0.295, width: 0.08, height: 0.025, lineID: 11),
            FoodLabelText(text: "24g", x: 0.6, y: 0.32, width: 0.08, height: 0.025, lineID: 12)]
        XCTAssertEqual(FoodLabelRecognition.columns(from: input).first?.carbs, 24)
    }

    func testOnlyUnambiguousObservedLabelAlternativesAreUsed() {
        for (alternatives, expected) in [(["Fett"], Optional(Decimal(3))), (["Fett", "Protein"], nil)] {
            let input = [token("100g", 0.6, 0.1),
                FoodLabelText(text: "Unreadable", x: 0.1, y: 0.2, width: 0.2, height: 0.025, alternatives: alternatives),
                token("3g", 0.6, 0.2)]
            XCTAssertEqual(FoodLabelRecognition.columns(from: input).first?.fat, expected)
        }
        let input = [token("100g", 0.6, 0.1),
            FoodLabelText(text: "Sugar", x: 0.1, y: 0.2, width: 0.2, height: 0.025, alternatives: ["Fat"]),
            token("3g", 0.6, 0.2)]
        XCTAssertNil(FoodLabelRecognition.columns(from: input).first?.fat)
    }

    func testVisionLinePairsPreserveCurvedTableOrder() {
        func word(_ text: String, _ x: Double, _ y: Double, _ lineID: Int) -> FoodLabelText {
            FoodLabelText(text: text, x: x, y: y, width: 0.10, height: 0.04, lineID: lineID)
        }
        let result = FoodLabelRecognition.analyze([word("100ml", 0.65, 0.1, 0),
            word("Energie", 0.1, 0.20, 1), word("45kcal", 0.65, 0.23, 2),
            word("Fett", 0.1, 0.24, 3), word("<0.2g", 0.65, 0.27, 4),
            word("Zucker", 0.1, 0.32, 5), word("7g", 0.65, 0.35, 6),
            word("Eiweiss", 0.1, 0.36, 7), word("1g", 0.65, 0.39, 8)])
        XCTAssertEqual(result.columns.first?.calories, 45)
        XCTAssertEqual(result.columns.first?.protein, 1)
        XCTAssertNil(result.columns.first?.fat)
        XCTAssertNil(result.columns.first?.carbs)
        XCTAssertTrue(result.issues.contains { $0.field == "fat" && $0.reason == .nonExactValue })
    }

    func testEnglishRowsKeepReferenceAndServingSeparate() {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.1),
            token("Serving", 0.77, 0.06), token("25g", 0.77, 0.1),
            token("Calories", 0.1, 0.2), token("240", 0.48, 0.2), token("60", 0.77, 0.2),
            token("Fat", 0.1, 0.26), token("<0.4g", 0.48, 0.26), token("2g", 0.77, 0.26),
            token("Carbohydrate", 0.1, 0.32), token("40g", 0.48, 0.32), token("10g", 0.77, 0.32),
            token("Sugar", 0.1, 0.38), token("20g", 0.48, 0.38), token("5g", 0.77, 0.38)])
        XCTAssertEqual(columns.count, 2)
        XCTAssertEqual(columns.first?.calories, 240)
        XCTAssertEqual(columns.last?.calories, 60)
        XCTAssertEqual(columns.last?.quantity, 25)
        XCTAssertNil(columns.first?.fat)
        XCTAssertEqual(columns.last?.fat, 2)
        XCTAssertEqual(columns.first?.carbs, 40)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
    }

    func testInequalityIsDiagnosedWithoutInventingExactValueOrServingMass() {
        let analysis = FoodLabelRecognition.analyze([token("Serving", 0.6, 0.1),
            token("Fat", 0.1, 0.2), token("<0.1g", 0.6, 0.2)])
        XCTAssertNil(analysis.columns.first?.quantity)
        XCTAssertNil(analysis.columns.first?.fat)
        XCTAssertTrue(analysis.issues.contains { $0.field == "fat" && $0.reason == .nonExactValue })
    }

    func testHeaderColonAndEnergySeparatorPreserveExplicitUnits() {
        let columns = FoodLabelRecognition.columns(from: [token("100ml:", 0.60, 0.10),
            token("Energie", 0.10, 0.20), token("840", 0.40, 0.20, width: 0.03),
            token("kJ/", 0.44, 0.20, width: 0.035), token("200", 0.58, 0.20, width: 0.03),
            token("kcal", 0.62, 0.20, width: 0.04)])
        XCTAssertEqual(columns.first?.quantity, 100)
        XCTAssertEqual(columns.first?.unit, .milliliters)
        XCTAssertEqual(columns.first?.calories, 200)
    }

    func testClippedPeripheralWordDoesNotRejectTheTable() {
        let peripheral = FoodLabelText(text: "Randtext", x: 0.2, y: 0.95, width: 0.2, height: 0.06)
        XCTAssertFalse(peripheral.isValid)
        let clipped = peripheral.clippedToImageBounds()
        XCTAssertTrue(clipped.isValid)
        XCTAssertEqual(clipped.y + clipped.height, 1)
        XCTAssertEqual(FoodLabelRecognition.columns(from: table() + [clipped]).first?.calories, 200)
        for invalid in [FoodLabelText(text: "100g", x: 1.1, y: 0.1, width: 0.1, height: 0.1),
                        FoodLabelText(text: "100g", x: .nan, y: 0.1, width: 0.1, height: 0.1),
                        FoodLabelText(text: "100g", x: 0.1, y: 0.1, width: 0, height: 0.1)] {
            XCTAssertFalse(invalid.clippedToImageBounds().isValid)
        }
    }

    func testClippedNumericOrUnitWordsRemainOpen() {
        for cell in [[token("8g", 0.95, 0.20).clippedToImageBounds()],
                     [token("8", 0.88, 0.20, width: 0.03), token("g", 0.94, 0.20).clippedToImageBounds()]] {
            let result = FoodLabelRecognition.analyze([token("100g", 0.90, 0.10), token("Fett", 0.1, 0.20)] + cell)
            XCTAssertNil(result.columns.first?.fat)
            XCTAssertTrue(result.issues.contains { $0.field == "fat" && $0.reason == .ambiguousOCRNumber })
        }
        let clippedLabel = FoodLabelText(text: "Fett (g)", x: -0.01, y: 0.2, width: 0.2, height: 0.025).clippedToImageBounds()
        let result = FoodLabelRecognition.analyze([token("100g", 0.6, 0.1), clippedLabel, token("8", 0.6, 0.2)])
        XCTAssertNil(result.columns.first?.fat)
        XCTAssertTrue(result.issues.contains { $0.field == "fat" && $0.reason == .ambiguousOCRNumber })
    }

    func testCompleteEnergyRowDoesNotAbsorbNearbyReferenceHeader() {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.181),
            token("Energie", 0.10, 0.20), token("840", 0.43, 0.205), token("kJ", 0.52, 0.205, width: 0.025),
            token("200", 0.56, 0.205, width: 0.03), token("kcal", 0.60, 0.205)])
        XCTAssertEqual(columns.first?.calories, 200)
    }

    func testConflictingOCRNumbersAreDistinctFromLabelOrDecimalSpelling() {
        XCTAssertTrue(FoodLabelRecognition.hasConflictingNumbers(in: ["Fett 4,9 g", "Fett 9,9 g"]))
        XCTAssertTrue(FoodLabelRecognition.hasConflictingNumbers(in: ["100 g", "10 g"]))
        XCTAssertTrue(FoodLabelRecognition.hasConflictingNumbers(in: ["0,5 g", "<0,5 g"]))
        XCTAssertFalse(FoodLabelRecognition.hasConflictingNumbers(in: ["Fett 4,9 g", "Fett 4.9 g"]))
        XCTAssertFalse(FoodLabelRecognition.hasConflictingNumbers(in: ["Fett", "Felt"]))
    }

    func testAmbiguousOCRNumbersRemainOpenWithoutBorrowingFromAnotherColumn() {
        let input = [token("100g", 0.48, 0.10), token("Portion", 0.77, 0.06), token("30g", 0.77, 0.10),
            token("Fett", 0.10, 0.20),
            FoodLabelText(text: "10g", x: 0.48, y: 0.20, width: 0.08, height: 0.025, numberIsAmbiguous: true),
            token("3g", 0.77, 0.20)]
        let analysis = FoodLabelRecognition.analyze(input)
        XCTAssertEqual(analysis.columns.count, 2)
        XCTAssertNil(analysis.columns.first?.fat)
        XCTAssertEqual(analysis.columns.last?.fat, 3)
        XCTAssertTrue(analysis.issues.contains { $0.columnID == 0 && $0.field == "fat" && $0.reason == .ambiguousOCRNumber })
    }

    func testAmbiguousOCRBasisRemainsOpenWhileOtherValuesStayReviewable() {
        let analysis = FoodLabelRecognition.analyze([
            FoodLabelText(text: "100g", x: 0.60, y: 0.10, width: 0.08, height: 0.025, numberIsAmbiguous: true),
            token("Fett", 0.10, 0.20), token("0g", 0.60, 0.20)])
        XCTAssertEqual(analysis.columns.count, 1)
        XCTAssertNil(analysis.columns.first?.quantity)
        XCTAssertEqual(analysis.columns.first?.fat, 0)
        XCTAssertEqual(analysis.columns.first?.hasValues, true)
        XCTAssertTrue(analysis.issues.contains { $0.field == "basis" && $0.reason == .ambiguousOCRNumber })
    }

    func testDiagnosticsDistinguishMissingTextHeaderAndValues() {
        XCTAssertEqual(FoodLabelRecognition.analyze([]).issues.first?.reason, .noText)
        XCTAssertEqual(FoodLabelRecognition.analyze([token("Fett", 0.1, 0.2)]).issues.first?.reason, .missingOrConflictingHeader)
        let input = [token("100g", 0.6, 0.1), token("Fett", 0.1, 0.2), token("3", 0.6, 0.2)]
        let analysis = FoodLabelRecognition.analyze(input)
        XCTAssertEqual(analysis.columns, FoodLabelRecognition.columns(from: input))
        XCTAssertTrue(analysis.issues.contains { $0.field == "fat" && $0.reason == .missingValueOrUnit })
    }

    func testCurvedCellsDoNotMixReferenceAndPortionColumns() {
        let input = [token("100g", 0.48, 0.10), token("Portion", 0.77, 0.06), token("30g", 0.77, 0.10),
            token("Fett", 0.10, 0.20), token("12", 0.48, 0.20), token("g/", 0.57, 0.216),
            token("3,6", 0.77, 0.209), token("g/", 0.86, 0.223),
            token("gesättigte Fettsäuren", 0.10, 0.26, width: 0.3), token("9g", 0.48, 0.26), token("2,7g", 0.77, 0.26)]
        let columns = FoodLabelRecognition.columns(from: input)
        XCTAssertEqual(columns.count, 2)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertEqual(columns.first?.quantity, 100)
        XCTAssertEqual(columns.first?.fat, 12)
        XCTAssertEqual(columns.last?.quantity, 30)
        XCTAssertEqual(columns.last?.fat, Decimal(string: "3.6"))
        XCTAssertTrue(columns.allSatisfy { $0.protein == nil && $0.carbs == nil })
    }

    func testPartialColumnWithUnknownBasisRemainsReviewableAndDiagnosed() {
        let analysis = FoodLabelRecognition.analyze([token("Portion", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("0g", 0.60, 0.20)])
        let selected = FoodLabelRecognition.selectedColumn(from: analysis.columns, id: nil)
        XCTAssertEqual(selected?.hasValues, true)
        XCTAssertNil(selected?.quantity)
        XCTAssertEqual(selected?.fat, 0)
        XCTAssertTrue(analysis.issues.contains { $0.field == "basis" && $0.reason == .missingValueOrUnit })
    }

    func testTallCarbohydrateLabelDoesNotAbsorbNeighboringSugarCell() throws {
        let input = [token("100g", 0.60, 0.10),
            FoodLabelText(text: "Kohlenhydrate", x: 0.10, y: 0.20, width: 0.30, height: 0.05),
            token("23,4", 0.60, 0.225), token("g/", 0.69, 0.225),
            token("Zucker", 0.10, 0.26), token("9,8", 0.60, 0.26), token("g/", 0.69, 0.26)]
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: input).first)
        XCTAssertEqual(column.carbs, Decimal(string: "23.4"))
        XCTAssertNil(column.fat)
    }

    func testExplicitBilingualGramUnitsDoNotGuessOtherUnits() {
        for unitText in ["г/", "г/g", "g/г", "mg/g", "g/mg"] {
            let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
                token("Fett", 0.10, 0.20), token("7,3", 0.60, 0.20), token(unitText, 0.69, 0.20)])
            if unitText.contains("mg") { XCTAssertNil(columns.first?.fat) }
            else { XCTAssertEqual(columns.first?.fat, Decimal(string: "7.3")) }
        }
    }

    func testWrappedUnitsAndCurvedMultilingualCellsRemainTogether() throws {
        let input = [token("100g", 0.60, 0.10),
            token("Valore", 0.10, 0.18), token("Energie", 0.10, 0.21),
            token("143", 0.60, 0.19), token("kcal/", 0.63, 0.21),
            token("Grassi/", 0.10, 0.27), token("Fett", 0.10, 0.30),
            token("7,3", 0.60, 0.30), token("g/", 0.69, 0.316),
            FoodLabelText(text: "Kohlenhydrate", x: 0.10, y: 0.37, width: 0.30, height: 0.04),
            token("42,1", 0.60, 0.395), token("g/", 0.69, 0.395)]
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: input).first)
        XCTAssertEqual(column.calories, 143)
        XCTAssertEqual(column.fat, Decimal(string: "7.3"))
        XCTAssertEqual(column.carbs, Decimal(string: "42.1"))
        XCTAssertNil(column.protein)
    }

    func testGermanDecimalCommaEnergyAndSaturatedFat() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: table()).first)
        XCTAssertEqual(column.quantity, 100)
        XCTAssertEqual(column.unit, .grams)
        XCTAssertEqual(column.calories, 200)
        XCTAssertEqual(column.fat, Decimal(string: "4.5"))
        XCTAssertEqual(column.carbs, 30)
        XCTAssertEqual(column.protein, Decimal(string: "8.2"))
    }

    func testTwoColumnsAreKeptSeparateAndPortionDoesNotBecome100Grams() throws {
        let tokens = [token("100g", 0.48, 0.10), token("Portion", 0.77, 0.06), token("30g", 0.77, 0.10),
                      token("Fett", 0.10, 0.20), token("10g", 0.48, 0.20), token("3g", 0.77, 0.20),
                      token("Eiweiß", 0.10, 0.26), token("20g", 0.48, 0.26), token("6g", 0.77, 0.26)]
        let columns = FoodLabelRecognition.columns(from: tokens.reversed())
        XCTAssertEqual(columns.count, 2)
        XCTAssertEqual(columns[0].quantity, 100)
        XCTAssertEqual(columns[0].fat, 10)
        XCTAssertEqual(columns[1].quantity, 30)
        XCTAssertEqual(columns[1].fat, 3)
        XCTAssertEqual(columns[1].protein, 6)
        XCTAssertTrue(columns[1].heading.contains("Portion"))
    }

    func testMissingValuesAndKilojoulesNeverBecomeZeroOrCalories() throws {
        let tokens = [token("100ml", 0.60, 0.10), token("Energie", 0.10, 0.20), token("800kJ", 0.60, 0.20),
                      token("Fett", 0.10, 0.26), token("0g", 0.60, 0.26)]
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: tokens).first)
        XCTAssertEqual(column.unit, .milliliters)
        XCTAssertNil(column.calories)
        XCTAssertEqual(column.fat, 0)
        XCTAssertNil(column.protein)
        XCTAssertNil(column.carbs)
    }

    func testUnknownPortionQuantityRemainsOpen() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: [token("Portion", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)]).first)
        XCTAssertNil(column.quantity)
        XCTAssertNil(column.unit)
        XCTAssertEqual(column.fat, 3)
    }

    func testAmbiguousDuplicateRowsAndColumnBoundaryRemainOpen() throws {
        var tokens = table()
        tokens += [token("Eiweiß", 0.10, 0.50), token("5g", 0.60, 0.50)]
        XCTAssertNil(FoodLabelRecognition.columns(from: tokens).first?.protein)
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.45, 0.10), token("30g", 0.75, 0.10),
            token("Portion", 0.75, 0.06), token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)])
        XCTAssertEqual(columns.count, 2)
        XCTAssertTrue(columns.allSatisfy { $0.fat == nil })
    }

    func testInequalityUnsupportedUnitsAndUnitlessCellsStayOpen() {
        for text in ["<0,5g", "-2g", "2mg", "2", "1.234g", "5%", "NaNg"] {
            let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
                token("Fett", 0.10, 0.20), token(text, 0.60, 0.20)])
            XCTAssertNil(columns.first?.fat, text)
        }
    }

    func testExplicitRowUnitAndSplitValueUnit() throws {
        let column = try XCTUnwrap(FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie (kcal)", 0.10, 0.20), token("200", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("4,5", 0.58, 0.26), token("g", 0.67, 0.26)]).first)
        XCTAssertEqual(column.calories, 200)
        XCTAssertEqual(column.fat, Decimal(string: "4.5"))
    }

    func testInvalidGeometryIsRejectedAndUnheadedValuesRequireManualBasis() {
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("100g", -0.1, 0.1)]).isEmpty)
        let analysis = FoodLabelRecognition.analyze([token("Fett", 0.1, 0.2), token("3g", 0.6, 0.2)])
        XCTAssertEqual(analysis.columns.first?.fat, 3)
        XCTAssertNil(analysis.columns.first?.quantity)
        XCTAssertNil(analysis.columns.first?.unit)
        XCTAssertTrue(analysis.issues.contains { $0.field == "basis" && $0.reason == .missingValueOrUnit })
    }

    func testUnknownBasisDoesNotMergeColumnsOrIgnoreConflictingHeaders() {
        let row = [token("Fett", 0.1, 0.2), token("3g", 0.6, 0.2)]
        XCTAssertTrue(FoodLabelRecognition.columns(from: row + [token("6g", 0.8, 0.2)]).isEmpty)
        XCTAssertTrue(FoodLabelRecognition.columns(from: row + [token("6g", 0.8, 0.2),
            token("Eiweiss", 0.1, 0.3), token("4g", 0.6, 0.3)]).isEmpty)
        XCTAssertTrue(FoodLabelRecognition.columns(from: row + [token("Eiweiss", 0.1, 0.3), token("6g", 0.8, 0.3)]).isEmpty)
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("100g", 0.6, 0.1),
            token("pro", 0.4, 0.15), token("50g", 0.6, 0.15)] + row).isEmpty)
    }

    func testMultipleColumnsRequireExplicitSelection() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("Portion", 0.77, 0.10), token("Fett", 0.10, 0.20),
            token("10g", 0.48, 0.20), token("3g", 0.77, 0.20)])
        XCTAssertEqual(columns.count, 2)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: 8))
        XCTAssertEqual(FoodLabelRecognition.selectedColumn(from: columns, id: 1)?.fat, 3)
        XCTAssertNotNil(FoodLabelRecognition.selectedColumn(from: Array(columns.prefix(1)), id: nil))
    }

    func testSwitchingColumnsKeepsMissingAndZeroValuesWithTheirOwnBasis() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100ml", 0.48, 0.10),
            token("Portion", 0.77, 0.06), token("250ml", 0.77, 0.10),
            token("Energie", 0.10, 0.20), token("40kcal", 0.48, 0.20), token("100kcal", 0.77, 0.20),
            token("Fett", 0.10, 0.26), token("0g", 0.48, 0.26),
            token("Eiweiß", 0.10, 0.32), token("5g", 0.77, 0.32)])
        let reference = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: 0))
        let portion = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: 1))
        XCTAssertEqual(reference.quantity, 100)
        XCTAssertEqual(reference.unit, .milliliters)
        XCTAssertEqual(reference.calories, 40)
        XCTAssertEqual(reference.fat, 0)
        XCTAssertNil(reference.protein)
        XCTAssertEqual(portion.quantity, 250)
        XCTAssertEqual(portion.unit, .milliliters)
        XCTAssertEqual(portion.calories, 100)
        XCTAssertEqual(portion.protein, 5)
        XCTAssertNil(portion.fat)
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertEqual(FoodLabelRecognition.selectedColumn(from: columns, id: 0), reference)
    }

    func testSecondRecognitionDoesNotReusePreviousValuesOrBasis() throws {
        var columns = FoodLabelRecognition.columns(from: table())
        XCTAssertNotNil(FoodLabelRecognition.selectedColumn(from: columns, id: nil)?.protein)
        columns = FoodLabelRecognition.columns(from: [token("Portion", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("0g", 0.60, 0.20)])
        let replacement = try XCTUnwrap(FoodLabelRecognition.selectedColumn(from: columns, id: nil))
        XCTAssertNil(replacement.quantity)
        XCTAssertNil(replacement.unit)
        XCTAssertNil(replacement.calories)
        XCTAssertNil(replacement.protein)
        XCTAssertNil(replacement.carbs)
        XCTAssertEqual(replacement.fat, 0)
        columns = FoodLabelRecognition.columns(from: [])
        XCTAssertNil(FoodLabelRecognition.selectedColumn(from: columns, id: 0))
    }

    func testExtraUnheadedColumnDoesNotSilentlySelectOneValue() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("Fett", 0.10, 0.20), token("10g", 0.48, 0.20), token("3g", 0.77, 0.20)])
        XCTAssertNil(try XCTUnwrap(columns.first).fat)
    }

    func testPercentColumnIsNotANutrientOrPortion() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.48, 0.10),
            token("RI%", 0.77, 0.10), token("Fett", 0.10, 0.20),
            token("10g", 0.48, 0.20), token("14%", 0.77, 0.20)])
        XCTAssertEqual(columns.count, 1)
        XCTAssertEqual(columns.first?.fat, 10)
    }

    func testRepeatedValuesWithinOneColumnAndSplitInequalityRemainOpen() {
        for values in [[token("3g", 0.54, 0.20), token("4g", 0.66, 0.20)],
                       [token("<", 0.49, 0.20), token("0,5g", 0.60, 0.20)]] {
            let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10), token("Fett", 0.10, 0.20)] + values)
            XCTAssertNil(columns.first?.fat)
        }
    }

    func testStandaloneCaloriesAwayFromEnergyRowAreNotUsed() throws {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie", 0.10, 0.20), token("840kJ", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("4g", 0.60, 0.26), token("200kcal", 0.60, 0.70)])
        XCTAssertNil(try XCTUnwrap(columns.first).calories)
        XCTAssertEqual(columns.first?.fat, 4)
    }

    func testOutOfRangeValuesAndUnsupportedBasisAreNotFilled() {
        let columns = FoodLabelRecognition.columns(from: [token("100g", 0.60, 0.10),
            token("Energie", 0.10, 0.20), token("10001kcal", 0.60, 0.20),
            token("Fett", 0.10, 0.26), token("1001g", 0.60, 0.26)])
        XCTAssertNil(columns.first?.calories)
        XCTAssertNil(columns.first?.fat)
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("1kg", 0.60, 0.10),
            token("Fett", 0.10, 0.20), token("3g", 0.60, 0.20)]).isEmpty)
    }

    func testPortableSyntheticFixtures() throws {
        struct Expected: Decodable {
            let quantity: String?
            let unit: String?
            let calories: String?
            let protein: String?
            let carbs: String?
            let fat: String?
        }
        struct Case: Decodable {
            let id: String
            let tokens: [FoodLabelText]
            let expected: [Expected]
        }
        struct Fixture: Decodable {
            let version: Int
            let coordinates: String
            let cases: [Case]
        }
        let url = try XCTUnwrap(Bundle.module.url(forResource: "nutrition-label-v1", withExtension: "json", subdirectory: "Fixtures"))
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))
        XCTAssertEqual(fixture.version, 1)
        XCTAssertEqual(fixture.coordinates, "normalized-top-left")
        for sample in fixture.cases {
            let columns = FoodLabelRecognition.columns(from: sample.tokens)
            XCTAssertEqual(columns.count, sample.expected.count, sample.id)
            for (column, expected) in zip(columns, sample.expected) {
                func decimal(_ text: String?) -> Decimal? { text.flatMap { Decimal(string: $0, locale: Locale(identifier: "en_US_POSIX")) } }
                XCTAssertEqual(column.quantity, decimal(expected.quantity), sample.id)
                XCTAssertEqual(column.unit?.rawValue, expected.unit, sample.id)
                XCTAssertEqual(column.calories, decimal(expected.calories), sample.id)
                XCTAssertEqual(column.protein, decimal(expected.protein), sample.id)
                XCTAssertEqual(column.carbs, decimal(expected.carbs), sample.id)
                XCTAssertEqual(column.fat, decimal(expected.fat), sample.id)
            }
        }
    }
}
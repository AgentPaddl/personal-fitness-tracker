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

    func testInvalidGeometryAndUnheadedTableAreRejected() {
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("100g", -0.1, 0.1)]).isEmpty)
        XCTAssertTrue(FoodLabelRecognition.columns(from: [token("Fett", 0.1, 0.2), token("3g", 0.6, 0.2)]).isEmpty)
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
import XCTest

@testable import FoodAnalysisKit

final class FoodAnalysisReviewDraftTests: XCTestCase {
    private func makeEstimate() -> FoodAnalysisResponseDTO.Estimate {
        FoodAnalysisResponseDTO.Estimate(
            foodName: "Apfel und Vollkornbrot",
            calories: 241,
            proteinGrams: 4.5,
            carbohydrateGrams: 43,
            fatGrams: 5.5,
            confidence: 0.7,
            warnings: ["Portionsgrößen geschätzt"]
        )
    }

    func testDraftIsPrefilledFromEstimate() {
        let draft = FoodAnalysisReviewDraft(estimate: makeEstimate())

        XCTAssertEqual(draft.name, "Apfel und Vollkornbrot")
        XCTAssertEqual(draft.calories, "241")
        XCTAssertEqual(draft.protein, "4.5")
        XCTAssertEqual(draft.carbs, "43.0")
        XCTAssertEqual(draft.fat, "5.5")
        XCTAssertEqual(draft.confidence, 0.7)
        XCTAssertEqual(draft.warnings, ["Portionsgrößen geschätzt"])
    }

    func testValidatedReturnsInputForWellFormedDraft() throws {
        let draft = FoodAnalysisReviewDraft(estimate: makeEstimate())

        let input = try XCTUnwrap(draft.validated())

        XCTAssertEqual(input.name, "Apfel und Vollkornbrot")
        XCTAssertEqual(input.calories, 241)
        XCTAssertEqual(input.proteinGrams, 4.5)
        XCTAssertEqual(input.carbsGrams, 43)
        XCTAssertEqual(input.fatGrams, 5.5)
    }

    func testValidatedAcceptsCommaDecimalSeparator() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.protein = "4,5"

        XCTAssertEqual(draft.validated()?.proteinGrams, 4.5)
    }

    func testValidatedTrimsWhitespaceFromName() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.name = "  Apfel  "

        XCTAssertEqual(draft.validated()?.name, "Apfel")
    }

    func testValidatedRejectsBlankName() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.name = "   "

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsUnparsableCalories() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.calories = "viel"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsBlankMacro() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.fat = ""

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsUnparsableMacro() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.carbs = "viele"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsNegativeCalories() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.calories = "-50"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsNegativeMacro() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.protein = "-1"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsNaN() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.fat = "nan"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsInfinity() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.carbs = "inf"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsCaloriesAboveUpperBound() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.calories = "10001"

        XCTAssertNil(draft.validated())
    }

    func testValidatedRejectsMacroAboveUpperBound() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.fat = "1000.1"

        XCTAssertNil(draft.validated())
    }

    func testValidatedAcceptsBoundaryValues() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())
        draft.calories = "10000"
        draft.protein = "1000"
        draft.carbs = "0"
        draft.fat = "0"

        let input = draft.validated()

        XCTAssertEqual(input?.calories, 10000)
        XCTAssertEqual(input?.proteinGrams, 1000)
        XCTAssertEqual(input?.carbsGrams, 0)
        XCTAssertEqual(input?.fatGrams, 0)
    }

    /// Documents the explicit calories rounding rule: the calories field is
    /// parsed as a decimal (comma or dot) and rounded to the nearest whole
    /// number, matching the rounding already applied when the draft is
    /// first created from an estimate.
    func testValidatedRoundsCaloriesToNearestWholeNumber() {
        var draft = FoodAnalysisReviewDraft(estimate: makeEstimate())

        draft.calories = "95.4"
        XCTAssertEqual(draft.validated()?.calories, 95)

        draft.calories = "95.6"
        XCTAssertEqual(draft.validated()?.calories, 96)

        draft.calories = "95,5"
        XCTAssertEqual(draft.validated()?.calories, 96)
    }
}

import XCTest

@testable import FoodAnalysisKit

final class FoodAnalysisDTOsTests: XCTestCase {
    func testRequestEncodesSnakeCaseKey() throws {
        let dto = FoodAnalysisRequestDTO(foodDescription: "Ein Apfel")

        let data = try JSONEncoder().encode(dto)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["food_description"] as? String, "Ein Apfel")
        XCTAssertEqual(json?.count, 1)
    }

    func testResponseDecodesBackendContract() throws {
        let json = """
            {"estimate": {"food_name": "Apfel", "calories": 95, "protein_grams": 0.5,
            "carbohydrate_grams": 25, "fat_grams": 0.3, "confidence": 0.8, "warnings": []}}
            """.data(using: .utf8)!

        let decoded = try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json)

        XCTAssertEqual(decoded.estimate.foodName, "Apfel")
        XCTAssertEqual(decoded.estimate.calories, 95)
        XCTAssertEqual(decoded.estimate.proteinGrams, 0.5)
        XCTAssertEqual(decoded.estimate.carbohydrateGrams, 25)
        XCTAssertEqual(decoded.estimate.fatGrams, 0.3)
        XCTAssertEqual(decoded.estimate.confidence, 0.8)
        XCTAssertEqual(decoded.estimate.warnings, [])
    }

    func testResponseDecodingFailsForMissingRequiredField() {
        let json = #"{"estimate": {"food_name": "Apfel"}}"#.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json))
    }

    func testResponseDecodingFailsForMissingEstimate() {
        let json = #"{}"#.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(FoodAnalysisResponseDTO.self, from: json))
    }
}

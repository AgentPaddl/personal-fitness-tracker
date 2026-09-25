import Foundation

public struct FoodLabelText: Codable, Equatable, Sendable {
    public let text: String
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double
    public let numberIsAmbiguous: Bool?

    public init(text: String, x: Double, y: Double, width: Double, height: Double, numberIsAmbiguous: Bool? = nil) {
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.numberIsAmbiguous = numberIsAmbiguous
    }

    var centerX: Double { x + width / 2 }
    var centerY: Double { y + height / 2 }
    var isValid: Bool {
        [x, y, width, height].allSatisfy(\.isFinite) && x >= 0 && y >= 0
            && width > 0 && height > 0 && x + width <= 1.001 && y + height <= 1.001
            && !text.isEmpty && text.count <= 200
    }
}

public struct FoodLabelColumn: Equatable, Identifiable {
    public let id: Int
    public let heading: String
    public let quantity: Decimal?
    public let unit: FoodProductUnit?
    public let calories: Decimal?
    public let protein: Decimal?
    public let carbs: Decimal?
    public let fat: Decimal?

    public var hasValues: Bool { [calories, protein, carbs, fat].contains { $0 != nil } }
}

public struct FoodLabelAnalysis {
    public let columns: [FoodLabelColumn]
    public let issues: [FoodLabelIssue]
}

public struct FoodLabelIssue: Equatable {
    public enum Reason: String {
        case noText, invalidInput, noNutrientLabels, missingOrConflictingHeader, tooManyColumns
        case missingRow, repeatedRows, missingValueOrUnit, ambiguousValues, outsideColumn, outOfRange
        case ambiguousOCRNumber
    }
    public let columnID: Int?
    public let field: String?
    public let reason: Reason
}

public enum FoodLabelRecognition {
    private enum Nutrient: String, CaseIterable { case calories, protein, carbs, fat }
    private struct Measurement {
        let value: Decimal
        let unit: String
        let centerX: Double
        let numberIsAmbiguous: Bool
    }
    private struct Header {
        var centerX: Double
        var quantity: Decimal?
        var unit: FoodProductUnit?
        var portion: Bool
        var numberIsAmbiguous = false
    }

    public static func columns(from input: [FoodLabelText]) -> [FoodLabelColumn] {
        analyze(input).columns
    }

    public static func hasConflictingNumbers(in candidates: [String]) -> Bool {
        let expression = try! NSRegularExpression(pattern: #"[<>≤≥~≈−+-]?\s*[0-9]+(?:[,.][0-9]+)?"#)
        let readings = candidates.map { candidate -> [String] in
            let text = normalized(candidate)
            return expression.matches(in: text, range: NSRange(text.startIndex..., in: text)).compactMap { match in
                guard let range = Range(match.range, in: text) else { return nil }
                return text[range].filter { !$0.isWhitespace }.replacingOccurrences(of: ",", with: ".")
            }
        }
        guard let first = readings.first else { return false }
        return readings.dropFirst().contains { $0 != first }
    }

    public static func analyze(_ input: [FoodLabelText]) -> FoodLabelAnalysis {
        func rejected(_ reason: FoodLabelIssue.Reason) -> FoodLabelAnalysis {
            FoodLabelAnalysis(columns: [], issues: [.init(columnID: nil, field: nil, reason: reason)])
        }
        guard !input.isEmpty else { return rejected(.noText) }
        guard input.count <= 2048, input.allSatisfy(\.isValid) else { return rejected(.invalidInput) }
        let rows = makeRows(input)
        guard let firstNutrient = rows.firstIndex(where: { nutrient(in: $0) != nil }) else { return rejected(.noNutrientLabels) }
        let headerRows = Array(rows[..<firstNutrient]).filter {
            (rows[firstNutrient].first?.y ?? 0) - ($0.first?.y ?? 0) < 0.22
        }
        let headers = findHeaders(headerRows)
        guard !headers.isEmpty else { return rejected(.missingOrConflictingHeader) }
        guard headers.count <= 6 else { return rejected(.tooManyColumns) }
        let nutrientRows = rows.map { row -> [FoodLabelText] in
            guard let kind = nutrient(in: row),
                  let anchor = row.first(where: { nutrient(in: [$0]) == kind }),
                  kind != .calories || contains(#"\b(brennwert|energie|kalorien)\b"#, in: normalized(anchor.text)) else { return row }
            let boundaries = input.filter { token in
                if contains(#"gesattigt|fettsaur|zucker|ballaststoff|salz"#, in: normalized(token.text)) { return true }
                return nutrient(in: [token]).map { $0 != kind } ?? false
            }
            let nearby = input.filter { token in
                token.x >= anchor.x && abs(token.centerY - anchor.centerY) <= max(token.height, anchor.height)
                    && boundaries.allSatisfy { boundary in
                        abs(token.centerY - anchor.centerY) + min(token.height, boundary.height) * 0.1
                            < abs(token.centerY - boundary.centerY)
                    }
            }.sorted { $0.x < $1.x }
            return nutrient(in: nearby) == kind ? nearby : row
        }
        var issues: [FoodLabelIssue] = []
        let columns = headers.enumerated().map { index, header in
            if header.numberIsAmbiguous || header.quantity == nil || header.unit == nil {
                issues.append(.init(columnID: index, field: "basis",
                                    reason: header.numberIsAmbiguous ? .ambiguousOCRNumber : .missingValueOrUnit))
            }
            var values: [Nutrient: Decimal] = [:]
            for kind in Nutrient.allCases {
                func reject(_ reason: FoodLabelIssue.Reason) {
                    issues.append(.init(columnID: index, field: kind.rawValue, reason: reason))
                }
                let matchingRows = nutrientRows.enumerated().compactMap { rowIndex, row -> [FoodLabelText]? in
                    guard nutrient(in: row) == kind else { return nil }
                    if kind == .calories {
                        let label = normalized(row.prefix { !contains(#"[0-9]"#, in: $0.text) }.map(\.text).joined(separator: " "))
                        let explicit = contains(#"\b(brennwert|energie|kalorien|kcal)\b"#, in: label)
                        let previous = rowIndex > 0 ? rows[rowIndex - 1] : []
                        let previousText = normalized(previous.map(\.text).joined(separator: " "))
                        let continuation = contains(#"\b(brennwert|energie)\b"#, in: previousText)
                            && contains(#"(?:^|[^a-z])kj\b"#, in: previousText)
                            && !contains(#"kcal"#, in: previousText)
                            && (row.first?.centerY ?? 1) - (previous.first?.centerY ?? 0)
                                <= 3 * min(row.first?.height ?? 0, previous.first?.height ?? 0)
                        guard explicit || continuation,
                              measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                                .contains(where: { $0.unit == "kcal" }) else { return nil }
                    }
                    return row
                }
                guard matchingRows.count == 1, let row = matchingRows.first else {
                    reject(matchingRows.isEmpty ? .missingRow : .repeatedRows)
                    continue
                }
                let readings = measurements(in: row, implicitUnit: implicitUnit(in: row, kind: kind))
                    .filter { $0.unit == (kind == .calories ? "kcal" : "g") }
                guard !readings.isEmpty else { reject(.missingValueOrUnit); continue }
                guard headers.count != 1 || readings.count <= 1 else { reject(.ambiguousValues); continue }
                let assigned = readings.filter { reading in
                    let distances = headers.map { abs($0.centerX - reading.centerX) }
                    guard let nearest = distances.min(), nearest <= 0.15,
                          distances[index] == nearest,
                          distances.filter({ abs($0 - nearest) < 0.025 }).count == 1 else { return false }
                    return true
                }
                if assigned.contains(where: \.numberIsAmbiguous) {
                    reject(.ambiguousOCRNumber)
                } else if assigned.count == 1, let value = assigned.first?.value,
                   value <= (kind == .calories ? 10000 : 1000) {
                    values[kind] = value
                } else {
                    reject(assigned.isEmpty ? .outsideColumn : assigned.count > 1 ? .ambiguousValues : .outOfRange)
                }
            }
            let quantity = header.numberIsAmbiguous ? nil : header.quantity
            let basis = quantity.map { NSDecimalNumber(decimal: $0).stringValue }
            let heading: String
            if let basis, let unit = header.unit {
                heading = header.portion ? "Portion (\(basis) \(unit.rawValue))" : "\(basis) \(unit.rawValue)"
            } else {
                heading = header.portion ? "Portion ohne eindeutige Bezugsmenge" : "Bezugsmenge nicht eindeutig"
            }
            return FoodLabelColumn(id: index, heading: heading, quantity: quantity, unit: header.unit,
                calories: values[.calories], protein: values[.protein], carbs: values[.carbs], fat: values[.fat])
        }
            return FoodLabelAnalysis(columns: columns, issues: issues)
    }

    public static func selectedColumn(from columns: [FoodLabelColumn], id: Int?) -> FoodLabelColumn? {
        if columns.count == 1, id == nil { return columns.first }
        guard let id else { return nil }
        return columns.first { $0.id == id }
    }

    private static func normalized(_ text: String) -> String {
        text.lowercased().folding(options: [.diacriticInsensitive, .widthInsensitive], locale: Locale(identifier: "de_DE"))
            .replacingOccurrences(of: "ß", with: "ss")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func makeRows(_ input: [FoodLabelText]) -> [[FoodLabelText]] {
        var rows: [[FoodLabelText]] = []
        for token in input.sorted(by: { $0.centerY < $1.centerY }) {
            if let index = rows.indices.last, let anchor = rows[index].first,
               abs(anchor.centerY - token.centerY) <= min(anchor.height, token.height) * 0.45 {
                rows[index].append(token)
            } else {
                rows.append([token])
            }
        }
        return rows.map { $0.sorted { $0.x < $1.x } }
    }

    private static func contains(_ pattern: String, in text: String) -> Bool {
        text.range(of: pattern, options: .regularExpression) != nil
    }

    private static func nutrient(in row: [FoodLabelText]) -> Nutrient? {
        let text = normalized(row.map(\.text).joined(separator: " "))
        guard !contains(#"gesattigt|fettsaur|zucker|ballaststoff|salz"#, in: text) else { return nil }
        var kinds: [Nutrient] = []
        if contains(#"\b(eiweiss|protein)\b"#, in: text) { kinds.append(.protein) }
        if contains(#"\bkohlenhydrate\b"#, in: text) { kinds.append(.carbs) }
        if contains(#"\bfett\b"#, in: text) { kinds.append(.fat) }
        if contains(#"\b(brennwert|energie|kalorien)\b"#, in: text) || kinds.isEmpty && contains(#"(?:^|[^a-z])kcal\b"#, in: text) {
            kinds.append(.calories)
        }
        return kinds.count == 1 ? kinds.first : nil
    }

    private static func implicitUnit(in row: [FoodLabelText], kind: Nutrient) -> String? {
        let label = normalized(row.prefix { !contains(#"[0-9]"#, in: $0.text) }.map(\.text).joined(separator: " "))
        if kind == .calories {
            return contains(#"\bkcal\b"#, in: label) && !contains(#"\bkj\b"#, in: label) ? "kcal" : nil
        }
        return contains(#"\bg\b"#, in: label) ? "g" : nil
    }

    private static func measurements(in row: [FoodLabelText], implicitUnit: String? = nil) -> [Measurement] {
        var result: [Measurement] = []
        guard !row.contains(where: { contains(#"[<>≤≥~≈−]|^[+-]$"#, in: $0.text) }) else { return [] }
        let expression = try! NSRegularExpression(pattern: #"^([0-9]+(?:[,.][0-9]+)?)\s*(kcal|kj|ml|g|г)?$"#)
        for (index, token) in row.enumerated() {
            let text = normalized(token.text).trimmingCharacters(in: CharacterSet(charactersIn: "()/"))
            guard let match = expression.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
                  let numberRange = Range(match.range(at: 1), in: text) else { continue }
            let number = String(text[numberRange])
            guard !contains(#"^[1-9][0-9]*[.,][0-9]{3}$"#, in: number),
                  let value = FoodProductBasis.parseNumber(number) else { continue }
            let previous = index > 0 ? row[index - 1] : nil
            if let previous, token.x - previous.x - previous.width < 0.04,
               contains(#"^[<>≤≥~≈−-]$|^[0-9]+$"#, in: previous.text) { continue }
            let next = index + 1 < row.count ? row[index + 1] : nil
            if let next, next.x - token.x - token.width < 0.04,
               contains(#"^[0-9]+$|^%$"#, in: normalized(next.text)) { continue }
            var unit = Range(match.range(at: 2), in: text).flatMap { canonicalUnit(String(text[$0])) }
            var endX = token.x + token.width
            if unit == nil, let next, next.x - endX < 0.04 {
                let nextText = normalized(next.text).trimmingCharacters(in: CharacterSet(charactersIn: "()/"))
                if let nextUnit = canonicalUnit(nextText) {
                    unit = nextUnit
                    endX = next.x + next.width
                } else if contains(#"[a-z%]"#, in: nextText) {
                    continue
                }
            }
            if let unit = unit ?? implicitUnit {
                result.append(Measurement(value: value, unit: unit, centerX: (token.x + endX) / 2,
                                          numberIsAmbiguous: token.numberIsAmbiguous == true))
            }
        }
        return result
    }

    private static func canonicalUnit(_ text: String) -> String? {
        let parts = text.split(separator: "/").map(String.init)
        if !parts.isEmpty, parts.allSatisfy({ $0 == "g" || $0 == "г" }) { return "g" }
        return ["ml", "kcal", "kj"].contains(text) ? text : nil
    }

    private static func findHeaders(_ rows: [[FoodLabelText]]) -> [Header] {
        let portions = rows.flatMap { $0 }.filter { contains(#"\bportion\b"#, in: normalized($0.text)) }
        var headers: [Header] = []
        for row in rows {
            let text = normalized(row.map(\.text).joined(separator: " "))
            guard !contains(#"netto|inhalt|zutaten"#, in: text) else { continue }
            for reading in measurements(in: row) where ["g", "ml"].contains(reading.unit) {
                let portion = portions.contains { abs($0.centerX - reading.centerX) < 0.13
                    && abs($0.centerY - (row.first?.centerY ?? 0)) < 0.08 }
                guard reading.value > 0, reading.value <= 1_000_000,
                      reading.value == 100 || portion || contains(#"\b(pro|je)\b"#, in: text) else { continue }
                let unit: FoodProductUnit = reading.unit == "g" ? .grams : .milliliters
                if let existing = headers.firstIndex(where: { abs($0.centerX - reading.centerX) < 0.045 }) {
                    if headers[existing].quantity != reading.value || headers[existing].unit != unit {
                        return []
                    }
                    headers[existing].numberIsAmbiguous = headers[existing].numberIsAmbiguous || reading.numberIsAmbiguous
                } else {
                    headers.append(Header(centerX: reading.centerX, quantity: reading.value, unit: unit,
                                          portion: portion, numberIsAmbiguous: reading.numberIsAmbiguous))
                }
            }
        }
        for portion in portions where !headers.contains(where: { abs($0.centerX - portion.centerX) < 0.13 }) {
            headers.append(Header(centerX: portion.centerX, quantity: nil, unit: nil, portion: true))
        }
        return headers.sorted { $0.centerX < $1.centerX }
    }
}
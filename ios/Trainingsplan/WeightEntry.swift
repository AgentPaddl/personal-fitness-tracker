import Foundation
import SwiftData

@Model
final class WeightEntry {
    var date: Date
    var weightKg: Double

    init(
        date: Date = Date(),
        weightKg: Double
    ) {
        self.date = date
        self.weightKg = weightKg
    }
}

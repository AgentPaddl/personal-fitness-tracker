import SwiftUI
import SwiftData

struct NutritionHistoryView: View {
    @Query(sort: \FoodEntry.date, order: .reverse)
    private var foodEntries: [FoodEntry]
    @State private var searchText = ""

    var body: some View {
        List {
            if groupedEntries.isEmpty {
                Text("Noch keine Ernährungshistorie")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(groupedEntries, id: \.date) { group in
                    NavigationLink {
                        NutritionDayDetailView(
                            date: group.date,
                            entries: group.entries
                        )
                    } label: {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(
                                group.date,
                                format: .dateTime
                                    .day()
                                    .month()
                                    .year()
                            )
                            .fontWeight(.semibold)

                            Text(
                                "\(group.totalCalories) kcal · \(group.totalProtein, specifier: "%.0f") g Protein"
                            )
                            .foregroundStyle(.secondary)

                            Text("\(group.entries.count) Einträge")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 3)
                    }
                }
            }
        }
        .navigationTitle("Historie")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(
            text: $searchText,
            prompt: "Lebensmittel oder Mahlzeit suchen"
        )
    }

    private var groupedEntries: [FoodEntryGroup] {
        let calendar = Calendar.current

        let filteredEntries: [FoodEntry]

        if searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            filteredEntries = foodEntries
        } else {
            let search = searchText.trimmingCharacters(in: .whitespacesAndNewlines)

            filteredEntries = foodEntries.filter { entry in
                entry.name.localizedCaseInsensitiveContains(search) ||
                (entry.notes?.localizedCaseInsensitiveContains(search) ?? false)
            }
        }

        let grouped = Dictionary(grouping: filteredEntries) { entry in
            calendar.startOfDay(for: entry.date)
        }

        return grouped
            .map { date, entries in
                FoodEntryGroup(
                    date: date,
                    entries: entries.sorted { $0.date > $1.date }
                )
            }
            .sorted { $0.date > $1.date }
    }
}

private struct FoodEntryGroup {
    let date: Date
    let entries: [FoodEntry]

    var totalCalories: Int {
        entries.reduce(0) { $0 + $1.calories }
    }

    var totalProtein: Double {
        entries.reduce(0) { $0 + $1.proteinGrams }
    }
}

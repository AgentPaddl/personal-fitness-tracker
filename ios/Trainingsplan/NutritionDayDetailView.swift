import SwiftUI
import SwiftData

struct NutritionDayDetailView: View {
    @Environment(\.modelContext) private var modelContext
    let date: Date
    let entries: [FoodEntry]
    
    @State private var selectedEntry: FoodEntry?
    @State private var selectedEntryToEdit: FoodEntry?
    
    var body: some View {
        List {
            Section("Tagessumme") {
                LabeledContent("Kalorien") {
                    Text("\(totalCalories) kcal")
                }
                
                LabeledContent("Protein") {
                    Text("\(totalProtein, specifier: "%.0f") g")
                }
                
                LabeledContent("Kohlenhydrate") {
                    Text("\(totalCarbs, specifier: "%.0f") g")
                }
                
                LabeledContent("Fett") {
                    Text("\(totalFat, specifier: "%.0f") g")
                }
            }
            
            Section("Einträge") {
                ForEach(entries) { entry in
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(entry.name)
                                .fontWeight(.semibold)
                            
                            Text(
                                "\(entry.calories) kcal · \(entry.proteinGrams, specifier: "%.0f") g Protein"
                            )
                            .foregroundStyle(.secondary)
                            
                            Text(
                                "\(entry.carbsGrams, specifier: "%.0f") g Carbs · \(entry.fatGrams, specifier: "%.0f") g Fett"
                            )
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        
                        Spacer()
                        
                        Button {
                            selectedEntry = entry
                        } label: {
                            Image(systemName: "plus.circle")
                                .font(.title3)
                        }
                        .buttonStyle(.borderless)
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        selectedEntryToEdit = entry
                    }
                }
            }
        }
        .navigationTitle(
            date.formatted(
                .dateTime.day().month().year()
            )
        )
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $selectedEntry) { entry in
            ReuseFoodEntryView(sourceEntry: entry)
        }
        .sheet(item: $selectedEntryToEdit) { entry in
            EditFoodEntryView(entry: entry)
        }
    }
    
    private var totalCalories: Int {
        entries.reduce(0) { $0 + $1.calories }
    }
    
    private var totalProtein: Double {
        entries.reduce(0) { $0 + $1.proteinGrams }
    }
    
    private var totalCarbs: Double {
        entries.reduce(0) { $0 + $1.carbsGrams }
    }
    
    private var totalFat: Double {
        entries.reduce(0) { $0 + $1.fatGrams }
    }
}

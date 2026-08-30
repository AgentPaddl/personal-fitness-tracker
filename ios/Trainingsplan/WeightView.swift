import SwiftUI
import SwiftData
import Charts

struct WeightView: View {
    @Environment(\.modelContext) private var modelContext
    
    @Query(sort: \WeightEntry.date, order: .reverse)
    private var weightEntries: [WeightEntry]
    
    @State private var weightText = ""
    @State private var saveError: String?
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Heute") {
                    if let todaysWeight {
                        Text("\(todaysWeight.weightKg, specifier: "%.1f") kg")
                            .font(.title2)
                            .fontWeight(.semibold)
                    } else {
                        Text("Noch kein Gewicht eingetragen")
                            .foregroundStyle(.secondary)
                    }
                }
                
                Section("Gewicht eintragen") {
                    TextField("z. B. 81,5", text: $weightText)
                        .keyboardType(.decimalPad)
                    
                    Button("Speichern") {
                        saveWeight()
                    }
                    .disabled(parsedWeight == nil)
                }
                
                Section("Verlauf") {
                    if weightEntries.count < 2 {
                        Text("Für den Verlauf werden mindestens zwei Gewichtseinträge benötigt.")
                            .foregroundStyle(.secondary)
                    } else {
                        Chart(chartEntries) { entry in
                            LineMark(
                                x: .value("Datum", entry.date),
                                y: .value("Gewicht", entry.weightKg)
                            )
                            
                            PointMark(
                                x: .value("Datum", entry.date),
                                y: .value("Gewicht", entry.weightKg)
                            )
                        }
                        .chartYScale(domain: chartYDomain)
                        .frame(height: 220)
                    }
                }
                
                Section("Historie") {
                    if weightEntries.isEmpty {
                        Text("Noch keine Einträge")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(weightEntries) { entry in
                            HStack {
                                Text(entry.date, format: .dateTime.day().month().year())
                                
                                Spacer()
                                
                                Text("\(entry.weightKg, specifier: "%.1f") kg")
                                    .fontWeight(.medium)
                            }
                        }
                        .onDelete(perform: deleteWeightEntries)
                    }
                }
            }
            .scrollDismissesKeyboard(.interactively)
            .dismissesKeyboardOnBackgroundTap()
            .navigationTitle("Gewicht")
            .alert("Fehler beim Speichern", isPresented: Binding(
                get: { saveError != nil },
                set: { if !$0 { saveError = nil } }
            )) {
                Button("OK") {
                    saveError = nil
                }
            } message: {
                Text(saveError ?? "Unbekannter Fehler")
            }
        }
    }
    
    private var chartEntries: [WeightEntry] {
        weightEntries.sorted { $0.date < $1.date }
    }
    
    private var todaysWeight: WeightEntry? {
        weightEntries.first {
            Calendar.current.isDateInToday($0.date)
        }
    }
    
    private var parsedWeight: Double? {
        let normalized = weightText.replacingOccurrences(of: ",", with: ".")
        return Double(normalized)
    }
    
    private func saveWeight() {
        guard let weight = parsedWeight else {
            return
        }
        
        if let todaysWeight {
            todaysWeight.weightKg = weight
            todaysWeight.date = Date()
        } else {
            let newEntry = WeightEntry(
                date: Date(),
                weightKg: weight
            )
            
            modelContext.insert(newEntry)
        }
        
        do {
            try modelContext.save()
            weightText = ""
        } catch {
            saveError = error.localizedDescription
            print("SwiftData Fehler:", error)
        }
    }
    private func deleteWeightEntries(at offsets: IndexSet) {
        for index in offsets {
            let entry = weightEntries[index]
            modelContext.delete(entry)
        }
        
        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Löschen des Gewichtseintrags:", error)
        }
    }
    private var chartYDomain: ClosedRange<Double> {
        let weights = chartEntries.map(\.weightKg)

        guard
            let minimum = weights.min(),
            let maximum = weights.max()
        else {
            return 70...90
        }

        if minimum == maximum {
            return (minimum - 1)...(maximum + 1)
        }

        return (minimum - 1)...(maximum + 1)
    }
}

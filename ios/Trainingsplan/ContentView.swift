import SwiftUI
import SwiftData

struct ContentView: View {
    @Environment(\.modelContext) private var modelContext
    @Query private var userGoals: [UserGoals]

    var body: some View {
        TabView {
            TodayView()
                .tabItem {
                    Label("Heute", systemImage: "house")
                }

            TrainingView()
                .tabItem {
                    Label("Training", systemImage: "dumbbell")
                }

            NutritionView()
                .tabItem {
                    Label("Ernährung", systemImage: "fork.knife")
                }

            WeightView()
                .tabItem {
                    Label("Gewicht", systemImage: "scalemass")
                }
        }
        .task {
            createGoalsIfNeeded()
        }
    }

    private func createGoalsIfNeeded() {
        guard userGoals.isEmpty else {
            return
        }

        let goals = UserGoals(
            calorieGoal: 2300,
            proteinGoalGrams: 150,
            weeklyActivityGoal: 3
        )

        modelContext.insert(goals)

        do {
            try modelContext.save()
        } catch {
            print("Fehler beim Anlegen der Ziele:", error)
        }
    }
}

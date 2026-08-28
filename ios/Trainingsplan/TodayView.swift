import SwiftUI
import SwiftData

struct TodayView: View {
    @Query(sort: \FoodEntry.date, order: .reverse)
    private var foodEntries: [FoodEntry]

    @Query
    private var userGoals: [UserGoals]

    @Query(sort: \WorkoutSession.startedAt, order: .reverse)
    private var workoutSessions: [WorkoutSession]

    @Query(sort: \Activity.date, order: .reverse)
    private var activities: [Activity]

    @State private var showGoals = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Ernährung") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(todayCalories) / \(calorieGoal) kcal")
                            .font(.title2)
                            .fontWeight(.semibold)

                        Text("\(todayProtein, specifier: "%.0f") / \(proteinGoal) g Protein")
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Bewegung") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(weeklyActivityCount) / \(weeklyActivityGoal) Aktivitäten diese Woche")
                            .font(.title3)
                            .fontWeight(.semibold)

                        Text("Aktivität: ca. \(weeklyActivityCalories) kcal")
                            .foregroundStyle(.secondary)

                        Text("Montag bis Sonntag")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Heute")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showGoals = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showGoals) {
                GoalsView()
            }
        }
    }

    private var todaysFoodEntries: [FoodEntry] {
        foodEntries.filter {
            Calendar.current.isDateInToday($0.date)
        }
    }

    private var todayCalories: Int {
        todaysFoodEntries.reduce(0) { $0 + $1.calories }
    }

    private var todayProtein: Double {
        todaysFoodEntries.reduce(0) { $0 + $1.proteinGrams }
    }

    private var calorieGoal: Int {
        userGoals.first?.calorieGoal ?? 2300
    }

    private var proteinGoal: Int {
        userGoals.first?.proteinGoalGrams ?? 150
    }

    private var weeklyActivityGoal: Int {
        userGoals.first?.weeklyActivityGoal ?? 3
    }

    private var weeklyActivityCount: Int {
        completedWorkoutSessionsThisWeek.count + activitiesThisWeek.count
    }

    private var weeklyActivityCalories: Int {
        let workoutCalories = completedWorkoutSessionsThisWeek.reduce(0) {
            $0 + ($1.estimatedCalories ?? 0)
        }

        let otherActivityCalories = activitiesThisWeek.reduce(0) {
            $0 + $1.estimatedCalories
        }

        return workoutCalories + otherActivityCalories
    }

    private var completedWorkoutSessionsThisWeek: [WorkoutSession] {
        workoutSessions.filter {
            $0.isCompleted && isDateInCurrentWeek($0.startedAt)
        }
    }

    private var activitiesThisWeek: [Activity] {
        activities.filter {
            isDateInCurrentWeek($0.date)
        }
    }

    private func isDateInCurrentWeek(_ date: Date) -> Bool {
        var calendar = Calendar(identifier: .iso8601)
        calendar.timeZone = .current

        guard let weekInterval = calendar.dateInterval(
            of: .weekOfYear,
            for: Date()
        ) else {
            return false
        }

        return weekInterval.contains(date)
    }
}

#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
ios_dir="${script_dir:h:h:h}"
temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/fitness-marker-tests.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT

cp "$script_dir/Package.swift" "$temporary_dir/Package.swift"
ln -s "$ios_dir/ActivitySummaryKit" "$temporary_dir/ActivitySummaryKit"
mkdir -p "$temporary_dir/Sources/MarkerAppPersistence" "$temporary_dir/Tests/MarkerAppPersistenceTests"

for source_name in Exercise WorkoutSession ExercisePerformance WorkoutSet Activity FoodEntry FoodPreset WeightEntry UserGoals BackupModels BackupService ExerciseWeightIncreaseMarkerPersistence WorkoutSessionDeletionService; do
    ln -s "$ios_dir/Trainingsplan/$source_name.swift" "$temporary_dir/Sources/MarkerAppPersistence/$source_name.swift"
done

ln -s "$script_dir/WeightIncreaseMarkerPersistenceTests.swift" "$temporary_dir/Tests/MarkerAppPersistenceTests/WeightIncreaseMarkerPersistenceTests.swift"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
swift test --package-path "$temporary_dir" "$@"
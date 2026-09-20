#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
ios_dir="${script_dir:h:h:h}"
temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/fitness-marker-tests.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT

cp "$script_dir/Package.swift" "$temporary_dir/Package.swift"
ln -s "$ios_dir/ActivitySummaryKit" "$temporary_dir/ActivitySummaryKit"
ln -s "$ios_dir/FoodAnalysisKit" "$temporary_dir/FoodAnalysisKit"
mkdir -p "$temporary_dir/Sources/MarkerAppPersistence" "$temporary_dir/Tests/MarkerAppPersistenceTests"

for source_name in Exercise WorkoutSession ExercisePerformance WorkoutSet Activity FoodEntry FoodPreset WeightEntry UserGoals BackupModels BackupService ExerciseWeightIncreaseMarkerPersistence WorkoutSessionDeletionService FoodProductPersistence; do
    ln -s "$ios_dir/Trainingsplan/$source_name.swift" "$temporary_dir/Sources/MarkerAppPersistence/$source_name.swift"
done

ln -s "$script_dir/WeightIncreaseMarkerPersistenceTests.swift" "$temporary_dir/Tests/MarkerAppPersistenceTests/WeightIncreaseMarkerPersistenceTests.swift"
ln -s "$script_dir/FoodProductPersistenceTests.swift" "$temporary_dir/Tests/MarkerAppPersistenceTests/FoodProductPersistenceTests.swift"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
mkdir -p "$temporary_dir/Sources/LegacyFoodStoreWriter"
legacy_sources=()
for source_name in Exercise WorkoutSession ExercisePerformance WorkoutSet Activity FoodEntry FoodPreset WeightEntry UserGoals; do
    legacy_sources+=("ios/Trainingsplan/$source_name.swift")
done
git -C "$ios_dir/.." archive 6eac77e "${legacy_sources[@]}" | tar -x -C "$temporary_dir/Sources/LegacyFoodStoreWriter" --strip-components=2
ln -s "$script_dir/LegacyFoodStoreWriter.swift" "$temporary_dir/Sources/LegacyFoodStoreWriter/LegacyFoodStoreWriter.swift"
export PFT_LEGACY_STORE_URL="$temporary_dir/legacy.store"
swift run --package-path "$temporary_dir" LegacyFoodStoreWriter "$PFT_LEGACY_STORE_URL"
swift test --package-path "$temporary_dir" "$@"
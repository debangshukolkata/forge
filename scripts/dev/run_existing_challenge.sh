#!/usr/bin/env bash
# One live challenge of the existing-codebase benchmark (TODO C22): prepare, run DebCraft, score.
#   scripts/dev/run_existing_challenge.sh E01 live1 [--template-python PATH]
# Run from the Forge repo in Git Bash. Spends Azure tokens. The run goes to C:\Work\ForgeRuns\existing\<run-name>\<id>.
set -u
ID="$1"; RUN="$2"; shift 2
PY=".venv/Scripts/python"
BENCH="$PY scripts/dev/run_existing_codebase_bench.py"
$BENCH prepare "$ID" --run-name "$RUN" "$@" > /dev/null || exit 1
DIR="C:\\Work\\ForgeRuns\\existing\\$RUN\\$ID"
LOWER=$(echo "$ID" | tr 'A-Z' 'a-z')
APP="."; case "$ID" in T*) APP="backend";; esac
export FORGE_HOME="$DIR\\home" FORGE_ENV_FILE="$(pwd -W)\\.env" PYTHONIOENCODING=utf-8
START=$(date +%s)
$PY -m forge.cli new --repo "$DIR\\repo" --project "existing-$LOWER" --workspace "$DIR\\workspace" --app-folder "$APP" || exit 1
$PY scripts/campaign/drive_forge.py "$DIR\\workspace" "$DIR\\prompt.txt" "$DIR\\run.json"
SECS=$(( $(date +%s) - START ))
$BENCH evaluate "$ID" --run-dir "$DIR" --seconds "$SECS" "$@"

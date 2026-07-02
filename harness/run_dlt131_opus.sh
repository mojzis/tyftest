#!/usr/bin/env bash
# Round 4 — OPUS, big task dlt-131, conditions A / D, 5 reps each.
#   A = no tyf            D = tyf + STRONG snippet
# Mirrors run_dlt120_opus.sh but pinned to dlt-131 and WALL=3600: the task is
# much bigger (8 gold files, ~1.2k-line reference fix), so the default 20-min
# wall would confound timeouts with convergence failures. Validity gate runs
# as pre-flight so the oracle is proven BEFORE any opus tokens are spent.
# Self-contained: run OUTSIDE the Claude session.
#   bash harness/run_dlt131_opus.sh           # REPS=5
#   REPS=8 bash harness/run_dlt131_opus.sh    # more if you want tighter CIs
# Results  -> results/round4-dlt131-opus.jsonl
# Read-out -> python3 harness/analyze.py results/round4-dlt131-opus.jsonl
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export REPO=dlt
export MODEL=opus
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-5}"
export WALL="${WALL:-3600}"
export OUT="$ROOT/results/round4-dlt131-opus.jsonl"
export RUN_TAG=round4-dlt131-opus
TASKS=(dlt-131)
read -ra CONDS <<< "$CONDS_OVERRIDE"

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]        || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/dlt.venv" ] || { echo "FATAL: venv missing — run harness/setup_repo.sh"; exit 1; }
# duckdb + the dlt-131 oracle-path deps (see docs/changes/2026-07-01-dlt-131-task.md)
"$ROOT/repos/dlt.venv/bin/python" -c "import duckdb, pyarrow, pandas, botocore, pydantic" 2>/dev/null \
    || { echo "FATAL: venv deps missing (duckdb/pyarrow/pandas/botocore/pydantic) — run harness/setup_repo.sh"; exit 1; }
for t in "${TASKS[@]}"; do
  for c in "${CONDS[@]}"; do
    [ -d "$ROOT/fixtures/$t/$c" ] || { echo "FATAL: fixtures/$t/$c missing — rebuild with CONDS_OVERRIDE='$CONDS_OVERRIDE' harness/build_conditions.sh $t"; exit 1; }
  done
done

# --- validity gate: prove the oracle before burning opus tokens ---
echo ">> validating oracle for ${TASKS[*]} ..."
for t in "${TASKS[@]}"; do
  bash "$ROOT/harness/validate.sh" "$t" || { echo "FATAL: $t failed the validity gate — do not run the round"; exit 1; }
done

N=$(( ${#TASKS[@]} * ${#CONDS[@]} * REPS ))
echo ">> OPUS dlt-131 round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=opus  wall=${WALL}s  output=$OUT"
echo ">> (dlt-131 is ~2-3x dlt-120; expect each opus cell \$1-2 and up to ${WALL}s)"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

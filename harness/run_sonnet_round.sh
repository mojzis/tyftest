#!/usr/bin/env bash
# Sonnet-5 round — mirror of run_opus_round.sh for cross-model comparison.
#   dlt-110, conditions A / D (C dropped), same reps.
#   A = no tyf            D = tyf + STRONG snippet
# Self-contained: run this OUTSIDE the Claude session whenever you want.
#   bash harness/run_sonnet_round.sh            # default REPS=10 (matches opus round)
#   REPS=15 bash harness/run_sonnet_round.sh
# Results -> results/round2-sonnet.jsonl  (separate from opus + pilot)
# Read-out -> python3 harness/analyze.py results/round2-sonnet.jsonl
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export MODEL=sonnet
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-10}"
export OUT="$ROOT/results/round2-sonnet.jsonl"
export RUN_TAG=round2-sonnet
TASKS=(dlt-110)
read -ra CONDS <<< "$CONDS_OVERRIDE"

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]            || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/dlt.venv" ]     || { echo "FATAL: venv missing — run harness/setup_repo.sh"; exit 1; }
"$ROOT/repos/dlt.venv/bin/python" -c "import duckdb" 2>/dev/null \
    || { echo "FATAL: duckdb missing in venv — run harness/setup_repo.sh"; exit 1; }
for t in "${TASKS[@]}"; do
  for c in "${CONDS[@]}"; do
    [ -d "$ROOT/fixtures/$t/$c" ] || { echo "FATAL: fixtures/$t/$c missing — rebuild with CONDS_OVERRIDE='$CONDS_OVERRIDE' harness/build_conditions.sh $t"; exit 1; }
  done
done

N=$(( ${#TASKS[@]} * ${#CONDS[@]} * REPS ))
echo ">> SONNET round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=sonnet  output=$OUT"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

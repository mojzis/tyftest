#!/usr/bin/env bash
# Round 3 — OPUS, new task dlt-120, conditions A / D, 5 reps each.
#   A = no tyf            D = tyf + STRONG snippet
# Mirrors run_opus_round.sh but pinned to dlt-120 and REPS=5, and runs the
# validity gate (validate.sh) as pre-flight so the oracle is proven BEFORE
# any opus tokens are spent. Self-contained: run OUTSIDE the Claude session.
#   bash harness/run_dlt120_opus.sh          # REPS=5
#   REPS=8 bash harness/run_dlt120_opus.sh   # more if you want tighter CIs
# Results  -> results/round3-dlt120-opus.jsonl
# Read-out -> python3 harness/analyze.py results/round3-dlt120-opus.jsonl
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export MODEL=opus
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-5}"
export OUT="$ROOT/results/round3-dlt120-opus.jsonl"
export RUN_TAG=round3-dlt120-opus
TASKS=(dlt-120)
read -ra CONDS <<< "$CONDS_OVERRIDE"

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]        || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/dlt.venv" ] || { echo "FATAL: venv missing — run harness/setup_repo.sh"; exit 1; }
"$ROOT/repos/dlt.venv/bin/python" -c "import duckdb" 2>/dev/null \
    || { echo "FATAL: duckdb missing in venv — run harness/setup_repo.sh"; exit 1; }
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
echo ">> OPUS dlt-120 round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=opus  output=$OUT"
echo ">> (each opus cell ~\$0.4-0.8 and a few min; ${N} cells total)"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

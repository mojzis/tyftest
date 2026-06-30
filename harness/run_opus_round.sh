#!/usr/bin/env bash
# Round 2 — OPUS only, harder tasks, conditions A / C / D.
#   A = no tyf            C = tyf + standard snippet      D = tyf + STRONG snippet
# Self-contained: run this OUTSIDE the Claude session whenever you want.
#   bash harness/run_opus_round.sh           # default REPS=3
#   REPS=5 bash harness/run_opus_round.sh    # more reps
# Results -> results/round2-opus.jsonl  (separate from the pilot's results.jsonl)
# Read-out -> python3 harness/analyze.py results/round2-opus.jsonl
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export MODEL=opus
export CONDS_OVERRIDE="A C D"
export REPS="${REPS:-3}"
export OUT="$ROOT/results/round2-opus.jsonl"
TASKS=(dlt-103 dlt-110)          # the validated harder tasks

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]            || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/dlt.venv" ]     || { echo "FATAL: venv missing — run harness/setup_repo.sh"; exit 1; }
"$ROOT/repos/dlt.venv/bin/python" -c "import duckdb" 2>/dev/null \
    || { echo "FATAL: duckdb missing in venv — run harness/setup_repo.sh"; exit 1; }
for t in "${TASKS[@]}"; do
  for c in A C D; do
    [ -d "$ROOT/fixtures/$t/$c" ] || { echo "FATAL: fixtures/$t/$c missing — rebuild with CONDS_OVERRIDE='A C D' harness/build_conditions.sh $t"; exit 1; }
  done
done

N=$(( ${#TASKS[@]} * 3 * REPS ))
echo ">> OPUS round: tasks=[${TASKS[*]}] conds=[A C D] reps=$REPS  => $N cells"
echo ">> model=opus  output=$OUT"
echo ">> (each opus cell ~\$0.4-0.8 and a few min; ${N} cells total)"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

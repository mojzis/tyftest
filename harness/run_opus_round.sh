#!/usr/bin/env bash
# Round 3 — OPUS only, harder tasks, conditions A / D (C dropped).
#   A = no tyf            D = tyf + STRONG snippet
# C is dropped: the standard snippet was unreliable (collapsed to A when tyf never
# fired). Spend the whole rep budget on the two clean arms. See
# docs/learnings/tyf-experiment-scaling.md §4–5.
# Self-contained: run this OUTSIDE the Claude session whenever you want.
#   bash harness/run_opus_round.sh            # default REPS=10 (minimum credible)
#   REPS=15 bash harness/run_opus_round.sh    # comfortable
# Results -> results/round2-opus.jsonl  (separate from the pilot's results.jsonl)
# Read-out -> python3 harness/analyze.py results/round2-opus.jsonl
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export MODEL=opus
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-10}"
export OUT="$ROOT/results/round2-opus.jsonl"
TASKS=(dlt-110)                  # dlt-103 dropped: its tyf arm never fired in round 2
                                 # (adherence screen). Only keep tasks where tyf fires.
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
echo ">> OPUS round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=opus  output=$OUT"
echo ">> (each opus cell ~\$0.4-0.8 and a few min; ${N} cells total)"
[[ " $CONDS_OVERRIDE " != *" C "* ]] && \
  echo ">> NOTE: C dropped, dlt-103 dropped (tyf never fired). Clean A/D on tyf-firing tasks only."

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

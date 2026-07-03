#!/usr/bin/env bash
# Round 5 — OPUS, task dlt-140 (incremental dedup-key precedence), A / D, 5 reps.
#   A = no tyf            D = tyf + STRONG snippet
# Mirrors run_dlt131_opus.sh. dlt-140's reference fix is smaller than dlt-131's
# (~100 mechanism lines in 4 files) but the navigation is subtle: the bug lives
# in the hints->incremental precedence spread across extract/resource.py,
# extract/incremental and the sql_database workaround. WALL=2400 sits between
# dlt-120 (1200) and dlt-131 (3600). Validity gate runs as pre-flight so the
# oracle is proven BEFORE any opus tokens are spent.
# Self-contained: run OUTSIDE the Claude session.
#   bash harness/run_dlt140_opus.sh           # REPS=5
#   REPS=8 bash harness/run_dlt140_opus.sh    # more if you want tighter CIs
# Each invocation writes its OWN timestamped results file (so an abort-and-rerun
# after a usage-limit stop never appends into an earlier attempt's rows) and a
# matching RUN_TAG, keeping session names unique across attempts.
# Results  -> results/round5-dlt140-opus.<start-stamp>.jsonl
# Read-out -> python3 harness/analyze.py results/round5-dlt140-opus.*.jsonl
#             (analyze.py concatenates all files given — merging is explicit)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export REPO=dlt
export MODEL=opus
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-5}"
export WALL="${WALL:-2400}"
STAMP="$(date +%Y%m%d-%H%M%S)"                 # script start time
export OUT="$ROOT/results/round5-dlt140-opus.$STAMP.jsonl"
export RUN_TAG="round5-dlt140-$STAMP"
TASKS=(dlt-140)
read -ra CONDS <<< "$CONDS_OVERRIDE"

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]        || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/dlt.venv" ] || { echo "FATAL: venv missing — run harness/setup_repo.sh"; exit 1; }
# oracle path needs pyarrow/pandas (arrow-table oracle variant) + duckdb
"$ROOT/repos/dlt.venv/bin/python" -c "import duckdb, pyarrow, pandas" 2>/dev/null \
    || { echo "FATAL: venv deps missing (duckdb/pyarrow/pandas) — run harness/setup_repo.sh"; exit 1; }
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
echo ">> OPUS dlt-140 round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=opus  wall=${WALL}s  output=$OUT"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

#!/usr/bin/env bash
# Round 6 — OPUS, litestar starter set, A / D, 5 reps.
#   A = no tyf            D = tyf + STRONG snippet
# First round on REPO=litestar (see docs/changes/2026-07-03-litestar-repo-and-tasks.md).
# Default task set = one per difficulty slot: litestar-4866 (easy, cookie
# precedence), litestar-4806 (medium, Annotated params reclassified as query),
# litestar-4687 (hard anchor, 4-file OpenAPI required-fields). Backups
# (4659/4815/4833) are validated and ready — override with TASKS_OVERRIDE.
# litestar's suite is fast (4655 offline tests in ~60s), so WALL=1800 covers
# even the hard task with slack. Validity gates run as pre-flight so the
# oracles are proven BEFORE any opus tokens are spent.
# Self-contained: run OUTSIDE the Claude session.
#   bash harness/run_litestar_opus.sh                                # REPS=5
#   REPS=8 bash harness/run_litestar_opus.sh                         # tighter CIs
#   TASKS_OVERRIDE="litestar-4687" bash harness/run_litestar_opus.sh # one task
# Each invocation writes its OWN timestamped results file (so an abort-and-rerun
# after a usage-limit stop never appends into an earlier attempt's rows) and a
# matching RUN_TAG, keeping session names unique across attempts.
# Results  -> results/round6-litestar-opus.<start-stamp>.jsonl
# Read-out -> python3 harness/analyze.py results/round6-litestar-opus.*.jsonl
#             (analyze.py concatenates all files given — merging is explicit)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"

# --- round config ---
export REPO=litestar
export MODEL=opus
export CONDS_OVERRIDE="A D"
export REPS="${REPS:-5}"
export WALL="${WALL:-1800}"
STAMP="$(date +%Y%m%d-%H%M%S)"                 # script start time
export OUT="$ROOT/results/round6-litestar-opus.$STAMP.jsonl"
export RUN_TAG="round6-litestar-$STAMP"
read -ra TASKS <<< "${TASKS_OVERRIDE:-litestar-4866 litestar-4806 litestar-4687}"
read -ra CONDS <<< "$CONDS_OVERRIDE"

# --- pre-flight (fail fast before spending tokens) ---
[ -x "$ROOT/bin/tyf" ]             || { echo "FATAL: bin/tyf missing — run harness/build_tyf.sh"; exit 1; }
[ -d "$ROOT/repos/litestar.venv" ] || { echo "FATAL: venv missing — run REPO=litestar harness/setup_repo.sh"; exit 1; }
# oracle paths need msgspec/attrs/pydantic (4687 spec-generation oracles) and
# annotated_types (4806 constraint oracle); all come from the locked dev+test groups
"$ROOT/repos/litestar.venv/bin/python" -c "import msgspec, attrs, pydantic, annotated_types" 2>/dev/null \
    || { echo "FATAL: venv deps missing (msgspec/attrs/pydantic/annotated_types) — run REPO=litestar harness/setup_repo.sh"; exit 1; }
for t in "${TASKS[@]}"; do
  for c in "${CONDS[@]}"; do
    [ -d "$ROOT/fixtures/$t/$c" ] || { echo "FATAL: fixtures/$t/$c missing — rebuild with CONDS_OVERRIDE='$CONDS_OVERRIDE' REPO=litestar harness/build_conditions.sh $t"; exit 1; }
  done
done

# --- validity gate: prove the oracles before burning opus tokens ---
echo ">> validating oracles for ${TASKS[*]} ..."
for t in "${TASKS[@]}"; do
  REPO=litestar bash "$ROOT/harness/validate.sh" "$t" || { echo "FATAL: $t failed the validity gate — do not run the round"; exit 1; }
done

N=$(( ${#TASKS[@]} * ${#CONDS[@]} * REPS ))
echo ">> OPUS litestar round: tasks=[${TASKS[*]}] conds=[$CONDS_OVERRIDE] reps=$REPS  => $N cells"
echo ">> model=opus  wall=${WALL}s  output=$OUT"

bash "$ROOT/harness/drive.sh" "${TASKS[@]}"

echo
echo "=================== READ-OUT ==================="
python3 "$ROOT/harness/analyze.py" "$OUT"

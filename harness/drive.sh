#!/usr/bin/env bash
# Orchestrate the pilot matrix: every (task × cond × rep) cell in RANDOMIZED
# order (avoids all-A-then-all-C drift / rate-limit artifacts). run -> score ->
# append one JSON row to results/results.jsonl.
#   drive.sh [task ...]      (default: all tasks in holdout/)
#   env: DRY=1, REPS=N, MODEL=...
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASKS=("$@"); [ ${#TASKS[@]} -eq 0 ] && mapfile -t TASKS < <(list_tasks)
[ ${#TASKS[@]} -eq 0 ] && { echo "no tasks in holdout/"; exit 1; }
OUT="$ROOT/results/results.jsonl"
mkdir -p "$ROOT/results"

# build the cell list, then shuffle
CELLS=()
for t in "${TASKS[@]}"; do for c in "${CONDS[@]}"; do
  for r in $(seq 1 "$REPS"); do CELLS+=("$t|$c|$r"); done
done; done
mapfile -t CELLS < <(printf '%s\n' "${CELLS[@]}" | shuf)

log "pilot: ${#CELLS[@]} cells  tasks=[${TASKS[*]}] conds=[${CONDS[*]}] reps=$REPS dry=${DRY:-0}"
i=0
for cell in "${CELLS[@]}"; do
  i=$((i+1)); IFS='|' read -r t c r <<< "$cell"
  log "[$i/${#CELLS[@]}] $t/$c/rep$r"
  bash "$ROOT/harness/run.sh" "$t" "$c" "$r" || { log "run failed, skipping score"; continue; }
  ROW="$(bash "$ROOT/harness/score.sh" "$t" "$c" "$r")"
  # verification gate: B/C must show >=1 successful tyf invocation
  GATE="$(python3 - "$ROW" "$c" <<'PY'
import json,sys
row=json.loads(sys.argv[1]); cond=sys.argv[2]
inv=row.get("tyf_invocations",0)
if cond in ("B","C") and inv==0: print("WARN_NO_TYF")
elif cond=="A" and inv>0:        print("WARN_TYF_IN_A")
else:                            print("ok")
PY
)"
  ROW="$(python3 -c 'import json,sys; r=json.loads(sys.argv[1]); r["gate"]=sys.argv[2]; print(json.dumps(r))' "$ROW" "$GATE")"
  echo "$ROW" >> "$OUT"
  [ "$GATE" != "ok" ] && log "  gate: $GATE"
done
log "wrote rows to $OUT  (total now: $(wc -l < "$OUT"))"

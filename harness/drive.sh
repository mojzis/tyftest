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
# Default: per-invocation file stamped with the driver's start time — separate
# attempts never append into each other; merge explicitly via
# `analyze.py results/adhoc.*.jsonl`. Round scripts set OUT (stamped) themselves.
OUT="${OUT:-$ROOT/results/adhoc.$(date +%Y%m%d-%H%M%S).jsonl}"
mkdir -p "$(dirname "$OUT")"

# Usage-limit backstop: if a cell dies because the Claude usage limit was hit,
# the run is invalid (not a convergence failure) and every following cell would
# hit the same wall. So we stop scoring it, sleep until the reset, then re-run
# the SAME cell completely fresh (run.sh wipes $RUN every invocation — nothing
# is resumed). Sized for unattended overnight runs: a 5h-window reset is at
# most ~5h away, so the default cap rides out any reset, even twice a night.
LIMIT_WAIT_MAX="${LIMIT_WAIT_MAX:-21600}"      # max seconds to sleep for a reset (6h)
LIMIT_FALLBACK_WAIT="${LIMIT_FALLBACK_WAIT:-3600}"  # sleep when limited but reset time unparseable
LIMIT_MAX_RETRIES="${LIMIT_MAX_RETRIES:-4}"    # per-cell cap on limit waits (overnight can hit 2)

# Transient-API backstop: a 529/Overloaded death — or worse, an in-place CLI
# auto-resume after one (2 result events in one transcript, per-segment stats;
# see round4 A-rep4) — makes the cell non-comparable. Discard and re-run fresh
# after a short backoff so every scored run had identical conditions.
OVERLOAD_MAX_RETRIES="${OVERLOAD_MAX_RETRIES:-3}"
OVERLOAD_BACKOFF="${OVERLOAD_BACKOFF:-180}"    # seconds; doubled each retry

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
  RUN="$ROOT/runs/$t/$c/rep$r"
  lim_tries=0; ovl_tries=0
  while :; do   # retry loop: re-enters only for a FRESH re-run (limit reset / overload backoff)
  log "[$i/${#CELLS[@]}] $t/$c/rep$r"
  bash "$ROOT/harness/run.sh" "$t" "$c" "$r" || { log "run failed, skipping score"; break; }

  # --- usage-limit backstop (before scoring: a limited run isn't a real result) ---
  if LIM="$(python3 "$ROOT/harness/limit_check.py" "$RUN/transcript.jsonl")"; then
    RESET="$(printf '%s' "$LIM" | jq -r '.resets_at // empty')"
    NOW="$(date +%s)"
    if [ -n "$RESET" ] && [ "$RESET" -gt "$NOW" ]; then WAIT=$((RESET - NOW + 30)); else WAIT="$LIMIT_FALLBACK_WAIT"; fi
    WHEN="$([ -n "$RESET" ] && date -d "@$RESET" '+%Y-%m-%d %H:%M:%S %Z' || echo unknown)"
    lim_tries=$((lim_tries+1))
    if [ "$lim_tries" -gt "$LIMIT_MAX_RETRIES" ]; then
      log "USAGE LIMIT hit on $t/$c/rep$r for the ${lim_tries}. time — giving up on the matrix."
      log "  Stopping at cell $i/${#CELLS[@]}. Re-run drive.sh after the reset to resume; $((${#CELLS[@]} - i + 1)) cell(s) remain."
      exit 3
    fi
    if [ "$WAIT" -le "$LIMIT_WAIT_MAX" ]; then
      log "USAGE LIMIT hit on $t/$c/rep$r — resets $WHEN; sleeping ${WAIT}s, then re-running the cell FRESH (attempt $((lim_tries+1)))"
      sleep "$WAIT"; continue    # run.sh wipes $RUN -> full fresh restart of the SAME cell
    fi
    log "USAGE LIMIT hit on $t/$c/rep$r — resets $WHEN (in ${WAIT}s), beyond LIMIT_WAIT_MAX=${LIMIT_WAIT_MAX}s."
    log "  Stopping at cell $i/${#CELLS[@]}. Re-run drive.sh after the reset to resume; $((${#CELLS[@]} - i + 1)) cell(s) remain."
    exit 3
  fi

  # --- transient-API backstop (529/Overloaded death or in-place auto-resume) ---
  if INT="$(python3 "$ROOT/harness/interruption_check.py" "$RUN/transcript.jsonl")"; then
    ovl_tries=$((ovl_tries+1))
    REASON="$(printf '%s' "$INT" | jq -r '.reason')"
    if [ "$ovl_tries" -gt "$OVERLOAD_MAX_RETRIES" ]; then
      log "API DISRUPTION on $t/$c/rep$r ($REASON) — retries exhausted (${OVERLOAD_MAX_RETRIES}); SKIPPING cell, re-run it later"
      break
    fi
    BACKOFF=$((OVERLOAD_BACKOFF * (1 << (ovl_tries - 1))))
    log "API DISRUPTION on $t/$c/rep$r ($REASON) — discarding run, sleeping ${BACKOFF}s, re-running the cell FRESH (attempt $((ovl_tries+1)))"
    sleep "$BACKOFF"; continue    # fresh restart: resumed/errored runs are not comparable
  fi

  ROW="$(bash "$ROOT/harness/score.sh" "$t" "$c" "$r")"
  # verification gate: B/C must show >=1 successful tyf invocation
  GATE="$(python3 - "$ROW" "$c" <<'PY'
import json,sys
row=json.loads(sys.argv[1]); cond=sys.argv[2]
inv=row.get("tyf_invocations",0)
# A: no tyf available -> any use is a leak. B: binary but no snippet -> non-use expected.
# C/D: snippet present -> non-use is an adherence miss worth flagging.
if cond=="A" and inv>0:          print("WARN_TYF_IN_A")
elif cond in ("C","D") and inv==0: print("WARN_NO_TYF")
else:                            print("ok")
PY
)"
  ROW="$(python3 -c 'import json,sys; r=json.loads(sys.argv[1]); r["gate"]=sys.argv[2]; print(json.dumps(r))' "$ROW" "$GATE")"
  echo "$ROW" >> "$OUT"
  [ "$GATE" != "ok" ] && log "  gate: $GATE"
  break   # cell done; leave the usage-limit retry loop
  done
done
log "wrote rows to $OUT  (total now: $(wc -l < "$OUT"))"

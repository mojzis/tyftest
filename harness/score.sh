#!/usr/bin/env bash
# Score one finished run against the held-out oracle (§7).
# Restores pristine tests/, applies oracle.patch, runs FAIL_TO_PASS + PASS_TO_PASS.
# Emits one JSON object (merged with transcript metrics) to stdout.
#   score.sh <task> <cond> <rep>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task}"; COND="${2:?cond}"; REP="${3:?rep}"
FIX="$ROOT/fixtures/$TASK/$COND"
RUN="$ROOT/runs/$TASK/$COND/rep$REP"
HOLD="$ROOT/holdout/$TASK"
[ -d "$RUN" ] || { echo "no run dir: $RUN" >&2; exit 2; }

# --- did the agent touch test SOURCE files? (flag, don't auto-fail) ---
# ignore __pycache__/*.pyc which pytest writes on every run (not tampering)
TEST_TAMPERED=false
if [ -n "$(diff -rq -x '__pycache__' -x '*.pyc' "$FIX/tests" "$RUN/tests" 2>&1)" ]; then
    TEST_TAMPERED=true
fi

# --- restore pristine tests, then apply the held-out verifier ---
rm -rf "$RUN/tests"
cp -a "$FIX/tests" "$RUN/tests"
ORACLE_APPLIED=true
git -C "$RUN" apply --whitespace=nowarn "$HOLD/oracle.patch" 2>"$RUN/oracle_apply.err" \
    || patch -p1 -d "$RUN" < "$HOLD/oracle.patch" 2>>"$RUN/oracle_apply.err" \
    || ORACLE_APPLIED=false

# ensure `import dlt` resolves from THIS run copy (agent's edits) before scoring
install_editable "$RUN"

run_pytest() {  # <id-file> -> prints "PASS"/"FAIL"/"SKIP(no ids)"
    local idfile="$1" ; local ids
    [ -s "$idfile" ] || { echo "SKIP"; return; }
    mapfile -t ids < "$idfile"
    if ( cd "$RUN" && PATH="$VENV/bin:$PATH" VIRTUAL_ENV="$VENV" \
            python -m pytest "${ids[@]}" -q -p no:cacheprovider \
            >"$RUN/pytest_$(basename "$idfile").log" 2>&1 ); then
        echo "PASS"; else echo "FAIL"; fi
}

if $ORACLE_APPLIED; then
    F2P="$(run_pytest "$HOLD/oracle_tests.txt")"
    P2P="$(run_pytest "$HOLD/pass_to_pass.txt")"
else
    F2P="ERROR_APPLY"; P2P="ERROR_APPLY"
fi

# oracle_pass = the held-out FAIL_TO_PASS now passes (the bug got fixed)
ORACLE_PASS=$([ "$F2P" = "PASS" ] && echo true || echo false)
REGRESS_OK=$([ "$P2P" = "PASS" ] || [ "$P2P" = "SKIP" ] && echo true || echo false)

# --- merge transcript metrics + scoring + factor columns into one row ---
METRICS="$(python3 "$ROOT/harness/parse_transcript.py" "$RUN/transcript.jsonl" 2>/dev/null || echo '{}')"
TY_STATUS="$(grep -E '^ty_status:' "$HOLD/manifest.yaml" 2>/dev/null | awk '{print $2}')"
EC="$(cat "$RUN/exit_code" 2>/dev/null || echo NA)"

[ -n "$METRICS" ] || METRICS='{}'
jq -nc \
  --argjson m "$METRICS" \
  --arg task "$TASK" --arg cond "$COND" --argjson rep "$REP" \
  --arg repo "$REPO_SLUG" --arg pin "$PIN_SHA" --arg ty "${TY_STATUS:-unknown}" \
  --arg ec "$EC" --arg sname "$(session_name "$TASK" "$COND" "$REP")" \
  --argjson oracle_pass "$ORACLE_PASS" --arg f2p "$F2P" --arg p2p "$P2P" \
  --argjson regression_ok "$REGRESS_OK" --argjson oracle_applied "$ORACLE_APPLIED" \
  --argjson test_tampered "$TEST_TAMPERED" \
  '$m + {task:$task, cond:$cond, rep:$rep, repo:$repo, pin_sha:$pin,
         session_name:$sname,
         ty_status:$ty, exit_code:$ec, oracle_pass:$oracle_pass,
         fail_to_pass:$f2p, pass_to_pass:$p2p, regression_ok:$regression_ok,
         oracle_applied:$oracle_applied, test_tampered:$test_tampered}'

#!/usr/bin/env bash
# Validity gate for a task (repo-prep §3 "Validity gate", §5 oracle correctness).
# Proves the oracle BEFORE the task counts:
#   pre-fix tree + oracle.patch                -> oracle test FAILS (bug present)
#   pre-fix tree + solution.patch + oracle     -> oracle test PASSES (fix is real)
#   pre-fix tree + pass_to_pass                -> PASSES (regression baseline green)
#   validate.sh <task_id>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task_id}"; HOLD="$ROOT/holdout/$TASK"; FIXA="$ROOT/fixtures/$TASK/A"
[ -d "$FIXA" ] || { echo "build fixtures first" >&2; exit 2; }
[ -s "$HOLD/oracle_tests.txt" ] || { echo "curate $HOLD/oracle_tests.txt first" >&2; exit 2; }
SCRATCH="$ROOT/runs/_validate/$TASK"
PYENV=(env PATH="$VENV/bin:$PATH" VIRTUAL_ENV="$VENV")

pytest_ids() {  # <dir> <id-file>
    local d="$1" f="$2"; mapfile -t ids < "$f"
    ( cd "$d" && "${PYENV[@]}" python -m pytest "${ids[@]}" -q -p no:cacheprovider )
}

fresh() { rm -rf "$SCRATCH"; mkdir -p "$(dirname "$SCRATCH")"; cp -a "$FIXA" "$SCRATCH"; }

echo "== gate 1: pre-fix + oracle  -> expect FAIL =="
fresh; git -C "$SCRATCH" apply "$HOLD/oracle.patch"
if pytest_ids "$SCRATCH" "$HOLD/oracle_tests.txt" >/dev/null 2>&1; then
    echo "  UNEXPECTED PASS — bug not reproduced. TASK INVALID."; G1=bad; else
    echo "  ok: oracle fails on buggy tree"; G1=ok; fi

echo "== gate 2: pre-fix + solution + oracle  -> expect PASS =="
fresh; git -C "$SCRATCH" apply "$HOLD/solution.patch"; git -C "$SCRATCH" apply "$HOLD/oracle.patch"
if pytest_ids "$SCRATCH" "$HOLD/oracle_tests.txt" >/dev/null 2>&1; then
    echo "  ok: oracle passes once fixed"; G2=ok; else
    echo "  UNEXPECTED FAIL — oracle/solution mismatch. TASK INVALID."; G2=bad; fi

echo "== gate 3: pre-fix + pass_to_pass  -> expect PASS =="
if [ -s "$HOLD/pass_to_pass.txt" ]; then
    fresh
    if pytest_ids "$SCRATCH" "$HOLD/pass_to_pass.txt" >/dev/null 2>&1; then
        echo "  ok: regression baseline green"; G3=ok; else
        echo "  WARN: pass_to_pass not green on pristine — trim the list"; G3=warn; fi
else echo "  (no pass_to_pass set)"; G3=skip; fi

echo "---"; echo "RESULT $TASK: gate1=$G1 gate2=$G2 gate3=$G3"
[ "$G1" = ok ] && [ "$G2" = ok ] && echo "VALID" || { echo "INVALID — discard or fix"; exit 1; }

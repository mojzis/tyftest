#!/usr/bin/env bash
# Construct one task fixture from a reverted-PR bugfix commit (repo-prep §3).
# Writes the held-out record into holdout/<task>/ and the pre-fix tree into
# repos/stage-<task>/ (input to launder.sh).
#   make_task.sh <task_id> <FIX_SHA>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task_id e.g. dlt-001}"; FIX="${2:?FIX sha}"
HOLD="$ROOT/holdout/$TASK"; STAGE="$ROOT/repos/stage-$TASK"
mkdir -p "$HOLD"
cd "$REPO_SRC"

# split source vs test files touched by FIX
ALL="$(git show "$FIX" --name-only --pretty=format: | grep '\.py$' || true)"
SRC="$(echo "$ALL" | grep -vE '/tests?/|(^|/)test_|conftest' || true)"
TST="$(echo "$ALL" | grep -E  '/tests?/|(^|/)test_'           || true)"
[ -n "$SRC" ] || { echo "no source files in $FIX" >&2; exit 1; }
[ -n "$TST" ] || { echo "no test files in $FIX"   >&2; exit 1; }

log "SRC files:"; echo "$SRC" | sed 's/^/   /'
log "TST files:"; echo "$TST" | sed 's/^/   /'

# solution = source diff (NEVER applied to agent tree; gold file set only)
git diff "$FIX~1" "$FIX" -- $SRC > "$HOLD/solution.patch"
# oracle = test diff (applied only at scoring)
git diff "$FIX~1" "$FIX" -- $TST > "$HOLD/oracle.patch"
echo "$SRC" > "$HOLD/gold_files.txt"

# suggested oracle test ids (added/modified top-level test funcs) — REVIEW THESE
{ git diff "$FIX~1" "$FIX" -- $TST | grep -E '^\+\s*def (test_|.*test)' \
    | sed -E 's/^\+\s*def ([a-zA-Z0-9_]+).*/\1/' | sort -u ; } > "$HOLD/_oracle_funcs.txt" || true
log "suggested test functions (curate into oracle_tests.txt as path::name):"
cat "$HOLD/_oracle_funcs.txt" | sed 's/^/   /'
# seed the id files for manual curation
[ -f "$HOLD/oracle_tests.txt" ] || : > "$HOLD/oracle_tests.txt"
[ -f "$HOLD/pass_to_pass.txt" ] || : > "$HOLD/pass_to_pass.txt"

# pre-fix tree (what the agent starts from) -> STAGE, git-free
rm -rf "$STAGE"; mkdir -p "$STAGE"
git archive "$FIX~1" | tar -x -C "$STAGE"
log "pre-fix tree extracted to $STAGE"

# partial manifest (completed by launder + curation)
cat > "$HOLD/manifest.yaml" <<YAML
task_id:      $TASK
repo:         $REPO_SLUG
pin_sha:      $PIN_SHA
fix_sha:      $FIX
prompt_file:  holdout/$TASK/prompt.txt
gold_files:   $(echo "$SRC" | paste -sd, -)
oracle_patch: holdout/$TASK/oracle.patch
oracle_tests: []      # curate holdout/$TASK/oracle_tests.txt   (FAIL_TO_PASS)
pass_to_pass: []      # curate holdout/$TASK/pass_to_pass.txt
ty_status:    unset   # set by launder.sh
YAML
log "wrote holdout/$TASK/ — now: write prompt.txt, curate oracle_tests.txt, run launder.sh + build_conditions.sh, then validate.sh"

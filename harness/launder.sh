#!/usr/bin/env bash
# De-leak the staged pre-fix tree and normalize its agent file (repo-prep §4).
# Operates in-place on repos/stage-<task>/. Run AFTER make_task.sh.
#   launder.sh <task_id>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task_id}"; STAGE="$ROOT/repos/stage-$TASK"; HOLD="$ROOT/holdout/$TASK"
[ -d "$STAGE" ] || { echo "no stage: $STAGE (run make_task.sh first)" >&2; exit 2; }
cd "$STAGE"

# 1. report potential leaks for manual review (don't auto-delete source logic)
log "leak scan (review — neutralize anything that reveals the fix):"
grep -rInE 'fixe?[ds]|work[- ]?around|regression|issue ?#?[0-9]+|#[0-9]{3,}' \
    --include='*.py' "$REPO_CORE" tests 2>/dev/null | head -40 | sed 's/^/   /' || true
log "changelog/news files present (consider trimming the relevant entry):"
find . -maxdepth 3 -iregex '.*\(changelog\|history\|news\|release\).*' 2>/dev/null | sed 's/^/   /' || true

# 2. normalize the repo's own agent file -> ONE neutral CLAUDE.md (controls a confound)
find . -maxdepth 2 \( -iname 'CLAUDE.md' -o -iname 'AGENTS.md' -o -iname '.cursorrules' \) -delete 2>/dev/null || true
cp "$NEUTRAL_CLAUDE" "$STAGE/CLAUDE.md"
log "installed neutral CLAUDE.md"

# 3. launder git: single neutral fixed-date commit (kills `git log` mining)
rm -rf .git
git init -q
git config gc.auto 0          # prevent background repack racing the fixture copy
git add -A
GIT_AUTHOR_DATE="2025-09-01T12:00:00" GIT_COMMITTER_DATE="2025-09-01T12:00:00" \
  git -c user.name=dev -c user.email=dev@example.com commit -qm "Initial import"
log "git laundered -> single 'Initial import' commit"

# 4. pre-flight ty on the gold source files -> tyf-working | tyf-degraded.
# MUST point ty at the project venv (VIRTUAL_ENV) or it falls back to an unrelated
# environment and reports bogus unresolved-imports. Platform-optional modules that
# legitimately aren't installed on Linux are NOT a degradation (tyf still resolves
# first-party symbols) — filter them out.
OPTIONAL_MODS='win_precise_time|winreg|_winapi|pwd|grp'
TY_STATUS="working"
if [ -s "$HOLD/gold_files.txt" ]; then
    VIRTUAL_ENV="$VENV" PATH="$VENV/bin:$PATH" "$VENV/bin/ty" check $(cat "$HOLD/gold_files.txt") \
        > "$HOLD/ty_check.log" 2>&1 || true
    # real degradation = an unresolved import that is NOT a known platform-optional module
    if grep -E 'unresolved-import' "$HOLD/ty_check.log" \
         | grep -ivE "$OPTIONAL_MODS" | grep -q 'unresolved-import'; then
        TY_STATUS="degraded"
    fi
fi
sed -i "s/^ty_status:.*/ty_status:    $TY_STATUS/" "$HOLD/manifest.yaml"
log "ty_status = $TY_STATUS (see $HOLD/ty_check.log)"
log "launder done. Review leaks above, then run build_conditions.sh $TASK"

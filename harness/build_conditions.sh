#!/usr/bin/env bash
# Snapshot the laundered stage tree into the three condition fixtures (repo-prep
# §5). A/B share an identical neutral CLAUDE.md; C = that + the tyf snippet.
#   build_conditions.sh <task_id>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task_id}"; STAGE="$ROOT/repos/stage-$TASK"
[ -d "$STAGE" ] || { echo "no stage: $STAGE" >&2; exit 2; }
[ -f "$SNIPPET_SRC" ] || { echo "no snippet: $SNIPPET_SRC" >&2; exit 2; }

for c in "${CONDS[@]}"; do
    FIX="$ROOT/fixtures/$TASK/$c"
    rm -rf "$FIX"; mkdir -p "$FIX"
    # materialize the laundered tree atomically (no live .git copy race)
    git -C "$STAGE" archive HEAD | tar -x -C "$FIX"
    case "$c" in
        A|B) : ;;                                   # neutral CLAUDE.md already in place
        C)   { printf '\n'; cat "$SNIPPET_SRC"; } >> "$FIX/CLAUDE.md" ;;  # + snippet
    esac
    # fresh deterministic single-commit git (absence of git is itself a tell)
    ( cd "$FIX" && git init -q && git config gc.auto 0 && git add -A \
      && GIT_AUTHOR_DATE="2025-09-01T12:00:00" GIT_COMMITTER_DATE="2025-09-01T12:00:00" \
         git -c user.name=dev -c user.email=dev@example.com commit -qm "Initial import" )
done
# sanity: C's CLAUDE.md must differ from A/B by exactly the snippet
if diff -q "$ROOT/fixtures/$TASK/A/CLAUDE.md" "$ROOT/fixtures/$TASK/B/CLAUDE.md" >/dev/null \
   && ! diff -q "$ROOT/fixtures/$TASK/A/CLAUDE.md" "$ROOT/fixtures/$TASK/C/CLAUDE.md" >/dev/null; then
    log "fixtures built: A==B CLAUDE.md, C has snippet appended"
else
    log "WARN: CLAUDE.md condition integrity check unexpected — inspect fixtures/$TASK/*/CLAUDE.md"
fi
log "fixtures/$TASK/{A,B,C} ready"

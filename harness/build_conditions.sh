#!/usr/bin/env bash
# Snapshot the laundered stage tree into the condition fixtures (repo-prep §5).
# A/B share the repo's REAL CLAUDE.md verbatim (the within-project baseline);
# C/D = that same file + the standard/strong tyf snippet appended.
#   build_conditions.sh <task_id>
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task_id}"; STAGE="$ROOT/repos/stage-$TASK"
[ -d "$STAGE" ] || { echo "no stage: $STAGE" >&2; exit 2; }

for c in "${CONDS[@]}"; do
    FIX="$ROOT/fixtures/$TASK/$c"
    rm -rf "$FIX"; mkdir -p "$FIX"
    # materialize the laundered tree atomically (no live .git copy race)
    git -C "$STAGE" archive HEAD | tar -x -C "$FIX"
    case "$c" in
        A|B) : ;;                                                        # neutral CLAUDE.md only
        C)   [ -f "$SNIPPET_SRC" ]    || { echo "no snippet $SNIPPET_SRC" >&2; exit 2; }
             { printf '\n'; cat "$SNIPPET_SRC"; }    >> "$FIX/CLAUDE.md" ;;  # + standard snippet
        D)   [ -f "$SNIPPET_STRONG" ] || { echo "no snippet $SNIPPET_STRONG" >&2; exit 2; }
             { printf '\n'; cat "$SNIPPET_STRONG"; } >> "$FIX/CLAUDE.md" ;;  # + strong snippet
        *)   echo "unknown condition: $c" >&2; exit 2 ;;
    esac
    # fresh deterministic single-commit git (absence of git is itself a tell)
    ( cd "$FIX" && git init -q && git config gc.auto 0 && git add -A \
      && GIT_AUTHOR_DATE="2025-09-01T12:00:00" GIT_COMMITTER_DATE="2025-09-01T12:00:00" \
         git -c user.name=dev -c user.email=dev@example.com commit -qm "Initial import" )
done
# integrity: snippet conditions must differ from A by exactly their snippet; A==B
A="$ROOT/fixtures/$TASK/A"
for c in "${CONDS[@]}"; do
    f="$ROOT/fixtures/$TASK/$c/CLAUDE.md"
    case "$c" in
      A) : ;;
      B) diff -q "$A/CLAUDE.md" "$f" >/dev/null && log "  $c: CLAUDE.md == A (ok)" || log "  WARN $c != A" ;;
      C|D) ! diff -q "$A/CLAUDE.md" "$f" >/dev/null && log "  $c: snippet appended (ok)" || log "  WARN $c has no snippet" ;;
    esac
done
log "fixtures/$TASK/{${CONDS[*]}} ready"

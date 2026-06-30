#!/usr/bin/env bash
# List candidate bugfix commits that touched BOTH a source file and a test file
# in the core package (repo-prep §2). Inspect output, pick ~3 good ones.
#   mine_tasks.sh [N]     (default 40 most-recent candidates scanned)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_SRC"
N="${1:-40}"

printf '%-12s  %-4s %-4s  %s\n' "COMMIT" "SRC" "TST" "SUBJECT"
git log --oneline --no-merges -n 300 -- "$REPO_CORE" \
  | grep -iE 'fix|bug|regression|incorrect|broken|raise|error|crash' \
  | head -n "$N" | while read -r sha rest; do
    files="$(git show "$sha" --name-only --pretty=format: | grep '\.py$' || true)"
    nsrc="$(echo "$files" | grep -vE '/tests?/|(^|/)test_|conftest' | grep -c . || true)"
    ntst="$(echo "$files" | grep -E  '/tests?/|(^|/)test_'           | grep -c . || true)"
    # keep only commits that touched >=1 source AND >=1 test
    if [ "${nsrc:-0}" -ge 1 ] && [ "${ntst:-0}" -ge 1 ]; then
        printf '%-12s  %-4s %-4s  %s\n' "$sha" "$nsrc" "$ntst" "$rest"
    fi
done
echo
echo "# Pick commits with a SMALL focused source change + a clear test."
echo "# Inspect one with:  git -C $REPO_SRC show <sha> --stat"

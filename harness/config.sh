#!/usr/bin/env bash
# Shared config sourced by every harness script. Edit knobs here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

# --- tool under test ---
TYF_BIN="$ROOT/bin/tyf"

# --- target repo (the pilot) ---
REPO_SLUG="dlt-hub/dlt"
REPO_URL="https://github.com/dlt-hub/dlt"
REPO_SRC="$ROOT/repos/dlt-src"          # pristine pinned clone
VENV="$ROOT/repos/dlt.venv"             # OUT-OF-TREE venv (survives per-run reset)
REPO_CORE="dlt"                         # core package dir for task mining
PIN_FILE="$ROOT/repos/dlt.pin"          # written by setup_repo.sh
[ -f "$PIN_FILE" ] && PIN_SHA="$(cat "$PIN_FILE")" || PIN_SHA="UNSET"

# --- experiment matrix (pilot) ---
CONDS=(A B C)
REPS=3
# TASKS is discovered from holdout/ at run time:
list_tasks() { ls "$ROOT/holdout" 2>/dev/null | sort; }

# --- run discipline ---
MODEL="${MODEL:-sonnet}"                 # pinned; actual id recorded per row
# NO visible budget/turn cap on the agent — a cap induces "token fear" and
# degrades behavior, biasing the experiment. The ONLY backstop is an invisible
# wall-clock `timeout` the agent never sees; a timeout kill = failure-to-converge.
WALL="${WALL:-1200}"                      # hard wall-clock backstop (seconds)
# claude flags held CONSTANT across all conditions:
CLAUDE_COMMON=(--output-format stream-json --verbose
               --dangerously-skip-permissions
               --setting-sources project)  # ignore user/global CLAUDE.md+settings

# C-condition snippet (verbatim from the tool repo @ pinned SHA)
SNIPPET_SRC="$HOME/git/ty-find/docs/shared/claude-snippet.md"

# neutral CLAUDE.md handed to every condition (A/B; C = this + snippet)
NEUTRAL_CLAUDE="$ROOT/harness/neutral_claude.md"

log() { printf '>> %s\n' "$*" >&2; }

# Make `import dlt` (and its metadata, read at import time) resolve from a
# specific working copy, NOT from the pristine clone — so the agent's edits are
# what runs/tests. Editable install writes a .pth to the shared venv; pilot runs
# are sequential so the single .pth is always the dir we're about to use.
install_editable() {  # <dir>
    VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" \
        -e "$1" --no-deps -q 2>/dev/null \
    || PATH="$VENV/bin:$PATH" pip install -e "$1" --no-deps -q 2>/dev/null || true
}

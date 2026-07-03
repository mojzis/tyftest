#!/usr/bin/env bash
# Shared config sourced by every harness script. Edit knobs here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

# --- tool under test ---
TYF_BIN="$ROOT/bin/tyf"

# --- target repo (selectable) ---
# Pick the repo to operate on with REPO=dlt|feast|litestar|dagster (default dlt, the pilot).
# Per-repo §0 facts (core dir, offline deps, test stack) live in the case block.
# See docs/tyf-experiment-task-mining.md §0.
REPO="${REPO:-dlt}"
# upin() = uv pip into the out-of-tree venv. install_stack() (per repo) owns the
# whole post-venv install so each repo's pinning mechanism stays self-contained.
upin() { VIRTUAL_ENV="$VENV" uv pip "$@" --python "$VENV/bin/python"; }
case "$REPO" in
  dlt)
    REPO_SLUG="dlt-hub/dlt"
    REPO_URL="https://github.com/dlt-hub/dlt"
    REPO_CORE="dlt"                     # core package dir for task mining
    REPO_PKG="dlt"                      # import name (uninstalled so cwd source wins)
    PY_VER=""                           # default interpreter is fine
    OFFLINE_DEPS="duckdb hexbytes pyarrow pandas botocore pydantic"
                                        # embedded/in-memory libs that still count as offline
                                        # (hexbytes: hard import in dlt<1.28 trees, e.g. dlt-120's pre-fix tree)
                                        # (pyarrow/pandas/botocore: module-level imports on dlt-131's
                                        #  oracle path in tests/load/pipeline; pydantic: optional dlt dep,
                                        #  without it ty flags a false unresolved-import in schema/typing.py)
    install_stack() {
        upin install ty $OFFLINE_DEPS >/dev/null
        # editable WITH deps, then install the PINNED test stack (PEP-735 dev group;
        # pytest<8 — latest breaks pytest-cases), then drop the pkg so cwd wins.
        upin install -e "$REPO_SRC" || log "WARN: editable install failed"
        ( cd "$REPO_SRC" && upin install --group dev >/dev/null 2>&1 ) \
            || log "WARN: '--group dev' failed — inspect dependency-groups"
        upin uninstall "$REPO_PKG" >/dev/null 2>&1 || true
    }
    ;;
  feast)
    REPO_SLUG="feast-dev/feast"
    REPO_URL="https://github.com/feast-dev/feast"
    REPO_CORE="sdk/python/feast"        # core package dir for task mining
    REPO_PKG="feast"                    # import name
    PY_VER="3.12"                       # pinned reqs cap at 3.12; system py3.14 is too new
    OFFLINE_DEPS="duckdb"               # local provider's embedded offline store
    # offline-testable = `local` provider (sqlite online + file/duckdb offline +
    # local registry); offline test entry point = sdk/python/tests/unit (integration
    # tests gated behind the --integration pytest flag). Pinned test stack = the
    # hash-locked CI requirements; `uv pip sync` REPLACES the env, so it runs FIRST,
    # then ty/duckdb + editable feast (--no-deps) are layered back on top.
    install_stack() {
        ( cd "$REPO_SRC" && upin sync --require-hashes \
            "sdk/python/requirements/py$PY_VER-ci-requirements.txt" >/dev/null 2>&1 ) \
            || log "WARN: pip sync of pinned CI requirements failed"
        upin install ty $OFFLINE_DEPS >/dev/null
        ( cd "$REPO_SRC" && upin install --no-deps -e . >/dev/null 2>&1 ) \
            || log "WARN: editable feast install failed"
        upin uninstall "$REPO_PKG" >/dev/null 2>&1 || true
    }
    ;;
  litestar)
    REPO_SLUG="litestar-org/litestar"
    REPO_URL="https://github.com/litestar-org/litestar"
    REPO_CORE="litestar"                # core package dir for task mining
    REPO_PKG="litestar"                 # import name
    PY_VER="3.12"                       # lock supports 3.11+; 3.12 for wheel safety
    OFFLINE_DEPS=""                     # offline = tests/unit, EXCEPT redis-parametrized
                                        # cases (docker_service_fixtures) and
                                        # tests/unit/test_testing/test_sub_client/ (spawns a
                                        # real uvicorn subprocess). 4655 tests pass in ~60s.
    # Pinned test stack = the repo's own uv.lock: `uv sync` with the dev+test
    # dependency groups, targeted at the out-of-tree venv via UV_PROJECT_ENVIRONMENT.
    # sync installs litestar editable from $REPO_SRC; drop it so cwd wins.
    install_stack() {
        ( cd "$REPO_SRC" && UV_PROJECT_ENVIRONMENT="$VENV" \
            uv sync --locked --group dev --group test >/dev/null 2>&1 ) \
            || log "WARN: uv sync of locked dev+test groups failed"
        upin install ty $OFFLINE_DEPS >/dev/null
        upin uninstall "$REPO_PKG" >/dev/null 2>&1 || true
    }
    ;;
  dagster)
    REPO_SLUG="dagster-io/dagster"
    REPO_URL="https://github.com/dagster-io/dagster"
    REPO_CORE="python_modules/dagster/dagster/_core"
    REPO_PKG="dagster"
    PY_VER=""
    OFFLINE_DEPS=""                     # in-process executor + ephemeral instance; no extra
    install_stack() {
        upin install ty $OFFLINE_DEPS >/dev/null
        upin install -e "$REPO_SRC[test]" || log "WARN: editable install failed"
        upin uninstall "$REPO_PKG" >/dev/null 2>&1 || true
    }
    ;;
  *) echo "unknown REPO=$REPO (want dlt|feast|litestar|dagster)" >&2; exit 1 ;;
esac
REPO_SRC="$ROOT/repos/$REPO-src"        # pristine pinned clone
VENV="$ROOT/repos/$REPO.venv"           # OUT-OF-TREE venv (survives per-run reset)
PIN_FILE="$ROOT/repos/$REPO.pin"        # written by setup_repo.sh
[ -f "$PIN_FILE" ] && PIN_SHA="$(cat "$PIN_FILE")" || PIN_SHA="UNSET"

# --- experiment matrix ---
# Conditions are env-overridable: e.g. CONDS_OVERRIDE="A C D" for the opus round.
#   A = no tyf, no snippet            (control)
#   B = tyf present, no snippet       (binary-only; dropped after pilot — never used tyf)
#   C = tyf + standard snippet        (claude-snippet.md)
#   D = tyf + STRONG snippet          (claude-snippet-strong.md)
read -r -a CONDS <<< "${CONDS_OVERRIDE:-A B C}"
REPS="${REPS:-3}"
# Floor-abort backstop (opt-in, off by default). After a small pilot of rep(s)
# from EVERY condition, if a task fails in ALL of them (no arm passed -> the cell
# can't discriminate A vs D), skip its remaining reps to save spend. Requires
# failure across BOTH arms, so an asymmetric "A fails, D passes" result survives,
# and it NEVER triggers on a pass. FLOOR_PILOT_PER_COND = reps per condition in
# the pilot (1 -> 2-run A/D pilot; 2 -> 4-run, fewer false aborts on borderline
# tasks). Aborted cells write no row; the pilot rows land in the same OUT file.
FLOOR_ABORT="${FLOOR_ABORT:-0}"
FLOOR_PILOT_PER_COND="${FLOOR_PILOT_PER_COND:-1}"
# TASKS is discovered from holdout/ at run time:
list_tasks() { ls "$ROOT/holdout" 2>/dev/null | sort; }

# --- run discipline ---
MODEL="${MODEL:-sonnet}"                 # pinned; actual id recorded per row
# Session naming: joins introspect/session searches to result rows. RUN_TAG
# disambiguates rounds (set it in run_*.sh round scripts); name is display-only
# metadata, NOT injected into model context, so no condition leak.
RUN_TAG="${RUN_TAG:-adhoc}"
session_name() { printf '%s-%s-%s-rep%s' "$RUN_TAG" "$1" "$2" "$3"; }  # <task> <cond> <rep>
# NO visible budget/turn cap on the agent — a cap induces "token fear" and
# degrades behavior, biasing the experiment. The ONLY backstop is an invisible
# wall-clock `timeout` the agent never sees; a timeout kill = failure-to-converge.
WALL="${WALL:-1200}"                      # hard wall-clock backstop (seconds)
# claude flags held CONSTANT across all conditions:
CLAUDE_COMMON=(--output-format stream-json --verbose
               --dangerously-skip-permissions
               --setting-sources project)  # ignore user/global CLAUDE.md+settings

# condition snippets
SNIPPET_SRC="$HOME/git/ty-find/docs/shared/claude-snippet.md"   # C: standard (verbatim from tool repo @ pinned SHA)
SNIPPET_STRONG="$ROOT/harness/claude-snippet-strong.md"         # D: stronger wording to drive adoption

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

#!/usr/bin/env bash
# Clone + pin the target repo and build an OUT-OF-TREE venv so per-run resets
# don't trigger a reinstall (repo-prep §1). Idempotent-ish.
#   setup_repo.sh [PIN_SHA]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

PIN="${1:-}"
mkdir -p "$ROOT/repos"

if [ ! -d "$REPO_SRC/.git" ]; then
    log "cloning $REPO_URL (full history — needed for task mining)"
    git clone "$REPO_URL" "$REPO_SRC"
fi

cd "$REPO_SRC"
git fetch --quiet origin || true
if [ -n "$PIN" ]; then git checkout --quiet "$PIN"; fi
SHA="$(git rev-parse --short HEAD)"
echo "$SHA" > "$PIN_FILE"
log "pinned $REPO_SLUG @ $SHA  -> $PIN_FILE"

# --- out-of-tree venv ---
if [ ! -d "$VENV" ]; then
    log "creating venv $VENV${PY_VER:+ (python $PY_VER)}"
    uv venv ${PY_VER:+--python "$PY_VER"} "$VENV"
fi
# Per-repo install: pinned test stack + ty + offline deps + editable pkg, then
# drop ONLY the package so `import $REPO_PKG` resolves from the per-run cwd (the
# agent's edits get tested). The pinning mechanism differs per repo (config.sh).
log "installing stack for $REPO (ty${OFFLINE_DEPS:+ + $OFFLINE_DEPS} + pinned test deps)"
install_stack

log "smoke: python + pytest + ty present?"
"$VENV/bin/python" -c "import sys; print('py', sys.version.split()[0])"
"$VENV/bin/python" -m pytest --version 2>/dev/null | head -1 || log "pytest missing!"
"$VENV/bin/ty" --version 2>/dev/null || log "ty missing!"
log "done. Verify deps with: cd $REPO_SRC && PATH=$VENV/bin:\$PATH python -c 'import $REPO_PKG'"

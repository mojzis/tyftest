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
if [ ! -d "$VENV" ]; then log "creating venv $VENV"; uv venv "$VENV"; fi
log "installing ty (for tyf) into venv"
VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" ty >/dev/null

log "installing target deps (editable, then drop the package so cwd source wins)"
# Install dlt + its deps editable, then uninstall ONLY the package: this leaves
# every dependency in site-packages but makes `import dlt` resolve from the
# per-run working copy's cwd (RUN/dlt), so the agent's edits are what gets tested.
VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" -e "$REPO_SRC" \
    || log "WARN: editable install failed — inspect extras/deps manually"
# install the repo's PINNED test stack (dev group) — NOT latest, which breaks
# pytest-cases/pytest-asyncio against the repo's expected pytest<8.
( cd "$REPO_SRC" && VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" \
    --group dev >/dev/null 2>&1 ) \
  || log "WARN: 'uv pip install --group dev' failed — inspect dependency-groups"
VIRTUAL_ENV="$VENV" uv pip uninstall --python "$VENV/bin/python" dlt >/dev/null 2>&1 || true

log "smoke: python + pytest + ty present?"
"$VENV/bin/python" -c "import sys; print('py', sys.version.split()[0])"
"$VENV/bin/python" -m pytest --version 2>/dev/null | head -1 || log "pytest missing!"
"$VENV/bin/ty" --version 2>/dev/null || log "ty missing!"
log "done. Verify deps with: cd $REPO_SRC && PATH=$VENV/bin:\$PATH python -c 'import dlt'"

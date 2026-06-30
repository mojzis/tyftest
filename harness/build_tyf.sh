#!/usr/bin/env bash
# Build the tyf binary from ~/git/ty-find at its current HEAD and pin it.
# Records the tool SHA (the "tested commit") — findings are only valid as of it.
set -euo pipefail

TYF_SRC="${TYF_SRC:-$HOME/git/ty-find}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/bin/tyf"

cd "$TYF_SRC"
SHA="$(git rev-parse --short HEAD)"
TAG="$(git describe --tags --always 2>/dev/null || echo '(no tag)')"
DIRTY=""
git diff --quiet || DIRTY=" (dirty tree!)"

echo ">> ty-find @ $SHA $TAG$DIRTY"
echo ">> cargo build --release ..."
cargo build --release

cp "$TYF_SRC/target/release/tyf" "$DEST"
chmod +x "$DEST"

echo ">> smoke test:"
"$DEST" --version || true
"$DEST" --help | head -5

# emit the pin so build_tyf can feed TOOL_VERSION.md / manifests
echo "TYF_SHA=$SHA"
echo "TYF_TAG=$TAG"
echo "$SHA $TAG$DIRTY" > "$ROOT/bin/.tyf_sha"
echo ">> pinned binary at $DEST"

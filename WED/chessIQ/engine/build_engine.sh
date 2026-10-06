#!/bin/bash
# Build Fairy-Stockfish with the Kramnik self-capture patch (sprint CM-1, 2026-10-06).
# Result: engine/fairy-stockfish-kramnik  (play with VariantPath=engine/kramnik.ini, UCI_Variant=kramnik)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT=9f778da667f6e07dae1e85d3e2ea204fc6dee94d
SRC="${FSF_SRC:-$HERE/Fairy-Stockfish}"
if [ ! -d "$SRC/.git" ]; then
  git clone -q https://github.com/fairy-stockfish/Fairy-Stockfish.git "$SRC"
fi
cd "$SRC"
git fetch -q origin "$COMMIT" 2>/dev/null || true
git checkout -q -f "$COMMIT"
git clean -fdq     # the build clone only: drop files a previous patch added
git apply "$HERE/kramnik-selfcapture.patch"
cd src
make -j"$(nproc)" build ARCH="${ARCH:-x86-64-modern}" > "$HERE/build.log" 2>&1
cp stockfish "$HERE/fairy-stockfish-kramnik"
git -C "$SRC" checkout -q -- . && git -C "$SRC" clean -fdq -e src/stockfish
echo "built $HERE/fairy-stockfish-kramnik"

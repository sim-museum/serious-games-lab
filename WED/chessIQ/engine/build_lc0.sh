#!/bin/bash
# Build lc0 that plays Kramnik chess (EPIC NN, sprint NN-1, 2026-10-06): lc0 v0.32.1 + lc0-kramnik.patch,
# compiled with -DLC0_KRAMNIK. CPU build (OpenBLAS); needs meson, ninja, protobuf, libopenblas-dev.
# Result: engine/lc0-kramnik. Any lc0 network works with it (every Kramnik position is a chess position).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG=v0.32.1
SRC="${LC0_SRC:-$HERE/lc0}"
[ -d "$SRC/.git" ] || git clone -q https://github.com/LeelaChessZero/lc0.git "$SRC"
cd "$SRC"
git checkout -q -f "$TAG"
git clean -fdq -e build
git apply "$HERE/lc0-kramnik.patch"
meson setup build/kramnik --reconfigure --buildtype release -Dgtest=false -Dcpp_args=-DLC0_KRAMNIK \
  -Dopencl=false -Dcudnn=false -Dplain_cuda=false -Ddx=false -Donednn=false > "$HERE/build_lc0.log" 2>&1
ninja -C build/kramnik -j"${JOBS:-$(nproc)}" >> "$HERE/build_lc0.log" 2>&1
cp build/kramnik/lc0 "$HERE/lc0-kramnik"
git checkout -q -- .
echo "built $HERE/lc0-kramnik"

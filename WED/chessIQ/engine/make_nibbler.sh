#!/bin/bash
# Make a Nibbler that plays Kramnik chess (EPIC NN, sprint NN-2, 2026-10-06): copy a Nibbler 2.5.3 Linux release
# and apply nibbler-kramnik.patch (rules in 40_position.js and 41_fen.js, KRAMNIK switch in 10_globals.js, and a
# test hook in 99_start.js: NIBBLER_BEHAVIOUR=self_play starts play without a keypress, NIBBLER_DUMP=<file> writes
# what the window shows). Point it at engine/lc0-kramnik. Your original Nibbler is not touched.
#   engine/make_nibbler.sh [nibbler release dir]   -> engine/nibbler-kramnik/
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:-$HERE/../../INSTALL/nibbler-2.5.3-linux}"
DST="$HERE/nibbler-kramnik"
[ -x "$SRC/nibbler" ] || { echo "no Nibbler release at $SRC" >&2; exit 1; }
rm -rf "${DST:?}"
cp -a "$SRC" "$DST"
patch -s -d "$DST" -p1 < "$HERE/nibbler-kramnik.patch"
echo "made $DST (engine: $HERE/lc0-kramnik)"

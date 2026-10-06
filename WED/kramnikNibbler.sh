#!/bin/bash
# kramnikNibbler.sh - analyse Kramnik chess (no castling, capture anything but your own king) in Nibbler, with
# Leela (lc0) and a neural network trained on Kramnik chess (chessIQ EPIC NN, 2026-10-06).
#
#   ./kramnikNibbler.sh [game.pgn]
#
# Builds what is missing on first use (chessIQ/engine/build_lc0.sh, make_nibbler.sh), then starts the Kramnik copy
# of Nibbler with its own settings in ~/.config/chessiq-kramnik-nibbler -- your normal Nibbler and its settings are
# not touched. Network: the newest chessIQ/engine/nets/kramnik-*.pb.gz (falls back to a standard-chess network).
set -euo pipefail
WED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENG="$WED/chessIQ/engine"
CONF="${XDG_CONFIG_HOME_KRAMNIK:-$HOME/.config/chessiq-kramnik-nibbler}"

[ -x "$ENG/lc0-kramnik" ] || { echo "Building lc0 for Kramnik chess (once, a few minutes)..."; bash "$ENG/build_lc0.sh"; }
[ -x "$ENG/nibbler-kramnik/nibbler" ] || { echo "Making the Kramnik Nibbler (once)..."; bash "$ENG/make_nibbler.sh"; }

NET="$(ls "$ENG"/nets/kramnik-*.pb.gz 2>/dev/null | sort | tail -n 1 || true)"
if [ -z "$NET" ]; then
  NET="$WED/INSTALL/otherWeights/LD2.pb.gz"
  echo "No Kramnik network in $ENG/nets -- using the standard-chess network $NET"
fi
[ -f "$NET" ] || { echo "No network found ($NET)" >&2; exit 1; }

mkdir -p "$CONF/Nibbler"
python3 - "$CONF/Nibbler" "$ENG/lc0-kramnik" "$NET" "$(nproc)" <<'PYEOF'
import json, os, sys
d, eng, net, cpus = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
cfg_path, eng_path = os.path.join(d, "config.json"), os.path.join(d, "engines.json")
cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
cfg["path"] = eng                                             # always the Kramnik lc0
json.dump(cfg, open(cfg_path, "w"), indent=1)
engines = json.load(open(eng_path)) if os.path.exists(eng_path) else {}
e = engines.setdefault(eng, {"args": [], "options": {}, "search_nodes": None, "search_nodes_special": 10000})
e["options"].update({"WeightsFile": net, "Backend": "blas", "Threads": max(1, cpus - 1)})
json.dump(engines, open(eng_path, "w"), indent=1)
print("network:", os.path.basename(net))
PYEOF

cd "$ENG/nibbler-kramnik"
exec env XDG_CONFIG_HOME="$CONF" ./nibbler --no-sandbox "$@"

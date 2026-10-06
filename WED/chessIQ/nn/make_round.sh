#!/bin/bash
# One training round (EPIC NN): games -> lc0 V6 chunks -> compact arrays -> train -> verify inside lc0.
#   nn/make_round.sh <name> "<games.jsonl ...>" [train.py options]
# Needs: engine/lc0-kramnik with the kramnik-convert mode, ~/kramnik-nn/venv (PyTorch). Work dir: ~/kramnik-nn/<name>
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
NAME="$1"; GAMES="$2"; shift 2
W="${KRAMNIK_NN:-$HOME/kramnik-nn}/$NAME"
PY="${KRAMNIK_NN:-$HOME/kramnik-nn}/venv/bin/python"
LC0="${LC0:-$ROOT/engine/lc0-kramnik}"
rm -rf "${W:?}"; mkdir -p "$W/chunks"
python3 "$ROOT/tools/games_to_lc0.py" $GAMES > "$W/games.txt"
KRAMNIK_IN="$W/games.txt" KRAMNIK_OUT="$W/chunks" "$LC0" kramnik-convert 2>/dev/null | tail -n 1
"$PY" "$HERE/prepare.py" "$W/chunks" "$W/data.npz" --holdout-every 20
"$PY" "$HERE/train.py" "$W/data.npz" "$W/data_holdout.npz" "$W/net" "$@"
head -n 2 "$(echo $GAMES | awk '{print $1}')" > "$W/verify.jsonl"
python3 "$ROOT/tools/games_to_lc0.py" "$W/verify.jsonl" > "$W/verify.txt"
mkdir -p "$W/verify_chunks"
KRAMNIK_IN="$W/verify.txt" KRAMNIK_OUT="$W/verify_chunks" "$LC0" kramnik-convert > /dev/null 2>&1
B=$(echo "$@" | { grep -oE -- '--blocks [0-9]+' || true; } | awk '{print $2}')      # absent when fine-tuning
C=$(echo "$@" | { grep -oE -- '--channels [0-9]+' || true; } | awk '{print $2}')
POL=classical; echo "$@" | grep -q -- '--init' && POL=conv
INIT=$(echo "$@" | { grep -oE -- '--init [^ ]+' || true; } | awk '{print $2}')
if [ -n "$INIT" ]; then B=$("$PY" -c "import sys; sys.path.insert(0,'$HERE'); import lc0net as L; n=L.load_lc0('$INIT'); print(n.blocks, n.channels)"); C=${B#* }; B=${B% *}; fi
POLICY=$POL LC0="$LC0" "$PY" "$HERE/verify_export.py" "$W/net.pt" "$W/net.pb.gz" "${B:-6}" "${C:-64}" "$W/verify.jsonl" "$W/verify_chunks" 2
echo "round $NAME: $W/net.pb.gz"

#!/bin/bash
# Self-play for Kramnik chess (EPIC NN, NN-10): lc0's own selfplay mode, Kramnik build on the GPU.
#   selfplay.sh WEIGHTS GAMES OUTDIR   -> OUTDIR/games.txt (gameready lines), chunks under OUTDIR/cache/lc0/data-*
W=$1; N=$2; OUT=$3
ENG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../engine" && pwd)"
mkdir -p "$OUT/cache"
cd "$OUT"
XDG_CACHE_HOME="$OUT/cache" exec "$ENG/lc0-kramnik-gpu" selfplay --weights="$W" \
  --backend=cuda-fp16 --games="$N" --parallelism=32 --visits="${VISITS:-800}" --minibatch-size=256 --training=true \
  --noise-epsilon=0.25 --noise-alpha=0.3 --temperature=1.0 --temp-cutoff-move=30 \
  --resign-percentage=3 --resign-earliest-move=40 > "$OUT/games.txt" 2> "$OUT/stderr.txt"

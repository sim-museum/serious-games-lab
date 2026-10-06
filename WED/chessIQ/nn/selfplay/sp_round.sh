#!/bin/bash
# Train one self-play generation (NN-10): chunks -> npz -> fine-tune -> lc0 identity check.
#   sp_round.sh GENDIR INIT_WEIGHTS [train.py options]
set -euo pipefail
G=$1; INIT=$2; shift 2
NN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; PY=~/kramnik-nn/venv/bin/python; V=~/kramnik-nn/r3
"$PY" $NN/prepare.py "$G/cache" "$G/data.npz" --holdout-every 20
"$PY" $NN/train.py "$G/data.npz" "$G/data_holdout.npz" "$G/net" --init "$INIT" "$@"
POLICY=conv LC0="$NN/../engine/lc0-kramnik" "$PY" $NN/verify_export.py "$G/net.pt" "$G/net.pb.gz" 10 128 "$V/verify.jsonl" "$V/verify_chunks" 2
echo "generation done: $G/net.pb.gz"

#!/usr/bin/env bash
# julia vs gold sweep: chase captures every STEP m round the lap, converted to jpg
set -u
D=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native
t=$1; L=$2; STEP=$3; TAG=${4:-ours}
O=/home/admin/jr-parity/p2/$TAG/$t; mkdir -p $O; rm -f $O/*.ppm
SH=""; for s in $(seq 0 $STEP $L); do SH="${SH}${s}:1:s$(printf %05d $s);"; done
cd $D
~/bin/gl-lock timeout -k 5 3600 env TRACK=$t JM_SMOKE=1 JM_NOREPLAY=1 JM_SHOT_SETTLE=20 JM_TWINBOARD_DIAG=1 JM_SHOTS="$SH" JM_SHOTS_DIR=$O \
    julia --project=. drive_native_mtk.jl > $O/run.log 2>&1
echo "$t rc=$? shots=$(ls $O/*.ppm 2>/dev/null | wc -l)"
python3 - "$O" <<'PY'
import sys, glob, os
from PIL import Image
for f in glob.glob(sys.argv[1]+'/*.ppm'):
    Image.open(f).resize((720,405)).save(f[:-4]+'.jpg', quality=85); os.remove(f)
PY

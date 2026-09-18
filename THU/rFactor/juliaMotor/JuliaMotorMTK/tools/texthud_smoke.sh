#!/usr/bin/env bash
# TEXTHUD-1 smoke (GOLDMATCH-JR-1 S1, 2026-09-17): the text timing overlay is DRAWN, and it is
# drawn where the gold draws it. Two cockpit shots at Watkins Glen, one with the overlay and one
# with JM_NO_TEXT_HUD=1 (the control), same s, same settle. The overlay's own rows live in the
# top-left 340x80 px; the control arm must be near-empty there and the treatment must carry ink.
# PASS/FAIL/CANNOT MEASURE, like every other gate here. NEVER /tmp (tmpfs; frame dumps are game data).
set -u
ROOT=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor; D="$ROOT/demo/native"
OUT="${OUT:-/home/admin/jr-parity/texthud}"; mkdir -p "$OUT"; rm -f "$OUT"/th_*.ppm
TMO="${TMO:-900}"
run() { # $1 name  $2 extra env
  timeout -k 5 "$TMO" stdbuf -oL env $2 TRACK="${TRACK:-watglen}" JM_SMOKE=1 JM_SHOTS="8300:0:$1" \
      JM_SHOTS_DIR="$OUT" JM_SHOT_SETTLE="${JM_SHOT_SETTLE:-38}" \
      julia --project="$D" "$D/drive_native_mtk.jl" > "$OUT/$1.log" 2>&1
  echo "  $1: exit $?"
}
echo "TEXTHUD-1 smoke -- overlay vs control, Watkins Glen cockpit s=8300"
run th_text ""
run th_ctl  "JM_NO_TEXT_HUD=1"
[ -s "$OUT/th_text.ppm" ] && [ -s "$OUT/th_ctl.ppm" ] || { echo "  CANNOT MEASURE: a capture is missing -- see $OUT/*.log"; exit 2; }
python3 - "$OUT" <<'PY'
import sys; from PIL import Image; import numpy as np
out=sys.argv[1]
def strip(p): return np.asarray(Image.open(p).convert('RGB')).astype(float)[6:86,8:348]
t=strip(f'{out}/th_text.ppm'); c=strip(f'{out}/th_ctl.ppm')
if t.shape != c.shape: print('  CANNOT MEASURE: capture sizes differ'); sys.exit(2)
# The first metric ("pixels +90 above the strip median") read 0.00% on a frame that visibly carried
# the text: the sky's median is ~200, so white glyphs cannot clear it. Measure the overlay as what
# it IS -- the difference between the two arms in the strip -- against the run-to-run noise the
# chase gate measured for this renderer (0.6-2.2 mean|diff|; threshold 4.0 is its floor).
d=np.abs(t-c).mean(); frac=float((np.abs(t-c).max(2)>60).mean()*100)
print(f'  top-left strip {t.shape[1]}x{t.shape[0]}: mean|diff| treatment-control {d:.2f}   pixels changed >60: {frac:.2f}%')
ok = d >= 4.0 and frac >= 1.0
print("PASS: the overlay is drawn in the gold's corner" if ok else 'FAIL: the two arms do not differ where the overlay should be')
sys.exit(0 if ok else 1)
PY

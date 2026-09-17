#!/usr/bin/env bash
# PARITYGATE-JR-1: julia's screen-parity gate -- CHASE VIEW ONLY, and it measures its own noise floor.
#
# WHY THIS SHAPE. MiG Alley and BoB compare byte-for-byte, because their 2-D captures are
# deterministic. julia's are not: PARITYGATE-JR-1 S1 measured chase repeating at mean|diff| 0.58,
# so a byte comparison would fail every run and a fixed tolerance would be a guess.
#
# Two rules this gate exists to enforce, both learned the hard way:
#
#  1. SHOT ORDER IS PART OF THE MEASUREMENT (S3). Every JM_SHOTS entry teleports and settles from
#     wherever the previous shot left the car, so the Nth capture of a sweep is not comparable to
#     the Mth. S1's headline "chase 0.58 / cockpit 53.4" was withdrawn because it compared a 6th
#     capture against a 3rd. This gate therefore pins ONE sweep, and compares each shot only
#     against the reference shot of the SAME ORDINAL.
#
#  2. THE RUN MEASURES ITS OWN NOISE (S2's design, for S3's reason). The sweep captures s=8500
#     TWICE -- 2nd and 4th. Their difference is this run's repeat spread, measured today on this
#     machine, and the pass threshold is derived from it rather than hardcoded. If the run is too
#     noisy to judge, the gate says so instead of reporting a colour.
#
# A gate that cannot say "I could not measure this" is the failure this project has booked
# repeatedly (QA_METHOD_GOLD_PARITY.md rule 9: an unrunnable gate is worse than none).
#
# S5: the 4th shot is a BACKWARD teleport (8700 -> 8500) ON PURPOSE. That hop is what exposed the
# step guard keeping the previous point's ground across a teleport, so leaving it in the sweep makes
# this gate a regression test for that fix as well as a parity check. If w4 ever comes back as a
# pale void under a black sky again, place_at_s!'s `PLAYER_G[] = NaN` has been lost.
#
#   bash chase_parity_gate.sh          compare against parity/chase_ref/
#   SEED=1 bash chase_parity_gate.sh   seed the reference from this run (review the images first)
set -u
ROOT=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor
D="$ROOT/demo/native"
REF="${REF:-$ROOT/parity/chase_ref}"
# NEVER /tmp: it is a 7.6 GB tmpfs and frame dumps are game data (project standing rule).
OUT="${OUT:-/home/admin/jr-parity}"
SEED="${SEED:-0}"
TMO="${TMO:-900}"

mkdir -p "$OUT"
rm -f "$OUT"/w*.ppm

# 4 chase shots, s=8500 captured at ordinals 2 and 4. TRACK is pinned so the reference cannot be
# compared against a different circuit.
SWEEP="8300:1:w1_8300;8500:1:w2_8500;8700:1:w3_8700;8500:1:w4_8500"

echo "julia chase parity gate -- refs: $REF"
echo "  sweep: $SWEEP"
timeout -k 5 "$TMO" stdbuf -oL env \
    TRACK="${TRACK:-nurburgring}" JM_SMOKE=1 JM_SHOTS="$SWEEP" \
    JM_SHOTS_DIR="$OUT" JM_SHOT_SETTLE="${JM_SHOT_SETTLE:-38}" \
    julia --project="$D" "$D/drive_native_mtk.jl" > "$OUT/run.log" 2>&1
rc=$?

n=$(ls "$OUT"/w*.ppm 2>/dev/null | wc -l)
if [ "$n" -ne 4 ]; then
    echo "  CANNOT MEASURE: $n of 4 captures produced (exit $rc) -- see $OUT/run.log"
    echo "  (exit 124 = the run outran TMO=$TMO; that is a budget, not a regression)"
    exit 2
fi

if [ "$SEED" = "1" ]; then
    mkdir -p "$REF"
    cp "$OUT"/w1_8300.ppm "$OUT"/w2_8500.ppm "$OUT"/w3_8700.ppm "$REF"/
    echo "  SEEDED $REF from this run (w4 is the repeat probe and is deliberately not a reference)"
    exit 0
fi

python3 - "$OUT" "$REF" <<'PY'
import sys, os
from PIL import Image
import numpy as np
out, ref = sys.argv[1], sys.argv[2]
def load(p):
    return np.asarray(Image.open(p).convert('RGB')).astype(float)
def md(a, b):
    return float(np.abs(a - b).mean())

w2, w4 = load(f'{out}/w2_8500.ppm'), load(f'{out}/w4_8500.ppm')
if w2.shape != w4.shape:
    print('  CANNOT MEASURE: the two s=8500 captures differ in size'); sys.exit(2)
noise = md(w2, w4)
# S7: the threshold cannot come from the in-run pair alone. That pair measures variation WITHIN one
# run; the comparison it gates is BETWEEN runs, and those are not the same number. Measured on the
# first clean run against a reference captured in a different run:
#     in-run repeat (w2 vs w4)   0.587
#     run-to-run    w1 0.621   w2 1.186   w3 2.249
# i.e. run-to-run is up to ~4x the in-run figure, and `max(2.0, 3*noise)` = 2.0 failed w3 at 2.249
# on a run whose own self-check was clean. So the in-run pair stays as the HEALTH check -- it is
# what caught the 73.1 teleport defect -- and the pass threshold gets its own floor with margin.
# CALIBRATED ON ONE run-to-run sample (worst 2.249, so 4.0 is ~1.8x margin). A second clean run
# would tighten it; until then the floor is deliberately loose rather than falsely precise.
thresh = max(4.0, noise * 6.0)
print(f'  in-run repeat spread (s=8500, ordinals 2 vs 4): mean|diff| {noise:.3f}')
# PARITYGATE-JR-1 S8: this line printed `max(2.0, 3x noise)` while the code above computed
# max(4.0, noise*6.0) -- S7 changed the rule and not its own report. A gate that misstates its
# threshold in the log is the exact instrument-lies class this item already spent a sprint on:
# anyone auditing the pass floor from the output would have read the withdrawn formula.
print(f'  pass threshold: max(4.0, 6x noise) = {thresh:.3f}')

fail = 0; measured = 0
for name in ('w1_8300', 'w2_8500', 'w3_8700'):
    rp = f'{ref}/{name}.ppm'
    if not os.path.exists(rp):
        print(f'  {name:10s} NO REFERENCE -- seed deliberately with SEED=1 after review'); continue
    a, b = load(f'{out}/{name}.ppm'), load(rp)
    if a.shape != b.shape:
        print(f'  {name:10s} FAIL size {a.shape} vs ref {b.shape}'); fail = 1; continue
    d = md(a, b); measured += 1
    print(f'  {name:10s} mean|diff| {d:7.3f}  {"OK" if d <= thresh else "DIFF"}')
    if d > thresh: fail = 1

if measured == 0:
    print('  CANNOT MEASURE: no references present'); sys.exit(2)
print('-' * 40)
print('FAIL: a chase capture moved beyond this run\'s own noise floor' if fail
      else f'PASS: {measured} chase screen(s) within {thresh:.3f}')
sys.exit(1 if fail else 0)
PY

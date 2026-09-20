#!/usr/bin/env bash
# OFFTRACK-2: reproduce the PO's Watkins Glen excursion (lapdist ~2386, +30 m off the line, 150 km/h, 40 deg outward) and trace it per frame.
/tmp/claude-1001/-home-admin/679c6939-a4c2-41fb-8e58-365614e5ffb5/scratchpad/po_idle.sh
D=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native; OUT=$HOME/jr-parity; mkdir -p $OUT
for arm in c d; do
  case $arm in c) probe="2386:30:190:40:35"; extra="";; d) probe="2386:30:190:40:35"; extra="JM_WRECK_DAMP_OLD=1";; esac
  gl-lock -w 3600 timeout -k 5 900 env DISPLAY=:0 TRACK=watglen JM_SMOKE=1 JM_OFFTRACK_PROBE="$probe" JM_OFFTRACK_FRAMES=420 JM_OFFTRACK_EXIT=1 JM_NO_AUTOEXIT=1 $extra julia --project=$D $D/drive_native_mtk.jl > $OUT/offtrack2_$arm.log 2>&1
  echo "arm $arm ($probe): exit=$?  offtrack lines: $(grep -a -c '\[offtrack\]' $OUT/offtrack2_$arm.log)"
  grep -a 'JM_OFFTRACK_PROBE\|\[WRECK\]\|ERROR\|Error' $OUT/offtrack2_$arm.log | head -8 | cut -c1-200
  grep -a '\[offtrack\]' $OUT/offtrack2_$arm.log | awk 'NR%20==1' | head -22 | cut -c1-200
done
echo JR-OFFTRACK2-done

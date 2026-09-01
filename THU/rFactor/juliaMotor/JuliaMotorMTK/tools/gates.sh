#!/usr/bin/env bash
# JuliaMotorMTK gate suite -- every headless smoke, one command, one verdict.
#
# WHY THIS EXISTS. The smokes were only ever run by hand, and nothing in the repo referenced
# them. A gate nobody runs protects nothing: BoB shipped a flagship campaign gate that was
# unpassable from the day it was written and stayed green for nine sprints because no one
# watched it fail (BoB S206). Per-sprint they must run as a set, and a regression in one must
# be impossible to miss because another printed PASS after it.
#
# SMOKES only -- the *_probe / *_compare tools are investigation instruments, not assertions,
# and a suite that mixes them reports "fail" for a tool that never had a verdict to give.
#
#   tools/gates.sh            all smokes
#   tools/gates.sh stall      only those matching "stall"
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)"
FILTER="${1:-}"
SMOKES="parse_smoke wreck_smoke contact_smoke boundary3d_smoke extforce3d_smoke wheelmu_smoke drive3d_smoke stall_smoke transmission_smoke controls_smoke people_smoke damage_smoke mipcolor_smoke ai_field_smoke susp_pose_smoke netplay_smoke setup_tab_smoke offroad_smoke wreck_seal_smoke reground_smoke"

pass=0; fail=0; failed=""
echo "JuliaMotorMTK gates  (project: $PROJ)"
for g in $SMOKES; do
  [ -n "$FILTER" ] && case "$g" in *"$FILTER"*) ;; *) continue ;; esac
  [ -f "$HERE/$g.jl" ] || { echo "  MISSING  $g.jl"; fail=$((fail+1)); failed="$failed $g(missing)"; continue; }
  log="/tmp/jm_gate_$g.log"
  printf "  %-22s " "$g"
  # Gates that go through demo/native/render.jl (extract_gpl_car) need the app's project, which
  # carries GLFW/ModernGL; the physics project does not. susp_pose_smoke failed on exactly that.
  gproj="$PROJ"; case "$g" in susp_pose_smoke|netplay_smoke|setup_tab_smoke|reground_smoke) gproj="$PROJ/../demo/native" ;; esac
  timeout 900 julia --project="$gproj" "$HERE/$g.jl" > "$log" 2>&1
  rc=$?
  # Exit status FIRST -- it is the only signal a crashed run gives. The text is a second
  # opinion for the smokes that report "✓ OK" rather than an exit code they set themselves.
  if [ "$rc" -eq 0 ]; then echo "PASS   ($log)"; pass=$((pass+1))
  else
    echo "FAIL rc=$rc   ($log)"; fail=$((fail+1)); failed="$failed $g"
    sed -n '$p' "$log" | sed 's/^/      /'
  fi
done
echo "----------------------------------------"
if [ "$fail" -eq 0 ]; then echo "ALL GATES PASS ($pass)"; exit 0
else echo "GATES FAILED ($fail of $((pass+fail))):$failed"; exit 1; fi

#!/usr/bin/env bash
# REPLAYLOAD-1 S2 part 2: after jlracer.so exists -- time the replay with/without it, pack AppImage 'f', verify from the AppImage.
set -u
P=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor; D=$P/demo/native; OUT=$HOME/jr-parity/sysimage
REC="$P/data/juliaracer/replay_watglen 5ai 2026-09-02 10-08-03.jmr"
PRE=/tmp/claude-1001/-home-admin/679c6939-a4c2-41fb-8e58-365614e5ffb5/scratchpad/po_idle.sh
ts() { date +%H:%M:%S; }
[ -s $D/jlracer.so ] || { echo NO-SYSIMAGE; exit 1; }
echo "=== $(ts) local replay timing (60 frames), nosys vs sys"; $PRE
for arm in nosys sys; do J=""; [ $arm = sys ] && J="-J $D/jlracer.so"
  t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=watglen JM_REPLAY="$REC" JM_SMOKE=1 JM_SMOKE_FRAMES=60 julia $J --project=$D $D/drive_native_mtk.jl > $OUT/time_$arm.log 2>&1; rc=$?
  echo "$arm: replay start-to-exit $(( $(date +%s) - t0 )) s  exit=$rc errors=$(grep -a -c 'ERROR' $OUT/time_$arm.log)"; done
echo "=== $(ts) pack AppImage f"
cd /home/admin/appimage-build || exit 1
systemd-run --user --scope -p MemoryMax=10G ./build_julia.sh > $HOME/jr-parity/build_julia_f.log 2>&1 || { echo BUILD-APPDIR-FAILED; tail -3 $HOME/jr-parity/build_julia_f.log; exit 1; }
ls -la JuliaRacer.AppDir/usr/share/julia/juliaMotor/demo/native/jlracer.so | awk '{print "bundled sysimage", $5, "bytes"}'
systemd-run --user --scope -p MemoryMax=10G env ARCH=x86_64 ./appimagetool/AppRun JuliaRacer.AppDir /home/admin/Documents/260919/JuliaRacer-x86_64-260919f.AppImage > $HOME/jr-parity/pack_julia_f.log 2>&1; echo "pack rc=$? $(ts)"
ls -la /home/admin/Documents/260919/JuliaRacer-x86_64-260919f.AppImage; sha256sum /home/admin/Documents/260919/*.AppImage > /home/admin/Documents/260919/SHA256SUMS
echo "=== $(ts) verify from the AppImage (replay timing with the bundled sysimage)"
A=/home/admin/Documents/260919/JuliaRacer-x86_64-260919f.AppImage; V=/home/admin/appimage-build/verify_jr_260919f; mkdir -p "$V"; $PRE
"$A" --appimage-mount > "$V/mount.txt" 2>&1 & MP=$!
for i in $(seq 1 30); do M=$(head -1 "$V/mount.txt" 2>/dev/null); [ -n "$M" ] && [ -d "$M/usr" ] && break; sleep 1; done
[ -d "$M/usr/share/julia/runtime/bin" ] || { echo "NO MOUNT"; kill $MP; exit 1; }
mkdir -p "$V/THU/rFactor" "$V/THU/WP/drive_c/Sierra/GPL" "$V/depot"; rm -rf "$V/THU/rFactor/juliaMotor"; cp -a "$M/usr/share/julia/juliaMotor" "$V/THU/rFactor/"; chmod -R u+w "$V/THU/rFactor/juliaMotor"
ln -sfn "$M/usr/share/julia/tracks" "$V/THU/WP/drive_c/Sierra/GPL/tracks"; ln -sfn "$M/usr/share/julia/cars" "$V/THU/WP/drive_c/Sierra/GPL/cars"; ln -sfn "$M/usr/share/julia/sound" "$V/THU/WP/drive_c/Sierra/GPL/sound"
cd "$V/THU/rFactor/juliaMotor" || exit 1
export PATH="$M/usr/share/julia/runtime/bin:$PATH" JULIA_DEPOT_PATH="$V/depot:$M/usr/share/julia/depot:"
t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=watglen JM_REPLAY="$REC" JM_SMOKE=1 JM_SMOKE_FRAMES=60 julia -J demo/native/jlracer.so --project=demo/native demo/native/drive_native_mtk.jl > "$V/replay.log" 2>&1; rc=$?
echo "appimage replay start-to-exit $(( $(date +%s) - t0 )) s exit=$rc errors=$(grep -a -c 'ERROR\|UndefVar' "$V/replay.log")"; grep -a -n 'ERROR\|UndefVar' "$V/replay.log" | head -3 | cut -c1-160
t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=skidpad JM_SMOKE=1 JM_SHOTS="60:1:chase_skidpad" JM_SHOTS_DIR="$V" JM_SHOT_SETTLE=38 julia -J demo/native/jlracer.so --project=demo/native demo/native/drive_native_mtk.jl > "$V/skidpad.log" 2>&1; rc=$?
echo "appimage skidpad $(( $(date +%s) - t0 )) s exit=$rc errors=$(grep -a -c 'ERROR\|UndefVar' "$V/skidpad.log") shot=$(ls "$V"/chase_skidpad.ppm 2>/dev/null)"
kill $MP 2>/dev/null; echo JR-SYSIMAGE-AFTER-done

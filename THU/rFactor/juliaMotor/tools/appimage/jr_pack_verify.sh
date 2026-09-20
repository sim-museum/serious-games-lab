#!/usr/bin/env bash
# REPLAYLOAD-1 S2: repack with the depot-relative runtime ('g'), then verify from a FRESH depot: no precompile expected, replay timed.
set -u
while systemctl --user is-active jr-after.service >/dev/null 2>&1; do sleep 30; done
P=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor; REC="$P/data/juliaracer/replay_watglen 5ai 2026-09-02 10-08-03.jmr"
PRE=/tmp/claude-1001/-home-admin/679c6939-a4c2-41fb-8e58-365614e5ffb5/scratchpad/po_idle.sh
ts() { date +%H:%M:%S; }
cd /home/admin/appimage-build || exit 1
echo "=== $(ts) build_julia.sh (g)"; ./build_julia.sh > $HOME/jr-parity/build_julia_g.log 2>&1 || { echo BUILD-APPDIR-FAILED; tail -3 $HOME/jr-parity/build_julia_g.log; exit 1; }
ls -la JuliaRacer.AppDir/usr/share/julia/depot/juliaup/ | tail -2; ls -la JuliaRacer.AppDir/usr/share/julia/runtime
echo "=== $(ts) appimagetool"; env ARCH=x86_64 ./appimagetool/AppRun JuliaRacer.AppDir /home/admin/Documents/260919/JuliaRacer-x86_64-260919g.AppImage > $HOME/jr-parity/pack_julia_g.log 2>&1; echo "pack rc=$? $(ts)"
ls -la /home/admin/Documents/260919/JuliaRacer-x86_64-260919g.AppImage; sha256sum /home/admin/Documents/260919/*.AppImage > /home/admin/Documents/260919/SHA256SUMS
A=/home/admin/Documents/260919/JuliaRacer-x86_64-260919g.AppImage; V=/home/admin/appimage-build/verify_jr_260919g; rm -rf "$V"; mkdir -p "$V"; $PRE
"$A" --appimage-mount > "$V/mount.txt" 2>&1 & MP=$!
for i in $(seq 1 30); do M=$(head -1 "$V/mount.txt" 2>/dev/null); [ -n "$M" ] && [ -d "$M/usr" ] && break; sleep 1; done
RT="$M/usr/share/julia/depot/juliaup/julia-1.12.6+0.x64.linux.gnu/bin"; [ -x "$RT/julia" ] || { echo "NO RUNTIME at $RT"; kill $MP; exit 1; }
mkdir -p "$V/THU/rFactor" "$V/THU/WP/drive_c/Sierra/GPL" "$V/depot"; cp -a "$M/usr/share/julia/juliaMotor" "$V/THU/rFactor/"; chmod -R u+w "$V/THU/rFactor/juliaMotor"
ln -sfn "$M/usr/share/julia/tracks" "$V/THU/WP/drive_c/Sierra/GPL/tracks"; ln -sfn "$M/usr/share/julia/cars" "$V/THU/WP/drive_c/Sierra/GPL/cars"; ln -sfn "$M/usr/share/julia/sound" "$V/THU/WP/drive_c/Sierra/GPL/sound"
cd "$V/THU/rFactor/juliaMotor" || exit 1
export PATH="$RT:$PATH" JULIA_DEPOT_PATH="$V/depot:$M/usr/share/julia/depot:"
echo "=== $(ts) cache check (fresh depot): using Base64 + ModelingToolkit"
JULIA_DEBUG=loading timeout 900 julia -J demo/native/jlracer.so --project=demo/native -e 'using Base64, ModelingToolkit' > "$V/cachecheck.log" 2>&1
echo "rejections: $(grep -a -c 'Rejecting cache' "$V/cachecheck.log")  precompiled: $(grep -a -c 'Precompiling' "$V/cachecheck.log")  new .ji in fresh depot: $(find "$V/depot" -name '*.ji' | wc -l)"
grep -a 'Rejecting cache' "$V/cachecheck.log" | sed 's/.*because/because/; s/ for Base.PkgId.*since/ since/' | sort | uniq -c | sort -rn | head -4 | cut -c1-200
for arm in replay1 replay2; do t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1800 env DISPLAY=:0 TRACK=watglen JM_REPLAY="$REC" JM_SMOKE=1 JM_SMOKE_FRAMES=60 julia -J demo/native/jlracer.so --project=demo/native demo/native/drive_native_mtk.jl > "$V/$arm.log" 2>&1; rc=$?
  echo "appimage $arm start-to-exit $(( $(date +%s) - t0 )) s exit=$rc errors=$(grep -a -c 'ERROR\|UndefVar' "$V/$arm.log") precompiled=$(grep -a -c 'Precompiling' "$V/$arm.log")"; done
t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1800 env DISPLAY=:0 TRACK=skidpad JM_SMOKE=1 JM_SHOTS="60:1:chase_skidpad" JM_SHOTS_DIR="$V" JM_SHOT_SETTLE=38 julia -J demo/native/jlracer.so --project=demo/native demo/native/drive_native_mtk.jl > "$V/skidpad.log" 2>&1; rc=$?
echo "appimage skidpad $(( $(date +%s) - t0 )) s exit=$rc errors=$(grep -a -c 'ERROR\|UndefVar' "$V/skidpad.log") shot=$(ls "$V"/chase_skidpad.ppm 2>/dev/null)"
kill $MP 2>/dev/null; echo JR-PACK-G-done

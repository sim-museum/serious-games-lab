#!/usr/bin/env bash
# REPLAYLOAD-1 S2: trace real runs -> build jlracer.so (portable cpu target) -> pack AppImage 'f' -> verify + time the replay load.
set -u
P=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor; D=$P/demo/native; OUT=$HOME/jr-parity/sysimage; mkdir -p $OUT $HOME/jr-parity/tmp
REC="$P/data/juliaracer/replay_watglen 5ai 2026-09-02 10-08-03.jmr"
PRE=/tmp/claude-1001/-home-admin/679c6939-a4c2-41fb-8e58-365614e5ffb5/scratchpad/po_idle.sh
ts() { date +%H:%M:%S; }
echo "=== $(ts) trace-compile: replay"; $PRE
gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=watglen JM_REPLAY="$REC" JM_SMOKE=1 JM_SMOKE_FRAMES=400 JM_NO_AUTOEXIT=1 \
  julia --trace-compile=$OUT/stmts_replay.jl --project=$D $D/drive_native_mtk.jl > $OUT/trace_replay.log 2>&1
echo "replay trace exit=$? stmts=$(wc -l < $OUT/stmts_replay.jl) errors=$(grep -a -c 'ERROR' $OUT/trace_replay.log)"
echo "=== $(ts) trace-compile: drive"; $PRE
gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=watglen JM_AI=3 JM_SMOKE=1 JM_SMOKE_FRAMES=400 JM_NO_AUTOEXIT=1 \
  julia --trace-compile=$OUT/stmts_drive.jl --project=$D $D/drive_native_mtk.jl > $OUT/trace_drive.log 2>&1
echo "drive trace exit=$? stmts=$(wc -l < $OUT/stmts_drive.jl) errors=$(grep -a -c 'ERROR' $OUT/trace_drive.log)"
echo "=== $(ts) sysimage build (alone, MemoryMax=13G)"
rm -f $D/jlracer.so
systemd-run --user --scope -p MemoryMax=13G env TMPDIR=$HOME/jr-parity/tmp JM_SYSIMG_STMTS=$OUT/stmts_replay.jl:$OUT/stmts_drive.jl JM_SYSIMG_HEAP=7G \
  julia $D/build_sysimage.jl > $OUT/build_full.log 2>&1
echo "full build exit=$? $(ts) so=$(ls -la $D/jlracer.so 2>/dev/null | awk '{print $5}')"
if [ ! -s $D/jlracer.so ]; then
  echo "=== $(ts) retry without transitive deps"; tail -5 $OUT/build_full.log | cut -c1-160
  systemd-run --user --scope -p MemoryMax=13G env TMPDIR=$HOME/jr-parity/tmp JM_SYSIMG_STMTS=$OUT/stmts_replay.jl:$OUT/stmts_drive.jl JM_SYSIMG_HEAP=7G JM_SYSIMG_TRANSITIVE=0 \
    julia $D/build_sysimage.jl > $OUT/build_notrans.log 2>&1
  echo "notrans build exit=$? $(ts) so=$(ls -la $D/jlracer.so 2>/dev/null | awk '{print $5}')"
fi
[ -s $D/jlracer.so ] || { echo SYSIMAGE-FAILED; exit 1; }
echo "=== $(ts) local timing with -J (drive smoke, 60 frames)"; $PRE
for arm in nosys sys; do J=""; [ $arm = sys ] && J="-J $D/jlracer.so"
  t0=$(date +%s); gl-lock -w 7200 timeout -k 5 1500 env DISPLAY=:0 TRACK=watglen JM_REPLAY="$REC" JM_SMOKE=1 JM_SMOKE_FRAMES=60 julia $J --project=$D $D/drive_native_mtk.jl > $OUT/time_$arm.log 2>&1
  echo "$arm: replay to exit $(( $(date +%s) - t0 )) s  exit=$? errors=$(grep -a -c 'ERROR' $OUT/time_$arm.log)"; done
echo "=== $(ts) pack AppImage f"
cd /home/admin/appimage-build || exit 1
systemd-run --user --scope -p MemoryMax=10G ./build_julia.sh > $HOME/jr-parity/build_julia_f.log 2>&1 || { echo BUILD-APPDIR-FAILED; tail -3 $HOME/jr-parity/build_julia_f.log; exit 1; }
ls -la JuliaRacer.AppDir/usr/share/julia/juliaMotor/demo/native/jlracer.so
systemd-run --user --scope -p MemoryMax=10G env ARCH=x86_64 ./appimagetool/AppRun JuliaRacer.AppDir /home/admin/Documents/260919/JuliaRacer-x86_64-260919f.AppImage > $HOME/jr-parity/pack_julia_f.log 2>&1; echo "pack rc=$? $(ts)"
ls -la /home/admin/Documents/260919/JuliaRacer-x86_64-260919f.AppImage; sha256sum /home/admin/Documents/260919/*.AppImage > /home/admin/Documents/260919/SHA256SUMS
echo JR-SYSIMAGE-PIPELINE-done

#!/usr/bin/env bash
# Julia Racer (juliaMotor) — self-contained AppImage: Julia runtime + package depot +
# the project + the five GPL tracks it can actually load + PyQt6/Qt6 for the launcher.
set -euo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; . "$S/lib_bundle.sh"
JLROOT="$HOME/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu"
PROJ=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor
TRACKS=/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks
APP="$S/JuliaRacer.AppDir"

[ -x "$JLROOT/bin/julia" ] || { echo "julia runtime not found at $JLROOT"; exit 1; }
rm -rf "$APP"
mkdir -p "$APP/usr/share/julia" "$APP/usr/lib/python" "$APP/usr/lib/x86_64-linux-gnu" "$APP/usr/lib/qt6"

# REPLAYLOAD-1 S2 (2026-09-20): the runtime MUST sit at the same depot-relative path it had when the
# package caches were compiled. The caches record stdlib sources as
# @depot/juliaup/julia-1.12.6+0.x64.linux.gnu/share/julia/stdlib/...; with the runtime copied to
# usr/share/julia/runtime every stdlib cache was "wrong source" and 166 packages recompiled on the
# PO's first launch (the 25-minute precompile). Keep the runtime INSIDE the bundled depot, at the
# juliaup path, and it validates.
RTREL="juliaup/$(basename "$JLROOT")"
echo ">> julia runtime (depot-relative)..."; mkdir -p "$APP/usr/share/julia/depot/juliaup"; cp -a "$JLROOT" "$APP/usr/share/julia/depot/juliaup/"
ln -sfn "depot/$RTREL" "$APP/usr/share/julia/runtime"   # old path kept as a symlink for tools that use it
echo ">> julia depot..."        ; mkdir -p "$APP/usr/share/julia/depot"
for d in packages artifacts compiled registries; do
  [ -d "$HOME/.julia/$d" ] && cp -a "$HOME/.julia/$d" "$APP/usr/share/julia/depot/"
done
echo ">> project..."            ; cp -a "$PROJ"                  "$APP/usr/share/julia/juliaMotor"
# STARTUP-1 / 2026-09-06 PO crash: the sim reads the GPL CARS (cars/cars67, 443 MB) and SOUND (63 MB)
# next to the tracks; an older packer bundled them and its AppRun linked them per launch. This
# script had lost both, so installs pointed at a dead mount and the Lotus load died with ENOENT.
GPLROOT=/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL
echo ">> GPL cars (cars67) + sound..."; mkdir -p "$APP/usr/share/julia/cars"
cp -a "$GPLROOT/cars/cars67" "$APP/usr/share/julia/cars/"
cp -a "$GPLROOT/sound"       "$APP/usr/share/julia/sound"
date +%Y%m%d-%H%M%S > "$APP/usr/share/julia/.build-stamp"   # STARTUP-1: the AppRun refreshes an install's code when this changes
# PO 2026-09-04: "When the julia appImage is packed, there should be no replays; all replays
# should be newly created by the user." data/juliaracer/ is the sim's OUTPUT directory -- the
# replay (.jmr) and .ibt recordings it writes during a session. Copying the project wholesale
# shipped 398 MB of MY OWN test sessions (167 files, Aug 27 - Sep 3), so a fresh install opened
# with a replay list full of races the user never drove.
# Keep the DIRECTORY (the sim writes into it) and drop its contents. This is NOT the physics
# reference: that is usr/share/julia/iracing, which JM_IBTDIR points at and which is untouched.
echo ">> clearing bundled session output (replays/recordings)..."
find "$APP/usr/share/julia/juliaMotor/data/juliaracer" -mindepth 1 -maxdepth 1 -type f \
     \( -name "*.jmr" -o -name "*.ibt" -o -name "*_racer_*.txt" \
        -o -name "last_race_result.txt" -o -name "human_*.txt" \) -delete 2>/dev/null || true
echo ">> GPL tracks (only the five TRACKSEL can select)..."
mkdir -p "$APP/usr/share/julia/tracks"
for t in nurburg zandvort watglen monza spa67; do
  [ -d "$TRACKS/$t" ] && cp -a "$TRACKS/$t" "$APP/usr/share/julia/tracks/"
done
echo ">> PyQt6 + Qt6..."
cp -a /usr/lib/python3/dist-packages/PyQt6 "$APP/usr/lib/python/" 2>/dev/null || true
for f in /usr/lib/x86_64-linux-gnu/libQt6*.so.6*; do cp -Ln "$f" "$APP/usr/lib/x86_64-linux-gnu/" 2>/dev/null || true; done
cp -a /usr/lib/x86_64-linux-gnu/qt6/plugins "$APP/usr/lib/qt6/" 2>/dev/null || true
# Qt6 pulls in icu/xkb/etc. that are NOT in the host-provided deny list; bundle them.
for lib in "$APP/usr/lib/x86_64-linux-gnu"/libQt6Core.so.6 "$APP/usr/lib/x86_64-linux-gnu"/libQt6Gui.so.6; do
  [ -f "$lib" ] && bundle_libs "$lib" "$APP/usr/lib/x86_64-linux-gnu" 64 >/dev/null
done

cat > "$APP/AppRun" <<'EOF'
#!/usr/bin/env bash
# Julia writes precompilation output and the sim writes telemetry/replays, so the
# project and a depot overlay are materialised into a writable directory on first run.
# The 1.2 GB of GPL track data stays read-only inside the image and is symlinked in.
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"

command -v python3 >/dev/null || { echo "python3 not found (it ships with Ubuntu Desktop)." >&2; exit 1; }

W="${JR_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/julia-racer}"
if [ ! -e "$W/.installed" ]; then
  echo "First run: setting up in $W (about 450 MB, once)..." >&2
  mkdir -p "$W/THU/rFactor" "$W/THU/WP/drive_c/Sierra/GPL" "$W/depot"
  cp -a --reflink=auto "$HERE/usr/share/julia/juliaMotor" "$W/THU/rFactor/" 2>/dev/null \
    || cp -a "$HERE/usr/share/julia/juliaMotor" "$W/THU/rFactor/"
  chmod -R u+w "$W/THU/rFactor/juliaMotor"
  # GPLBASE resolves to <project>/../../../../WP/drive_c/Sierra/GPL/tracks
  ln -sfn "$HERE/usr/share/julia/tracks" "$W/THU/WP/drive_c/Sierra/GPL/tracks"
  touch "$W/.installed"
fi
# the symlink points into the mount, whose path changes every run
ln -sfn "$HERE/usr/share/julia/tracks" "$W/THU/WP/drive_c/Sierra/GPL/tracks"
ln -sfn "$HERE/usr/share/julia/cars"   "$W/THU/WP/drive_c/Sierra/GPL/cars"     # re-linked every launch: the mount path changes
ln -sfn "$HERE/usr/share/julia/sound"  "$W/THU/WP/drive_c/Sierra/GPL/sound"

export PATH="$HERE/usr/share/julia/depot/juliaup/julia-1.12.6+0.x64.linux.gnu/bin:$PATH"   # REPLAYLOAD-1 S2: the real (depot-relative) runtime path, so stdlib caches validate
# writable depot FIRST, bundled read-only depot second: Julia reads packages/artifacts
# from the bundle and writes anything new into the user's own depot.
# STARTUP-1 (2026-09-06): the trailing ":" appends Julia's DEFAULT depots -- in particular the
# runtime's own share/julia, where the stdlib pkgimages live. Without it every launch recompiled
# Pkg (161 s), REPL (97 s), Markdown, Test, Distributed... into the user's depot.
export JULIA_DEPOT_PATH="$W/depot:$HERE/usr/share/julia/depot:"
# CODE REFRESH (restored 2026-09-06). The first-run copy above is skipped forever once "$W/.installed"
# exists, so an install never received a fixed .jl again -- the PO drove 09-04 code on 09-06 images.
# Refresh the code directories whenever the image's build stamp differs from the install's, copy to
# a temp name first and swap (never rm-then-cp), and RECORD the stamp so it runs once per image.
STAMP_SRC="$HERE/usr/share/julia/.build-stamp"
STAMP_DST="$W/.build-stamp"
if [ -f "$STAMP_SRC" ] && ! cmp -s "$STAMP_SRC" "$STAMP_DST" 2>/dev/null; then
  echo "Updating game code from this AppImage ($(cat "$STAMP_SRC"))..." >&2
  ok=1
  for d in demo JuliaMotor JuliaMotorMTK RFactorData RFactorTelemetry JRPhysics; do   # PHYSPRE-1: JRPhysics is new (and RFactorTelemetry was never refreshed)
    [ -d "$HERE/usr/share/julia/juliaMotor/$d" ] || continue
    rm -rf "$W/THU/rFactor/juliaMotor/.new_$d"
    if cp -a "$HERE/usr/share/julia/juliaMotor/$d" "$W/THU/rFactor/juliaMotor/.new_$d"; then
      rm -rf "$W/THU/rFactor/juliaMotor/$d"
      mv "$W/THU/rFactor/juliaMotor/.new_$d" "$W/THU/rFactor/juliaMotor/$d"
    else
      echo "  WARNING: could not refresh $d -- keeping the existing copy" >&2
      rm -rf "$W/THU/rFactor/juliaMotor/.new_$d"; ok=0
    fi
  done
  chmod -R u+w "$W/THU/rFactor/juliaMotor" 2>/dev/null || true
  [ "$ok" = 1 ] && cp "$STAMP_SRC" "$STAMP_DST"
fi
export PYTHONPATH="$HERE/usr/lib/python:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$HERE/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="$HERE/usr/lib/qt6/plugins"

cd "$W/THU/rFactor/juliaMotor"
exec python3 demo/native/juliaRacer.py "$@"
EOF
chmod +x "$APP/AppRun"
cat > "$APP/juliaracer.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Julia Racer
Comment=juliaMotor - GPL 1967 racing sim in Julia
Exec=AppRun
Icon=juliaracer
Categories=Game;Simulation;
EOF
python3 "$S/mkicon.py" "$APP/juliaracer.png" 8b2f3f
ln -sf juliaracer.png "$APP/.DirIcon"
# PHYSPRE-1 (2026-09-25): the in-house path packages (JuliaMotor, RFactor*, JRPhysics -- the precompiled car
# physics) record their ABSOLUTE source path in their caches, so caches built in the dev tree are rejected in
# an install ("because it is for file <dev path> not file <install path>") and the first launch recompiles
# them (~3 min). Precompile them once more AT THE INSTALL PATH the AppRun uses, inside a bubblewrap mount
# namespace that binds this AppDir's project there (the real install is not touched), into the bundled
# depot. On this machine they then validate as shipped; another user/machine pays the one-time precompile.
INST="${JR_PRECOMPILE_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/julia-racer}/THU/rFactor/juliaMotor"
if command -v bwrap >/dev/null && [ "${JR_NO_INSTALL_PRECOMPILE:-0}" = 0 ]; then
  echo ">> precompiling the path packages at the install path $INST ..."
  mkdir -p "$INST"
  bwrap --dev-bind / / --bind "$APP/usr/share/julia/juliaMotor" "$INST" \
    env PATH="$APP/usr/share/julia/depot/$RTREL/bin:$PATH" JULIA_DEPOT_PATH="$APP/usr/share/julia/depot:" \
    julia --project="$INST/demo/native" -e 'using Pkg; Pkg.precompile(); using JRPhysics, JuliaMotor, RFactorData; println("   install-path caches OK")'
fi
echo ">> AppDir ready: $APP  ($(du -sh "$APP" | cut -f1))"

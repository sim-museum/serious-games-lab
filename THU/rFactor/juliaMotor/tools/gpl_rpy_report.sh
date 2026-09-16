#!/usr/bin/env bash
# tools/gpl_rpy_report.sh — decode a GPL .rpy replay into text reports.
#
# GOLDVID-JR-3 S2. S1 established that the .rpy per-car payload is BIT-PACKED and will not yield to
# byte scanning, and proposed playing the replay back in GPL under Wine with GPL_Tel. That is not
# needed: the PO's own Wine prefix already has **GPL Replay Analyser**, which parses .rpy directly
# and has a documented COMMAND-LINE mode -- no GUI, no menu driving, no synthetic input.
#
#   tools/gpl_rpy_report.sh <replay.rpy> [outdir]
#
# Produces <name>_Race.txt, _LapChart.txt, _LapByLap.txt, _Practice.txt, _Complete.txt:
# per-driver per-lap times for the WHOLE FIELD, finishing order, gaps, and an overtake narrative.
#
# Notes that cost time to find:
#  * The exe must be given its FULL Windows path. Launching it by bare name from its own directory
#    makes wine look in C:\windows\system32 and fail with "not found".
#  * Both -f and -d must be paths inside the prefix's drive_c, so the replay is COPIED in.
#  * Use the runner gpl.sh uses for the GAME (lutris-5.7). The system wine is 10.0 and would
#    upgrade -- i.e. modify -- the PO's prefix.
set -u
RPY="${1:?usage: gpl_rpy_report.sh <replay.rpy> [outdir]}"
OUT="${2:-$(cd "$(dirname "$0")/.." && pwd)/doc/ref/gpl-replay-$(basename "${RPY%.rpy}")}"
PREFIX="${WINEPREFIX:-/home/admin/sgl/THU/WP}"
RUNNER="${GPL_RUNNER:-$HOME/.local/share/lutris/runners/wine/lutris-5.7-x86_64}"
EXE='C:\Program Files\GPL Replay Analyser\GPLReplayAnalyser.exe'
[ -f "$RPY" ] || { echo "no replay at $RPY" >&2; exit 2; }
[ -x "$RUNNER/bin/wine" ] || { echo "no wine runner at $RUNNER" >&2; exit 2; }
[ -f "$PREFIX/drive_c/Program Files/GPL Replay Analyser/GPLReplayAnalyser.exe" ] || {
  echo "GPL Replay Analyser not installed in $PREFIX (run ~/sgl/THU/gpl.sh)" >&2; exit 2; }
name="$(basename "${RPY%.rpy}")"
stage="$PREFIX/drive_c/gplra_in.rpy"
wout="$PREFIX/drive_c/gplra_out"
rm -rf "$wout"; mkdir -p "$wout" "$OUT"
cp "$RPY" "$stage"
export WINEPREFIX="$PREFIX"
export LD_LIBRARY_PATH="$RUNNER/lib:$RUNNER/lib64"
export WINEDLLPATH="$RUNNER/lib/wine:$RUNNER/lib64/wine"
timeout -k 5 -s KILL 300 "$RUNNER/bin/wine" "$EXE" \
    -expreports -fc:\\gplra_in.rpy -dc:\\gplra_out\\ >/dev/null 2>&1
rc=$?
n=0
for f in "$wout"/gplra_in_*.txt; do
  [ -e "$f" ] || continue
  cp "$f" "$OUT/${name}_$(basename "${f#"$wout"/gplra_in_}")"; n=$((n+1))
done
rm -f "$stage"; rm -rf "$wout"
echo "$n reports -> $OUT (wine exit $rc)"
[ "$n" -gt 0 ] || { echo "  NO REPORTS -- the analyser produced nothing" >&2; exit 1; }
grep -a "^ 1 \| 2 \| 3 " "$OUT/${name}_Race.txt" | head -4

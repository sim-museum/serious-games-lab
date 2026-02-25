#!/bin/bash
# Automated test: Launch FFViper, click Instant Action, click FLY, screenshot
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDDIR="$SCRIPT_DIR/build"
SCREENSHOTS="/tmp/ffviper_test"
STDERR_LOG="/tmp/ffviper_test_stderr.log"
mkdir -p "$SCREENSHOTS"
rm -f "$SCREENSHOTS"/*

snap() {
    local outfile="$1"
    xwd -id "$WINID" -silent > "/tmp/_snap.xwd" 2>/dev/null
    if command -v ffmpeg &>/dev/null; then
        ffmpeg -y -i "/tmp/_snap.xwd" -update 1 "$outfile" 2>/dev/null
        if [ $? -ne 0 ]; then
            cp "/tmp/_snap.xwd" "${outfile%.png}.xwd"
            echo "Warning: Could not convert xwd to png, keeping xwd"
        fi
    else
        cp "/tmp/_snap.xwd" "${outfile%.png}.xwd"
    fi
    rm -f "/tmp/_snap.xwd"
    echo "Saved: $(basename $outfile)"
}

pkill -9 FFViper 2>/dev/null; sleep 1

echo "=== Starting FFViper ==="
cd "$BUILDDIR"
./src/ffviper/FFViper -window 2>"$STDERR_LOG" &
FFPID=$!
echo "PID=$FFPID"

# Wait for window
WINID=""
echo "Waiting for window..."
for i in $(seq 1 30); do
    WINID=$(xdotool search --name "Free Falcon 6 Linux Port" 2>/dev/null | head -1)
    [ -n "$WINID" ] && break
    sleep 1
done
[ -z "$WINID" ] && { echo "ERROR: No window"; kill -9 $FFPID 2>/dev/null; exit 1; }
echo "Found window: $WINID (0x$(printf '%x' $WINID))"

echo "Waiting for UI to load..."
sleep 8
snap "$SCREENSHOTS/01_main_menu.png"

# Click Instant Action (724, 740)
echo "Clicking Instant Action at (724, 740)..."
xdotool windowactivate --sync "$WINID" 2>/dev/null
xdotool mousemove --window "$WINID" 724 740; sleep 0.2
xdotool mousedown --window "$WINID" 1; sleep 0.15; xdotool mouseup --window "$WINID" 1
sleep 4

snap "$SCREENSHOTS/02_ia_setup.png"

# Click FLY (150, 740)
echo "Clicking FLY at (150, 740)..."
xdotool mousemove --window "$WINID" 150 740; sleep 0.2
xdotool mousedown --window "$WINID" 1; sleep 0.15; xdotool mouseup --window "$WINID" 1

# Wait for campaign load and sim entry
echo "Waiting for campaign load and sim entry..."
for i in $(seq 1 24); do
    sleep 5
    kill -0 $FFPID 2>/dev/null || { echo "CRASHED at ${i}x5=${((i*5))}s!"; tail -30 "$STDERR_LOG"; exit 1; }
    echo "  ... waited ${i}x5 = $((i*5)) seconds"
done

# Take several screenshots at this point
echo "Taking flight screenshots..."
snap "$SCREENSHOTS/03_flight_120s.png"
sleep 5
snap "$SCREENSHOTS/04_flight_125s.png"

echo ""
echo "=== D3D Diagnostics ==="
echo "--- SetTexture calls ---"
grep "D3D_DIAG.*SetTexture" "$STDERR_LOG" | tail -30
echo ""
echo "--- DrawVerts calls ---"
grep "D3D_DIAG.*DrawVerts" "$STDERR_LOG" | tail -30
echo ""
echo "--- SimFrame summaries ---"
grep "D3D_DIAG.*SimFrame" "$STDERR_LOG" | tail -20
echo ""
echo "--- glTexImage2D errors ---"
grep "D3D_DIAG.*glTexImage2D ERROR" "$STDERR_LOG"
echo ""
echo "--- DDS7_Flip messages ---"
grep "DDS7_Flip" "$STDERR_LOG" | tail -10
echo ""
echo "--- FM messages ---"
grep "\[FM\]" "$STDERR_LOG" | tail -20
echo ""
echo "--- Mode transitions ---"
grep -i "currentMode\|RunningGraphics\|StartRunningGraphics\|mode=" "$STDERR_LOG" | tail -20
echo ""
echo "=== Done. PID=$FFPID ==="
echo "Screenshots: $SCREENSHOTS/"
ls -la "$SCREENSHOTS/"

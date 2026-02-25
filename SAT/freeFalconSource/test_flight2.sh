#!/bin/bash
# Automated test: Launch FFViper, click Instant Action, click TAKEOFF, screenshot
# Uses absolute screen coordinates for SDL2 compatibility
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILDDIR="$SCRIPT_DIR/build"
SCREENSHOTS="/tmp/ffviper_test"
STDERR_LOG="/tmp/ffviper_test_stderr.log"
mkdir -p "$SCREENSHOTS"
rm -f "$SCREENSHOTS"/*

snap() {
    local outfile="$1"
    # Try import (ImageMagick) first, then xwd
    if command -v import &>/dev/null; then
        import -window "$WINID" "$outfile" 2>/dev/null
    elif command -v xwd &>/dev/null; then
        xwd -id "$WINID" -silent > "/tmp/_snap.xwd" 2>/dev/null
        if command -v ffmpeg &>/dev/null; then
            ffmpeg -y -i "/tmp/_snap.xwd" -update 1 "$outfile" 2>/dev/null
        else
            cp "/tmp/_snap.xwd" "${outfile%.png}.xwd"
        fi
        rm -f "/tmp/_snap.xwd"
    fi
    echo "Saved: $(basename $outfile)"
}

# Click at UI coordinates (window-relative), using xdotool absolute screen position
click_at() {
    local ux=$1  # UI X coordinate (0-1024)
    local uy=$2  # UI Y coordinate (0-768)

    # Get window position on screen
    eval $(xdotool getwindowgeometry --shell "$WINID" 2>/dev/null)
    local wx=$X
    local wy=$Y

    # Calculate absolute screen coordinates
    local sx=$((wx + ux))
    local sy=$((wy + uy))

    echo "  Click: UI($ux,$uy) -> Screen($sx,$sy) [window at ($wx,$wy)]"

    # Focus window first
    xdotool windowactivate --sync "$WINID" 2>/dev/null
    xdotool windowfocus --sync "$WINID" 2>/dev/null
    sleep 0.3

    # Move mouse to absolute screen position, then click
    xdotool mousemove --sync $sx $sy
    sleep 0.2
    xdotool click 1
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
sleep 10
snap "$SCREENSHOTS/01_main_menu.png"

# Click Instant Action button at UI coordinates (724, 740)
echo "Clicking Instant Action..."
click_at 724 740
sleep 5
snap "$SCREENSHOTS/02_after_ia_click.png"

# Click TAKEOFF/FLY button - let's check what the IA setup screen shows
# The TAKEOFF button is typically near (150, 740) or the center-bottom area
echo "Clicking TAKEOFF/FLY..."
click_at 150 740
sleep 3

# Also try clicking at common positions for the "COMMIT" or "FLY" button
echo "Clicking FLY/COMMIT at center-bottom..."
click_at 512 740
sleep 2

snap "$SCREENSHOTS/03_after_fly_click.png"

# Wait for campaign load and sim entry
echo "Waiting for campaign load and sim entry..."
for i in $(seq 1 30); do
    sleep 5
    kill -0 $FFPID 2>/dev/null || { echo "CRASHED at $((i*5))s!"; tail -30 "$STDERR_LOG"; exit 1; }
    echo "  ... waited $((i*5)) seconds"

    # Check if we've entered sim mode by looking for mode transitions
    if grep -q "RunningGraphics" "$STDERR_LOG" 2>/dev/null; then
        echo "  *** Detected RunningGraphics mode! ***"
        break
    fi
    if grep -q "FM_START_INSTANTACTION" "$STDERR_LOG" 2>/dev/null; then
        echo "  *** Detected FM_START_INSTANTACTION! ***"
    fi
done

# Take flight screenshots
echo "Taking flight screenshots..."
snap "$SCREENSHOTS/04_flight.png"
sleep 5
snap "$SCREENSHOTS/05_flight_5s.png"

echo ""
echo "=== D3D Diagnostics ==="
echo "--- FM messages ---"
grep "\[FM\]" "$STDERR_LOG" | tail -20
echo ""
echo "--- SimFrame summaries ---"
grep "D3D_DIAG.*SimFrame" "$STDERR_LOG" | tail -20
echo ""
echo "--- Mode transitions ---"
grep -i "currentMode\|RunningGraphics\|StartRunningGraphics\|mode=" "$STDERR_LOG" | tail -20
echo ""
echo "--- SDL Events ---"
grep "SDL_EVENT\|LBUTTON\|mouse" "$STDERR_LOG" | head -20
echo ""
echo "--- Assertions/Errors ---"
grep -i "assert\|error\|fail\|crash" "$STDERR_LOG" | tail -20
echo ""
echo "=== Done. PID=$FFPID ==="
echo "Screenshots: $SCREENSHOTS/"
ls -la "$SCREENSHOTS/"

# Kill the process
kill -9 $FFPID 2>/dev/null

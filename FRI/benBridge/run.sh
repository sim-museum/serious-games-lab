#!/bin/bash
# Launch the Ben Bridge AI
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Pidfile dir for background Claude critiques (see ben_bridge/ui/game_logger.py).
# Polled at script exit so the launcher doesn't move the BDL mid-insert.
CRITIQUE_PID_DIR="/tmp/ben_bridge_critiques_$$"
export CRITIQUE_PID_DIR
mkdir -p "$CRITIQUE_PID_DIR"

if [[ ! -d venv ]]; then
    echo "Error: venv not found. Run install_dependencies.sh first."
    exit 1
fi

source venv/bin/activate

# --- Launch ---

cd ben_bridge
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
python3 main.py "$@" 2>/dev/null
exit_code=$?

if [[ $exit_code -ne 0 ]]; then
    echo ""
    echo "benBridge exited with error code $exit_code"
    echo "Re-run with verbose output:"
    echo "  cd $(pwd) && source ../venv/bin/activate && python3 main.py 2>&1 | head -50"
fi

# --- Wait for any in-flight Claude critiques before the launcher moves files ---
cd "$SCRIPT_DIR"
if [[ -d "$CRITIQUE_PID_DIR" ]]; then
    _wait_deadline=$(( $(date +%s) + 180 ))
    while :; do
        _alive=0
        shopt -s nullglob
        for _pidfile in "$CRITIQUE_PID_DIR"/*.pid; do
            _pid=$(cat "$_pidfile" 2>/dev/null) || { rm -f "$_pidfile"; continue; }
            if [[ -n "$_pid" ]] && kill -0 "$_pid" 2>/dev/null; then
                _alive=1
            else
                rm -f "$_pidfile"
            fi
        done
        shopt -u nullglob
        (( _alive == 0 )) && break
        (( $(date +%s) >= _wait_deadline )) && { echo "Critique wait timed out; continuing." ; break; }
        echo "Waiting for Claude critique to finish..."
        sleep 2
    done
    rmdir "$CRITIQUE_PID_DIR" 2>/dev/null || true
fi

# --- Chain to Q-Plus Bridge for comparison ---
# Find the newest BDL from this session (ben writes .bdl; .pbn/.ppl are derived later)
_newest_bdl=""
_newest_bdl_mod=0
while IFS= read -r -d '' f; do
    fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$_newest_bdl_mod" ]]; then
        _newest_bdl="$f"
        _newest_bdl_mod="$fmod"
    fi
done < <(find "$SCRIPT_DIR/ben/DATA/LOG" -maxdepth 1 -name "*.bdl" -type f -print0 2>/dev/null)

if [[ -n "$_newest_bdl" ]]; then
    echo "Found BDL: $_newest_bdl"
    FRI_DIR="$SCRIPT_DIR"
    HARNESS_DIR="$FRI_DIR/guiHarness"

    # Check if Q-Plus Bridge is installed.  Q-Plus is the comparison
    # target — without it the harness has nothing to do, so we skip BOTH
    # when Q-Plus is missing (rather than launching a dangling harness).
    FRI_WP="$FRI_DIR/WP"
    QBRIDGE_DIR=""
    [[ -d "$FRI_WP/drive_c/games/qbridge17" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge17"
    [[ -z "$QBRIDGE_DIR" && -d "$FRI_WP/drive_c/games/qbridge15" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge15"

    if [[ -z "$QBRIDGE_DIR" ]]; then
        echo "(Q-Plus Bridge not installed under $FRI_WP — skipping harness + Q-Plus.)"
    elif [[ ! -f "$HARNESS_DIR/bridge_harness.py" ]]; then
        echo "(GUI harness not found at $HARNESS_DIR — skipping Q-Plus.)"
    else
        # Q-Plus is installed AND the harness is available — launch them
        # together automatically (no y/N prompt).  The harness is what
        # converts the Q-Plus output back into a BEN-readable BDL after
        # the user finishes the closed-room replay, so the two need to
        # come up at the same time.
        echo ""
        echo "Launching Q-Plus Bridge and GUI Harness..."
        echo "Use the Comparison Workflow tab (source is pre-loaded from BEN Bridge)."
        echo "  1. In Q-Plus: Own Deals → Enter, then click 'Enter into Q-Plus' in harness"
        echo "  2. Play the hand in Q-Plus — do NOT exit Q-Plus yet"
        echo "  3. In harness: click 'Auto-detect latest' to find Q-Plus log"
        echo "  4. In harness: click 'Convert & copy' to save and annotate with Claude"
        echo "  5. Exit Q-Plus"
        echo ""

        # Make sure the wine prefix is registered against winxp so Q-Plus
        # behaves the same way as the manually-launched version. This was
        # done before launching wine directly; the harness now spawns
        # wine internally, but the registry key still has to be in place.
        export WINEPREFIX="$FRI_WP"
        export WINEARCH=win32
        wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

        # Launch the harness (foreground — blocks until the user closes
        # it). The harness now auto-launches Q-Plus on startup, so we
        # don't run wine directly here any more.
        (
            cd "$HARNESS_DIR"
            if [[ -d venv ]]; then
                source venv/bin/activate
            else
                python3 -m venv venv && source venv/bin/activate
                pip install -q PyQt5 pyautogui 2>/dev/null
            fi
            python3 bridge_harness.py \
                --source "$(realpath "$_newest_bdl")" \
                --game benbridge 2>/dev/null
        )
        cd "$SCRIPT_DIR"
    fi
else
    echo "(No BDL found in $SCRIPT_DIR/ben/DATA/LOG/ — skipping Q-Plus comparison)"
fi

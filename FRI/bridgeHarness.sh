#!/bin/bash
# Launch the Bridge Harness GUI for Q-Plus Bridge hand entry and comparison.
# Creates the Python venv and installs dependencies if needed.

cd "$(dirname "${BASH_SOURCE[0]}")"
HARNESS_DIR="$PWD/guiHarness"
VENV="$HARNESS_DIR/venv"

# Use the same Lutris wine runner the regular launcher uses for
# qplus.sh. Without this the harness picked up /usr/bin/wine, which
# rendered Q-Plus's Hand Input dialog with empty boxes where the card
# glyphs should be (font / dxvk mismatch).  config/wine_runners.csv
# pins qplus.sh to lutris-6.21-6-x86_64; sourcing wine_runner.sh
# prepends the runner's bin/ to PATH and sets WINE/WINESERVER/etc.
export REPO_ROOT="$(cd "$PWD/.." && pwd)"
export SGL_GAME_SCRIPT="qplus.sh"
if [ -f "$REPO_ROOT/launcher/lib/wine_runner.sh" ]; then
    # shellcheck source=/dev/null
    . "$REPO_ROOT/launcher/lib/wine_runner.sh"
fi

# Create venv and install packages if missing
if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

if ! "$VENV/bin/python" -c "import PyQt5, pyautogui" 2>/dev/null; then
    echo "Installing dependencies..."
    "$VENV/bin/pip" install --quiet PyQt5 pyautogui
fi

cd "$HARNESS_DIR"
exec "$VENV/bin/python" bridge_harness.py "$@"

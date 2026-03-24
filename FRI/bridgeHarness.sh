#!/bin/bash
# Launch the Bridge Harness GUI for Q-Plus Bridge hand entry and comparison.
# Creates the Python venv and installs dependencies if needed.

cd "$(dirname "${BASH_SOURCE[0]}")"
HARNESS_DIR="$PWD/guiHarness"
VENV="$HARNESS_DIR/venv"

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

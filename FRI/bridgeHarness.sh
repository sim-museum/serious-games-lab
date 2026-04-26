#!/bin/bash
# Launch the Bridge Harness GUI for Q-Plus Bridge hand entry and comparison.
# Creates the Python venv and installs dependencies if needed.

cd "$(dirname "${BASH_SOURCE[0]}")"
HARNESS_DIR="$PWD/guiHarness"
VENV="$HARNESS_DIR/venv"

# pyautogui imports python-Xlib, which needs an X11 auth cookie with an
# explicit display number. On Wayland, Mutter writes its Xwayland cookie to
# /run/user/$UID/.mutter-Xwaylandauth.* with an empty display-number field --
# C Xlib treats that as wildcard but python-Xlib does not, so we rebuild a
# normalized cookie file with an explicit ":0" entry.
RUNDIR="/run/user/$(id -u)"
if [ -z "$XAUTHORITY" ] || [ ! -r "$XAUTHORITY" ]; then
    for xauth in "$RUNDIR"/.mutter-Xwaylandauth.* "$RUNDIR"/xauth_* "$HOME/.Xauthority"; do
        if [ -r "$xauth" ]; then
            export XAUTHORITY="$xauth"
            break
        fi
    done
fi
if command -v xauth >/dev/null 2>&1 && [ -r "$XAUTHORITY" ]; then
    NORMALIZED="$RUNDIR/bridgeHarness-xauth"
    COOKIE=$(xauth -f "$XAUTHORITY" list 2>/dev/null | awk '/MIT-MAGIC-COOKIE-1/ {print $3; exit}')
    if [ -n "$COOKIE" ]; then
        rm -f "$NORMALIZED"
        xauth -f "$NORMALIZED" add "${DISPLAY:-:0}" MIT-MAGIC-COOKIE-1 "$COOKIE" 2>/dev/null \
            && export XAUTHORITY="$NORMALIZED"
    fi
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

#!/bin/bash
# Keep GNOME's Xwayland input-emulation session alive.
#
# Under GNOME 50 / Wayland, synthetic X input (xdotool / XTest) reaches the
# screen only through a compositor session that the user approves once
# ("screen share" consent dialog). That session is torn down after synthetic
# input goes idle for a while, after which every harness click silently
# vanishes until the user approves again (seen 2026-09-24/25 between runs).
# A zero-pixel relative pointer move every INTERVAL seconds is enough activity
# to keep it alive and is invisible to the user.
#
# Usage: xtest_keepalive.sh [INTERVAL]    (runs until killed; biq-panel starts
#        it and stops it on exit)
INTERVAL="${1:-25}"
export DISPLAY="${DISPLAY:-:0}"
while true; do
    xdotool mousemove_relative -- 0 0 2>/dev/null
    sleep "$INTERVAL"
done

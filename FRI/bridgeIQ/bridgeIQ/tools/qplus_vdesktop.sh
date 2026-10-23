#!/bin/bash
# Turn Wine's VIRTUAL DESKTOP on/off for the Q-Plus prefix.
#
# Why: under GNOME 50 / Xwayland, Wine never learns that the compositor moved
# the Q-Plus window, so it keeps placing menus and dialogs where the window
# USED to be (e.g. on the other monitor) and every harness click into a dialog
# misses. Inside a virtual desktop all Q-Plus windows are children of ONE X
# window that Wine lays out itself, so their positions stay consistent.
#
# The harness turns it ON when it launches the Q-Plus server
# (tools/qplus_dual_instance.sh server); FRI/qplus.sh (hand play) turns it OFF.
#
# Usage: qplus_vdesktop.sh on [WxH] | off | status
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WINEPREFIX="${WINEPREFIX:-$(cd "$HERE/../../.." && pwd)/WP}"
unset WINEARCH
WINE="${WINE_BIN_SERVER:-}"
if [ -z "$WINE" ]; then
    if [ -x /usr/bin/wine32 ]; then WINE=/usr/bin/wine32; else WINE=wine; fi
fi
SIZE="${2:-1920x1080}"
case "${1:-status}" in
  on)
    "$WINE" reg add 'HKCU\Software\Wine\Explorer' /v Desktop /t REG_SZ /d Default /f >/dev/null 2>&1
    "$WINE" reg add 'HKCU\Software\Wine\Explorer\Desktops' /v Default /t REG_SZ /d "$SIZE" /f >/dev/null 2>&1
    echo "[vdesktop] ON ($SIZE) for $WINEPREFIX" ;;
  off)
    "$WINE" reg delete 'HKCU\Software\Wine\Explorer' /v Desktop /f >/dev/null 2>&1
    echo "[vdesktop] OFF for $WINEPREFIX" ;;
  status)
    "$WINE" reg query 'HKCU\Software\Wine\Explorer' /v Desktop 2>/dev/null | grep -q Default && echo on || echo off ;;
esac

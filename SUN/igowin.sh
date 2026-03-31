#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
INSTALL_DIR="$PWD/INSTALL"
# Set Windows XP mode silently (no GUI)
mkdir -p "$WINEPREFIX"
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# Set up KataGo for post-game analysis
source "$SCRIPT_DIR/ensure_katago.sh"
source "$SCRIPT_DIR/analyze_new_sgf.sh"

# Snapshot SGF files and touch game-started marker
snapshot_sgf_files
if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
    touch "$SGL_GAME_STARTED_MARKER"
fi

cd "$INSTALL_DIR/igowin"
wine igowin.exe 2>/dev/null 1>/dev/null

# Run KataGo analysis on any new SGF files
cd "$SCRIPT_DIR"
analyze_new_sgf_files


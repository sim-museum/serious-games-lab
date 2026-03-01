#!/bin/bash

# Scid - Shane's Chess Information Database
# Try native scid first (apt-installed), fall back to Wine version
# Builds lc0 from source if not present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "The first time you run Scid you should specify the path to the lc0 chess engine."
echo "From the menu select Tools/Analysis Engine.../New and specify the name and path for the lc0 executable."
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "The Linux version of lc0 is $SCRIPT_DIR/INSTALL/lc0_cpu"
else
    echo ""
    echo "lc0 engine not found. Building from source..."
    bash "$SCRIPT_DIR/install_lc0.sh"
    if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
        echo ""
        echo "lc0 built successfully: $SCRIPT_DIR/INSTALL/lc0_cpu"
    fi
fi
echo ""

if command -v scid &>/dev/null; then
    cd "$SCRIPT_DIR/INSTALL" 2>/dev/null || cd "$SCRIPT_DIR"
    clear
    scid 2>/dev/null 1>/dev/null
    clear
    echo -e "Scid optional scripts:\n\nRandomly choose opening book move (to practice different positions):\ngrandmasterOpeningMove.sh\n\n"
else
    # Fall back to Wine version if available
    export WINEPREFIX="$SCRIPT_DIR/WP"
    if [[ -f "$WINEPREFIX/drive_c/Scid-4.7.0/bin/scid.exe" ]]; then
        export WINEARCH=win32
        # Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
        cd "$SCRIPT_DIR/INSTALL" 2>/dev/null || cd "$SCRIPT_DIR"
        clear
        wine "$WINEPREFIX/drive_c/Scid-4.7.0/bin/scid.exe" 2>/dev/null 1>/dev/null
        clear
        echo -e "Scid optional scripts:\n\nRandomly choose opening book move (to practice different positions):\ngrandmasterOpeningMove.sh\n\n"
    else
        echo "scid not found. Install with: sudo apt install scid"
    fi
fi

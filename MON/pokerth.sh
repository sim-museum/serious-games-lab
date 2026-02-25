#!/bin/bash

# PokerTH - Texas Hold'em poker game
# Try apt-installed pokerth first, fall back to INSTALL/ binary

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v pokerth &>/dev/null; then
    pokerth 2>/dev/null 1>/dev/null
elif [[ -x "$SCRIPT_DIR/INSTALL/PokerTH-1.1.2/pokerth" ]]; then
    install_dir="$SCRIPT_DIR/INSTALL/PokerTH-1.1.2"
    LD_LIBRARY_PATH="$install_dir/libs"
    export LD_LIBRARY_PATH
    export QT_QPA_FONTDIR="$install_dir/data/fonts"
    "$install_dir/pokerth" 2>/dev/null 1>/dev/null
else
    echo "pokerth not found."
    echo ""
    echo "Install with: sudo apt install pokerth"
fi

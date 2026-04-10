#!/bin/bash

# PokerTH - Texas Hold'em poker game
# Try apt-installed pokerth first, fall back to INSTALL/ binary

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clean up old log files from previous sessions (afterGameReport already collected them)
rm -f "$HOME/.pokerth/log-files/"pokerth-log*.pdb 2>/dev/null
rm -f "$HOME/.pokerth/log-files/"pokerth-log*.txt 2>/dev/null

snapshot_time=$(date +%s)

if command -v pokerth &>/dev/null; then
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    pokerth 2>/dev/null 1>/dev/null
elif [[ -x "$SCRIPT_DIR/INSTALL/PokerTH-1.1.2/pokerth" ]]; then
    install_dir="$SCRIPT_DIR/INSTALL/PokerTH-1.1.2"
    LD_LIBRARY_PATH="$install_dir/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export LD_LIBRARY_PATH
    export QT_QPA_FONTDIR="$install_dir/data/fonts"
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    "$install_dir/pokerth"
else
    echo "pokerth not found."
    echo ""
    echo "Install with: sudo apt install pokerth"
    exit 1
fi

# Find the most recent PokerTH log file from this session and annotate with Claude
source "$SCRIPT_DIR/claude_annotate_poker.sh"
_newest_pdb=""
_newest_mod=0
for search_dir in "$HOME/.pokerth/log-files" "$HOME" "$SCRIPT_DIR"; do
    [[ -d "$search_dir" ]] || continue
    while IFS= read -r -d '' log_file; do
        fmod=$(stat -c %Y "$log_file" 2>/dev/null) || continue
        if [[ "$fmod" -gt "$snapshot_time" && "$fmod" -gt "$_newest_mod" ]]; then
            _newest_mod="$fmod"
            _newest_pdb="$log_file"
        fi
    done < <(find "$search_dir" -maxdepth 5 \( -name "pokerth-log*" -o -name "PokerTH*Log*" \) -type f -print0 2>/dev/null)
done
if [[ -n "$_newest_pdb" ]]; then
    claude_annotate_poker "$_newest_pdb"
fi

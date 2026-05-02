#!/bin/bash

# PokerTH - Texas Hold'em poker game
# Modern Debian/Ubuntu PokerTH 2.x ships the binary as pokerth_client
# in /usr/games/. Older releases used the name pokerth. The bundled
# INSTALL/PokerTH-1.1.2/ binary ships its own libdrm/libGL from ~2014
# that crashes on modern NVIDIA libnvidia-egl-gbm.so.1 ("undefined
# symbol: drmGetDevices2"), so it's only a last-resort fallback.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure /usr/games is on PATH when this script is run directly
# (Ubuntu 26.04 dropped /usr/games from the default profile PATH).
case ":$PATH:" in
    *":/usr/games:"*) ;;
    *) PATH="$PATH:/usr/games" ;;
esac

# Clean up old log files from previous sessions (afterGameReport already collected them)
rm -f "$HOME/.pokerth/log-files/"pokerth-log*.pdb 2>/dev/null
rm -f "$HOME/.pokerth/log-files/"pokerth-log*.txt 2>/dev/null

snapshot_time=$(date +%s)

pokerth_bin=
for cand in pokerth_client pokerth; do
    if command -v "$cand" &>/dev/null; then
        pokerth_bin=$cand
        break
    fi
done

REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"

if [[ -n "$pokerth_bin" ]]; then
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    capture_marker_epoch
    "$pokerth_bin" 2>/dev/null 1>/dev/null
elif [[ -x "$SCRIPT_DIR/INSTALL/PokerTH-1.1.2/pokerth" ]]; then
    install_dir="$SCRIPT_DIR/INSTALL/PokerTH-1.1.2"
    LD_LIBRARY_PATH="$install_dir/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export LD_LIBRARY_PATH
    export QT_QPA_FONTDIR="$install_dir/data/fonts"
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    capture_marker_epoch
    "$install_dir/pokerth"
else
    echo "pokerth not found."
    echo ""
    echo "Install with: sudo apt install pokerth"
    exit 1
fi

# Find the most recent PokerTH log file from this session.  Move it into
# the timestamped afterGameReport subdir BEFORE running Claude annotation
# so a concurrent game's collect_after_game_report can't grab it
# mid-annotation.
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
    report_subdir="$(post_game_subdir "$SCRIPT_DIR" pokerth)"
    target="$report_subdir/$(basename "$_newest_pdb")"
    cp "$_newest_pdb" "$target"
    source "$SCRIPT_DIR/claude_annotate_poker.sh"
    claude_annotate_poker "$target"
    echo "  Annotated PokerTH log saved to afterGameReport/$(basename "$report_subdir")/"
fi

restore_marker_epoch

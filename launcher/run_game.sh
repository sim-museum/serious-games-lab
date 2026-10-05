#!/usr/bin/env bash
# run_game.sh - Dispatches to source game scripts or Lutris.
# Applies Rowan fixes for MigAlley/BattleOfBritain before launch.
#
# Usage: run_game.sh <game_name>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <game_name>"
    echo ""
    echo "Source games: bridgeIQ, mathquiz, dual_nback, chess, go, katrain, poker, freefalcon"
    echo "Binary games: Use the Lutris name from the CSV"
    exit 1
fi

GAME_NAME="$1"
shift

# Rowan games that need Wine fixes applied before launch
ROWAN_GAMES=("MA" "battle of britain")

apply_rowan_fixes() {
    local game="$1"
    echo "Applying Rowan game Wine fixes for: $game"
    if [[ -x "$REPO_ROOT/scripts/fix_rowan_games.sh" ]]; then
        "$REPO_ROOT/scripts/fix_rowan_games.sh" "$game"
    else
        echo "Warning: fix_rowan_games.sh not found or not executable"
    fi
}

# Backlog 26 (2026-10-05): the Serious Games Week matchmaker only matches two copies built from the same commit. The
# sgw client sends $SGW_BUILD with every announce and list; for a game run from this checkout it is the repository's
# commit, plus "-dirty" when that game's Python sources differ from it (game logs and settings do not count).
sgw_build_for() {
    [ -n "${SGW_BUILD:-}" ] && return
    local b
    b=$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null) || return
    git -C "$REPO_ROOT" diff --quiet HEAD -- ":(glob)$1/**/*.py" 2>/dev/null || b="$b-dirty"
    export SGW_BUILD="$b"
}

case "$GAME_NAME" in
    bridge)
        sgw_build_for FRI/bridgeIQ
        cd "$REPO_ROOT/FRI/bridgeIQ" && source venv/bin/activate && python3 main.py "$@"
        ;;
    claudemath)
        cd "$REPO_ROOT/FRI/mathQuiz" && source venv/bin/activate && python3 main.py "$@"
        ;;
    dual_nback)
        cd "$REPO_ROOT/FRI/dual_nback" && source venv/bin/activate && python3 main.py "$@"
        ;;
    chess)
        cd "$REPO_ROOT/WED/openingRepertoire" && source venv/bin/activate && python3 OpeningRepertoire.py "$@"
        ;;
    go)
        exec "$REPO_ROOT/SUN/run_human_like_go_gui.sh" "$@"
        ;;
    katrain)
        exec "$REPO_ROOT/SUN/run_katrain.sh" "$@"
        ;;
    poker)
        sgw_build_for MON/pokerIQ
        cd "$REPO_ROOT/MON/pokerIQ" && source venv/bin/activate && python3 main.py "$@"
        ;;
    freefalcon)
        cd "$REPO_ROOT/SAT/freeFalconSource"
        echo "FreeFalcon source directory. Build/run per project instructions."
        ;;
    MA|"mig alley"|migalley)
        apply_rowan_fixes "MA"
        lutris lutris:rungame/ma 2>/dev/null || echo "Launch MiG Alley via Lutris GUI."
        ;;
    "battle of britain"|bob)
        apply_rowan_fixes "battle of britain"
        lutris lutris:rungame/battle-of-britain 2>/dev/null || echo "Launch Battle of Britain via Lutris GUI."
        ;;
    *)
        # Try Lutris for any other game
        safe_name=$(echo "$GAME_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-')
        echo "Attempting to launch '$GAME_NAME' via Lutris..."
        lutris "lutris:rungame/$safe_name" 2>/dev/null || echo "Game '$GAME_NAME' not found. Check 'main_launcher.sh' for available games."
        ;;
esac

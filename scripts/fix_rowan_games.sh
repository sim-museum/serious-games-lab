#!/usr/bin/env bash
# fix_rowan_games.sh - Applies Wine registry fixes for Rowan Software games
# (MiG Alley, Battle of Britain) based on the Rowan games analysis.
#
# Fixes applied:
#   - Virtual desktop 1024x768
#   - Windows XP compatibility mode
#   - DirectDraw renderer = opengl
#   - FBO offscreen rendering
#   - GDI surface type
#   - mfc42 via winetricks
#   - Disable window decorations
#
# Usage: fix_rowan_games.sh [game_name]
#   game_name: "MA" for MiG Alley, "battle of britain" for BoB
#   If no args, fixes all known Rowan games.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

fix_wine_prefix() {
    local prefix="$1"
    local game_name="$2"

    if [[ ! -d "$prefix" ]]; then
        echo "Wine prefix not found: $prefix"
        echo "  Install the game first, then run this script."
        return 1
    fi

    export WINEPREFIX="$prefix"
    export WINEARCH=win32

    echo "Applying Wine fixes for $game_name..."
    echo "  Wine prefix: $prefix"

    # Set Windows XP compatibility mode
    echo "  Setting Windows XP mode..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v "Version" /t REG_SZ /d "winxp" /f 2>/dev/null || true

    # Enable virtual desktop 1024x768
    echo "  Enabling virtual desktop (1024x768)..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Explorer\\Desktops" /v "Default" /t REG_SZ /d "1024x768" /f 2>/dev/null || true

    # DirectDraw renderer = opengl
    echo "  Setting DirectDraw renderer to OpenGL..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Direct3D" /v "DirectDrawRenderer" /t REG_SZ /d "opengl" /f 2>/dev/null || true

    # FBO offscreen rendering
    echo "  Setting offscreen rendering mode to FBO..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Direct3D" /v "OffscreenRenderingMode" /t REG_SZ /d "fbo" /f 2>/dev/null || true

    # GDI surface type
    echo "  Setting DirectDraw surface type to GDI..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\DirectDraw" /v "DefaultSurfaceType" /t REG_SZ /d "gdi" /f 2>/dev/null || true

    # Disable window decorations
    echo "  Disabling window decorations..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v "Decorated" /t REG_SZ /d "N" /f 2>/dev/null || true

    # Install mfc42 via winetricks
    echo "  Installing mfc42 via winetricks..."
    if command -v winetricks &>/dev/null; then
        winetricks -q mfc42 2>/dev/null || echo "    Warning: mfc42 installation may have failed"
    else
        echo "    Warning: winetricks not found. Install with: sudo apt install winetricks"
    fi

    echo "  Fixes applied for $game_name."
    echo ""
}

TARGET="${1:-all}"

case "$TARGET" in
    MA|"mig alley"|migalley)
        # MiG Alley wine prefix
        MA_PREFIX="$REPO_ROOT/TUE/MigAlley/WP"
        fix_wine_prefix "$MA_PREFIX" "MiG Alley"
        ;;
    "battle of britain"|bob|BoB)
        # Battle of Britain wine prefix
        BOB_PREFIX="$REPO_ROOT/TUE/BattleOfBritain/WP"
        fix_wine_prefix "$BOB_PREFIX" "Battle of Britain"
        ;;
    all)
        echo "Applying fixes to all known Rowan games..."
        echo ""
        MA_PREFIX="$REPO_ROOT/TUE/MigAlley/WP"
        BOB_PREFIX="$REPO_ROOT/TUE/BattleOfBritain/WP"
        if [[ -d "$MA_PREFIX" ]]; then
            fix_wine_prefix "$MA_PREFIX" "MiG Alley"
        else
            echo "MiG Alley not installed (prefix not found at $MA_PREFIX)"
        fi
        if [[ -d "$BOB_PREFIX" ]]; then
            fix_wine_prefix "$BOB_PREFIX" "Battle of Britain"
        else
            echo "Battle of Britain not installed (prefix not found at $BOB_PREFIX)"
        fi
        ;;
    *)
        echo "Unknown game: $TARGET"
        echo "Usage: $0 [MA|bob|all]"
        exit 1
        ;;
esac

echo "Rowan game fixes complete."

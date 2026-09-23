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
#   - mfc42 (via scripts/install_mfc42.sh)
#   - Disable window decorations
#
# Usage: fix_rowan_games.sh [game_name]
#   game_name: "MA" for MiG Alley, "battle of britain" for BoB
#   If no args, fixes all known Rowan games.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Hard-bind to a specific Lutris wine runner. The Rowan prefixes are 32-bit,
# and Ubuntu 26.04's system wine (v10) runs in wow64 mode and rejects
# WINEARCH=win32 — so falling through to /usr/bin/wine would silently fail.
# Refuse to proceed unless the matching runner is actually installed.
setup_wine_runner() {
    local runner_name="$1"
    local runner_dir="$HOME/.local/share/lutris/runners/wine/$runner_name"
    if [[ ! -x "$runner_dir/bin/wine" ]]; then
        echo "ERROR: Lutris wine runner '$runner_name' not installed at $runner_dir" >&2
        echo "       Refusing to use system wine (v10/wow64) on a 32-bit prefix." >&2
        echo "       Install runners with: sudo $REPO_ROOT/install.sh" >&2
        return 1
    fi
    export PATH="$runner_dir/bin:$PATH"
    export WINE="$runner_dir/bin/wine"
    export WINELOADER="$runner_dir/bin/wine"
    export WINESERVER="$runner_dir/bin/wineserver"
    export LD_LIBRARY_PATH="$runner_dir/lib64:$runner_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export WINEDLLPATH="$runner_dir/lib64/wine/x86_64-unix:$runner_dir/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"
}

fix_wine_prefix() {
    local prefix="$1"
    local game_name="$2"
    local runner_name="$3"

    if [[ ! -d "$prefix" ]]; then
        echo "Wine prefix not found: $prefix"
        echo "  Install the game first, then run this script."
        return 1
    fi

    setup_wine_runner "$runner_name" || return 1

    export WINEPREFIX="$prefix"

    echo "Applying Wine fixes for $game_name..."
    echo "  Wine prefix: $prefix"
    echo "  Wine runner: $runner_name"

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

    # Install mfc42. Not a bare `winetricks mfc42` — that step is fragile on a
    # fresh prefix; see scripts/install_mfc42.sh for the why.
    echo "  Installing mfc42..."
    "$SCRIPT_DIR/install_mfc42.sh" "$prefix" \
        || echo "    Warning: mfc42 installation failed"

    echo "  Fixes applied for $game_name."
    echo ""
}

TARGET="${1:-all}"

# Per-game Lutris runner — must match config/wine_runners.csv so the prefix
# is touched by the same wine version that created it.
MA_RUNNER="lutris-5.21-x86_64"
BOB_RUNNER="lutris-5.7-x86_64"

case "$TARGET" in
    MA|"mig alley"|migalley)
        # MiG Alley wine prefix
        MA_PREFIX="$REPO_ROOT/TUE/MigAlley/WP"
        fix_wine_prefix "$MA_PREFIX" "MiG Alley" "$MA_RUNNER"
        ;;
    "battle of britain"|bob|BoB)
        # Battle of Britain wine prefix
        BOB_PREFIX="$REPO_ROOT/TUE/BattleOfBritain/WP"
        fix_wine_prefix "$BOB_PREFIX" "Battle of Britain" "$BOB_RUNNER"
        ;;
    all)
        echo "Applying fixes to all known Rowan games..."
        echo ""
        MA_PREFIX="$REPO_ROOT/TUE/MigAlley/WP"
        BOB_PREFIX="$REPO_ROOT/TUE/BattleOfBritain/WP"
        if [[ -d "$MA_PREFIX" ]]; then
            fix_wine_prefix "$MA_PREFIX" "MiG Alley" "$MA_RUNNER"
        else
            echo "MiG Alley not installed (prefix not found at $MA_PREFIX)"
        fi
        if [[ -d "$BOB_PREFIX" ]]; then
            fix_wine_prefix "$BOB_PREFIX" "Battle of Britain" "$BOB_RUNNER"
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

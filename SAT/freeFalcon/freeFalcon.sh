#!/bin/bash
# freeFalcon.sh - Install and run FreeFalcon 6 under Wine
#
# A native Linux port (alpha) can be built separately with:
#   ./buildFFViper.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"
WINEPREFIX_DIR="$SCRIPT_DIR/WP"
GAME_DATA="$WINEPREFIX_DIR/drive_c/FreeFalcon6"

# --- Wine runner pin: lutris-GE-Proton8-26-x86_64 (wine 8.0 staging, GE) ---
# History: system wine 10 (wow64) can't boot this 32-bit prefix at all;
# lutris-9.22-staging detected the joystick but the setup screen locked up.
# Wine-GE 8 boots the prefix and the game enumerates the stick via DirectInput8
# (verified: dinput "found device ... Logitech Extreme 3D" + CreateDevice).
RUNNER_NAME="lutris-GE-Proton8-26-x86_64"
RUNNER_DIR="$HOME/.local/share/lutris/runners/wine/$RUNNER_NAME"
if [[ ! -x "$RUNNER_DIR/bin/wine" ]]; then
    echo "ERROR: Lutris wine runner '$RUNNER_NAME' not installed at $RUNNER_DIR" >&2
    echo "       Install it: sudo $(cd "$SCRIPT_DIR/../.." && pwd)/install.sh" >&2
    exit 1
fi
export PATH="$RUNNER_DIR/bin:$PATH"
export WINE="$RUNNER_DIR/bin/wine"
export WINELOADER="$RUNNER_DIR/bin/wine"
export WINESERVER="$RUNNER_DIR/bin/wineserver"
export LD_LIBRARY_PATH="$RUNNER_DIR/lib64:$RUNNER_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WINEDLLPATH="$RUNNER_DIR/lib64/wine/x86_64-unix:$RUNNER_DIR/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"

export WINEPREFIX="$WINEPREFIX_DIR"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# ── Install if not present ─────────────────────────────────────────────

if [[ ! -d "$GAME_DATA" ]]; then
    if ! command -v wine &>/dev/null; then
        echo "Error: Wine is not installed."
        echo "  Install with:  sudo apt install wine wine32:i386 wine64 winetricks"
        echo "  Or re-run the launcher — it auto-installs Wine when sglBinaries are present."
        exit 1
    fi

    if [[ ! -d "$INSTALL_DIR/FF6d" ]]; then
        echo "Error: FreeFalcon installer not found at $INSTALL_DIR/FF6d"
        echo "  Make sure sglBinaries_1 has been extracted."
        exit 1
    fi

    echo ""
    echo "FreeFalcon game data not found. Installing..."
    echo ""

    echo "Step 1 of 4: Installing Free Falcon 6"
    echo "When you reach the final install screen, deselect 'Launch Free Falcon 6 Config Editor'"
    echo ""
    cd "$INSTALL_DIR/FF6d"
    wine FreeFalcon6.0_Installer.exe 2>/dev/null 1>/dev/null

    echo ""
    echo "Step 2 of 4: Installing Cockpit art"
    echo ""
    cd "$INSTALL_DIR/FF6_FreeFalcon5_Cockpit_Pack_www.g4g.it/FreeFalcon5_Cockpit_Pack"
    wine 'FreeFalcon5 Cockpit Pack v1.5.exe' 2>/dev/null 1>/dev/null

    echo ""
    echo "Step 3 of 4: Installing Israel Theater"
    echo ""
    cd "$INSTALL_DIR/FF6_ITOv4c_www.g4g.it/ITO V4c"
    wine 'ITO2 V4c.exe' 2>/dev/null 1>/dev/null

    echo ""
    echo "Step 4 of 4: Installing Balkans Theater"
    echo ""
    cd "$INSTALL_DIR/FF6_Balkans3_www.g4g.it/BalkansFF6-3/"
    wine 'Balkans 2.exe' 2>/dev/null 1>/dev/null

    if [[ ! -d "$GAME_DATA" ]]; then
        echo ""
        echo "Error: Installation did not create $GAME_DATA"
        echo "  Something went wrong with the Wine installers."
        exit 1
    fi

    # Post-install configuration
    echo ""
    echo "Configuring game data..."

    # Remove outdated documentation (ignore if missing)
    rm -f "$GAME_DATA/_the_MANUAL/FF6 COMPANION_v.5.5.pdf"

    # Move movie directories (they crash the game under Wine)
    [[ -d "$GAME_DATA/movies" ]] && mv "$GAME_DATA/movies" "$GAME_DATA/movies_DoNotPlayInGame"
    [[ -d "$GAME_DATA/Theaters/Israel/movies" ]] && mv "$GAME_DATA/Theaters/Israel/movies" "$GAME_DATA/Theaters/Israel/movies_DoNotPlayInGame"

    # Copy optimized config and fix breathing sound
    cp "$INSTALL_DIR/mods/ffviper.cfg" "$GAME_DATA/"
    cp "$GAME_DATA/F4Patch/FFViper/pit/Breathing/BreathingOff/EnviroControlSys.wav" "$GAME_DATA/sounds/" 2>/dev/null || true
    cp "$GAME_DATA/F4Patch/FFViper/pit/Breathing/BreathingOff/EnviroControlSys.wav" "$GAME_DATA/F4Patch/Persist/Breathing/" 2>/dev/null || true

    # Add saved campaigns to the Israeli classic theater
    if [[ -d "$INSTALL_DIR/mods/israeliClassicSavedCampaigns" ]]; then
        rsync -a "$INSTALL_DIR/mods/israeliClassicSavedCampaigns/" "$GAME_DATA/Theaters/Israel_Classic/campaign/"
    fi

    echo "Game data installation complete."
fi

# ── Launch FreeFalcon under Wine ───────────────────────────────────────

echo ""
echo "Launching FreeFalcon 6..."
echo ""
cd "$GAME_DATA"
# Mark game start so afterGamesReport only collects files from gameplay, not install
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
wine explorer /desktop=FreeFalcon,1024x768 FFViper.exe 2>/dev/null 1>/dev/null

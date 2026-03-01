#!/bin/bash
# freeFalcon.sh - Install game data (via Wine) and run native Linux FFViper
#
# Flow:
#   1. If game data not installed: run Wine installers to extract game data
#   2. If native binary not built: build FFViper from source
#   3. Launch native Linux FFViper pointing at the game data

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"
WINEPREFIX_DIR="$SCRIPT_DIR/WP"
GAME_DATA="$WINEPREFIX_DIR/drive_c/FreeFalcon6"
SOURCE_DIR="$SCRIPT_DIR/freeFalconSource"
BUILD_DIR="$SOURCE_DIR/build"
FFVIPER_BIN="$BUILD_DIR/src/ffviper/FFViper"

# ── Step 1: Install game data via Wine if not present ──────────────────

install_game_data() {
    if ! command -v wine &>/dev/null; then
        echo "Error: Wine is not installed. Wine is needed to run the FreeFalcon"
        echo "installers that extract the game data files."
        echo ""
        echo "  Install with:  sudo apt install wine wine32:i386 wine64 winetricks"
        echo "  Or re-run the launcher — it auto-installs Wine when sglBinaries are present."
        return 1
    fi

    if [[ ! -d "$INSTALL_DIR/FF6d" ]]; then
        echo "Error: FreeFalcon installer not found at $INSTALL_DIR/FF6d"
        echo "  Make sure sglBinaries_1 has been extracted."
        return 1
    fi

    echo ""
    echo "FreeFalcon game data not found. Installing via Wine..."
    echo "(Wine is only used for installation — the game itself runs natively on Linux.)"
    echo ""

    export WINEPREFIX="$WINEPREFIX_DIR"
    export WINEARCH=win32
    wine winecfg -v winxp 2>/dev/null 1>/dev/null

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
        return 1
    fi

    # Post-install configuration
    echo ""
    echo "Configuring game data..."

    # Remove outdated documentation (ignore if missing)
    rm -f "$GAME_DATA/_the_MANUAL/FF6 COMPANION_v.5.5.pdf"

    # Move movie directories (Wine can't play them; they crash the game)
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
    return 0
}

# ── Step 2: Build FFViper from source if not present ───────────────────

build_ffviper() {
    if [[ ! -d "$SOURCE_DIR" ]]; then
        echo "Error: FreeFalcon source not found at $SOURCE_DIR"
        return 1
    fi

    echo ""
    echo "Building FFViper from source..."
    echo ""

    # Install build dependencies if needed
    local BUILD_DEPS=(libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev
                      libgl-dev libglew-dev libopenal-dev
                      cmake ninja-build build-essential)
    local MISSING=()
    for pkg in "${BUILD_DEPS[@]}"; do
        if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
            MISSING+=("$pkg")
        fi
    done
    if [[ ${#MISSING[@]} -gt 0 ]]; then
        echo "Installing build dependencies: ${MISSING[*]}"
        sudo apt-get install -y "${MISSING[@]}"
    fi

    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    cmake -G Ninja -DCMAKE_BUILD_TYPE=Release "$SOURCE_DIR"
    ninja

    if [[ ! -x "$FFVIPER_BIN" ]]; then
        echo ""
        echo "Error: Build failed — $FFVIPER_BIN not found."
        echo "  Check the build output above for errors."
        return 1
    fi

    echo ""
    echo "FFViper built successfully."
    return 0
}

# ── Main ───────────────────────────────────────────────────────────────

cd "$SCRIPT_DIR"

# Ensure game data is installed
if [[ ! -d "$GAME_DATA" ]]; then
    install_game_data || exit 1
fi

# Ensure native binary is built
if [[ ! -x "$FFVIPER_BIN" ]]; then
    build_ffviper || exit 1
fi

# Launch native FFViper with game data path
echo ""
echo "Launching FFViper (native Linux)..."
echo "  Data: $GAME_DATA"
echo ""
cd "$GAME_DATA"
"$FFVIPER_BIN" -d "$GAME_DATA" -w 2>/dev/null

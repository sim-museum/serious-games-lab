#!/bin/bash
# Republic: The Revolution (2003) - Elixir Studios / Demis Hassabis
# GOG edition, runs via Wine with DXVK (D3D8 → Vulkan)

cd "$(dirname "${BASH_SOURCE[0]}")"

INSTALLER="INSTALL/Republic-The-Revolution_Win_EN.exe"
GAME_DIR="game"
DXVK_VER="2.4"
DXVK_DIR="INSTALL/dxvk-${DXVK_VER}/x32"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
export WINEDLLOVERRIDES="d3d8,d3d9,dxgi=n,b"

# Find the game executable after extraction
find_exe() {
    GAME_EXE=$(find "$GAME_DIR" -iname "Republic.exe" -not -iname "*setup*" -not -iname "*unins*" 2>/dev/null | head -1)
    [ -n "$GAME_EXE" ] || return 1
    GAME_EXE_DIR="$(dirname "$GAME_EXE")"
}

# --- Already installed: just launch ---
if find_exe 2>/dev/null && [ -d "$WINEPREFIX" ]; then
    cd "$GAME_EXE_DIR"
    wine explorer /desktop=Republic,1024x768 Republic.exe 2>/dev/null
    wineserver -k 2>/dev/null
    exit 0
fi

# --- First run: extract, configure, launch ---

# Check for GOG installer
if [ ! -f "$INSTALLER" ]; then
    echo "ERROR: Republic installer not found at $INSTALLER"
    echo ""
    echo "Place sglBinaries_2 in ~/sgl/downloads/ and run:"
    echo "  sudo ./install.sh"
    exit 1
fi

# Check dependencies
for cmd in wine innoextract curl; do
    if ! command -v "$cmd" >/dev/null; then
        echo "ERROR: $cmd not found. Install with: sudo apt install $cmd"
        exit 1
    fi
done

# Extract GOG installer
if [ ! -d "$GAME_DIR" ]; then
    echo "Extracting Republic: The Revolution..."
    mkdir -p "$GAME_DIR"
    innoextract -d "$GAME_DIR" "$INSTALLER"
fi

find_exe || { echo "ERROR: Could not find Republic.exe after extraction"; exit 1; }

# Download DXVK if needed
if [ ! -f "$DXVK_DIR/d3d8.dll" ]; then
    echo "Downloading DXVK ${DXVK_VER}..."
    mkdir -p INSTALL
    curl -sL "https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VER}/dxvk-${DXVK_VER}.tar.gz" \
        -o "INSTALL/dxvk-${DXVK_VER}.tar.gz"
    tar xzf "INSTALL/dxvk-${DXVK_VER}.tar.gz" -C INSTALL/
    rm -f "INSTALL/dxvk-${DXVK_VER}.tar.gz"
fi

# Install DXVK DLLs into game directory
cp "$DXVK_DIR/d3d8.dll" "$GAME_EXE_DIR/"
cp "$DXVK_DIR/d3d9.dll" "$GAME_EXE_DIR/"
cp "$DXVK_DIR/dxgi.dll" "$GAME_EXE_DIR/"

# Create DXVK config to force windowed mode (fixes mouse input)
cat > "$GAME_EXE_DIR/dxvk.conf" << 'DXVKEOF'
d3d9.forceWindowed = True
DXVKEOF

# Create Wine prefix
echo "Creating Wine prefix..."
wineboot --init 2>/dev/null
sleep 2
wine reg add "HKCU\\Software\\Wine" /v Version /t REG_SZ /d winxp /f 2>/dev/null

# Launch
cd "$GAME_EXE_DIR"
wine explorer /desktop=Republic,1024x768 Republic.exe 2>/dev/null

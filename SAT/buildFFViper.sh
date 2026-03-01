#!/bin/bash
# buildFFViper.sh - Build the native Linux FFViper binary from source (alpha)
#
# This builds the alpha-quality native Linux port of FreeFalcon.
# Game data must already be installed (run freeFalcon.sh first).
# After building, launch with:
#   cd WP/drive_c/FreeFalcon6 && ./build/src/ffviper/FFViper -d . -w

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/freeFalconSource"
BUILD_DIR="$SOURCE_DIR/build"
FFVIPER_BIN="$BUILD_DIR/src/ffviper/FFViper"
GAME_DATA="$SCRIPT_DIR/WP/drive_c/FreeFalcon6"

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: FreeFalcon source not found at $SOURCE_DIR"
    exit 1
fi

echo ""
echo "Building FFViper from source (alpha native port)..."
echo ""

# Install build dependencies if needed
BUILD_DEPS=(libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev
            libgl-dev libglew-dev libopenal-dev
            cmake ninja-build build-essential)
MISSING=()
for pkg in "${BUILD_DEPS[@]}"; do
    dpkg -s "$pkg" &>/dev/null 2>&1 || MISSING+=("$pkg")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Installing build dependencies: ${MISSING[*]}"
    sudo apt-get install -y "${MISSING[@]}"
fi

mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release "$SOURCE_DIR" && ninja

if [[ ! -x "$FFVIPER_BIN" ]]; then
    echo ""
    echo "Error: Build failed — $FFVIPER_BIN not found."
    exit 1
fi

echo ""
echo "FFViper built successfully: $FFVIPER_BIN"
echo ""

if [[ -d "$GAME_DATA" ]]; then
    echo "To run:  cd $GAME_DATA && $FFVIPER_BIN -d . -w"
else
    echo "Game data not installed yet. Run ./freeFalcon.sh first to install via Wine,"
    echo "then:  cd WP/drive_c/FreeFalcon6 && $FFVIPER_BIN -d . -w"
fi

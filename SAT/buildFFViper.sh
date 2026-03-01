#!/bin/bash
# buildFFViper.sh - Build and optionally run native Linux FFViper
#
# Prerequisites:
#   1. Ubuntu 24.04 LTS
#   2. Run ./freeFalcon.sh first to install game data via Wine
#      (installs to SAT/WP/drive_c/FreeFalcon6)
#      The build binary auto-detects this game data location.
#
# Usage:
#   ./buildFFViper.sh          # build only
#   ./buildFFViper.sh --run    # build and launch in windowed mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/freeFalconSource"
BUILD_DIR="$SOURCE_DIR/build"
FFVIPER_BIN="$BUILD_DIR/src/ffviper/FFViper"
# Game data installed by freeFalcon.sh into the Wine prefix
GAME_DATA="$SCRIPT_DIR/WP/drive_c/FreeFalcon6"

RUN_AFTER_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --run|-r) RUN_AFTER_BUILD=true ;;
    esac
done

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Error: FreeFalcon source not found at $SOURCE_DIR"
    exit 1
fi

if [[ ! -d "$GAME_DATA" ]]; then
    echo "Error: Game data not found at $GAME_DATA"
    echo "Run ./freeFalcon.sh first to install FreeFalcon 6 via Wine."
    exit 1
fi

echo ""
echo "Building FFViper from source (native Linux port)..."
echo ""

# ── Install build tools and libraries ──────────────────────────────────
#
# Build tools:
#   build-essential  - gcc, g++, make, libc-dev
#   cmake            - cross-platform build system generator
#   ninja-build      - fast parallel build tool (used by cmake -G Ninja)
#   pkg-config       - helper for finding library compile/link flags
#
# Graphics libraries:
#   libsdl2-dev       - SDL2 (window creation, input, audio device)
#   libsdl2-image-dev - SDL2_image (image file loading)
#   libsdl2-mixer-dev - SDL2_mixer (audio mixing)
#   libgl-dev         - OpenGL (3D rendering, replaces Direct3D)
#   libglew-dev       - GLEW (OpenGL extension loading)
#
# Audio:
#   libopenal-dev     - OpenAL (3D positional audio, replaces DirectSound)

BUILD_DEPS=(
    build-essential cmake ninja-build pkg-config
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev
    libgl-dev libglew-dev
    libopenal-dev
)
MISSING=()
for pkg in "${BUILD_DEPS[@]}"; do
    dpkg -s "$pkg" &>/dev/null 2>&1 || MISSING+=("$pkg")
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Installing build dependencies: ${MISSING[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING[@]}"
fi

# ── Build ──────────────────────────────────────────────────────────────

mkdir -p "$BUILD_DIR" && cd "$BUILD_DIR"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release "$SOURCE_DIR" && ninja

if [[ ! -x "$FFVIPER_BIN" ]]; then
    echo ""
    echo "Error: Build failed — $FFVIPER_BIN not found."
    exit 1
fi

echo ""
echo "FFViper built successfully: $FFVIPER_BIN"
echo "Game data directory: $GAME_DATA"
echo ""

# ── Run ────────────────────────────────────────────────────────────────

if [[ "$RUN_AFTER_BUILD" == true ]]; then
    echo "Launching FFViper..."
    cd "$GAME_DATA"
    exec "$FFVIPER_BIN" -d "$GAME_DATA" -w
else
    echo "To run:"
    echo "  $FFVIPER_BIN -d $GAME_DATA -w"
    echo ""
    echo "Or:  ./buildFFViper.sh --run"
fi

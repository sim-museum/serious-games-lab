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
# Native-port source checkout (sim-museum/free-falcon, branch develop).
# It lives outside this repo; override with FF_SOURCE_DIR.
SOURCE_DIR="${FF_SOURCE_DIR:-$HOME/free-falcon}"
BUILD_DIR="$SOURCE_DIR/build"
FFVIPER_BIN="$BUILD_DIR/src/ffviper/FFViper"
# Game data installed by freeFalcon/freeFalcon.sh into the Wine prefix
GAME_DATA="$SCRIPT_DIR/freeFalcon/WP/drive_c/FreeFalcon6"

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
    echo ""
    echo "Error: FreeFalcon 6 game data not found."
    echo ""
    echo "  Expected at: $GAME_DATA"
    echo ""
    echo "  The native Linux build requires game data (art, terrain, campaign"
    echo "  files, etc.) from the Windows FreeFalcon 6 installation."
    echo ""
    echo "  To install, run:  ./freeFalcon/freeFalcon.sh"
    echo ""
    echo "  This will install FreeFalcon 6 via Wine into freeFalcon/WP/."
    echo "  Wine must be installed first:  sudo apt install wine wine32:i386"
    echo ""
    exit 1
fi

echo ""
echo "Building FFViper from source (native Linux port)..."
echo ""

# ── Build tools ────────────────────────────────────────────────────────
#
# These genuinely have to be installed system-wide (a compiler toolchain
# can't be unpacked into a private prefix), so we only *check* for them and
# tell the user what to run. We probe for the binaries rather than the
# package names: dpkg -s reports success for a foreign-architecture install,
# which is exactly how this box hid the fact that its SDL2/OpenAL dev
# packages were i386-only.

MISSING_TOOLS=()
for t in cc c++ make cmake ninja pkg-config; do
    command -v "$t" &>/dev/null || MISSING_TOOLS+=("$t")
done
if [[ ${#MISSING_TOOLS[@]} -gt 0 ]]; then
    echo "Error: missing build tools: ${MISSING_TOOLS[*]}"
    echo "  Install them with:"
    echo "    sudo apt-get install build-essential cmake ninja-build pkg-config"
    exit 1
fi

# ── Development libraries (no sudo) ────────────────────────────────────
#
# The port's CMakeLists.txt expects SDL2/GLEW/OpenAL headers under
# $SOURCE_DIR/extern/usr (it adds extern/usr/include, extern/usr/include/
# $MULTIARCH and extern/usr/lib/$MULTIARCH to the include/link/rpath paths).
# That tree is gitignored, so we rebuild it here the way the port docs
# prescribe: apt-get download + dpkg -x, which needs no root.
#
#   libsdl2-dev   - SDL2 (window, input, audio device)
#   libglew-dev   - GLEW (OpenGL extension loading)
#   libglew2.2    - GLEW *runtime* (dev ships only the linker symlink, and
#                   the build rpaths extern/, so the .so.2.2 must be here)
#   libopenal-dev - OpenAL (3D positional audio, replaces DirectSound)
#
# OpenGL itself comes from the system (libgl-dev); it has no multiarch
# header-wrapper problem and pulls in a large driver dependency tree.

EXTERN_DIR="$SOURCE_DIR/extern"
MULTIARCH="$(cc -print-multiarch 2>/dev/null || echo x86_64-linux-gnu)"
HOST_ARCH="$(dpkg --print-architecture)"

if [[ ! -f "$EXTERN_DIR/usr/include/SDL2/SDL.h" \
   || ! -f "$EXTERN_DIR/usr/include/GL/glew.h" \
   || ! -f "$EXTERN_DIR/usr/include/AL/al.h" ]]; then
    echo "Fetching dev libraries into $EXTERN_DIR (no sudo required)..."
    mkdir -p "$EXTERN_DIR"
    (
        cd "$EXTERN_DIR"
        # Arch-qualify every package: an unqualified name can resolve to a
        # foreign arch when one is enabled (i386 is, for Wine).
        apt-get download \
            "libsdl2-dev:$HOST_ARCH" \
            "libglew-dev:$HOST_ARCH" \
            "libglew2.2:$HOST_ARCH" \
            "libopenal-dev:$HOST_ARCH"
        for deb in *.deb; do dpkg -x "$deb" .; done
    ) || { echo "Error: failed to fetch dev libraries into $EXTERN_DIR"; exit 1; }
fi

# The -dev packages ship libFoo.so as a symlink to a runtime that lives in
# *their own* package (libSDL2-2.0.so.0, libopenal.so.1) -- and those runtime
# packages are system-installed, not unpacked here. Left alone the symlinks
# dangle and the final link fails with "cannot find -lopenal". Repoint them
# at the system runtimes. GLEW is exempt: we unpacked its runtime above.
for lib in libSDL2:libSDL2-2.0.so.0 libopenal:libopenal.so.1; do
    name="${lib%%:*}"; target="/usr/lib/$MULTIARCH/${lib##*:}"
    link="$EXTERN_DIR/usr/lib/$MULTIARCH/$name.so"
    # -e follows symlinks, so this is false for both a dangling link and a
    # missing one, and true only when the link already resolves.
    if [[ ! -e "$link" ]]; then
        if [[ -e "$target" ]]; then
            mkdir -p "$(dirname "$link")"
            ln -sf "$target" "$link"
        else
            echo "Error: $name runtime not found at $target"
            echo "  Install it with:  sudo apt-get install libsdl2-2.0-0 libopenal1"
            exit 1
        fi
    fi
done

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

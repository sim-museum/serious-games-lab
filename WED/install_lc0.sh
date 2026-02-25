#!/bin/bash

# install_lc0.sh - Build lc0 (Leela Chess Zero) from source (CPU/OpenBLAS)
# and download neural network weights for nibbler.
#
# Usage: bash install_lc0.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"
LC0_BIN="$INSTALL_DIR/lc0_cpu"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

mkdir -p "$INSTALL_DIR"

# --- Install build dependencies ---
DEPS=(build-essential git curl meson ninja-build libopenblas-dev protobuf-compiler libprotobuf-dev)
MISSING=()
for pkg in "${DEPS[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING+=("$pkg")
    fi
done
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Installing build dependencies: ${MISSING[*]}"
    sudo apt-get install -y "${MISSING[@]}"
fi

# --- Build lc0 ---
if [[ -x "$LC0_BIN" ]] && ! $FORCE; then
    echo "lc0_cpu already exists at $LC0_BIN (use --force to rebuild)"
else
    echo "Building lc0 from source (CPU/OpenBLAS)..."
    BUILD_DIR="/tmp/lc0_build"
    rm -rf "$BUILD_DIR"

    git clone --recurse-submodules https://github.com/LeelaChessZero/lc0.git "$BUILD_DIR"
    cd "$BUILD_DIR"
    meson setup build --buildtype release -Ddefault_library=static
    meson compile -C build

    cp build/lc0 "$LC0_BIN"
    chmod +x "$LC0_BIN"
    rm -rf "$BUILD_DIR"

    echo "lc0 built successfully: $LC0_BIN"
fi

# --- Download weights ---
download_weights() {
    local url="$1"
    local dest="$2"

    if [[ -f "$dest" ]] && ! $FORCE; then
        echo "Weights already exist: $(basename "$dest") (use --force to re-download)"
        return
    fi

    echo "Downloading $(basename "$dest")..."
    if curl -fL -o "$dest" "$url" 2>&1; then
        echo "  Downloaded: $(basename "$dest")"
    else
        echo "  WARNING: Failed to download $(basename "$dest")"
        echo "  URL: $url"
        rm -f "$dest"
    fi
}

# Small/fast weights (good for testing)
download_weights \
    "https://github.com/dkappe/leela-chess-weights/files/4432261/tinygyal-8.pb.gz" \
    "$INSTALL_DIR/tinygyal-8.pb.gz"

# Stronger weights (better play quality)
download_weights \
    "https://storage.lczero.org/files/networks-contrib/t1-256x10-distilled-swa-2432500.pb.gz" \
    "$INSTALL_DIR/t1-256x10-distilled-swa-2432500.pb.gz"

echo ""
echo "Done. Engine: $LC0_BIN"
echo "Weights:  $INSTALL_DIR/tinygyal-8.pb.gz (small/fast)"
echo "          $INSTALL_DIR/t1-256x10-distilled-swa-2432500.pb.gz (stronger)"

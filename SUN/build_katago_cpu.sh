#!/bin/bash

# build_katago_cpu.sh - Build KataGo from source with Eigen backend (CPU-only)
# and download neural network models.
#
# Usage: bash build_katago_cpu.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATAGO_DIR="$SCRIPT_DIR/katago"
KATAGO_BIN="$KATAGO_DIR/katago"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

mkdir -p "$KATAGO_DIR"

# --- Install build dependencies ---
DEPS=(build-essential cmake git curl zlib1g-dev libeigen3-dev)
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

# --- Build KataGo ---
if [[ -x "$KATAGO_BIN" ]] && ! $FORCE; then
    echo "KataGo already exists at $KATAGO_BIN (use --force to rebuild)"
else
    echo "Building KataGo from source (CPU/Eigen)..."
    BUILD_DIR="/tmp/katago_build"
    rm -rf "$BUILD_DIR"

    git clone https://github.com/lightvector/KataGo.git "$BUILD_DIR"
    cd "$BUILD_DIR/cpp"
    # Detect CPU SIMD support and set flags accordingly
    CMAKE_ARGS="-DUSE_BACKEND=EIGEN"
    if grep -q avx2 /proc/cpuinfo; then
        CMAKE_ARGS="$CMAKE_ARGS -DUSE_AVX2=1"
    fi
    cmake . $CMAKE_ARGS
    make -j"$(nproc)"

    cp katago "$KATAGO_BIN"
    chmod +x "$KATAGO_BIN"
    rm -rf "$BUILD_DIR"

    echo "KataGo built successfully: $KATAGO_BIN"
fi

# --- Download models ---
download_model() {
    local url="$1"
    local dest="$2"

    if [[ -f "$dest" ]] && ! $FORCE; then
        echo "Model already exists: $(basename "$dest") (use --force to re-download)"
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

# Human SL model (for human-like play at various ranks)
download_model \
    "https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz" \
    "$KATAGO_DIR/b18c384nbt-humanv0.bin.gz"

# Strong model (for full-strength analysis)
download_model \
    "https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz" \
    "$KATAGO_DIR/main_model.bin.gz"

echo ""
echo "Done. Engine: $KATAGO_BIN"
echo "Models:  $KATAGO_DIR/b18c384nbt-humanv0.bin.gz (Human SL)"
echo "         $KATAGO_DIR/main_model.bin.gz (Strong)"

#!/usr/bin/env bash
# setup_flightgear.sh - Download and install FlightGear AppImage
#
# Installs the latest FlightGear release as an AppImage instead of the
# outdated version in the Ubuntu apt repository.
# Creates a wrapper at ~/.local/share/flightgear/bin/fgfs so existing
# scripts that call bare 'fgfs' work without modification.

set -euo pipefail

FG_VERSION="2024.1.4"
FG_DIR="$HOME/.local/share/flightgear"
FG_BIN="$FG_DIR/bin"
APPIMAGE_NAME="fgfs-${FG_VERSION}.AppImage"
APPIMAGE_PATH="$FG_DIR/$APPIMAGE_NAME"
DOWNLOAD_URL="https://download.flightgear.org/release-2024.1/flightgear-${FG_VERSION}-linux-amd64.AppImage"

echo "=============================================="
echo "  FlightGear Setup"
echo "  Serious Games Lab"
echo "=============================================="
echo ""
echo "  Version:  $FG_VERSION (AppImage)"
echo "  Install:  $FG_DIR"
echo ""

# Check if already installed
if [[ -f "$APPIMAGE_PATH" ]]; then
    echo "FlightGear $FG_VERSION is already installed."
    echo "  AppImage: $APPIMAGE_PATH"
    echo "  Wrapper:  $FG_BIN/fgfs"
    echo ""
    read -rp "Re-download? (y/N): " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Ensure libfuse2 is available (required for AppImages)
if ! dpkg -s libfuse2t64 &>/dev/null && ! dpkg -s libfuse2 &>/dev/null; then
    echo "AppImages require libfuse2. Run:"
    echo "  sudo apt-get install -y libfuse2t64"
    echo ""
    read -rp "Attempt to install now (requires sudo)? (Y/n): " reply
    if [[ ! "$reply" =~ ^[Nn]$ ]]; then
        sudo apt-get install -y libfuse2t64
    fi
    echo ""
fi

mkdir -p "$FG_DIR" "$FG_BIN"

echo "Downloading FlightGear $FG_VERSION AppImage..."
echo "  URL: $DOWNLOAD_URL"
echo ""
if ! curl -fSL --progress-bar -o "$APPIMAGE_PATH" "$DOWNLOAD_URL"; then
    echo ""
    echo "ERROR: Download failed."
    echo "  Try downloading manually from: https://www.flightgear.org/download/"
    echo "  Place the AppImage at: $APPIMAGE_PATH"
    rm -f "$APPIMAGE_PATH"
    exit 1
fi

chmod +x "$APPIMAGE_PATH"

# Create wrapper script so 'fgfs' works on PATH
cat > "$FG_BIN/fgfs" << EOF
#!/bin/bash
exec "$APPIMAGE_PATH" "\$@"
EOF
chmod +x "$FG_BIN/fgfs"

echo ""
echo "=============================================="
echo "  FlightGear $FG_VERSION installed successfully."
echo ""
echo "  AppImage: $APPIMAGE_PATH"
echo "  Wrapper:  $FG_BIN/fgfs"
echo ""
echo "  The launcher automatically adds $FG_BIN to PATH."
echo "  To run directly: $FG_BIN/fgfs --launcher"
echo "=============================================="

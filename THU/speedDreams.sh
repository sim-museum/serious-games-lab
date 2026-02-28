#!/bin/bash

# Set the Wine prefix to a directory named 'WP' in the current working directory
export WINEPREFIX="$PWD/WP"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"
APPIMAGE_NAME="Speed-Dreams-2.2.3-x86_64.AppImage"
APPIMAGE_PATH="$WINEPREFIX/$APPIMAGE_NAME"
DOWNLOAD_URL="https://sourceforge.net/projects/speed-dreams/files/2.2.3/$APPIMAGE_NAME/download"

# Move AppImage from INSTALL to WP if it exists there
if [[ -f "$INSTALL_DIR/$APPIMAGE_NAME" ]]; then
    mkdir -p "$WINEPREFIX"
    chmod +x "$INSTALL_DIR/$APPIMAGE_NAME"
    mv "$INSTALL_DIR/$APPIMAGE_NAME" "$WINEPREFIX/"
fi

# Download if not found anywhere
if [[ ! -f "$APPIMAGE_PATH" ]]; then
    echo ""
    echo "Speed Dreams AppImage not found. Downloading (~1.8 GB)..."
    echo ""
    mkdir -p "$INSTALL_DIR" "$WINEPREFIX"
    DL_PATH="$INSTALL_DIR/$APPIMAGE_NAME"
    if wget -q --show-progress -O "$DL_PATH" "$DOWNLOAD_URL"; then
        chmod +x "$DL_PATH"
        mv "$DL_PATH" "$WINEPREFIX/"
        echo ""
        echo "Download complete."
    else
        rm -f "$DL_PATH"
        echo ""
        echo "Download failed. Check your internet connection or download manually from:"
        echo "  $DOWNLOAD_URL"
        echo "and place it in: $INSTALL_DIR"
        echo ""
        exit 1
    fi
fi

# Verify it's actually a Linux ELF/AppImage (not a Windows exe from a redirect)
if file "$APPIMAGE_PATH" | grep -q "PE32"; then
    echo "Error: Downloaded file is a Windows executable, not a Linux AppImage."
    echo "Removing it and retrying on next run."
    rm -f "$APPIMAGE_PATH"
    exit 1
fi

# Launch Speed Dreams
if [[ -f "$APPIMAGE_PATH" ]]; then
    clear
    echo "Speed Dreams open source sim racing"; echo ""
    echo "To race a 67 Grand Prix car at Monza, Choose:"
    echo "Race"
    echo "Practics"
    echo "Configure"
    echo "Now select Grand Prix Circuits on the top line, and Forza on the second line"
    echo "Next"
    echo "Garage"
    echo "For Category on top left select 1967 Grand Prix"
    echo "Apply, Next, Next, Start"
    echo ""
    # Try direct execution; fall back to --appimage-extract-and-run if FUSE unavailable
    "$APPIMAGE_PATH" 2>/dev/null || "$APPIMAGE_PATH" --appimage-extract-and-run 2>/dev/null
fi


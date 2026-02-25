#!/bin/bash

# bcalc - Bridge Calculator (native Linux binary)
# Web site: bcalc.w8.pl
# Downloads Linux binary if not present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BCALC_DIR="$SCRIPT_DIR/LINUX"
BCALC_BIN="$BCALC_DIR/bcalcgui"

# Also check sglBinaries WP-relative location (legacy path)
WP_BCALC="$SCRIPT_DIR/WP/../LINUX/bcalcgui"

if [[ -x "$WP_BCALC" ]]; then
    BCALC_DIR="$(cd "$SCRIPT_DIR/WP/../LINUX" && pwd)"
    BCALC_BIN="$WP_BCALC"
fi

if [[ ! -x "$BCALC_BIN" ]]; then
    echo "bcalc not found at $BCALC_DIR"
    echo ""
    echo "To install bcalc:"
    echo "  1. Download the Linux version from http://bcalc.w8.pl/Download.html"
    echo "  2. Extract the archive into: $BCALC_DIR"
    echo "     (the directory should contain bcalcgui)"
    echo "  3. Run: chmod +x $BCALC_DIR/bcalcgui"
    echo "  4. Run this script again"
    echo ""

    echo "Attempting automatic download..."
    mkdir -p "$BCALC_DIR"
    DOWNLOAD_URL="http://bcalc.w8.pl/BCalc_lin64.tar.gz"
    echo "Downloading from $DOWNLOAD_URL ..."
    if curl -fL -o /tmp/bcalc_download.tar.gz "$DOWNLOAD_URL" 2>&1; then
        tar xzf /tmp/bcalc_download.tar.gz -C "$BCALC_DIR" 2>/dev/null
        rm -f /tmp/bcalc_download.tar.gz
        chmod +x "$BCALC_BIN" 2>/dev/null
        if [[ -x "$BCALC_BIN" ]]; then
            echo "bcalc installed successfully."
        else
            echo "Download succeeded but bcalcgui not found in archive."
            echo "Please extract manually to $BCALC_DIR"
            exit 1
        fi
    else
        echo "Download failed. The bcalc website may be temporarily unavailable."
        echo "Please download manually from http://bcalc.w8.pl/"
        rm -f /tmp/bcalc_download.tar.gz
        exit 1
    fi
fi

cd "$BCALC_DIR"
./bcalcgui 2>/dev/null

clear
[[ -f "$SCRIPT_DIR/DOC/REFERENCE/exitMessageBcalc.txt" ]] && cat "$SCRIPT_DIR/DOC/REFERENCE/exitMessageBcalc.txt"
echo ""
echo ""

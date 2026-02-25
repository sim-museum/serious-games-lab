#!/usr/bin/env bash
# download_go_problems.sh - Download Go problem collections for study
#
# Downloads:
#   1. Go Game Guru weekly problems (422 SGFs) - git clone from GitHub
#   2. MyGoGrinder / Xuan Xuan Qi Jing (347 SGFs) - zip from SourceForge
#
# All problems are stored under FRI/problems/
#
# Usage:
#   ./download_go_problems.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBLEMS_DIR="$SCRIPT_DIR/problems"

mkdir -p "$PROBLEMS_DIR"

echo ""
echo "=== Downloading Go Problem Collections ==="
echo ""

# --- 1. Go Game Guru weekly problems ---
GGG_DIR="$PROBLEMS_DIR/gogameguru"
if [ -d "$GGG_DIR/weekly-go-problems" ]; then
    echo "[OK] Go Game Guru problems already downloaded."
else
    echo "[DOWNLOAD] Go Game Guru weekly problems (422 SGFs)..."
    echo "  Source: https://github.com/gogameguru/go-problems"
    echo "  License: CC BY-NC-SA 4.0"
    echo ""
    git clone --depth 1 https://github.com/gogameguru/go-problems.git "$GGG_DIR"
    # Remove git metadata to save space
    rm -rf "$GGG_DIR/.git"
    echo "[OK] Go Game Guru problems installed."
fi
echo ""

# --- 2. MyGoGrinder / Xuan Xuan Qi Jing ---
MGG_DIR="$PROBLEMS_DIR/mygogrinder"
XXQJ_DIR="$MGG_DIR/xuan-xuan-qi-jing"
if [ -d "$XXQJ_DIR" ] && [ -n "$(ls -A "$XXQJ_DIR" 2>/dev/null)" ]; then
    echo "[OK] MyGoGrinder / Xuan Xuan Qi Jing problems already downloaded."
else
    echo "[DOWNLOAD] MyGoGrinder / Xuan Xuan Qi Jing (347 SGFs)..."
    echo "  Source: https://sourceforge.net/projects/mygogrinder/"
    echo "  License: GPL (software), public domain (problems)"
    echo ""
    mkdir -p "$MGG_DIR"
    tmpdir="$(mktemp -d)"
    tmpzip="$tmpdir/MyGoGrinder.zip"

    curl -fSL --progress-bar \
        -o "$tmpzip" \
        "https://sourceforge.net/projects/mygogrinder/files/MyGoGrinder-2.3.1.zip/download"

    # Extract the main zip
    unzip -q "$tmpzip" -d "$tmpdir/mgg"

    # Find and extract the nested Xuan Xuan Qi Jing problems zip
    xxqj_zip=$(find "$tmpdir/mgg" -name '*Xuan*problems*' -type f 2>/dev/null | head -1)
    if [ -n "$xxqj_zip" ]; then
        mkdir -p "$XXQJ_DIR"
        unzip -q "$xxqj_zip" -d "$XXQJ_DIR"
        # If files ended up in a subdirectory, flatten them
        subdir="$XXQJ_DIR/Xuan Xuan Qi Jing"
        if [ -d "$subdir" ]; then
            mv "$subdir"/* "$XXQJ_DIR/" 2>/dev/null || true
            rmdir "$subdir" 2>/dev/null || true
        fi
        echo "[OK] Xuan Xuan Qi Jing problems installed."
    else
        echo "[WARN] Could not find Xuan Xuan Qi Jing zip inside MyGoGrinder archive."
        echo "  Keeping full MyGoGrinder archive for manual extraction."
        unzip -q "$tmpzip" -d "$MGG_DIR"
    fi

    rm -rf "$tmpdir"
fi
echo ""

# --- Summary ---
ggg_count=0
xxqj_count=0
if [ -d "$GGG_DIR/weekly-go-problems" ]; then
    ggg_count=$(find "$GGG_DIR/weekly-go-problems" -name '*.sgf' | wc -l)
fi
if [ -d "$XXQJ_DIR" ]; then
    xxqj_count=$(find "$XXQJ_DIR" -name '*.sgf' | wc -l)
fi
total=$((ggg_count + xxqj_count))

echo "=== Go Problems Summary ==="
echo "  Go Game Guru:      $ggg_count SGF files"
echo "  Xuan Xuan Qi Jing: $xxqj_count SGF files"
echo "  Total:             $total SGF files"
echo ""
echo "  Location: $PROBLEMS_DIR/"
echo ""

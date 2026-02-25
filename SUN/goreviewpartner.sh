#!/bin/bash

# GoReviewPartner - Go game review tool (Python 3 port)
# Uses local copy bundled with the repo; installs Leela Zero engine on first run

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRP_DIR="$SCRIPT_DIR/goreviewpartner"
LEELAZ_WEIGHTS="$SCRIPT_DIR/leelaz_best_network.gz"
WEIGHTS_URL="http://zero.sjeng.org/best-network"

if [[ ! -d "$GRP_DIR" ]]; then
    echo "ERROR: GoReviewPartner directory not found at $GRP_DIR"
    echo "It should be included in the repository."
    exit 1
fi

# --- Leela Zero engine ---
if ! command -v leelaz &>/dev/null; then
    echo "Leela Zero not found. Installing via apt..."
    sudo apt-get install -y leela-zero
    if ! command -v leelaz &>/dev/null; then
        echo "Failed to install leela-zero."
        echo "Install manually: sudo apt-get install leela-zero"
        exit 1
    fi
fi

# --- Leela Zero network weights ---
if [[ ! -f "$LEELAZ_WEIGHTS" ]]; then
    echo "Downloading Leela Zero best network weights..."
    if ! wget -O "$LEELAZ_WEIGHTS" "$WEIGHTS_URL"; then
        echo "Download failed. Get weights manually from: $WEIGHTS_URL"
        rm -f "$LEELAZ_WEIGHTS"
        exit 1
    fi
fi

# Ensure tkinter is available
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Installing python3-tk..."
    sudo apt-get install -y python3-tk
fi

# Auto-configure Leela Zero in GoReviewPartner's config.ini
GRP_CONFIG="$GRP_DIR/config.ini"
LEELAZ_CMD="$(command -v leelaz)"
LEELAZ_PARAMS="--gtp --noponder --weights $LEELAZ_WEIGHTS"
if [[ -f "$GRP_CONFIG" ]] && grep -q "^\[LeelaZero-0\]" "$GRP_CONFIG"; then
    python3 -c "
import configparser, sys
cfg = configparser.ConfigParser()
cfg.read('$GRP_CONFIG')
for section in cfg.sections():
    if section.startswith('LeelaZero-'):
        cfg.set(section, 'command', '$LEELAZ_CMD')
        cfg.set(section, 'parameters', '$LEELAZ_PARAMS')
with open('$GRP_CONFIG', 'w') as f:
    cfg.write(f)
"
fi

# --- KataGo engine (via ensure_katago.sh) ---
source "$SCRIPT_DIR/ensure_katago.sh"

if [[ -x "$KATAGO_BIN" && -f "$MAIN_MODEL" && -f "$ANALYSIS_CFG" && -f "$GRP_CONFIG" ]]; then
    python3 -c "
import configparser
cfg = configparser.ConfigParser()
cfg.read('$GRP_CONFIG')
section = 'GTP bot-0'
if not cfg.has_section(section):
    cfg.add_section(section)
cfg.set(section, 'profile', 'KataGo')
cfg.set(section, 'command', '$KATAGO_BIN')
cfg.set(section, 'parameters', 'gtp -model $MAIN_MODEL -config $ANALYSIS_CFG')
with open('$GRP_CONFIG', 'w') as f:
    cfg.write(f)
"
fi

cd "$GRP_DIR"
python3 main.py

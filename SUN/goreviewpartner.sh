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

# --- KataGo engine (via ensure_katago.sh) ---
source "$SCRIPT_DIR/ensure_katago.sh"

# Auto-configure engines in GoReviewPartner's config.ini
GRP_CONFIG="$GRP_DIR/config.ini"
LEELAZ_CMD="$(command -v leelaz)"
LEELAZ_PARAMS="--gtp --noponder --weights $LEELAZ_WEIGHTS"
KATAGO_GTP_CFG="$KATAGO_DIR/default_gtp.cfg"
KATAGO_LOG_DIR="$KATAGO_DIR/gtp_logs"
mkdir -p "$KATAGO_LOG_DIR"

if [[ -f "$GRP_CONFIG" ]]; then
    python3 - "$GRP_CONFIG" "$LEELAZ_CMD" "$LEELAZ_PARAMS" "$KATAGO_BIN" "$MAIN_MODEL" "$KATAGO_GTP_CFG" "$KATAGO_LOG_DIR" << 'PYEOF'
import configparser, sys
config_path, leelaz_cmd, leelaz_params, katago_bin, main_model, katago_cfg, katago_logdir = sys.argv[1:8]
cfg = configparser.ConfigParser()
cfg.read(config_path)

# Configure Leela Zero profiles (19x19 only)
for section in cfg.sections():
    if section.startswith('LeelaZero-') and section != 'LeelaZero-2':
        cfg.set(section, 'command', leelaz_cmd)
        cfg.set(section, 'parameters', leelaz_params)

# Configure KataGo as a LeelaZero profile (supports all board sizes)
section = 'LeelaZero-2'
if not cfg.has_section(section):
    cfg.add_section(section)
cfg.set(section, 'profile', 'KataGo (all board sizes)')
cfg.set(section, 'command', katago_bin)
cfg.set(section, 'parameters',
    f'gtp -model {main_model} -config {katago_cfg} -override-config logDir={katago_logdir}')
cfg.set(section, 'timepermove', '10')

# Also keep KataGo as a GTP bot for live play
section = 'GTP bot-0'
if not cfg.has_section(section):
    cfg.add_section(section)
cfg.set(section, 'profile', 'KataGo')
cfg.set(section, 'command', katago_bin)
cfg.set(section, 'parameters',
    f'gtp -model {main_model} -config {katago_cfg} -override-config logDir={katago_logdir}')

with open(config_path, 'w') as f:
    cfg.write(f)
PYEOF
fi

cd "$GRP_DIR"
python3 main.py

#!/bin/bash

# Nibbler - Chess analysis GUI for Leela Chess Zero (lc0)
# Downloads from GitHub releases if not present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NIBBLER_VERSION="2.5.3"
NIBBLER_DIR="$SCRIPT_DIR/INSTALL/nibbler-${NIBBLER_VERSION}-linux"

clear

echo "The first time you run the default Leela Chess Zero (lc0) front end, named nibbler,"
echo "you must specify the path to the lc0 chess engine."

if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "from the menu select Engine/Choose Engine"
    echo "select $SCRIPT_DIR/INSTALL/lc0_cpu"
    echo "next select the weights file $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
    echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
    echo "once you have selected lc0_cpu once, nibbler stores its location in ~/.config/Nibbler"
    echo "so you do not have to enter this path again."
    echo ""
    echo "Optional: If you have a modern Nvidia GPU, you can run a faster version of lc0."
    echo "Optional: sudo apt install -y nvidia-opencl-dev"
    echo "Optional: then in nibbler Engine/Choose Engine select"
    echo "Optional: $SCRIPT_DIR/INSTALL/lc0_linux_graphicsAcceleration/lc0_opencl"
    echo "If in doubt, start with the default lc0_cpu option as described above."
else
    echo ""
    echo "lc0 engine not found. Building from source..."
    bash "$SCRIPT_DIR/install_lc0.sh"
    if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
        echo ""
        echo "lc0 built successfully. In nibbler, select Engine/Choose Engine"
        echo "and set engine path to: $SCRIPT_DIR/INSTALL/lc0_cpu"
        echo "and weights to: $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
        echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
    fi
fi

# Download nibbler if not present
if [[ ! -d "$NIBBLER_DIR" ]] || [[ ! -f "$NIBBLER_DIR/nibbler" ]]; then
    echo ""
    echo "Nibbler not found. Downloading v${NIBBLER_VERSION} from GitHub..."
    mkdir -p "$SCRIPT_DIR/INSTALL"
    DOWNLOAD_URL="https://github.com/rooklift/nibbler/releases/download/v${NIBBLER_VERSION}/nibbler-${NIBBLER_VERSION}-linux.zip"

    if curl -fL -o /tmp/nibbler_download.zip "$DOWNLOAD_URL" 2>&1; then
        unzip -o /tmp/nibbler_download.zip -d "$SCRIPT_DIR/INSTALL/" >/dev/null 2>&1
        rm -f /tmp/nibbler_download.zip
        chmod +x "$NIBBLER_DIR/nibbler" 2>/dev/null
        echo "Nibbler v${NIBBLER_VERSION} installed."
    else
        echo "Download failed. Please download manually from:"
        echo "  $DOWNLOAD_URL"
        echo "and extract to $SCRIPT_DIR/INSTALL/"
        rm -f /tmp/nibbler_download.zip
        exit 1
    fi
fi

# Download Maia chess weights if not present
MAIA_DIR="$SCRIPT_DIR/INSTALL/maia_weights"
mkdir -p "$MAIA_DIR"
for ELO in 1100 1200 1300 1400 1500 1600 1700 1800 1900; do
    MAIA_FILE="$MAIA_DIR/maia-${ELO}.pb.gz"
    if [[ ! -f "$MAIA_FILE" ]]; then
        echo "Downloading Maia ${ELO} weights..."
        curl -fL -o "$MAIA_FILE" "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-${ELO}.pb.gz" 2>&1 || {
            echo "Failed to download maia-${ELO}.pb.gz"
            rm -f "$MAIA_FILE"
        }
    fi
done
echo ""
echo "Maia weights (human-like play, ELO 1100-1900) are in: $MAIA_DIR/"
echo "To use: in nibbler, set weights path to a Maia file instead of tinygyal-8.pb.gz"
echo ""

cd "$NIBBLER_DIR"
./nibbler --no-sandbox 2>/dev/null

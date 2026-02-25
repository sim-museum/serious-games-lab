#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
KATAGO_DIR="$ROOT/katago"
GUI_DIR="$ROOT/gui"

# KataGo version and URLs
KATAGO_VERSION="1.15.3"
KATAGO_TARBALL="katago-v${KATAGO_VERSION}-opencl-linux-x64.zip"
KATAGO_URL="https://github.com/lightvector/KataGo/releases/download/v${KATAGO_VERSION}/${KATAGO_TARBALL}"
HUMANSL_MODEL_URL="https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz"
STRONG_MODEL_URL="https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"

# GUI URLs
SABAKI_VERSION="0.52.2"
SABAKI_URL="https://github.com/SabakiHQ/Sabaki/releases/download/v${SABAKI_VERSION}/Sabaki-v${SABAKI_VERSION}-linux-x64.AppImage"
KAYA_VERSION="0.2.4"
KAYA_URL="https://github.com/kaya-go/kaya/releases/download/v${KAYA_VERSION}/Kaya_${KAYA_VERSION}_amd64.AppImage"
LIZGOBAN_REPO="https://github.com/kaorahi/lizgoban"

# Detect download command
download() {
    local url="$1"
    local output="$2"
    if command -v curl &>/dev/null; then
        curl -L -o "$output" "$url"
    elif command -v wget &>/dev/null; then
        wget -O "$output" "$url"
    else
        echo "Error: Neither curl nor wget found." >&2
        exit 1
    fi
}

# Create directories
mkdir -p "$KATAGO_DIR"
mkdir -p "$GUI_DIR"

# --- KataGo Setup ---
echo "Downloading KataGo v${KATAGO_VERSION}..."
download "$KATAGO_URL" "$KATAGO_DIR/$KATAGO_TARBALL"

echo "Extracting KataGo..."
unzip -o "$KATAGO_DIR/$KATAGO_TARBALL" -d "$KATAGO_DIR"
rm "$KATAGO_DIR/$KATAGO_TARBALL"

# Move contents from nested directory if present
if [[ -d "$KATAGO_DIR/katago-v${KATAGO_VERSION}-opencl-linux-x64" ]]; then
    mv "$KATAGO_DIR/katago-v${KATAGO_VERSION}-opencl-linux-x64"/* "$KATAGO_DIR/"
    rmdir "$KATAGO_DIR/katago-v${KATAGO_VERSION}-opencl-linux-x64"
fi

chmod +x "$KATAGO_DIR/katago"

echo "Downloading Human SL model..."
download "$HUMANSL_MODEL_URL" "$KATAGO_DIR/b18c384nbt-humanv0.bin.gz"

echo "Downloading strong model..."
download "$STRONG_MODEL_URL" "$KATAGO_DIR/main_model.bin.gz"

# --- Sabaki Setup ---
echo "Downloading Sabaki..."
download "$SABAKI_URL" "$GUI_DIR/Sabaki.AppImage"
chmod +x "$GUI_DIR/Sabaki.AppImage"

# --- Kaya Setup ---
echo "Downloading Kaya..."
download "$KAYA_URL" "$GUI_DIR/Kaya.AppImage"
chmod +x "$GUI_DIR/Kaya.AppImage"

# --- LizGoban Setup ---
echo "Cloning LizGoban..."
if [[ -d "$GUI_DIR/lizgoban" ]]; then
    echo "LizGoban directory already exists, pulling latest..."
    git -C "$GUI_DIR/lizgoban" pull
else
    git clone "$LIZGOBAN_REPO" "$GUI_DIR/lizgoban"
fi

echo "Installing LizGoban dependencies..."
cd "$GUI_DIR/lizgoban"
npm install
cd "$ROOT"

echo ""
echo "Setup complete!"
echo "KataGo binary: $KATAGO_DIR/katago"
echo "Human SL model: $KATAGO_DIR/b18c384nbt-humanv0.bin.gz"
echo "Strong model: $KATAGO_DIR/main_model.bin.gz"
echo "Sabaki: $GUI_DIR/Sabaki.AppImage"
echo "Kaya: $GUI_DIR/Kaya.AppImage"
echo "LizGoban: cd $GUI_DIR/lizgoban && npm start"

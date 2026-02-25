#!/usr/bin/bash

# Sabaki - Go board GUI
# Downloads AppImage from GitHub releases if not present
# Auto-configures KataGo Human SL engine on first launch.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"
SABAKI_VERSION="0.52.2"
SABAKI_APPIMAGE="sabaki-v${SABAKI_VERSION}-linux-x64.AppImage"

# Ensure KataGo + models are present
source "$SCRIPT_DIR/ensure_katago.sh"

# Auto-configure Sabaki engine if not already set
SABAKI_CONFIG="$HOME/.config/Sabaki/settings.json"
if [[ -f "$SABAKI_CONFIG" ]]; then
    if ! grep -q "KataGo Human" "$SABAKI_CONFIG" 2>/dev/null; then
        echo "Configuring KataGo Human SL engine in Sabaki..."
        python3 - "$SABAKI_CONFIG" "$KATAGO_BIN" "$MAIN_MODEL" "$HUMAN_MODEL" "$DEFAULT_CONFIG" << 'PYEOF'
import json, sys
config_path, katago_bin, main_model, human_model, rank_config = sys.argv[1:6]
try:
    with open(config_path) as f:
        cfg = json.load(f)
    engines = cfg.get("engines.list", [])
    engines.append({
        "name": "KataGo Human",
        "path": katago_bin,
        "args": f"gtp -model {main_model} -human-model {human_model} -config {rank_config}",
        "commands": ""
    })
    cfg["engines.list"] = engines
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print("Sabaki config updated with KataGo Human SL engine.")
except Exception as e:
    print(f"Note: Could not auto-configure Sabaki: {e}", file=sys.stderr)
PYEOF
    fi
else
    # Create config dir and initial settings with engine entry
    mkdir -p "$(dirname "$SABAKI_CONFIG")"
    python3 - "$SABAKI_CONFIG" "$KATAGO_BIN" "$MAIN_MODEL" "$HUMAN_MODEL" "$DEFAULT_CONFIG" << 'PYEOF'
import json, sys
config_path, katago_bin, main_model, human_model, rank_config = sys.argv[1:6]
cfg = {
    "engines.list": [{
        "name": "KataGo Human",
        "path": katago_bin,
        "args": f"gtp -model {main_model} -human-model {human_model} -config {rank_config}",
        "commands": ""
    }]
}
with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)
print("Created Sabaki config with KataGo Human SL engine.")
PYEOF
fi

# Check for any version of sabaki AppImage
SABAKI_PATH=""
for f in "$INSTALL_DIR"/sabaki-*.AppImage; do
    [[ -f "$f" ]] && SABAKI_PATH="$f" && break
done

if [[ -z "$SABAKI_PATH" ]]; then
    echo "Sabaki not found. Downloading v${SABAKI_VERSION} from GitHub..."
    mkdir -p "$INSTALL_DIR"
    DOWNLOAD_URL="https://github.com/SabakiHQ/Sabaki/releases/download/v${SABAKI_VERSION}/${SABAKI_APPIMAGE}"

    if curl -fL -o "$INSTALL_DIR/$SABAKI_APPIMAGE" "$DOWNLOAD_URL" 2>&1; then
        chmod +x "$INSTALL_DIR/$SABAKI_APPIMAGE"
        SABAKI_PATH="$INSTALL_DIR/$SABAKI_APPIMAGE"
        echo "Sabaki v${SABAKI_VERSION} installed."
    else
        echo "Download failed. Please download manually from:"
        echo "  $DOWNLOAD_URL"
        echo "and place it in: $INSTALL_DIR/"
        rm -f "$INSTALL_DIR/$SABAKI_APPIMAGE"
        exit 1
    fi
fi

chmod +x "$SABAKI_PATH" 2>/dev/null
"$SABAKI_PATH" --no-sandbox 2>/dev/null 1>/dev/null

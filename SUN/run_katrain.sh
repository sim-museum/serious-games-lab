#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure KataGo + models are present
source "$SCRIPT_DIR/ensure_katago.sh"

# Set up venv if needed
if [[ ! -d "$SCRIPT_DIR/katrain_venv" ]]; then
    echo "KaTrain venv not found. Installing now..."
    bash "$SCRIPT_DIR/setup_katrain.sh"
fi

if [[ ! -f "$SCRIPT_DIR/katrain_venv/bin/activate" ]]; then
    echo "Error: KaTrain installation failed. Try running setup_katrain.sh manually."
    exit 1
fi

source "$SCRIPT_DIR/katrain_venv/bin/activate"

# If KaTrain config doesn't exist yet, do a quick launch to create the default,
# then immediately patch it with our KataGo paths.
KATRAIN_CONFIG="$HOME/.katrain/config.json"
if [[ ! -f "$KATRAIN_CONFIG" ]]; then
    echo "Creating initial KaTrain config..."
    # KaTrain copies its package config on first import
    python3 -c "import katrain" 2>/dev/null
fi

# Auto-configure KaTrain engine paths (runs every launch to keep paths current)
if [[ -f "$KATRAIN_CONFIG" ]] && command -v python3 &>/dev/null; then
    python3 - "$KATRAIN_CONFIG" "$KATAGO_BIN" "$MAIN_MODEL" "$HUMAN_MODEL" "$ANALYSIS_CFG" << 'PYEOF'
import json, sys
config_path, katago_bin, main_model, human_model, analysis_cfg = sys.argv[1:6]
try:
    with open(config_path) as f:
        cfg = json.load(f)
    engine = cfg.get("engine", {})
    changed = False
    for key, val in [("katago", katago_bin), ("model", main_model),
                     ("humanlike_model", human_model), ("config", analysis_cfg)]:
        if engine.get(key) != val:
            engine[key] = val
            changed = True
    if changed:
        cfg["engine"] = engine
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=4)
        print("KaTrain config updated with KataGo paths.")
except Exception as e:
    print(f"Note: Could not auto-configure KaTrain: {e}", file=sys.stderr)
PYEOF
fi

# Suppress Kivy debug/warning noise (cutbuffer, config upgrade, etc.)
export KIVY_LOG_LEVEL=error
katrain "$@" 2>/dev/null

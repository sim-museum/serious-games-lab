#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT/katrain_venv"

# Ensure KataGo + models are present
source "$ROOT/ensure_katago.sh"

echo "Setting up KaTrain in virtual environment..."

# Create virtual environment
if [[ -d "$VENV_DIR" ]]; then
    echo "Virtual environment already exists at $VENV_DIR"
else
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv and install KaTrain
echo "Installing KaTrain..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
# Install Kivy 2.3.0 first (2.3.1+ has freeze-on-move bug), then KaTrain 1.17.1
# with --no-deps to bypass its Kivy>=2.3.1 requirement.
pip install 'Kivy==2.3.0' 'kivymd==0.104.1'
pip install --no-deps 'KaTrain==1.17.1'

# Auto-configure KaTrain engine paths if config exists
KATRAIN_CONFIG="$HOME/.katrain/config.json"
if [[ -f "$KATRAIN_CONFIG" ]] && command -v python3 &>/dev/null; then
    python3 - "$KATRAIN_CONFIG" "$KATAGO_BIN" "$MAIN_MODEL" "$HUMAN_MODEL" "$ANALYSIS_CFG" << 'PYEOF'
import json, sys
config_path, katago_bin, main_model, human_model, analysis_cfg = sys.argv[1:6]
try:
    with open(config_path) as f:
        cfg = json.load(f)
    engine = cfg.get("engine", {})
    for key, val in [("katago", katago_bin), ("model", main_model),
                     ("humanlike_model", human_model), ("config", analysis_cfg)]:
        engine[key] = val
    cfg["engine"] = engine
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)
    print("KaTrain config updated with KataGo paths.")
except Exception as e:
    print(f"Note: Could not auto-configure KaTrain: {e}", file=sys.stderr)
PYEOF
fi

echo ""
echo "=============================================="
echo "KATRAIN INSTALLATION COMPLETE"
echo "=============================================="
echo ""
echo "To run KaTrain:"
echo "  ./run_katrain.sh"
echo ""
echo "KataGo path: $KATAGO_BIN"
echo "Model path:  $MAIN_MODEL"
echo "Human model: $HUMAN_MODEL"
echo "=============================================="

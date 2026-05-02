#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure KataGo + models are present
source "$SCRIPT_DIR/ensure_katago.sh"
source "$SCRIPT_DIR/analyze_new_sgf.sh"

# Set up venv if needed (missing, broken, or katrain itself not installed —
# e.g. a previous install on Ubuntu 26.04 where Python 3.14 silently rejected
# KaTrain's <3.14 requirement).
venv_has_katrain() {
    [[ -x "$SCRIPT_DIR/katrain_venv/bin/python" ]] && \
        "$SCRIPT_DIR/katrain_venv/bin/python" -c "import katrain" 2>/dev/null
}
if [[ ! -f "$SCRIPT_DIR/katrain_venv/bin/activate" ]] || ! venv_has_katrain; then
    echo "KaTrain venv not found or incomplete. Installing now..."
    bash "$SCRIPT_DIR/setup_katrain.sh"
fi

if ! venv_has_katrain; then
    echo "Error: KaTrain installation failed. Try running setup_katrain.sh manually."
    exit 1
fi

source "$SCRIPT_DIR/katrain_venv/bin/activate"

# Ensure KaTrain config exists. KaTrain only writes config.json when the GUI
# launches, so seed it from the package default on first run; later launches
# just patch the engine paths (KaTrain upgrades wipe custom paths).
KATRAIN_CONFIG="$HOME/.katrain/config.json"
echo "Ensuring KaTrain config is current..."
if [[ ! -f "$KATRAIN_CONFIG" ]]; then
    mkdir -p "$(dirname "$KATRAIN_CONFIG")"
    PKG_DEFAULT_CONFIG="$(python3 -c 'import katrain, os; print(os.path.join(os.path.dirname(katrain.__file__), "config.json"))' 2>/dev/null)"
    if [[ -n "$PKG_DEFAULT_CONFIG" && -f "$PKG_DEFAULT_CONFIG" ]]; then
        cp "$PKG_DEFAULT_CONFIG" "$KATRAIN_CONFIG"
    fi
fi

# Patch engine paths (runs every launch — KaTrain upgrades wipe custom paths)
if command -v python3 &>/dev/null; then
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

# Snapshot SGF files and touch game-started marker
snapshot_sgf_files
if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
    touch "$SGL_GAME_STARTED_MARKER"
fi
type capture_marker_epoch &>/dev/null && capture_marker_epoch

# Suppress Kivy debug/warning noise (cutbuffer, config upgrade, etc.)
export KIVY_LOG_LEVEL=error
katrain "$@" 2>/dev/null

# Run KataGo analysis on any new SGF files
analyze_new_sgf_files

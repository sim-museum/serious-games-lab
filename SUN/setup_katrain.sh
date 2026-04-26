#!/usr/bin/env bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT/katrain_venv"

# Ensure KataGo + models are present (skip if already sourced by caller)
if [[ -z "${KATAGO_BIN:-}" ]]; then
    source "$ROOT/ensure_katago.sh"
fi

# Ensure xclip is available (needed by Kivy clipboard)
if ! command -v xclip &>/dev/null; then
    echo "Installing xclip (needed by KaTrain)..."
    sudo apt-get install -y xclip 2>/dev/null || echo "Note: xclip not installed. Clipboard may not work."
fi

echo "Setting up KaTrain in virtual environment..."

# KaTrain 1.17.1 requires Python >=3.9,<3.14. Ubuntu 26.04 ships only 3.14
# (no other interpreters in the archive), so probe for a compatible one and,
# if none exists, provision Python 3.12 via uv (the same approach used for
# benBridge in scripts/install_dependencies.sh — uv installs a self-contained
# CPython into ~/.local/share/uv/python with no system modifications).
pick_python() {
    local p
    for p in python3.13 python3.12 python3.11 python3.10 python3.9 \
             "$HOME/.local/bin/python3.13" "$HOME/.local/bin/python3.12" \
             "$HOME/.local/bin/python3.11" python3; do
        if command -v "$p" &>/dev/null; then
            if "$p" -c 'import sys; sys.exit(0 if (3,9) <= sys.version_info < (3,14) else 1)' 2>/dev/null; then
                echo "$p"; return 0
            fi
        fi
    done
    return 1
}
PYTHON_BIN="$(pick_python)" || true
if [[ -z "$PYTHON_BIN" ]]; then
    echo "No compatible Python (3.9-3.13) found. Provisioning Python 3.12 via uv..."
    UV_BIN="$HOME/.local/bin/uv"
    if [[ ! -x "$UV_BIN" ]]; then
        echo "  Installing uv (standalone Python manager)..."
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; then
            echo "Error: uv install failed. Check network connectivity."
            exit 1
        fi
    fi
    if [[ ! -x "$UV_BIN" ]]; then
        echo "Error: uv not found at $UV_BIN after install."
        exit 1
    fi
    "$UV_BIN" python install 3.12 2>&1 | tail -1
    PYTHON_BIN="$("$UV_BIN" python find 3.12 2>/dev/null)"
    if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
        echo "Error: uv-managed Python 3.12 not found after install."
        exit 1
    fi
fi
echo "Using $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1)) for the venv."

# Create virtual environment (recreate if broken or wrong Python version)
venv_python_compatible() {
    [[ -x "$VENV_DIR/bin/python" ]] || return 1
    "$VENV_DIR/bin/python" -c 'import sys; sys.exit(0 if (3,9) <= sys.version_info < (3,14) else 1)' 2>/dev/null
}
if [[ -d "$VENV_DIR" ]] && ! venv_python_compatible; then
    echo "Existing venv has an incompatible Python. Recreating..."
    rm -rf "$VENV_DIR"
fi
if [[ -d "$VENV_DIR" && ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "Virtual environment is broken (missing bin/activate). Recreating..."
    rm -rf "$VENV_DIR"
fi
if [[ -d "$VENV_DIR" ]]; then
    echo "Virtual environment already exists at $VENV_DIR"
else
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# Activate venv and install KaTrain
echo "Installing KaTrain..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
# Install Kivy 2.3.0 first (2.3.1+ has freeze-on-move bug), then KaTrain 1.17.1
# with --no-deps to bypass its Kivy>=2.3.1 requirement. Install KaTrain's other
# dependencies explicitly since --no-deps skips them.
pip install 'Kivy==2.3.0' 'kivymd==0.104.1'
pip install chardet docutils ffpyplayer screeninfo urllib3
pip install --no-deps 'KaTrain==1.17.1'

# Create KaTrain config if it doesn't exist yet (first install).
# KaTrain only writes ~/.katrain/config.json when the GUI launches, so seed
# it from the default config that ships with the package.
KATRAIN_CONFIG="$HOME/.katrain/config.json"
if [[ ! -f "$KATRAIN_CONFIG" ]]; then
    echo "Creating initial KaTrain config..."
    mkdir -p "$(dirname "$KATRAIN_CONFIG")"
    PKG_DEFAULT_CONFIG="$(python3 -c 'import katrain, os; print(os.path.join(os.path.dirname(katrain.__file__), "config.json"))' 2>/dev/null)"
    if [[ -n "$PKG_DEFAULT_CONFIG" && -f "$PKG_DEFAULT_CONFIG" ]]; then
        cp "$PKG_DEFAULT_CONFIG" "$KATRAIN_CONFIG"
    else
        echo "Warning: could not locate KaTrain's default config.json in the package."
    fi
fi

# Auto-configure KaTrain engine paths
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

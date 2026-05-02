#!/bin/bash
# Launch the Ben Bridge AI
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Pidfile dir for background Claude critiques (see ben_bridge/ui/game_logger.py).
# Polled at script exit so the launcher doesn't move the BDL mid-insert.
CRITIQUE_PID_DIR="/tmp/ben_bridge_critiques_$$"
export CRITIQUE_PID_DIR
mkdir -p "$CRITIQUE_PID_DIR"

if [[ ! -d venv ]]; then
    echo "Error: venv not found. Run install_dependencies.sh first."
    exit 1
fi

source venv/bin/activate

# --- Self-heal: ensure engine prerequisites are in place ---

BEN_DIR="$(pwd)/ben"
BEN_GITHUB_RAW="https://raw.githubusercontent.com/lorserker/ben/main"

# 1. Config files (not included in a plain git clone)
if [[ ! -f "$BEN_DIR/src/config/default.conf" ]]; then
    echo "Downloading ben config files..."
    for _conf in default.conf BEN-21GF.conf BEN-Sayc.conf GIB-BBO.conf; do
        curl -fSL -o "$BEN_DIR/src/config/$_conf" \
            "$BEN_GITHUB_RAW/src/config/$_conf" 2>/dev/null \
            && echo "  OK: $_conf" || echo "  FAILED: $_conf"
    done
fi

# 2. TF2 model files (Git LFS objects, not fetched without git-lfs)
MODEL_DIR="$BEN_DIR/models/TF2models"
mkdir -p "$MODEL_DIR"
_model_count=$(find "$MODEL_DIR" -name "*.keras" -size +1k 2>/dev/null | wc -l)
if [[ "$_model_count" -lt 16 ]]; then
    echo "Downloading ben TF2 model files (~107 MB)..."
    _ben_models=(
        Contract_2024-12-09-E50.keras  Tricks_2024-12-09-E50.keras
        GIB-BBO-8730_2025-04-19-E30.keras  GIB-BBOInfo-8730_2025-04-19-E30.keras
        Lead-NT_2024-11-04-E200.keras  Lead-Suit_2024-11-04-E200.keras
        SD_2024-07-08-E20.keras  RPDD_2024-07-08-E02.keras
        lefty_nt_2024-07-08-E20.keras  lefty_suit_2024-07-08-E20.keras
        righty_nt_2024-07-16-E20.keras  righty_suit_2024-07-16-E20.keras
        dummy_nt_2024-07-08-E20.keras  dummy_suit_2024-07-08-E20.keras
        decl_nt_2024-07-08-E20.keras  decl_suit_2024-07-08-E20.keras
    )
    for _m in "${_ben_models[@]}"; do
        if [[ ! -f "$MODEL_DIR/$_m" ]] || [[ $(stat -c%s "$MODEL_DIR/$_m" 2>/dev/null) -lt 1024 ]]; then
            echo -n "  $_m ... "
            curl -fSL -o "$MODEL_DIR/$_m" \
                "https://github.com/lorserker/ben/raw/main/models/TF2models/$_m" 2>/dev/null \
                && echo "OK" || echo "FAILED"
        fi
    done
fi

# 3. libdds.so for the DDS solver (system libdds0 package)
if [[ ! -f "$BEN_DIR/bin/libdds.so" ]]; then
    mkdir -p "$BEN_DIR/bin"
    SYSTEM_DDS=$(ldconfig -p 2>/dev/null | grep 'libdds\.so' | head -1 | awk '{print $NF}' || true)
    if [[ -n "$SYSTEM_DDS" ]]; then
        ln -sf "$SYSTEM_DDS" "$BEN_DIR/bin/libdds.so"
        echo "Created libdds.so symlink -> $SYSTEM_DDS"
    else
        echo "WARNING: libdds not found. Install with: sudo apt install libdds0"
    fi
fi

# --- Launch ---

export LD_LIBRARY_PATH="$BEN_DIR/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$BEN_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

cd ben_bridge
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
python3 main.py "$@" 2>/dev/null
exit_code=$?

if [[ $exit_code -ne 0 ]]; then
    echo ""
    echo "benBridge exited with error code $exit_code"
    echo "Re-run with verbose output:"
    echo "  cd $(pwd) && source ../venv/bin/activate && python3 main.py 2>&1 | head -50"
fi

# --- Wait for any in-flight Claude critiques before the launcher moves files ---
cd "$SCRIPT_DIR"
if [[ -d "$CRITIQUE_PID_DIR" ]]; then
    _wait_deadline=$(( $(date +%s) + 180 ))
    while :; do
        _alive=0
        shopt -s nullglob
        for _pidfile in "$CRITIQUE_PID_DIR"/*.pid; do
            _pid=$(cat "$_pidfile" 2>/dev/null) || { rm -f "$_pidfile"; continue; }
            if [[ -n "$_pid" ]] && kill -0 "$_pid" 2>/dev/null; then
                _alive=1
            else
                rm -f "$_pidfile"
            fi
        done
        shopt -u nullglob
        (( _alive == 0 )) && break
        (( $(date +%s) >= _wait_deadline )) && { echo "Critique wait timed out; continuing." ; break; }
        echo "Waiting for Claude critique to finish..."
        sleep 2
    done
    rmdir "$CRITIQUE_PID_DIR" 2>/dev/null || true
fi

# --- Chain to Q-Plus Bridge for comparison ---
# Find the newest BDL from this session (ben writes .bdl; .pbn/.ppl are derived later)
_newest_bdl=""
_newest_bdl_mod=0
while IFS= read -r -d '' f; do
    fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$_newest_bdl_mod" ]]; then
        _newest_bdl="$f"
        _newest_bdl_mod="$fmod"
    fi
done < <(find "$SCRIPT_DIR/ben/DATA/LOG" -maxdepth 1 -name "*.bdl" -type f -print0 2>/dev/null)

if [[ -n "$_newest_bdl" ]]; then
    echo "Found BDL: $_newest_bdl"
    FRI_DIR="$SCRIPT_DIR"
    HARNESS_DIR="$FRI_DIR/guiHarness"

    # Check if Q-Plus Bridge is installed
    FRI_WP="$FRI_DIR/WP"
    QBRIDGE_DIR=""
    [[ -d "$FRI_WP/drive_c/games/qbridge17" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge17"
    [[ -z "$QBRIDGE_DIR" && -d "$FRI_WP/drive_c/games/qbridge15" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge15"

    if [[ -n "$QBRIDGE_DIR" && -f "$HARNESS_DIR/bridge_harness.py" ]]; then
        echo ""
        read -rp "Compare this hand with Q-Plus Bridge? (y/N): " _ben_compare
        if [[ "$_ben_compare" =~ ^[Yy]$ ]]; then
            echo ""
            echo "Launching Q-Plus Bridge and GUI Harness..."
            echo "Use the Comparison Workflow tab (source is pre-loaded from BEN Bridge)."
            echo "  1. In Q-Plus: Own Deals → Enter, then click 'Enter into Q-Plus' in harness"
            echo "  2. Play the hand in Q-Plus — do NOT exit Q-Plus yet"
            echo "  3. In harness: click 'Auto-detect latest' to find Q-Plus log"
            echo "  4. In harness: click 'Convert & copy' to save and annotate with Claude"
            echo "  5. Exit Q-Plus"
            echo ""

            # Launch harness with source pre-loaded (background)
            (
                cd "$HARNESS_DIR"
                if [[ -d venv ]]; then
                    source venv/bin/activate
                else
                    python3 -m venv venv && source venv/bin/activate
                    pip install -q PyQt5 pyautogui 2>/dev/null
                fi
                python3 bridge_harness.py --source "$(realpath "$_newest_bdl")" --game benbridge 2>/dev/null
            ) &
            _harness_pid=$!

            # Launch Q-Plus (foreground — blocks until user exits)
            export WINEPREFIX="$FRI_WP"
            export WINEARCH=win32
            wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
            cd "$QBRIDGE_DIR"
            wine QBRIDGE.EXE 2>/dev/null 1>/dev/null
            cd "$SCRIPT_DIR"

            # Wait for harness to complete (user may still be doing steps 3-4)
            if kill -0 "$_harness_pid" 2>/dev/null; then
                echo ""
                echo "Waiting for GUI Harness to finish..."
                echo "(Complete steps 3-4 in the harness, then close it)"
                wait "$_harness_pid" 2>/dev/null
            fi
        fi
    fi
else
    echo "(No BDL found in $SCRIPT_DIR/ben/DATA/LOG/ — skipping Q-Plus comparison)"
fi

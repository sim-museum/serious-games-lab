#!/bin/bash
# Launch the Ben Bridge AI
cd "$(dirname "$0")"

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

# --- Clean up log files from previous sessions (afterGameReport will have moved them) ---

LOG_DIR="$BEN_DIR/DATA/LOG"
rm -f "$LOG_DIR"/log-*.bdl "$LOG_DIR"/log-*.pbn "$LOG_DIR"/log-*.ppl 2>/dev/null

# --- Launch ---

export LD_LIBRARY_PATH="$BEN_DIR/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$BEN_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

cd ben_bridge
_ben_snapshot_time=$(date +%s)
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"

# Run benBridge in background and monitor for GUI window close.
# benBridge's PyQt app hangs after the window closes (zombie child from
# claude subprocess).  xdotool can't detect this because PyQt keeps
# hidden X11 windows alive.  Instead, detect when the main window is no
# longer mapped (visible) by checking WM_STATE with xprop.
python3 main.py "$@" 2>/dev/null &
MAIN_PID=$!

# Wait for a visible window to appear (up to 30s)
_ben_main_wid=""
for _ in $(seq 1 30); do
    kill -0 "$MAIN_PID" 2>/dev/null || break
    for wid in $(xdotool search --pid "$MAIN_PID" 2>/dev/null); do
        if xprop -id "$wid" WM_STATE 2>/dev/null | grep -q 'state: Normal'; then
            _ben_main_wid="$wid"
            break 2
        fi
    done
    sleep 1
done

# Poll until the main window is no longer in Normal (visible) state
if [[ -n "$_ben_main_wid" ]]; then
    while kill -0 "$MAIN_PID" 2>/dev/null; do
        if ! xprop -id "$_ben_main_wid" WM_STATE 2>/dev/null | grep -q 'state: Normal'; then
            sleep 3
            kill "$MAIN_PID" 2>/dev/null || true
            break
        fi
        sleep 2
    done
else
    # Fallback: no window found, just wait for the process
    wait "$MAIN_PID" 2>/dev/null || true
fi
wait "$MAIN_PID" 2>/dev/null || true
exit_code=$?

if [[ $exit_code -ne 0 && $exit_code -ne 143 ]]; then
    echo ""
    echo "benBridge exited with error code $exit_code"
    echo "Re-run with verbose output:"
    echo "  cd $(pwd) && source ../venv/bin/activate && python3 main.py 2>&1 | head -50"
fi

# Post-game: find new BDL files, convert to PBN and PPL, run Claude annotation
BEN_LOG_DIR="$BEN_DIR/DATA/LOG"
FRI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HARNESS_DIR="$FRI_DIR/guiHarness"
ANNOTATE_SCRIPT="$FRI_DIR/claude_annotate_bridge_single.sh"

if [[ -d "$BEN_LOG_DIR" ]]; then
    while IFS= read -r -d '' bdl_file; do
        fmod=$(stat -c %Y "$bdl_file" 2>/dev/null) || continue
        [[ "$fmod" -lt "$_ben_snapshot_time" ]] && continue
        base=$(basename "$bdl_file" .bdl)

        # Convert BDL to PBN (for scid/xboard import)
        if [[ -f "$HARNESS_DIR/ppl_to_pbn.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            pbn_file="${bdl_file%.bdl}.pbn"
            if [[ ! -f "$pbn_file" ]]; then
                PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import ppl_to_pbn, sys
try:
    data = ppl_to_pbn.bdl_to_ppl('$bdl_file')
    # Also generate PBN via bridge_harness
    import bridge_harness as bh
    pbn = bh.pbn_file_to_bdl('$bdl_file', source_label='BN')
except Exception:
    pass
# Direct BDL→PBN: parse BDL and produce PBN-like output
try:
    board = ppl_to_pbn._parse_bdl_file('$bdl_file')
    # Minimal PBN from BDL
    lines = []
    for key in ['Event','Dealer','Deal','Declarer','Contract','Result']:
        if key in board:
            lines.append(f'[{key} \"{board[key]}\"]')
    with open('$pbn_file', 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('  Converted $base.bdl -> $base.pbn')
except Exception as e:
    print(f'  PBN conversion failed: {e}', file=sys.stderr)
" 2>/dev/null || true
            fi
        fi

        # Convert BDL to PPL (for Bridge Baron 12 import)
        if [[ -f "$HARNESS_DIR/ppl_to_pbn.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            ppl_file="${bdl_file%.bdl}.ppl"
            if [[ ! -f "$ppl_file" ]]; then
                PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import ppl_to_pbn
ppl_to_pbn.bdl_to_ppl('$bdl_file', '$ppl_file')
print('  Converted $base.bdl -> $base.ppl')
" 2>/dev/null || true
            fi
        fi

        # Run Claude Code annotation on the BDL
        if [[ -x "$ANNOTATE_SCRIPT" ]]; then
            annotated="${bdl_file%.bdl}_annotated.bdl"
            if [[ ! -f "$annotated" ]]; then
                bash "$ANNOTATE_SCRIPT" "$bdl_file" "$annotated"
            fi
        fi
    done < <(find "$BEN_LOG_DIR" -maxdepth 1 -name "*.bdl" -type f -print0 2>/dev/null)
fi

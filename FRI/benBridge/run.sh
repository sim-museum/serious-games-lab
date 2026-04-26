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

# --- Annotate the most recent BEN PBN with Claude ---
# Q-Plus gold-standard comparison: arranged manually by the user in a
# separate qplus.sh session on the same board.
cd "$SCRIPT_DIR"
_newest_pbn=""
_newest_pbn_mod=0
while IFS= read -r -d '' f; do
    fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$_newest_pbn_mod" ]]; then
        _newest_pbn="$f"
        _newest_pbn_mod="$fmod"
    fi
done < <(find "$SCRIPT_DIR/ben/DATA/LOG" -maxdepth 1 -name "*.pbn" -type f -print0 2>/dev/null)

if [[ -n "$_newest_pbn" ]]; then
    FRI_DIR="$SCRIPT_DIR"
    HARNESS_DIR="$FRI_DIR/guiHarness"
    REPORT_DIR="$FRI_DIR/afterGameReport"

    # Reuse the launcher's most recent benbridge subdir if present, else
    # create one keyed on the current minute.
    _ben_dest=""
    if [[ -d "$REPORT_DIR" ]]; then
        _ben_dest=$(find "$REPORT_DIR" -mindepth 1 -maxdepth 1 -type d -name "*_benbridge" \
                        -printf '%T@ %p\n' 2>/dev/null \
                    | sort -rn | head -1 | cut -d' ' -f2-)
    fi
    if [[ -z "$_ben_dest" || ! -d "$_ben_dest" ]]; then
        _ben_dest="$REPORT_DIR/$(date '+%y%m%d_%H%M')_benbridge"
    fi
    mkdir -p "$_ben_dest"

    base=$(basename "$_newest_pbn" .pbn)
    cp "$_newest_pbn" "$_ben_dest/${base}.pbn"

    # Convert PBN → BDL via the harness's library function.
    if [[ -f "$HARNESS_DIR/bridge_harness.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
        PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import bridge_harness as bh
bdl = bh.pbn_file_to_bdl('$_ben_dest/${base}.pbn', source_label='BEN')
with open('$_ben_dest/${base}.bdl', 'w') as f:
    f.write(bdl)
print('  Converted ${base}.pbn -> ${base}.bdl')
" 2>/dev/null || true
    fi

    if [[ -f "$_ben_dest/${base}.bdl" && -x "$FRI_DIR/claude_annotate_bridge_single.sh" ]]; then
        echo "Running Claude annotation on BEN deal log..."
        bash "$FRI_DIR/claude_annotate_bridge_single.sh" \
            "$_ben_dest/${base}.bdl" "$_ben_dest/${base}_annotated.bdl"
    fi
fi

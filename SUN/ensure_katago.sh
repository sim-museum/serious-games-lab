#!/usr/bin/env bash
# ensure_katago.sh — Shared idempotent KataGo setup helper
# Source this file from GUI launcher scripts. It sets path variables and
# ensures KataGo binary + models exist, downloading/building as needed.
# All steps are idempotent — skipped if already done.

KATAGO_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATAGO_DIR="$KATAGO_SCRIPT_DIR/katago"
KATAGO_BIN="$KATAGO_DIR/katago"
MAIN_MODEL="$KATAGO_DIR/main_model.bin.gz"
HUMAN_MODEL="$KATAGO_DIR/b18c384nbt-humanv0.bin.gz"
TEMPLATE_CFG="$KATAGO_DIR/gtp_human5k_example.cfg"
ANALYSIS_CFG="$KATAGO_DIR/analysis_example.cfg"

KATAGO_VERSION="1.16.4"
KATAGO_ZIP="katago-v${KATAGO_VERSION}-opencl-linux-x64.zip"
KATAGO_URL="https://github.com/lightvector/KataGo/releases/download/v${KATAGO_VERSION}/${KATAGO_ZIP}"
HUMANSL_MODEL_URL="https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz"
STRONG_MODEL_URL="https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"

_katago_download() {
    local url="$1" output="$2"
    if command -v curl &>/dev/null; then
        curl -fL -o "$output" "$url"
    elif command -v wget &>/dev/null; then
        wget -O "$output" "$url"
    else
        echo "Error: Neither curl nor wget found." >&2
        return 1
    fi
}

# --- 1. Ensure KataGo binary ---
# Also rebuild if the binary exists but can't run (e.g. missing shared libraries)
if [[ -x "$KATAGO_BIN" ]] && ! "$KATAGO_BIN" version &>/dev/null; then
    echo "KataGo binary exists but cannot run (missing libraries). Rebuilding from source..."
    rm -f "$KATAGO_BIN"
fi
if [[ ! -x "$KATAGO_BIN" ]]; then
    mkdir -p "$KATAGO_DIR"
    echo "KataGo binary not found. Downloading OpenCL release v${KATAGO_VERSION}..."
    if _katago_download "$KATAGO_URL" "$KATAGO_DIR/$KATAGO_ZIP" && \
       unzip -o "$KATAGO_DIR/$KATAGO_ZIP" -d "$KATAGO_DIR"; then
        rm -f "$KATAGO_DIR/$KATAGO_ZIP"
        # Move contents from nested directory if present
        NESTED="$KATAGO_DIR/katago-v${KATAGO_VERSION}-opencl-linux-x64"
        if [[ -d "$NESTED" ]]; then
            mv "$NESTED"/* "$KATAGO_DIR/"
            rmdir "$NESTED"
        fi
        chmod +x "$KATAGO_BIN"
        # Verify the downloaded binary actually works on this system
        if "$KATAGO_BIN" version &>/dev/null; then
            echo "KataGo OpenCL v${KATAGO_VERSION} binary installed and verified."
        else
            echo "Downloaded KataGo binary has missing libraries:"
            ldd "$KATAGO_BIN" 2>/dev/null | grep "not found" || true
            echo "Falling back to CPU build from source..."
            rm -f "$KATAGO_BIN"
            bash "$KATAGO_SCRIPT_DIR/build_katago_cpu.sh"
        fi
    else
        rm -f "$KATAGO_DIR/$KATAGO_ZIP"
        echo "OpenCL download failed. Falling back to CPU build from source..."
        bash "$KATAGO_SCRIPT_DIR/build_katago_cpu.sh"
    fi
fi

# --- 2. Ensure strong model ---
if [[ ! -f "$MAIN_MODEL" ]]; then
    echo "Downloading strong model..."
    _katago_download "$STRONG_MODEL_URL" "$MAIN_MODEL" || \
        echo "WARNING: Failed to download strong model."
fi

# --- 3. Ensure Human SL model ---
if [[ ! -f "$HUMAN_MODEL" ]]; then
    echo "Downloading Human SL model..."
    _katago_download "$HUMANSL_MODEL_URL" "$HUMAN_MODEL" || \
        echo "WARNING: Failed to download Human SL model."
fi

# --- 4. Ensure at least one GTP human rank config exists ---
if ! ls "$KATAGO_DIR"/gtp_human_rank_*.cfg &>/dev/null; then
    if [[ -f "$TEMPLATE_CFG" ]]; then
        echo "Creating default human rank config (5k)..."
        cp "$TEMPLATE_CFG" "$KATAGO_DIR/gtp_human_rank_5k.cfg"
        sed -i 's/^humanSLProfile = .*/humanSLProfile = rank_5k/' \
            "$KATAGO_DIR/gtp_human_rank_5k.cfg"
    else
        echo "WARNING: Template config $TEMPLATE_CFG not found; skipping rank config creation."
    fi
fi

# --- 5. Set DEFAULT_CONFIG to the first available rank config ---
DEFAULT_CONFIG=""
for cfg in "$KATAGO_DIR"/gtp_human_rank_*.cfg; do
    [[ -f "$cfg" ]] && DEFAULT_CONFIG="$cfg" && break
done

# --- 6. Run OpenCL autotuning if needed ---
# KataGo tunes per GPU per model version. Tuning takes ~1 min per model and
# must complete uninterrupted; GUI clients may kill KataGo before it finishes,
# leaving a corrupt tuning file. Running it here ensures tuning is done once
# before any client launches.
_KATAGO_TUNE_DIR="$HOME/.katago/opencltuning"
_KATRAIN_TUNE_DIR="$HOME/.katrain/opencltuning"

_katago_needs_tuning() {
    # Returns 0 (true) if any expected tuning file is missing or if KataGo
    # reports it invalid. We check for mv14 (main model) and mv15 (human model).
    local dir="$1"
    [[ ! -d "$dir" ]] && return 0
    local count
    count=$(ls "$dir"/tune*_mv14.txt "$dir"/tune*_mv15.txt 2>/dev/null | wc -l)
    [[ "$count" -lt 2 ]]
}

if [[ -x "$KATAGO_BIN" && -f "$MAIN_MODEL" && -f "$HUMAN_MODEL" ]] && \
   _katago_needs_tuning "$_KATAGO_TUNE_DIR"; then
    # Verify katago can actually run before attempting tuning
    if "$KATAGO_BIN" version &>/dev/null; then
        echo ""
        echo "Running one-time KataGo GPU autotuning (this takes 1-2 minutes)..."
        echo "This must complete before Go GUIs can use the engine."
        echo ""

        # Tune main model (mv14) then human model (mv15) in one invocation.
        # GTP mode accepts "quit" cleanly. Using the human rank config so both
        # -model and -human-model are loaded and tuned.
        echo "quit" | timeout 180 "$KATAGO_BIN" gtp \
            -model "$MAIN_MODEL" \
            -human-model "$HUMAN_MODEL" \
            -config "${DEFAULT_CONFIG:-$KATAGO_DIR/default_gtp.cfg}" \
            2>&1 | grep -E '(Tuning|tuning|Done|ERROR|OpenCL|FP16|backend)' || true

        if _katago_needs_tuning "$_KATAGO_TUNE_DIR"; then
            echo "WARNING: GPU autotuning may not have completed successfully."
        else
            echo "GPU autotuning complete."
        fi
    else
        echo "WARNING: KataGo binary cannot run (missing libraries?). Skipping autotuning."
        echo "Try: ldd $KATAGO_BIN | grep 'not found'"
    fi
fi

# --- 7. Ensure Go problem collections are downloaded ---
PROBLEMS_DIR="$KATAGO_SCRIPT_DIR/problems"
if [[ ! -d "$PROBLEMS_DIR/gogameguru" || ! -d "$PROBLEMS_DIR/mygogrinder" ]]; then
    echo ""
    echo "Downloading Go problem collections..."
    bash "$KATAGO_SCRIPT_DIR/download_go_problems.sh"
fi

# Copy tuning files to KaTrain's location so it doesn't re-tune
if [[ -d "$_KATAGO_TUNE_DIR" ]]; then
    mkdir -p "$_KATRAIN_TUNE_DIR"
    for f in "$_KATAGO_TUNE_DIR"/tune*.txt; do
        [[ -f "$f" ]] && cp -n "$f" "$_KATRAIN_TUNE_DIR/" 2>/dev/null
    done
fi

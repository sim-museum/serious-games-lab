#!/bin/bash
# BanksiaGui - Chess GUI with lc0 (Leela Chess Zero) engine support
# Downloads BanksiaGui if not already installed, then launches it.
# Builds lc0 from source if not present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL/BanksiaGui"
BANKSIA_SH="$INSTALL_DIR/BanksiaGUI.sh"

# --- Ensure lc0 engine is available ---
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "lc0 engine path: $SCRIPT_DIR/INSTALL/lc0_cpu"
    echo "Weights file:    $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
    echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
else
    echo ""
    echo "lc0 engine not found. Building from source..."
    bash "$SCRIPT_DIR/install_lc0.sh"
    if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
        echo ""
        echo "lc0 built successfully."
        echo "lc0 engine path: $SCRIPT_DIR/INSTALL/lc0_cpu"
        echo "Weights file:    $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
        echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
    fi
fi
echo ""

# --- Download BanksiaGui if not present ---
if [[ ! -f "$BANKSIA_SH" ]]; then
    echo "BanksiaGui not found. Downloading..."
    mkdir -p "$SCRIPT_DIR/INSTALL"

    DOWNLOAD_URL="https://banksiagui.com/dl/BanksiaGui-0.58-linux64.zip"
    if curl -fL -o /tmp/banksia_download.zip "$DOWNLOAD_URL" 2>&1; then
        unzip -o /tmp/banksia_download.zip -d "$SCRIPT_DIR/INSTALL/" >/dev/null 2>&1
        rm -f /tmp/banksia_download.zip

        if [[ ! -f "$BANKSIA_SH" ]]; then
            echo "Download succeeded but BanksiaGUI.sh not found in archive."
            echo "Please download manually from https://banksiagui.com/"
            exit 1
        fi
        chmod +x "$BANKSIA_SH"
        chmod +x "$INSTALL_DIR/bin/BanksiaGUI" 2>/dev/null
        echo "BanksiaGui installed successfully."
    else
        echo "Download failed."
        echo "Please download manually from https://banksiagui.com/"
        rm -f /tmp/banksia_download.zip
        exit 1
    fi
fi

# --- Configure lc0 as default engine if not already configured ---
BANKSIA_CONFIG_DIR="$HOME/.config/BanksiaGUI"
BANKSIA_ENGINES="$BANKSIA_CONFIG_DIR/banksiaengines.json"
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    # Write lc0 engine config with maia-1100 weights (beginner-level human-like play)
    if [[ ! -f "$BANKSIA_ENGINES" ]] || ! grep -q "lc0" "$BANKSIA_ENGINES" 2>/dev/null; then
        mkdir -p "$BANKSIA_CONFIG_DIR"
        cat > "$BANKSIA_ENGINES" << ENGINES_EOF
[
  {
    "app" :
    {
      "arguments" : [],
      "author" : "LeelaChessZero Contributors",
      "color" : 4288092609,
      "command" : "$SCRIPT_DIR/INSTALL/lc0_cpu",
      "elo" : 1100,
      "gpu" : false,
      "idName" : "lc0",
      "initStrings" : [],
      "name" : "lc0 (Maia 1100)",
      "protocol" : "uci",
      "working folder" : "$SCRIPT_DIR/INSTALL"
    },
    "comment" : "Maia 1100 weights with movetime 0.1s (approx nibbler level 2)",
    "options" : [
      {
        "default" : "",
        "name" : "WeightsFile",
        "type" : "string",
        "value" : "$SCRIPT_DIR/INSTALL/maia_weights/maia-1100.pb.gz"
      }
    ]
  }
]
ENGINES_EOF
        echo "Configured lc0 with Maia 1100 weights as default engine in BanksiaGui."
    fi
    # Set time control to movetime 0.1s (equivalent to nibbler level 2: ~2 nodes)
    BANKSIA_MAIN="$BANKSIA_CONFIG_DIR/banksiamain.json"
    if [[ -f "$BANKSIA_MAIN" ]]; then
        python3 -c "
import json, sys
with open('$BANKSIA_MAIN') as f:
    cfg = json.load(f)
cfg['time control'] = {'mode': 'movetime', 'time': 0.1}
cfg['demo']['time control'] = {'mode': 'movetime', 'time': 0.1}
with open('$BANKSIA_MAIN', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null && echo "Set time control to movetime 0.1s (beginner level)."
    fi
fi

# --- Launch BanksiaGui ---
echo "Launching BanksiaGui..."
cd "$INSTALL_DIR"

# Touch game-started marker for afterGamesReport collection
if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
    touch "$SGL_GAME_STARTED_MARKER"
fi

# Launch opening repertoire helper alongside the chess GUI
if [[ -x "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" ]]; then
    echo "Launching Opening Repertoire helper..."
    bash "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" &
fi

# Snapshot existing PGN files before launching
pgn_snapshot=$(mktemp)
DAY_DIR="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/WED"
find "$DAY_DIR" -maxdepth 1 -name "*.pgn" -type f 2>/dev/null | sort > "$pgn_snapshot"
snapshot_time=$(stat -c %Y "$pgn_snapshot")

bash BanksiaGUI.sh 2>/dev/null

# Find PGN files created or modified during the session
new_pgn_files=""
while IFS= read -r -d '' f; do
    fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$snapshot_time" ]]; then
        new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
    fi
done < <(find "$DAY_DIR" -maxdepth 1 -name "*.pgn" -type f -print0 2>/dev/null)
rm -f "$pgn_snapshot"

new_pgn_files=$(echo "$new_pgn_files" | sed '/^$/d')

if [[ -n "$new_pgn_files" ]]; then
    echo ""
    echo "Running Stockfish analysis on saved PGN files..."
    VENV_DIR="$SCRIPT_DIR/openingRepertoire/venv"
    STOCKFISH="$(command -v stockfish 2>/dev/null || echo /usr/games/stockfish)"

    if [[ -d "$VENV_DIR" && -x "$STOCKFISH" ]]; then
        while IFS= read -r pgn_file; do
            [[ -z "$pgn_file" ]] && continue
            base=$(basename "$pgn_file")
            annotated="${pgn_file%.pgn}_analysed.pgn"
            echo "  Analysing: $base"
            "$VENV_DIR/bin/python3" "$SCRIPT_DIR/chessmaster/stockfish_annotate.py" \
                "$pgn_file" "$annotated" --engine "$STOCKFISH" --depth 15 \
                && { mv "$annotated" "$pgn_file"; echo "  Done: $base"; } \
                || { rm -f "$annotated"; echo "  Analysis failed for $base"; }
        done <<< "$new_pgn_files"
    else
        echo "  Stockfish or python-chess venv not available, skipping analysis."
    fi
fi

#!/bin/bash

# Nibbler - Chess analysis GUI for Leela Chess Zero (lc0)
# Downloads from GitHub releases if not present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NIBBLER_VERSION="2.5.3"
NIBBLER_DIR="$SCRIPT_DIR/INSTALL/nibbler-${NIBBLER_VERSION}-linux"

clear

echo "The first time you run the default Leela Chess Zero (lc0) front end, named nibbler,"
echo "you must specify the path to the lc0 chess engine."

if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "from the menu select Engine/Choose Engine"
    echo "select $SCRIPT_DIR/INSTALL/lc0_cpu"
    echo "next select the weights file $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
    echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
    echo "once you have selected lc0_cpu once, nibbler stores its location in ~/.config/Nibbler"
    echo "so you do not have to enter this path again."
    echo ""
    echo "Optional: If you have a modern Nvidia GPU, you can run a faster version of lc0."
    echo "Optional: sudo apt install -y nvidia-opencl-dev"
    echo "Optional: then in nibbler Engine/Choose Engine select"
    echo "Optional: $SCRIPT_DIR/INSTALL/lc0_linux_graphicsAcceleration/lc0_opencl"
    echo "If in doubt, start with the default lc0_cpu option as described above."
else
    echo ""
    echo "lc0 engine not found. Building from source..."
    bash "$SCRIPT_DIR/install_lc0.sh"
    if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
        echo ""
        echo "lc0 built successfully. In nibbler, select Engine/Choose Engine"
        echo "and set engine path to: $SCRIPT_DIR/INSTALL/lc0_cpu"
        echo "and weights to: $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
        echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
    fi
fi

# Download nibbler if not present
if [[ ! -d "$NIBBLER_DIR" ]] || [[ ! -f "$NIBBLER_DIR/nibbler" ]]; then
    echo ""
    echo "Nibbler not found. Downloading v${NIBBLER_VERSION} from GitHub..."
    mkdir -p "$SCRIPT_DIR/INSTALL"
    DOWNLOAD_URL="https://github.com/rooklift/nibbler/releases/download/v${NIBBLER_VERSION}/nibbler-${NIBBLER_VERSION}-linux.zip"

    if curl -fL -o /tmp/nibbler_download.zip "$DOWNLOAD_URL" 2>&1; then
        unzip -o /tmp/nibbler_download.zip -d "$SCRIPT_DIR/INSTALL/" >/dev/null 2>&1
        rm -f /tmp/nibbler_download.zip
        chmod +x "$NIBBLER_DIR/nibbler" 2>/dev/null
        echo "Nibbler v${NIBBLER_VERSION} installed."
    else
        echo "Download failed. Please download manually from:"
        echo "  $DOWNLOAD_URL"
        echo "and extract to $SCRIPT_DIR/INSTALL/"
        rm -f /tmp/nibbler_download.zip
        exit 1
    fi
fi

# Download Maia chess weights if not present
MAIA_DIR="$SCRIPT_DIR/INSTALL/maia_weights"
mkdir -p "$MAIA_DIR"
for ELO in 1100 1200 1300 1400 1500 1600 1700 1800 1900; do
    MAIA_FILE="$MAIA_DIR/maia-${ELO}.pb.gz"
    if [[ ! -f "$MAIA_FILE" ]]; then
        echo "Downloading Maia ${ELO} weights..."
        curl -fL -o "$MAIA_FILE" "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-${ELO}.pb.gz" 2>&1 || {
            echo "Failed to download maia-${ELO}.pb.gz"
            rm -f "$MAIA_FILE"
        }
    fi
done
echo ""
echo "Maia weights (human-like play, ELO 1100-1900) are in: $MAIA_DIR/"
echo "To use: in nibbler, set weights path to a Maia file instead of tinygyal-8.pb.gz"
echo ""

# Touch game-started marker for afterGameReport collection
if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
    touch "$SGL_GAME_STARTED_MARKER"
fi

# Launch opening repertoire helper alongside the chess GUI
if [[ -x "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" ]]; then
    echo "Launching Opening Repertoire helper..."
    bash "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" &
fi

# Snapshot existing PGN files before launching (check both WED/ and nibbler dir)
pgn_snapshot=$(mktemp)
find "$SCRIPT_DIR" -maxdepth 1 -name "*.pgn" -type f 2>/dev/null | sort > "$pgn_snapshot"
find "$NIBBLER_DIR" -maxdepth 1 -name "*.pgn" -type f 2>/dev/null | sort >> "$pgn_snapshot"
snapshot_time=$(date +%s)

# Launch nibbler from WED/ so default saves land in WED/
cd "$SCRIPT_DIR"
"$NIBBLER_DIR/nibbler" --no-sandbox 2>/dev/null

# Find PGN files created or modified during the session (check both locations)
new_pgn_files=""
for search_dir in "$SCRIPT_DIR" "$NIBBLER_DIR"; do
    while IFS= read -r -d '' f; do
        fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
        if [[ "$fmod" -gt "$snapshot_time" ]]; then
            # Move files from nibbler dir to WED/ so afterGameReport finds them
            if [[ "$search_dir" == "$NIBBLER_DIR" && "$f" == "$NIBBLER_DIR"/* ]]; then
                mv "$f" "$SCRIPT_DIR/"
                f="$SCRIPT_DIR/$(basename "$f")"
            fi
            # Add .pgn extension if missing
            if [[ "$f" != *.pgn ]]; then
                mv "$f" "${f}.pgn"
                f="${f}.pgn"
            fi
            new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
        fi
    done < <(find "$search_dir" -maxdepth 1 \( -name "*.pgn" -o -name "[0-9][0-9][0-9][0-9][0-9][0-9]*" \) -type f -print0 2>/dev/null)
done
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

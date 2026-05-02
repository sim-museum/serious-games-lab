#!/bin/bash
# BanksiaGui - Chess GUI with lc0 (Leela Chess Zero) engine support
# Downloads BanksiaGui if not already installed, then launches it.
# Builds lc0 from source if not present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/INSTALL/BanksiaGui"
BANKSIA_SH="$INSTALL_DIR/BanksiaGUI.sh"

# Ensure /usr/games is on PATH so `command -v stockfish` resolves when this
# script is run directly (Ubuntu 26.04 dropped /usr/games from the
# default profile PATH).
case ":$PATH:" in
    *":/usr/games:"*) ;;
    *) PATH="$PATH:/usr/games" ;;
esac

# --- Ensure lc0 engine is available (build from source, fall back to pre-built) ---
if [[ ! -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "lc0 engine not found. Building from source..."
    if bash "$SCRIPT_DIR/install_lc0.sh" 2>&1; then
        echo "lc0 built successfully."
    else
        echo "WARNING: lc0 not available. Build failed and no pre-built binary found."
    fi
fi
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    echo "lc0 engine path: $SCRIPT_DIR/INSTALL/lc0_cpu"
    echo "Weights file:    $SCRIPT_DIR/INSTALL/tinygyal-8.pb.gz"
    echo "Maia human-like weights (ELO 1100-1900) are also available in $SCRIPT_DIR/INSTALL/maia_weights/"
fi
echo ""

# --- Download BanksiaGui if not present ---
if [[ ! -x "$INSTALL_DIR/bin/BanksiaGUI" ]]; then
    echo "BanksiaGui not found. Downloading..."
    mkdir -p "$SCRIPT_DIR/INSTALL"

    DOWNLOAD_URL="https://banksiagui.com/dl/BanksiaGui-0.58-linux64.zip"
    if curl -fL -o /tmp/banksia_download.zip "$DOWNLOAD_URL" 2>&1; then
        unzip -o /tmp/banksia_download.zip -d "$SCRIPT_DIR/INSTALL/"
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

# --- Ensure Maia weights are available ---
MAIA_WEIGHTS="$SCRIPT_DIR/INSTALL/maia_weights/maia-1100.pb.gz"
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]] && [[ ! -f "$MAIA_WEIGHTS" ]]; then
    echo "Downloading Maia 1100 weights..."
    mkdir -p "$SCRIPT_DIR/INSTALL/maia_weights"
    curl -fSL --progress-bar -o "$MAIA_WEIGHTS" \
        "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1100.pb.gz" || {
        echo "  WARNING: Failed to download Maia weights."
        rm -f "$MAIA_WEIGHTS"
    }
fi

# --- Place lc0 in BanksiaGui's engine scan directory ---
BSG_ENGINES="$INSTALL_DIR/bin/bsg-engines"
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]] && [[ ! -x "$BSG_ENGINES/lc0" ]]; then
    cat > "$BSG_ENGINES/lc0" << 'WRAPPER_EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../../../" && pwd)"
exec "$SCRIPT_DIR/INSTALL/lc0_cpu" --weights="$SCRIPT_DIR/INSTALL/maia_weights/maia-1100.pb.gz" "$@"
WRAPPER_EOF
    chmod +x "$BSG_ENGINES/lc0"
    echo "Created lc0 wrapper in BanksiaGui engine directory."
fi

# --- Configure lc0 with Maia weights and set as default engine ---
BANKSIA_CONFIG_DIR="$HOME/.config/BanksiaGUI"
BANKSIA_ENGINES="$BANKSIA_CONFIG_DIR/banksiaengines.json"
if [[ -x "$SCRIPT_DIR/INSTALL/lc0_cpu" ]]; then
    # Remove stale config so BanksiaGui re-scans and picks up lc0
    if [[ -f "$BANKSIA_ENGINES" ]] && ! grep -q "lc0" "$BANKSIA_ENGINES" 2>/dev/null; then
        rm -f "$BANKSIA_ENGINES"
        echo "Cleared stale engine config to trigger lc0 detection."
    fi
fi

# --- Launch BanksiaGui ---
echo "Launching BanksiaGui..."
cd "$INSTALL_DIR"

# Touch game-started marker for afterGameReport collection
if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
    touch "$SGL_GAME_STARTED_MARKER"
fi

# Capture the marker's mtime now so the timestamped afterGameReport
# subdir name stays stable even if another launcher session starts a
# concurrent game and clobbers/removes the marker while we're still
# annotating.
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
capture_marker_epoch

# Launch opening repertoire helper alongside the chess GUI
if [[ -x "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" ]]; then
    echo "Launching Opening Repertoire helper..."
    bash "$SCRIPT_DIR/openingRepertoire/run_opening_repertoire.sh" &
fi

# Snapshot existing PGN files before launching
pgn_snapshot=$(mktemp)
DAY_DIR="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/WED"
find "$DAY_DIR" -maxdepth 3 -name "*.pgn" -not -path "*/INSTALL/*" -not -path "*/chessmaster/*" -type f 2>/dev/null | sort > "$pgn_snapshot"
snapshot_time=$(stat -c %Y "$pgn_snapshot")

bash BanksiaGUI.sh 2>/dev/null

# Find PGN files created or modified during the session
new_pgn_files=""
while IFS= read -r -d '' f; do
    fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$snapshot_time" ]]; then
        new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
    fi
done < <(find "$DAY_DIR" -maxdepth 3 -name "*.pgn" -not -path "*/INSTALL/*" -not -path "*/chessmaster/*" -not -path "*/afterGameReport/*" -type f -print0 2>/dev/null)
rm -f "$pgn_snapshot"

new_pgn_files=$(echo "$new_pgn_files" | sed '/^$/d')

if [[ -n "$new_pgn_files" ]]; then
    # Move PGN(s) into the timestamped afterGameReport subdir BEFORE
    # annotation so a concurrent game's collect_after_game_report can't
    # race in and grab them mid-annotation.  Files inside afterGameReport
    # are excluded from collect's search.
    report_subdir="$(post_game_subdir "$DAY_DIR" banksiagui)"
    moved_pgn_files=""
    while IFS= read -r pgn_file; do
        [[ -z "$pgn_file" ]] && continue
        [[ -f "$pgn_file" ]] || continue
        target="$report_subdir/$(basename "$pgn_file")"
        mv -f "$pgn_file" "$target"
        moved_pgn_files=$(printf '%s\n%s' "$moved_pgn_files" "$target")
    done <<< "$new_pgn_files"
    new_pgn_files=$(echo "$moved_pgn_files" | sed '/^$/d')

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

    # Add English-language annotations via Claude Code
    source "$SCRIPT_DIR/claude_annotate_pgn.sh"
    while IFS= read -r pgn_file; do
        [[ -z "$pgn_file" ]] && continue
        claude_annotate_pgn "$pgn_file"
    done <<< "$new_pgn_files"

    echo "  Annotated PGN(s) saved to afterGameReport/$(basename "$report_subdir")/"
fi

# Restore the marker's mtime so the launcher's collect_after_game_report
# derives the same subdir name we used.  No-op when run outside the launcher.
restore_marker_epoch

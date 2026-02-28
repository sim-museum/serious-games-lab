#!/bin/bash
# Launch Chess Opening Repertoire trainer
# Three-tier PGN data loading pipeline:
#   Tier 1: sglBinaries .sg4 → convert with scidpgn
#   Tier 2: Download Lichess Elite PGN (2500+ rated games)
#   Tier 3: Use existing downloaded PGN/cache

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/../INSTALL"
cd "$SCRIPT_DIR"

# --- Paths: sglBinaries source ---
SGL_BASE="$INSTALL_DIR/25000grandmasterGames"
SGL_PGN="$SGL_BASE.pgn"
SGL_CACHE="${SGL_PGN}.book_cache.pkl"

# --- Paths: downloaded source ---
DL_PGN="$INSTALL_DIR/lichess_elite_opening_games.pgn"
DL_CACHE="${DL_PGN}.book_cache.pkl"

MAX_GAMES=25000

# --- Helper: build cache for a PGN file ---
build_cache() {
    local pgn="$1"
    local cache="${pgn}.book_cache.pkl"
    if [[ -f "$cache" && "$cache" -nt "$pgn" ]]; then
        return 0
    fi
    echo "Building opening book cache (this may take a few minutes)..."
    rm -f "$cache"
    source venv/bin/activate
    python3 OpeningRepertoire.py --pgn "$pgn" --build-cache
}

# --- Helper: download Lichess Elite PGN ---
download_lichess_elite() {
    local year month url zipfile extracted_pgn
    # Try the 6 most recent months
    for i in $(seq 0 5); do
        year=$(date -d "today - $i months" +%Y)
        month=$(date -d "today - $i months" +%m)
        url="https://database.nikonoel.fr/lichess_elite_${year}-${month}.zip"
        zipfile="$INSTALL_DIR/lichess_elite_${year}-${month}.zip"

        echo "Trying Lichess Elite database: ${year}-${month}..."
        if wget -q --spider "$url" 2>/dev/null; then
            echo "Downloading $url ..."
            if wget -q --show-progress -O "$zipfile" "$url"; then
                # Extract the PGN file from the zip
                extracted_pgn=$(unzip -l "$zipfile" '*.pgn' 2>/dev/null | awk '/\.pgn$/{print $NF}' | head -1)
                if [[ -n "$extracted_pgn" ]]; then
                    unzip -o -j "$zipfile" "$extracted_pgn" -d "$INSTALL_DIR" >/dev/null 2>&1
                    local full_extracted="$INSTALL_DIR/$(basename "$extracted_pgn")"
                    if [[ -f "$full_extracted" ]]; then
                        echo "Truncating to $MAX_GAMES games..."
                        # Use awk to extract first MAX_GAMES games (games separated by blank lines after result)
                        awk -v max="$MAX_GAMES" '
                            /^\[Event / { count++ }
                            count > max { exit }
                            { print }
                        ' "$full_extracted" > "$DL_PGN"
                        # Clean up
                        [[ "$full_extracted" != "$DL_PGN" ]] && rm -f "$full_extracted"
                        rm -f "$zipfile"
                        echo "Downloaded and prepared $MAX_GAMES games from Lichess Elite ${year}-${month}"
                        return 0
                    fi
                fi
                rm -f "$zipfile"
            fi
        fi
    done
    echo "Error: Could not download Lichess Elite database from any recent month."
    return 1
}

# --- Tier 1: sglBinaries .sg4 exists ---
if [[ -f "${SGL_BASE}.sg4" ]]; then
    # Check if user was previously using downloaded data and sgl cache doesn't exist yet
    if [[ ( -f "$DL_CACHE" || -f "$DL_PGN" ) && ! -f "$SGL_CACHE" && ! -f "$SGL_PGN" ]]; then
        echo ""
        echo "sglBinaries grandmaster database detected."
        echo "You are currently using downloaded Lichess data."
        echo "Switching to sglBinaries requires a one-time conversion (~10 min)."
        read -r -p "Switch to sglBinaries database? (Y/n) " answer
        if [[ "$answer" =~ ^[Nn] ]]; then
            # User wants to keep downloaded data
            PGN_FILE="$DL_PGN"
        else
            # Convert .sg4 to PGN
            echo "Converting Scid database to PGN format..."
            if command -v scidpgn &>/dev/null; then
                scidpgn "$SGL_BASE" > "$SGL_PGN"
                echo "PGN file created: $SGL_PGN"
                PGN_FILE="$SGL_PGN"
            else
                echo "scidpgn not found. Install scid: sudo apt install scid"
                echo "Falling back to downloaded data."
                PGN_FILE="$DL_PGN"
            fi
        fi
    else
        # No previous downloaded data, or sgl data already exists — use sglBinaries
        if [[ ! -f "$SGL_PGN" ]]; then
            echo "Converting Scid database to PGN format..."
            if command -v scidpgn &>/dev/null; then
                scidpgn "$SGL_BASE" > "$SGL_PGN"
                echo "PGN file created: $SGL_PGN"
            else
                echo "scidpgn not found. Install scid: sudo apt install scid"
                exit 1
            fi
        fi
        PGN_FILE="$SGL_PGN"
    fi

# --- Tier 3: existing downloaded PGN/cache ---
elif [[ -f "$DL_PGN" || -f "$DL_CACHE" ]]; then
    PGN_FILE="$DL_PGN"

# --- Tier 2: download Lichess Elite ---
else
    echo "No opening book data found. Downloading Lichess Elite database..."
    if download_lichess_elite; then
        PGN_FILE="$DL_PGN"
    else
        echo "Could not obtain opening book data."
        echo "Install sglBinaries_1 or check your internet connection."
        exit 1
    fi
fi

# --- Stale cache handling ---
CACHE_FILE="${PGN_FILE}.book_cache.pkl"
if [[ -f "$CACHE_FILE" && -f "$PGN_FILE" && "$PGN_FILE" -nt "$CACHE_FILE" ]]; then
    echo "PGN file is newer than cache, removing stale cache..."
    rm -f "$CACHE_FILE"
fi

# --- Build cache if needed ---
if [[ -f "$PGN_FILE" && ! -f "$CACHE_FILE" ]]; then
    build_cache "$PGN_FILE"
fi

# --- Launch the application ---
source venv/bin/activate
python3 OpeningRepertoire.py --pgn "$PGN_FILE" "$@"

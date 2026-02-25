#!/bin/bash
# Launch Chess Opening Repertoire trainer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/../INSTALL"
PGN_FILE="$INSTALL_DIR/25000grandmasterGames.pgn"
SCID_BASE="$INSTALL_DIR/25000grandmasterGames"
CACHE_FILE="${PGN_FILE}.book_cache.pkl"

cd "$SCRIPT_DIR"

# Convert Scid database to PGN if PGN doesn't exist
if [[ ! -f "$PGN_FILE" && -f "${SCID_BASE}.sg4" ]]; then
    echo "Converting Scid database to PGN format..."
    if command -v scidpgn &>/dev/null; then
        scidpgn "$SCID_BASE" > "$PGN_FILE"
        echo "PGN file created: $PGN_FILE"
    else
        echo "scidpgn not found. Install scid: sudo apt install scid"
        exit 1
    fi
fi

# Remove stale cache only if PGN is newer (cache was from a previous PGN or missing PGN)
if [[ -f "$CACHE_FILE" && -f "$PGN_FILE" && "$PGN_FILE" -nt "$CACHE_FILE" ]]; then
    echo "PGN file is newer than cache, removing stale cache..."
    rm -f "$CACHE_FILE"
fi

source venv/bin/activate
python3 OpeningRepertoire.py "$@"

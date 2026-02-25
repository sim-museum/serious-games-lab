#!/usr/bin/env bash
# install_game.sh - Lists tar files from ~/2404tarFiles/, extracts selected game,
# calls configure_lutris.sh, and creates .installed marker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TAR_DIR="$HOME/2404tarFiles"

echo "=============================================="
echo "  Install Binary Game from Tar Archive"
echo "=============================================="
echo ""

if [[ ! -d "$TAR_DIR" ]]; then
    echo "Error: Tar archive directory not found: $TAR_DIR"
    echo "Place your game .tar.gz/.tar files in $TAR_DIR"
    exit 1
fi

# List available tar files
mapfile -t TAR_FILES < <(find "$TAR_DIR" -maxdepth 1 \( -name '*.tar.gz' -o -name '*.tar' -o -name '*.tar.xz' -o -name '*.tar.bz2' \) -printf '%f\n' | sort)

if [[ ${#TAR_FILES[@]} -eq 0 ]]; then
    echo "No tar archives found in $TAR_DIR"
    exit 1
fi

echo "Available archives:"
echo ""
for i in "${!TAR_FILES[@]}"; do
    printf "  %2d) %s\n" "$((i+1))" "${TAR_FILES[$i]}"
done

echo ""
read -rp "Select archive to install (number): " choice

if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#TAR_FILES[@]} )); then
    echo "Invalid selection."
    exit 1
fi

TAR_FILE="${TAR_FILES[$((choice-1))]}"
TAR_PATH="$TAR_DIR/$TAR_FILE"

# Ask which day-of-week dir to install into
echo ""
echo "Install into which day directory?"
echo "  1) MON   2) TUE   3) WED   4) THU   5) FRI   6) SAT   7) SUN"
read -rp "Select day (1-7): " day_choice

case "$day_choice" in
    1) DAY="MON" ;; 2) DAY="TUE" ;; 3) DAY="WED" ;; 4) DAY="THU" ;;
    5) DAY="FRI" ;; 6) DAY="SAT" ;; 7) DAY="SUN" ;;
    *) echo "Invalid day selection."; exit 1 ;;
esac

DEST_DIR="$REPO_ROOT/$DAY"
mkdir -p "$DEST_DIR"

echo ""
echo "Extracting $TAR_FILE into $DEST_DIR ..."
tar xf "$TAR_PATH" -C "$DEST_DIR"
echo "Extraction complete."

# Derive game name from tar filename (strip extensions)
GAME_NAME="${TAR_FILE%.tar.*}"
GAME_NAME="${GAME_NAME%.tar}"

# Create installed marker
touch "$DEST_DIR/.installed_${GAME_NAME}"
echo "Created marker: $DEST_DIR/.installed_${GAME_NAME}"

# Attempt Lutris configuration
echo ""
read -rp "Configure this game in Lutris? (y/N): " configure_lutris
if [[ "$configure_lutris" =~ ^[Yy]$ ]]; then
    "$SCRIPT_DIR/configure_lutris.sh" "$GAME_NAME" "$DEST_DIR"
fi

echo ""
echo "Installation complete: $GAME_NAME"

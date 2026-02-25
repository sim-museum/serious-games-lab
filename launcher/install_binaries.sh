#!/usr/bin/env bash
# install_binaries.sh - Extract sglBinaries archives into downloads/
#
# Scans downloads/ for sglBinaries_*.tar.gz files.
# Extracts into downloads/ (not the repo tree), creates .extracted_* marker.
# After extraction, runs distribute_binaries.sh to move files to game INSTALL/ dirs.
#
# Usage:
#   install_binaries.sh              # Process all pending archives
#   install_binaries.sh <file.tar.gz>  # Process a specific archive

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

mkdir -p "$DOWNLOADS_DIR"

extract_archive() {
    local archive="$1"
    local base
    base="$(basename "$archive")"
    local marker="$DOWNLOADS_DIR/.extracted_${base}"

    if [[ -f "$marker" ]]; then
        msg_ok "Already extracted: $base"
        return 0
    fi

    msg_info "Extracting $base into $DOWNLOADS_DIR/ ..."
    echo "  This may take a while for large archives."
    echo ""

    tar xzf "$archive" -C "$DOWNLOADS_DIR/"

    touch "$marker"
    msg_ok "Extracted: $base"
}

echo ""
echo -e "${BOLD}=============================================="
echo "  Serious Games Lab - Binary Archive Installer"
echo -e "==============================================${NC}"
echo ""

# If a specific file was given as argument, process just that one
if [[ $# -ge 1 ]]; then
    if [[ -f "$1" ]]; then
        extract_archive "$1"
    else
        msg_error "Not found: $1"
        exit 1
    fi
    "$REPO_ROOT/scripts/distribute_binaries.sh"
    exit 0
fi

# Otherwise, scan downloads/ for all sglBinaries
found=0

# Handle .tar.gz files
for f in "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz; do
    [[ -f "$f" ]] || continue
    found=1
    base="$(basename "$f")"
    marker="$DOWNLOADS_DIR/.extracted_${base}"
    if [[ -f "$marker" ]]; then
        msg_ok "Already extracted: $base"
    else
        extract_archive "$f"
    fi
done

if [[ $found -eq 0 ]]; then
    msg_warn "No sglBinaries archives found in $DOWNLOADS_DIR/"
    echo ""
    echo "  Place sglBinaries_*.tar.gz files in: $DOWNLOADS_DIR/"
    echo ""
    echo "  Available archives (see config/binary_archives.txt):"
    if [[ -f "$CONFIG_DIR/binary_archives.txt" ]]; then
        grep -v '^#' "$CONFIG_DIR/binary_archives.txt" | grep -v '^$' | while IFS='|' read -r name desc days; do
            printf "    %-25s %s\n" "$name" "$desc"
        done
    fi
    echo ""
fi

# Distribute extracted files to game INSTALL directories
"$REPO_ROOT/scripts/distribute_binaries.sh"

echo ""
msg_ok "Binary archive installation complete."

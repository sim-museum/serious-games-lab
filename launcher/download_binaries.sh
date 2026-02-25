#!/usr/bin/env bash
# download_binaries.sh - Download sglBinaries archives
#
# Reads config/binary_archives.txt for the list of available archives.
# Downloads them into downloads/ using wget or curl.
#
# Usage:
#   download_binaries.sh              # Interactive: choose which to download
#   download_binaries.sh <name>       # Download a specific archive by name

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

MANIFEST="$CONFIG_DIR/binary_archives.txt"

if [[ ! -f "$MANIFEST" ]]; then
    msg_error "Archive manifest not found: $MANIFEST"
    exit 1
fi

mkdir -p "$DOWNLOADS_DIR"

# Read manifest into arrays
declare -a ARCHIVE_NAMES=()
declare -a ARCHIVE_DESCS=()
declare -a ARCHIVE_DAYS=()

while IFS='|' read -r name desc days; do
    [[ "$name" =~ ^#.*$ ]] && continue
    [[ -z "$name" ]] && continue
    ARCHIVE_NAMES+=("$name")
    ARCHIVE_DESCS+=("$desc")
    ARCHIVE_DAYS+=("$days")
done < "$MANIFEST"

download_archive() {
    local name="$1"
    local dest="$DOWNLOADS_DIR/$name"

    if [[ -f "$dest" ]]; then
        msg_ok "Already downloaded: $name"
        return 0
    fi

    # The download URL needs to be configured by the user
    # Placeholder: check for a base URL file
    local base_url=""
    if [[ -f "$CONFIG_DIR/download_url.txt" ]]; then
        base_url="$(cat "$CONFIG_DIR/download_url.txt")"
        base_url="${base_url%/}"
    fi

    if [[ -z "$base_url" ]]; then
        msg_error "No download URL configured."
        echo ""
        echo "  To configure, create: $CONFIG_DIR/download_url.txt"
        echo "  containing the base URL where sglBinaries archives are hosted."
        echo "  Example: https://example.com/sglBinaries"
        echo ""
        echo "  Alternatively, download manually and place in: $DOWNLOADS_DIR/"
        return 1
    fi

    local url="$base_url/$name"
    msg_info "Downloading $name ..."
    echo "  URL: $url"
    echo "  Destination: $dest"
    echo ""

    if command -v wget &>/dev/null; then
        wget --progress=bar:force -O "$dest" "$url"
    elif command -v curl &>/dev/null; then
        curl -L --progress-bar -o "$dest" "$url"
    else
        msg_error "Neither wget nor curl found. Install one and try again."
        return 1
    fi

    if [[ -f "$dest" ]] && [[ -s "$dest" ]]; then
        msg_ok "Downloaded: $name"
    else
        msg_error "Download failed: $name"
        rm -f "$dest"
        return 1
    fi
}

echo ""
echo -e "${BOLD}=============================================="
echo "  Serious Games Lab - Binary Archive Downloader"
echo -e "==============================================${NC}"
echo ""

# If a specific archive name was given
if [[ $# -ge 1 ]]; then
    download_archive "$1"
    exit $?
fi

# Interactive mode: show available archives
echo "Available archives:"
echo ""

for i in "${!ARCHIVE_NAMES[@]}"; do
    local_name="${ARCHIVE_NAMES[$i]}"
    desc="${ARCHIVE_DESCS[$i]}"
    days="${ARCHIVE_DAYS[$i]}"

    status=""
    if [[ -f "$DOWNLOADS_DIR/$local_name" ]]; then
        if [[ -f "$DOWNLOADS_DIR/.extracted_${local_name}" ]]; then
            status="${GREEN}[extracted]${NC}"
        else
            status="${YELLOW}[downloaded, not extracted]${NC}"
        fi
    else
        status="${RED}[not downloaded]${NC}"
    fi

    printf "  %d) %-25s %s\n" "$((i+1))" "$local_name" "$desc"
    printf "     Days: %-20s %b\n" "$days" "$status"
done

echo ""
echo "  A) Download all missing archives"
echo "  Q) Back"
echo ""
read -rp "Enter choice: " choice

case "$choice" in
    [Aa])
        for name in "${ARCHIVE_NAMES[@]}"; do
            if [[ ! -f "$DOWNLOADS_DIR/$name" ]]; then
                download_archive "$name" || true
            fi
        done
        ;;
    [Qq])
        exit 0
        ;;
    *)
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#ARCHIVE_NAMES[@]} )); then
            download_archive "${ARCHIVE_NAMES[$((choice-1))]}"
        else
            msg_error "Invalid choice: $choice"
        fi
        ;;
esac

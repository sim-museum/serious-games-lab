#!/usr/bin/env bash
# setup_lutris.sh - Check and download Lutris wine runners for Serious Games Lab
#
# Reads config/wine_runners.csv, checks which runners are installed under
# ~/.local/share/lutris/runners/wine/, and offers to download missing ones
# from GitHub.

set -euo pipefail

# Runners install under $HOME — running as root would put them in /root
if [[ $EUID -eq 0 ]]; then
    echo "Error: do not run this script with sudo."
    echo "Runners install to ~/.local/share/lutris/runners/wine — as root"
    echo "they would land in /root and Lutris/the launcher won't find them."
    echo "Re-run as your normal user: ./setup_lutris.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CSV_FILE="$REPO_ROOT/config/wine_runners.csv"
RUNNERS_DIR="$HOME/.local/share/lutris/runners/wine"

echo "=============================================="
echo "  Lutris Wine Runner Setup"
echo "  Serious Games Lab"
echo "=============================================="
echo ""

if [[ ! -f "$CSV_FILE" ]]; then
    echo "Error: CSV not found: $CSV_FILE"
    exit 1
fi

mkdir -p "$RUNNERS_DIR"

# Extract unique runners from CSV (skip header, column 2)
mapfile -t RUNNERS < <(tail -n +2 "$CSV_FILE" | cut -d',' -f2 | sort -u)

echo "Required wine runners:"
echo ""

missing=()
for runner in "${RUNNERS[@]}"; do
    if [[ -d "$RUNNERS_DIR/$runner" ]]; then
        echo "  [OK]      $runner"
    else
        echo "  [MISSING] $runner"
        missing+=("$runner")
    fi
done

echo ""

if [[ ${#missing[@]} -eq 0 ]]; then
    echo "All runners are installed."
    echo "=============================================="
    exit 0
fi

echo "${#missing[@]} runner(s) missing."
echo ""
read -rp "Download and install missing runners? (Y/n): " reply
if [[ "$reply" =~ ^[Nn]$ ]]; then
    echo "Skipped. Install runners manually into: $RUNNERS_DIR/<runner-name>/"
    exit 0
fi

# --- Download helpers ---

download_and_extract() {
    local url="$1"
    local runner="$2"
    local tmpfile
    tmpfile="$(mktemp /tmp/runner-XXXXXX.tar.xz)"

    echo ""
    echo "  Downloading: $url"
    if ! curl -fSL --progress-bar -o "$tmpfile" "$url"; then
        echo "  FAILED to download: $url"
        rm -f "$tmpfile"
        return 1
    fi

    echo "  Extracting to $RUNNERS_DIR/"
    local before after
    before="$(ls -1 "$RUNNERS_DIR")"
    tar -xJf "$tmpfile" -C "$RUNNERS_DIR/"
    rm -f "$tmpfile"

    if [[ ! -d "$RUNNERS_DIR/$runner" ]]; then
        # Some archives extract under a different name (e.g. Kron4ek's
        # wine-9.22-staging-amd64) — if exactly one new directory appeared,
        # rename it to the expected runner name.
        after="$(ls -1 "$RUNNERS_DIR")"
        local -a newdirs=()
        mapfile -t newdirs < <(comm -13 <(sort <<<"$before") <(sort <<<"$after"))
        if [[ ${#newdirs[@]} -eq 1 && -d "$RUNNERS_DIR/${newdirs[0]}" ]]; then
            echo "  Renaming ${newdirs[0]} → $runner"
            mv "$RUNNERS_DIR/${newdirs[0]}" "$RUNNERS_DIR/$runner"
        fi
    fi

    if [[ -d "$RUNNERS_DIR/$runner" ]]; then
        echo "  [OK] $runner installed"
    else
        # Some archives extract with a slightly different name — check
        echo "  WARNING: Expected directory $runner not found after extraction."
        echo "  Contents of $RUNNERS_DIR/:"
        ls "$RUNNERS_DIR/" | head -20
    fi
}

# Build download URLs based on runner name pattern
# Runner dir names are lutris-*, but GitHub asset filenames are wine-lutris-*
# Returns newline-separated URLs (primary + fallback) since tag naming varies
get_download_urls() {
    local runner="$1"
    local asset="wine-${runner}.tar.xz"

    # Strip arch suffix to get base name for tag parsing
    local base="$runner"
    base="${base%-x86_64}"
    base="${base%-i686}"

    if [[ "$runner" == *GE-Proton* ]]; then
        # GE-Proton runners from GloriousEggroll/wine-ge-custom
        local tag="${base#lutris-}"
        echo "https://github.com/GloriousEggroll/wine-ge-custom/releases/download/${tag}/${asset}"

    elif [[ "$runner" == *fshack* ]]; then
        # Fshack runners from lutris/wine — fshack is only in asset name, not tag
        # Tag format varies: lutris-X.Y or lutris-wine-X.Y (newer releases)
        local tag="${base//-fshack/}"
        local ver="${tag#lutris-}"
        echo "https://github.com/lutris/wine/releases/download/${tag}/${asset}"
        echo "https://github.com/lutris/wine/releases/download/lutris-wine-${ver}/${asset}"

    else
        # Standard lutris runners from lutris/wine
        # Tag format varies: lutris-X.Y or lutris-wine-X.Y (newer releases)
        local tag="$base"
        local ver="${tag#lutris-}"
        echo "https://github.com/lutris/wine/releases/download/${tag}/${asset}"
        echo "https://github.com/lutris/wine/releases/download/lutris-wine-${ver}/${asset}"

        # lutris/wine stopped publishing GitHub releases after 7.2; newer
        # versions (e.g. 9.22-staging) are available from Kron4ek/Wine-Builds.
        # Their archive extracts as wine-X.Y[-staging]-amd64 — the caller
        # renames it to the expected runner directory name.
        local kver="${ver%-staging}"
        echo "https://github.com/Kron4ek/Wine-Builds/releases/download/${kver}/wine-${ver}-amd64.tar.xz"
    fi
}

echo ""
echo "Downloading ${#missing[@]} runner(s)..."

failed=()
for runner in "${missing[@]}"; do
    mapfile -t urls < <(get_download_urls "$runner")
    downloaded=false
    for url in "${urls[@]}"; do
        if download_and_extract "$url" "$runner"; then
            downloaded=true
            break
        fi
    done
    if ! $downloaded; then
        failed+=("$runner")
    fi
done

echo ""
echo "=============================================="
if [[ ${#failed[@]} -eq 0 ]]; then
    echo "  All runners installed successfully."
else
    echo "  ${#failed[@]} runner(s) failed to download:"
    for f in "${failed[@]}"; do
        echo "    - $f"
    done
    echo ""
    echo "  Download manually from:"
    echo "    https://github.com/lutris/wine/releases"
    echo "    https://github.com/GloriousEggroll/wine-ge-custom/releases"
    echo "  Extract into: $RUNNERS_DIR/<runner-name>/"
fi
echo "=============================================="

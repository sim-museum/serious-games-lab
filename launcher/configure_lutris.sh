#!/usr/bin/env bash
# configure_lutris.sh - Reads config/260213lutrisData.csv, normalizes paths,
# and generates Lutris YAML per game with correct wine runner, prefix isolation,
# and DXVK settings.
#
# Usage: configure_lutris.sh [GAME_NAME] [GAME_DIR]
#   If no args, processes all games in the CSV.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CSV_FILE="$REPO_ROOT/config/260213lutrisData.csv"
LUTRIS_CONFIG_DIR="$HOME/.config/lutris/games"

if [[ ! -f "$CSV_FILE" ]]; then
    echo "Error: CSV file not found: $CSV_FILE"
    exit 1
fi

mkdir -p "$LUTRIS_CONFIG_DIR"

FILTER_GAME="${1:-}"
GAME_DIR="${2:-}"

normalize_exe_path() {
    local original_path="$1"
    # Strip /home/{g,m}/ese/ prefix and rebuild with REPO_ROOT
    local relative_path
    relative_path=$(echo "$original_path" | sed -E 's|^/home/[^/]+/ese/||')
    echo "$REPO_ROOT/$relative_path"
}

# Skip header line, process CSV
tail -n +2 "$CSV_FILE" | while IFS=',' read -r name runner exe_path bits dxvk; do
    # Skip if filtering and doesn't match
    if [[ -n "$FILTER_GAME" ]] && [[ "$name" != "$FILTER_GAME" ]]; then
        continue
    fi

    # Skip entries with no executable path
    if [[ -z "$exe_path" ]]; then
        echo "Skipping $name: no executable path"
        continue
    fi

    # Normalize the executable path
    normalized_exe=$(normalize_exe_path "$exe_path")
    exe_dir=$(dirname "$normalized_exe")
    exe_basename=$(basename "$normalized_exe")

    # Derive wine prefix from the path (find WP/ directory)
    wine_prefix=$(echo "$normalized_exe" | sed -E 's|(.*)/WP/.*|\1/WP|')

    # Sanitize game name for filename
    safe_name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-')

    # Determine architecture
    arch="win32"
    if [[ "$bits" == "64" ]]; then
        arch="win64"
    fi

    # DXVK settings
    dxvk_enabled="false"
    if [[ "$dxvk" == "yes" ]]; then
        dxvk_enabled="true"
    fi

    # Determine runner name (strip trailing whitespace)
    runner=$(echo "$runner" | tr -d '[:space:]')

    # Generate Lutris YAML
    YAML_FILE="$LUTRIS_CONFIG_DIR/${safe_name}.yml"

    cat > "$YAML_FILE" << EOF
game:
    exe: $normalized_exe
    prefix: $wine_prefix
    working_dir: $exe_dir
    args: ""

runner:
    version: $runner

system:
    disable_runtime: false

game_slug: $safe_name
name: $name
runner: wine
year: 2026

wine:
    Wine prefix: $wine_prefix
    architecture: $arch
    dxvk: $dxvk_enabled
    vkd3d: $dxvk_enabled
EOF

    echo "Generated Lutris config: $YAML_FILE"
done

echo ""
echo "Lutris configuration complete."

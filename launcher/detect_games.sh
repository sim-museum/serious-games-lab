#!/usr/bin/env bash
# detect_games.sh - CSV-driven game detection
# Reads filesForLauncher/launcherScripts.csv and checks availability.
# Output: one line per game in format "DAY|AVAILABLE|DISPLAY_NAME|SCRIPT"
#   AVAILABLE is: "yes", "missing_data", or "no"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Read CSV: row 1 is header (MON,TUE,...,SUN), rows 2+ are script names
line_num=0
while IFS= read -r line; do
    ((line_num++)) || true
    if [[ $line_num -eq 1 ]]; then
        IFS=',' read -ra header <<< "$line"
        continue
    fi

    IFS=',' read -ra row <<< "$line"
    for col in "${!row[@]}"; do
        script="${row[$col]}"
        [[ -z "$script" ]] && continue
        day="${header[$col]}"

        available="yes"
        if is_source_game "$script"; then
            if ! script_exists "$day" "$script"; then
                available="no"
            fi
        else
            if ! script_exists "$day" "$script"; then
                available="no"
            elif ! has_binary_data "$day" "$script"; then
                available="missing_data"
            fi
        fi

        display="$(script_display_name "$script")"
        echo "$day|$available|$display|$script"
    done
done < "$CSV_FILE"

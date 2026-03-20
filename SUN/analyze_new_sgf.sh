#!/usr/bin/env bash
# analyze_new_sgf.sh — Post-game SGF analysis helper for Go game scripts
#
# Source this file after ensure_katago.sh. Call analyze_new_sgf_files after
# the game exits to find new .sgf files, run KataGo analysis, and save
# annotated versions for afterGamesReport collection.
#
# Requires: KATAGO_BIN, MAIN_MODEL, ANALYSIS_CFG (set by ensure_katago.sh)

# Snapshot SGF files before the game launches.
# Call this right before touching SGL_GAME_STARTED_MARKER.
snapshot_sgf_files() {
    _SGF_SNAPSHOT=$(mktemp)
    _SGF_SNAPSHOT_TIME=$(date +%s)
    local day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/SUN"
    find "$day_dir" -maxdepth 1 -name "*.sgf" -type f 2>/dev/null | sort > "$_SGF_SNAPSHOT"
}

# Find new/modified SGF files and run KataGo analysis on each.
# Call this after the game exits.
analyze_new_sgf_files() {
    local day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/SUN"
    local annotate_script="$SCRIPT_DIR/katago_annotate.py"

    # Find SGF files newer than the snapshot
    local new_sgf=""
    while IFS= read -r -d '' f; do
        local fmod
        fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
        if [[ "$fmod" -gt "$_SGF_SNAPSHOT_TIME" ]]; then
            new_sgf=$(printf '%s\n%s' "$new_sgf" "$f")
        fi
    done < <(find "$day_dir" -maxdepth 1 -name "*.sgf" -type f \
                -not -path "*/afterGamesReport/*" -print0 2>/dev/null)

    # Also check home directory for SGF files saved by GUIs
    for search_dir in "$HOME/.katrain" "$HOME/.config/q5go" "$HOME/.config/Sabaki"; do
        [[ -d "$search_dir" ]] || continue
        while IFS= read -r -d '' f; do
            local fmod
            fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
            if [[ "$fmod" -gt "$_SGF_SNAPSHOT_TIME" ]]; then
                new_sgf=$(printf '%s\n%s' "$new_sgf" "$f")
            fi
        done < <(find "$search_dir" -maxdepth 3 -name "*.sgf" -type f -print0 2>/dev/null)
    done

    rm -f "$_SGF_SNAPSHOT"
    new_sgf=$(echo "$new_sgf" | sort -u | sed '/^$/d')

    [[ -z "$new_sgf" ]] && return 0

    # Check that KataGo and analysis prerequisites are available
    if [[ ! -x "$KATAGO_BIN" || ! -f "$MAIN_MODEL" ]]; then
        echo "KataGo not available, skipping SGF analysis."
        return 0
    fi

    # Use analysis config, fall back to any available GTP config
    local cfg="${ANALYSIS_CFG:-}"
    if [[ ! -f "$cfg" ]]; then
        for c in "$KATAGO_DIR"/gtp_human_rank_*.cfg "$KATAGO_DIR"/default_gtp.cfg; do
            [[ -f "$c" ]] && cfg="$c" && break
        done
    fi
    if [[ -z "$cfg" || ! -f "$cfg" ]]; then
        echo "No KataGo config found, skipping SGF analysis."
        return 0
    fi

    echo ""
    echo "Running KataGo analysis on saved SGF files..."

    while IFS= read -r sgf_file; do
        [[ -z "$sgf_file" ]] && continue
        local base
        base=$(basename "$sgf_file")
        local annotated="$day_dir/${base%.sgf}_analysed.sgf"

        python3 "$annotate_script" "$sgf_file" "$annotated" \
            --katago "$KATAGO_BIN" --model "$MAIN_MODEL" --config "$cfg" \
            && { mv "$annotated" "$sgf_file"; echo "  Done: $base"; } \
            || { rm -f "$annotated"; echo "  Analysis failed for $base"; }
    done <<< "$new_sgf"
}

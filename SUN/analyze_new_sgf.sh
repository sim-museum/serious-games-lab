#!/usr/bin/env bash
# analyze_new_sgf.sh — Post-game SGF analysis helper for Go game scripts
#
# Source this file after ensure_katago.sh. Call analyze_new_sgf_files after
# the game exits to find new .sgf files, run KataGo analysis, and save
# annotated versions alongside the originals in afterGameReport.
#
# Requires: KATAGO_BIN, MAIN_MODEL, ANALYSIS_CFG (set by ensure_katago.sh)

# Snapshot SGF files before the game launches.
# Call this right before touching SGL_GAME_STARTED_MARKER.
snapshot_sgf_files() {
    _SGF_SNAPSHOT=$(mktemp)
    _SGF_SNAPSHOT_TIME=$(date +%s)
    local day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/SUN"
    find "$day_dir" -name "*.sgf" -type f 2>/dev/null | sort > "$_SGF_SNAPSHOT"
}

# Find new/modified SGF files and run KataGo analysis on each.
# Produces an _analysed.sgf alongside the original in afterGameReport.
# Call this after the game exits.
analyze_new_sgf_files() {
    local day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}/SUN"
    local annotate_script="$SCRIPT_DIR/katago_annotate.py"

    # Find SGF files newer than the snapshot — search the whole day dir
    # (including afterGameReport where users may save directly) plus
    # common GUI config dirs.
    local new_sgf=""
    local search_dirs=("$day_dir")
    for d in "$HOME/.katrain" "$HOME/.config/q5go" "$HOME/.config/Sabaki"; do
        [[ -d "$d" ]] && search_dirs+=("$d")
    done

    for search_dir in "${search_dirs[@]}"; do
        while IFS= read -r -d '' f; do
            local fmod
            fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
            if [[ "$fmod" -gt "$_SGF_SNAPSHOT_TIME" ]]; then
                new_sgf=$(printf '%s\n%s' "$new_sgf" "$f")
            fi
        done < <(find "$search_dir" -maxdepth 4 \( -name "*.sgf" -o -name "*.rsgf" \) -type f \
                    -not -name "*_analysed.sgf" -print0 2>/dev/null)
        # Also check for SGF files saved without extension (e.g. from Sabaki)
        while IFS= read -r -d '' f; do
            local fmod
            fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
            if [[ "$fmod" -gt "$_SGF_SNAPSHOT_TIME" ]]; then
                # Check if it's actually an SGF file by content
                if head -1 "$f" 2>/dev/null | grep -q '^(;GM\[1\]'; then
                    # Rename with .sgf extension so KataGo can process it
                    mv "$f" "${f}.sgf" 2>/dev/null && f="${f}.sgf"
                    new_sgf=$(printf '%s\n%s' "$new_sgf" "$f")
                fi
            fi
        done < <(find "$search_dir" -maxdepth 4 -type f \
                    -not -name "*.sgf" -not -name "*.rsgf" -not -name "*.py" \
                    -not -name "*.sh" -not -name "*.txt" -not -name "*.md" \
                    -not -name "*.json" -not -name "*.pkl" -not -name "*.cfg" \
                    -not -path "*/INSTALL/*" -not -path "*/.git/*" \
                    -newer "$_SGF_SNAPSHOT" -print0 2>/dev/null)
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

    # Create _analysed.sgf next to each original.
    # The launcher's collect_after_game_report runs AFTER this and will
    # pick up both the original and _analysed files.
    local analysed_files=""
    while IFS= read -r sgf_file; do
        [[ -z "$sgf_file" ]] && continue
        local base dir stem annotated
        base=$(basename "$sgf_file")
        dir=$(dirname "$sgf_file")
        stem="${base%.sgf}"
        annotated="${dir}/${stem}_analysed.sgf"

        if python3 "$annotate_script" "$sgf_file" "$annotated" \
            --katago "$KATAGO_BIN" --model "$MAIN_MODEL" --config "$cfg"; then
            echo "  Done: $base -> ${stem}_analysed.sgf"
            analysed_files=$(printf '%s\n%s' "$analysed_files" "$annotated")
        else
            rm -f "$annotated"
            echo "  Analysis failed for $base"
        fi
    done <<< "$new_sgf"

    # Add English-language annotations via Claude Code
    analysed_files=$(echo "$analysed_files" | sed '/^$/d')
    if [[ -n "$analysed_files" ]]; then
        source "$SCRIPT_DIR/claude_annotate_sgf.sh"
        while IFS= read -r analysed_sgf; do
            [[ -z "$analysed_sgf" ]] && continue
            claude_annotate_sgf "$analysed_sgf"
        done <<< "$analysed_files"
    fi
}

#!/usr/bin/env bash
# scores.sh - Score management functions for the Serious Games Lab launcher
# Sourced after common.sh; uses globals from common.sh.

# --- Global state ---
# scores[0..6]       — per-day score (float, 0 if no recent score)
# score_times[0..6]  — CSV timestamp string for that score (empty if none)
# average_score       — 7-day mean as string "X.XXX"

declare -a scores=()
declare -a score_times=()
average_score="0.000"

# --- Functions ---

# Parse launcherScores.csv backward; within 7-day window, take first
# (most recent) score per day; compute mean via bc.
read_scores() {
    scores=()
    score_times=()
    for i in {0..6}; do
        scores[$i]=0
        score_times[$i]=""
    done
    average_score="0.000"

    [[ -f "$SCORES_FILE" ]] || return 0

    local now_epoch
    now_epoch="$(date +%s)"
    local seven_days=$((7 * 24 * 3600))
    local -A found=()

    # Read lines into array, skip header, process in reverse
    local -a lines=()
    while IFS= read -r line; do
        lines+=("$line")
    done < "$SCORES_FILE"

    local i
    for (( i=${#lines[@]}-1; i>=1; i-- )); do
        local line="${lines[$i]}"
        [[ -z "$line" ]] && continue

        IFS=',' read -r ts day_idx score_val <<< "$line"
        [[ -z "$ts" || -z "$day_idx" || -z "$score_val" ]] && continue

        # Skip days we already have a score for (we want most recent)
        [[ -n "${found[$day_idx]:-}" ]] && continue

        # Parse timestamp: strip fractional seconds before date -d
        local ts_clean="${ts%%.*}"
        local ts_epoch
        ts_epoch="$(date -d "$ts_clean" +%s 2>/dev/null)" || continue

        local age=$(( now_epoch - ts_epoch ))
        if (( age <= seven_days )); then
            found[$day_idx]=1
            # Treat -1 as 0
            if [[ "$score_val" == "-1" ]]; then
                scores[$day_idx]=0
            else
                scores[$day_idx]="$score_val"
            fi
            score_times[$day_idx]="$ts"
        fi
    done

    # Compute mean
    local sum="0"
    for i in {0..6}; do
        sum="$(echo "$sum + ${scores[$i]}" | bc -l)"
    done
    average_score="$(printf "%.3f" "$(echo "scale=6; $sum / 7" | bc -l)")"
}

# Create export directory with matching archives, tar+sha256sum, cleanup, exit 0
export_scores() {
    # Prompt for user name
    local raw_name=""
    read -rp "  Enter your name: " raw_name
    # Replace spaces with dashes, strip non-alphabetic/non-dash characters
    local user_name
    user_name="$(echo "$raw_name" | tr ' ' '-' | tr -cd 'A-Za-z-' | sed 's/^-*//;s/-*$//')"
    if [[ -z "$user_name" ]]; then
        msg_warn "No name entered. Export cancelled."
        return 0
    fi

    local ts
    ts="$(date '+%y%m%d_%H%M')"
    local dir_name="${user_name}_seriousGamesLab-24041LTS_${average_score}_${ts}"
    local export_dir="$REPO_ROOT/$dir_name"

    mkdir -p "$export_dir"

    # Copy per-day score archives (from manual mode)
    local found_any=false
    for i in {0..6}; do
        [[ -z "${score_times[$i]}" ]] && continue
        local day="${DAY_ORDER[$i]}"
        for f in "$REPO_ROOT/${day}_score_"*".tar.gz"; do
            [[ -f "$f" ]] || continue
            cp "$f" "$export_dir/"
            found_any=true
        done
    done

    # Copy afterGamesReport directories from each day (auto mode keeps these intact)
    for i in {0..6}; do
        local day="${DAY_ORDER[$i]}"
        local agr_dir="$REPO_ROOT/$day/afterGamesReport"
        if [[ -d "$agr_dir" ]]; then
            local agr_count
            agr_count="$(find "$agr_dir" -type f 2>/dev/null | wc -l)"
            if [[ "$agr_count" -gt 0 ]]; then
                mkdir -p "$export_dir/$day/afterGamesReport"
                cp -r "$agr_dir/." "$export_dir/$day/afterGamesReport/"
                found_any=true
            fi
        fi
    done

    if [[ "$found_any" == false ]]; then
        msg_warn "No game output files found to export."
    fi

    # Copy scores CSV
    [[ -f "$SCORES_FILE" ]] && cp "$SCORES_FILE" "$export_dir/"

    # Create tar.gz of the export directory
    local tar_file="${export_dir}.tar.gz"
    tar -czf "$tar_file" -C "$REPO_ROOT" "$dir_name"

    # Show sha256sum
    echo ""
    msg_info "Export archive created:"
    sha256sum "$tar_file"

    # Cleanup the temporary directory
    rm -rf "$export_dir"

    echo ""
    msg_ok "Export complete."
    exit 0
}

# Display calculatingScore.txt from repo root
read_documentation() {
    local doc_file="$REPO_ROOT/calculatingScore.txt"
    if [[ -f "$doc_file" ]]; then
        less "$doc_file"
    else
        msg_warn "Documentation file not found: $doc_file"
        echo ""
        read -rp "Press Enter to continue..." _
    fi
}

# Remove all saved state: scores, archives, afterGamesReport dirs, auto-select memory
reset_scores() {
    echo ""
    echo "This will erase:"
    echo "  - All scores and archives"
    echo "  - All afterGamesReport directories"
    echo "  - Auto-select memory (games played, days played)"
    echo ""
    read -rp "Are you sure you want to reset all saved state? (y/N): " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "Reset cancelled."
        return 0
    fi

    rm -f "$SCORES_FILE"
    rm -f "$LAUNCHER_FILES_DIR"/*.tar.gz
    rm -f "$REPO_ROOT"/*_score_*.tar.gz

    # Clear auto-select tracking state
    rm -f "$LAUNCHER_FILES_DIR/.auto_days_played"
    rm -f "$LAUNCHER_FILES_DIR/.auto_games_played"

    # Remove afterGamesReport directories for each day
    for day in "${DAY_ORDER[@]}"; do
        rm -rf "$REPO_ROOT/$day/afterGamesReport"
    done

    msg_ok "All scores, archives, reports, and auto-select state have been reset."
    exit 0
}

# Display per-day calculatingScore.txt
show_day_score_doc() {
    local day="$1"
    local doc_file="$REPO_ROOT/$day/calculatingScore.txt"
    if [[ -f "$doc_file" ]]; then
        less "$doc_file"
    else
        msg_warn "No scoring documentation found for $day"
        echo "  Expected: $doc_file"
        echo ""
        read -rp "Press Enter to continue..." _
    fi
}

# Full score entry workflow for a day
# Usage: enter_score DAY DAY_IDX [--keep-report]
#   --keep-report: skip archiving and keep afterGamesReport (used in auto mode)
enter_score() {
    local day="$1"
    local day_idx="$2"
    local keep_report=false
    [[ "${3:-}" == "--keep-report" ]] && keep_report=true
    local day_dir="$REPO_ROOT/$day"

    # Create afterGamesReport directory
    mkdir -p "$day_dir/afterGamesReport"

    # Run copyRecentFiles script if it exists
    local copy_script="$day_dir/copyRecentFilesToAfterGameReport.sh"
    if [[ -f "$copy_script" ]]; then
        msg_info "Copying recent files to afterGamesReport..."
        (cd "$day_dir" && bash "$copy_script") 2>/dev/null || true
    fi

    # Collect screenshots taken since last game start into the game subdirectory
    local screenshots_dir="$HOME/Pictures/Screenshots"
    local latest_report_dir="$LAST_REPORT_DIR"
    if [[ -d "$screenshots_dir" && -n "$latest_report_dir" ]]; then
        # Use the report dir's mtime as the game start reference
        local ref_epoch
        ref_epoch="$(stat -c %Y "$latest_report_dir" 2>/dev/null)" || ref_epoch=0
        while IFS= read -r -d '' sfile; do
            local sfile_epoch
            sfile_epoch="$(stat -c %Y "$sfile" 2>/dev/null)" || continue
            if [[ "$sfile_epoch" -ge "$ref_epoch" ]]; then
                mkdir -p "$latest_report_dir"
                cp "$sfile" "$latest_report_dir/"
            fi
        done < <(find "$screenshots_dir" -maxdepth 1 -type f \
                    \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.bmp" \) \
                    -print0 2>/dev/null)
    fi

    # Check if afterGamesReport has any files
    local file_count
    file_count="$(find "$day_dir/afterGamesReport" -type f 2>/dev/null | wc -l)"
    if [[ "$file_count" -eq 0 ]]; then
        msg_info "No game output files to archive for $day."
    else
        echo ""
        msg_info "Files in $day/afterGamesReport/:"
        ls "$day_dir/afterGamesReport/"
        echo ""
    fi

    # Prompt for score
    local score_input
    while true; do
        read -rp "Enter score for $day (0 to 1, or 'c' to cancel): " score_input
        if [[ "$score_input" == "c" || "$score_input" == "C" ]]; then
            echo "Score entry cancelled."
            return 1
        fi
        # Validate: must be a number between 0 and 1
        if echo "$score_input" | grep -qE '^[0-9]*\.?[0-9]+$'; then
            local valid
            valid="$(echo "$score_input <= 1" | bc -l)"
            if [[ "$valid" -eq 1 ]]; then
                break
            fi
        fi
        msg_error "Invalid score. Please enter a number between 0 and 1."
    done

    if ! $keep_report; then
        # Archive afterGamesReport and clean up (normal/manual mode)
        local sanitized_ts
        sanitized_ts="$(date '+%y%m%d_%H%M')"
        local archive_name="${day}_score_${sanitized_ts}.tar.gz"

        if [[ "$file_count" -gt 0 ]]; then
            tar -czf "$REPO_ROOT/$archive_name" \
                -C "$day_dir" afterGamesReport
            msg_ok "Archived game files to $archive_name"
        fi

        # Clean afterGamesReport
        rm -rf "$day_dir/afterGamesReport"
    fi

    # Append score to CSV (create with header if needed)
    if [[ ! -f "$SCORES_FILE" ]]; then
        echo "timeStamp,day,score" > "$SCORES_FILE"
    fi
    # Use full timestamp with fractional seconds like Python version
    local full_ts
    full_ts="$(date '+%Y-%m-%d %H:%M:%S.%N')"
    echo "$full_ts,$day_idx,$score_input" >> "$SCORES_FILE"

    msg_ok "Score $score_input recorded for $day"

    # Refresh scores
    read_scores
}

#!/usr/bin/env bash
# auto_select.sh - Automatically select and launch a random game
# Sourced after common.sh, scores.sh, after_game_report.sh.
#
# Tracks which days and games have been played to ensure the user
# experiences the entire SGL collection over time.
#
# State files in filesForLauncher/:
#   .auto_days_played  — day indices (0-6) played in current 7-day cycle
#   .auto_games_played — "day_idx:script" pairs tracking per-day game history

AUTO_DAYS_FILE="$LAUNCHER_FILES_DIR/.auto_days_played"
AUTO_GAMES_FILE="$LAUNCHER_FILES_DIR/.auto_games_played"

# Get list of available games (not utilities) for a day.
# Prints one script path per line.
_auto_get_day_games() {
    local day="$1"
    local -a games=()

    # Regular games
    if [[ -n "${DAY_GAMES[$day]:-}" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            IFS='|' read -r script display available type_label archive <<< "$entry"
            [[ "$available" != "yes" ]] && continue
            is_utility "$script" && continue
            games+=("$script")
        done <<< "${DAY_GAMES[$day]}"
    fi

    # FlightGear scenarios (these are games)
    if [[ -n "${DAY_FG[$day]:-}" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            IFS='|' read -r script display available <<< "$entry"
            [[ "$available" != "yes" ]] && continue
            games+=("$script")
        done <<< "${DAY_FG[$day]}"
    fi

    # Non-violent options (still games)
    if [[ -n "${DAY_NV[$day]:-}" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            IFS='|' read -r script display available type_label archive <<< "$entry"
            [[ "$available" != "yes" ]] && continue
            is_utility "$script" && continue
            games+=("$script")
        done <<< "${DAY_NV[$day]}"
    fi

    if [[ ${#games[@]} -gt 0 ]]; then
        printf '%s\n' "${games[@]}"
    fi
}

# Get unplayed games for a day index.
# If all games have been played, clears that day's game memory and returns all.
_auto_get_unplayed_games() {
    local day_idx="$1"
    local day="${DAY_ORDER[$day_idx]}"

    local -a all_games=()
    while IFS= read -r g; do
        [[ -n "$g" ]] && all_games+=("$g")
    done < <(_auto_get_day_games "$day")

    if [[ ${#all_games[@]} -eq 0 ]]; then
        return
    fi

    # Collect already-played games for this day
    local -a played=()
    if [[ -f "$AUTO_GAMES_FILE" ]]; then
        while IFS= read -r line; do
            [[ "$line" == "${day_idx}:"* ]] && played+=("${line#*:}")
        done < "$AUTO_GAMES_FILE"
    fi

    # Filter out played games
    local -a unplayed=()
    for g in "${all_games[@]}"; do
        local was_played=false
        for p in "${played[@]+"${played[@]}"}"; do
            if [[ "$g" == "$p" ]]; then
                was_played=true
                break
            fi
        done
        $was_played || unplayed+=("$g")
    done

    # If all played, clear memory for this day and return all games
    if [[ ${#unplayed[@]} -eq 0 ]]; then
        if [[ -f "$AUTO_GAMES_FILE" ]]; then
            grep -v "^${day_idx}:" "$AUTO_GAMES_FILE" > "$AUTO_GAMES_FILE.tmp" 2>/dev/null || true
            mv "$AUTO_GAMES_FILE.tmp" "$AUTO_GAMES_FILE"
        fi
        printf '%s\n' "${all_games[@]}"
    else
        printf '%s\n' "${unplayed[@]}"
    fi
}

# Pick a random element from stdin lines
_auto_pick_random() {
    local -a items=()
    while IFS= read -r item; do
        [[ -n "$item" ]] && items+=("$item")
    done
    if [[ ${#items[@]} -eq 0 ]]; then
        return 1
    fi
    local idx=$(( RANDOM % ${#items[@]} ))
    echo "${items[$idx]}"
}

# Main auto-select entry point.
# Randomly picks a day and game, launches it, prompts for comment and score.
auto_select_game() {
    # Load played days
    local -a played_days=()
    if [[ -f "$AUTO_DAYS_FILE" ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && played_days+=("$line")
        done < "$AUTO_DAYS_FILE"
    fi

    # If all 7 days played, export scores and reset cycle
    if [[ ${#played_days[@]} -ge 7 ]]; then
        echo ""
        msg_info "All 7 days of the week have been played!"
        msg_info "Running export..."
        rm -f "$AUTO_DAYS_FILE"
        export_scores
        # export_scores calls exit 0
    fi

    # Build list of available (unplayed) day indices
    local -a available_days=()
    for i in {0..6}; do
        local is_played=false
        for p in "${played_days[@]+"${played_days[@]}"}"; do
            if [[ "$i" == "$p" ]]; then
                is_played=true
                break
            fi
        done
        $is_played || available_days+=("$i")
    done

    if [[ ${#available_days[@]} -eq 0 ]]; then
        msg_error "No available days (unexpected state)."
        return 1
    fi

    # Randomly select a day
    local day_idx
    day_idx="$(printf '%s\n' "${available_days[@]}" | _auto_pick_random)"
    local day="${DAY_ORDER[$day_idx]}"
    local theme="${DAY_THEMES[$day_idx]}"

    # Get unplayed games for this day
    local -a games=()
    while IFS= read -r g; do
        [[ -n "$g" ]] && games+=("$g")
    done < <(_auto_get_unplayed_games "$day_idx")

    if [[ ${#games[@]} -eq 0 ]]; then
        msg_warn "No available games for $day. Skipping."
        return 0
    fi

    # Randomly select a game
    local script
    script="$(printf '%s\n' "${games[@]}" | _auto_pick_random)"
    local display
    display="$(script_display_name "$script")"

    echo ""
    echo -e "${BOLD}=============================================="
    echo "  Auto-Select"
    echo -e "==============================================${NC}"
    echo ""
    echo -e "  Day:  ${CYAN}${BOLD}${day}${NC} - ${theme}"
    echo "  Game: $display"
    echo ""

    # Launch the game
    run_game "$day" "$script" || true

    # Remember the report dir so we can clean up on cancel
    local session_report_dir="$LAST_REPORT_DIR"

    # Prompt for a session comment
    prompt_game_comment "$day" "$script"

    # Prompt for score — if cancelled, roll back everything
    echo ""
    if ! enter_score "$day" "$day_idx"; then
        # Score cancelled — remove afterGamesReport files from this session
        if [[ -n "$session_report_dir" && -d "$session_report_dir" ]]; then
            rm -rf "$session_report_dir"
            msg_info "Removed session files from afterGamesReport."
        fi
        msg_info "Auto-select cancelled. No state changed."
        echo ""
        read -rp "Press Enter to continue..." _
        return 0
    fi

    # Score entered successfully — record game and day played
    echo "${day_idx}:${script}" >> "$AUTO_GAMES_FILE"
    echo "$day_idx" >> "$AUTO_DAYS_FILE"

    # Show progress
    local total_played
    total_played=$(wc -l < "$AUTO_DAYS_FILE" 2>/dev/null || echo 0)
    total_played="${total_played// /}"
    echo ""
    msg_info "Auto-select progress: $total_played of 7 days played."

    local remaining_days=""
    for i in {0..6}; do
        local found=false
        if [[ -f "$AUTO_DAYS_FILE" ]]; then
            while IFS= read -r line; do
                [[ "$line" == "$i" ]] && { found=true; break; }
            done < "$AUTO_DAYS_FILE"
        fi
        if ! $found; then
            remaining_days+="  ${DAY_ORDER[$i]}"
        fi
    done
    if [[ -n "$remaining_days" ]]; then
        msg_info "Remaining:$remaining_days"
    fi

    # If all 7 days now played, notify (export happens on next invocation)
    if [[ "$total_played" -ge 7 ]]; then
        echo ""
        msg_info "All 7 days complete! Next auto-select will export scores."
    fi

    echo ""
    read -rp "Press Enter to continue..." _
}

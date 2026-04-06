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

# Get or prompt for the player name, storing it persistently
get_player_name() {
    if [[ -f "$PLAYER_NAME_FILE" ]]; then
        cat "$PLAYER_NAME_FILE"
        return
    fi
    local raw_name=""
    read -rp "  Enter your name: " raw_name
    local user_name
    user_name="$(echo "$raw_name" | tr ' ' '-' | tr -cd 'A-Za-z-' | sed 's/^-*//;s/-*$//')"
    if [[ -n "$user_name" ]]; then
        echo "$user_name" > "$PLAYER_NAME_FILE"
    fi
    echo "$user_name"
}

# Create export directory with matching archives, tar+sha256sum, cleanup, exit 0
# Saves the archive to ~/sgl/<player_name>/ and runs Claude Code analysis.
export_scores() {
    local user_name
    user_name="$(get_player_name)"
    if [[ -z "$user_name" ]]; then
        msg_warn "No name entered. Export cancelled."
        return 0
    fi

    local player_dir="$REPO_ROOT/$user_name"
    mkdir -p "$player_dir"

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

    # Copy afterGameReport directories from each day (auto mode keeps these intact)
    for i in {0..6}; do
        local day="${DAY_ORDER[$i]}"
        local agr_dir="$REPO_ROOT/$day/afterGameReport"
        if [[ -d "$agr_dir" ]]; then
            local agr_count
            agr_count="$(find "$agr_dir" -type f 2>/dev/null | wc -l)"
            if [[ "$agr_count" -gt 0 ]]; then
                mkdir -p "$export_dir/$day/afterGameReport"
                cp -r "$agr_dir/." "$export_dir/$day/afterGameReport/"
                found_any=true
            fi
        fi
    done

    if [[ "$found_any" == false ]]; then
        msg_warn "No game output files found to export."
    fi

    # Copy scores CSV
    [[ -f "$SCORES_FILE" ]] && cp "$SCORES_FILE" "$export_dir/"

    # Create tar.gz in player directory
    local tar_file="$player_dir/${dir_name}.tar.gz"
    tar -czf "$tar_file" -C "$REPO_ROOT" "$dir_name"

    echo ""
    msg_info "Export archive created:"
    sha256sum "$tar_file"

    # Cleanup temporary directory
    rm -rf "$export_dir"

    # Clean up source afterGameReport directories and per-day score archives
    for i in {0..6}; do
        local day="${DAY_ORDER[$i]}"
        rm -rf "$REPO_ROOT/$day/afterGameReport"
        rm -f "$REPO_ROOT/${day}_score_"*".tar.gz"
    done

    # Run Claude Code analysis on all exports
    echo ""
    run_claude_analysis "$player_dir" "$tar_file" "$user_name"

    echo ""
    msg_ok "Export complete. Archive saved to $tar_file"
    exit 0
}

# Run Claude Code CLI to analyze all exports in the player directory.
# Calculates a revised score, provides rationale, trends, and suggestions.
# Saves analysis into the per-day afterGameReport dirs of the latest tar.gz.
# Args: player_dir latest_tar player_name
run_claude_analysis() {
    local player_dir="$1"
    local latest_tar="$2"
    local player_name="$3"

    if ! command -v claude &>/dev/null; then
        msg_warn "Claude Code CLI not found. Skipping analysis."
        return 1
    fi

    local tmpdir
    tmpdir="$(mktemp -d)"

    # Extract latest archive
    tar -xzf "$latest_tar" -C "$tmpdir"
    local latest_dir
    latest_dir="$(find "$tmpdir" -maxdepth 1 -mindepth 1 -type d | head -1)"

    if [[ -z "$latest_dir" ]]; then
        msg_warn "Could not extract latest archive for analysis."
        rm -rf "$tmpdir"
        return 1
    fi

    # Build the analysis prompt
    local prompt_file="$tmpdir/analysis_prompt.txt"

    {
        cat << 'HEADER'
You are analyzing a student's performance in the Serious Games Lab (SGL), a weekly training program spanning 7 strategic domains (MON=Poker, TUE=Historical Flight Sim, WED=Chess, THU=Sim Racing, FRI=Duplicate Bridge, SAT=Modern Flight Sim, SUN=Go).

Provide your analysis with these sections:

## Revised Score
Calculate a revised per-day score (0-1) and overall average based on the OKR scoring criteria and all available evidence. Show your work for each day.

## Rationale
Explain your scoring with specific reference to these three learning framework documents:
- fourElementsOfMentalFunctioning.txt (executive function, emotional regulation, memory, creativity)
- metaLearning.txt (deep processing, desirable difficulty, deliberate practice, interleaving, spaced practice)
- ObjectivesAndKeyResults_OKR.txt (committed vs aspirational OKRs, the 0.7 target for aspirational goals)

## Trends
Compare the latest export with any previous ones. Comment on improvement, regression, or consistency across days and overall.

## Suggestions
Provide both general and concrete day-specific suggestions for improvement. Be actionable.

Here is all the data:

HEADER

        echo "=========================================="
        echo "SCORING CRITERIA"
        echo "=========================================="
        echo ""

        if [[ -f "$REPO_ROOT/calculatingScore.txt" ]]; then
            echo "--- Overall Scoring Overview ---"
            cat "$REPO_ROOT/calculatingScore.txt"
            echo ""
        fi

        for day in "${DAY_ORDER[@]}"; do
            local doc="$REPO_ROOT/$day/calculatingScore.txt"
            if [[ -f "$doc" ]]; then
                echo "--- $day Scoring Criteria ---"
                cat "$doc"
                echo ""
            fi
        done

        echo "=========================================="
        echo "LEARNING FRAMEWORK DOCUMENTS"
        echo "=========================================="
        echo ""

        for doc in "$HOME/Downloads/fourElementsOfMentalFunctioning.txt" \
                   "$HOME/Downloads/metaLearning.txt" \
                   "$HOME/Downloads/ObjectivesAndKeyResults_OKR.txt"; do
            if [[ -f "$doc" ]]; then
                echo "--- $(basename "$doc") ---"
                cat "$doc"
                echo ""
            fi
        done

        echo "=========================================="
        echo "CURRENT EXPORT: $(basename "$latest_tar")"
        echo "=========================================="
        echo ""

        if [[ -f "$latest_dir/launcherScores.csv" ]]; then
            echo "--- Scores CSV ---"
            cat "$latest_dir/launcherScores.csv"
            echo ""
        fi

        for day in "${DAY_ORDER[@]}"; do
            local agr_dir="$latest_dir/$day/afterGameReport"
            [[ -d "$agr_dir" ]] || continue
            echo "--- $day Game Sessions ---"
            for sa in "$agr_dir"/*/self_assessment.txt "$agr_dir"/*/session_comment.txt; do
                [[ -f "$sa" ]] || continue
                echo "  [$(basename "$(dirname "$sa")")/$(basename "$sa")]"
                cat "$sa"
                echo ""
            done
            # List other collected game files
            local other_files
            other_files="$(find "$agr_dir" -type f \
                ! -name "self_assessment.txt" \
                ! -name "session_comment.txt" \
                ! -name "claude_analysis.txt" \
                -printf "  %P\n" 2>/dev/null)"
            if [[ -n "$other_files" ]]; then
                echo "  [Other collected files]"
                echo "$other_files"
                echo ""
            fi
        done

        echo "=========================================="
        echo "PREVIOUS EXPORTS (for trend analysis)"
        echo "=========================================="
        echo ""

        local has_previous=false
        for pt in "$player_dir"/*.tar.gz; do
            [[ -f "$pt" ]] || continue
            [[ "$pt" == "$latest_tar" ]] && continue
            has_previous=true

            echo "--- $(basename "$pt") ---"
            local ptmp
            ptmp="$(mktemp -d)"
            if tar -xzf "$pt" -C "$ptmp" 2>/dev/null; then
                local pdir
                pdir="$(find "$ptmp" -maxdepth 1 -mindepth 1 -type d | head -1)"
                if [[ -n "$pdir" ]]; then
                    if [[ -f "$pdir/launcherScores.csv" ]]; then
                        echo "Scores:"
                        cat "$pdir/launcherScores.csv"
                        echo ""
                    fi
                    for day in "${DAY_ORDER[@]}"; do
                        for sa in "$pdir/$day/afterGameReport/"*/self_assessment.txt \
                                  "$pdir/$day/afterGameReport/"*/session_comment.txt; do
                            [[ -f "$sa" ]] || continue
                            echo "$day/$(basename "$(dirname "$sa")")/$(basename "$sa"):"
                            cat "$sa"
                            echo ""
                        done
                    done
                fi
            fi
            rm -rf "$ptmp"
        done

        if [[ "$has_previous" == false ]]; then
            echo "No previous exports found. This is the first export for $player_name."
        fi

    } > "$prompt_file"

    msg_info "Analyzing with Claude Code (this may take a moment)..."
    echo ""

    # Call Claude Code CLI
    local analysis
    if analysis="$(claude -p "$(cat "$prompt_file")" 2>/dev/null)"; then
        # Print to screen
        echo "$analysis"
        echo ""

        # Save analysis to each day's afterGameReport dir that exists
        for day in "${DAY_ORDER[@]}"; do
            local agr_dir="$latest_dir/$day/afterGameReport"
            if [[ -d "$agr_dir" ]]; then
                echo "$analysis" > "$agr_dir/claude_analysis.txt"
            fi
        done

        # Re-archive with analysis files included
        local dir_name
        dir_name="$(basename "$latest_dir")"
        tar -czf "$latest_tar" -C "$tmpdir" "$dir_name"
        msg_ok "Analysis saved to archive."
    else
        msg_warn "Claude Code analysis could not be completed."
    fi

    rm -rf "$tmpdir"
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

# Remove all saved state: scores, archives, afterGameReport dirs, auto-select memory
reset_scores() {
    echo ""
    echo "This will erase:"
    echo "  - All scores and archives"
    echo "  - All afterGameReport directories"
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

    # Remove afterGameReport directories for each day
    for day in "${DAY_ORDER[@]}"; do
        rm -rf "$REPO_ROOT/$day/afterGameReport"
    done

    msg_ok "All scores, archives, reports, and auto-select state have been reset."
    exit 0
}


#!/usr/bin/env bash
# after_game_report.sh - Collect game output files after a game session
# Sourced after common.sh; uses globals from common.sh.
#
# Game scripts should touch "$WINEPREFIX/.sgl_game_started" (or
# "$SGL_GAME_STARTED_MARKER" if set) right before launching the game
# executable.  collect_after_game_report uses this marker's timestamp
# to distinguish files created during gameplay from files created
# during installation.  Falls back to the script start epoch if no
# marker is found.

# Path to the last after-game report directory (set by collect_after_game_report)
LAST_REPORT_DIR=""

# Map a game script to the file extensions/paths to search for output files.
# Returns newline-separated "search_dir|pattern" pairs relative to the day dir.
_game_output_patterns() {
    local day="$1"
    local script="$2"

    case "$script" in
        # WED - Chess: .pgn files
        scid.sh|nibbler.sh|banksiaGui.sh|chessmaster/chessmaster.sh)
            echo ".|*.pgn"
            ;;
        # WED - Opening repertoire is a helper utility, no files to collect
        openingRepertoire/run_opening_repertoire.sh)
            ;;
        # FRI - Bridge: .pbn and .bdl files
        wBridge5.sh)
            echo ".|*.pbn"
            echo ".|*.bdl"
            echo "HOMESCAN|*.txt"
            echo "HOMESCAN|*.pbn"
            ;;
        bb12/bb12.sh)
            echo ".|*.pbn"
            echo ".|*.ppl"
            echo ".|*.bdl"
            ;;
        bridgeIQ/run.sh)
            echo "./bridgeIQ/bridgeIQ/DATA/LOG|*.bdl"
            echo "./bridgeIQ/bridgeIQ/DATA/LOG|*.pbn"
            echo "./bridgeIQ/bridgeIQ/DATA/LOG|*.ppl"
            echo ".|*.pbn"
            echo ".|*.bdl"
            ;;
        bcalc.sh|qplus.sh|tenace.sh)
            echo ".|*.pbn"
            echo ".|*.bdl"
            ;;
        # FRI - Math quiz, memory training (no persistent output files)
        mathQuiz/run.sh|dual_nback/run.sh|memoryTraining.sh)
            ;;
        # MON - Poker
        pokerth.sh)
            echo "HOMESCAN|pokerth-log*"
            echo "HOMESCAN|PokerTH*Log*"
            ;;
        pokerIQ/run.sh)
            echo "./pokerIQ|poker_log_*.txt"
            ;;
        generalPokerEvaluator.sh)
            echo ".|ps_eval_log_*.txt"
            ;;
        pokerStove.sh)
            echo ".|pokerstove_*.txt"
            ;;
        bracelets.sh)
            echo "./WP/drive_c/Program Files/Activision Value/WSOP 2008/Saves|*.sav"
            ;;
        # TUE - Historical flight: saved flights, replays, campaigns
        FS9/fs9.sh)
            echo "./FS9/WP/drive_c/Program Files/Microsoft Games/Flight Simulator 9/Flights|*.FLT"
            echo "./FS9/WP/drive_c/Program Files/Microsoft Games/Flight Simulator 9/Flights|*.WX"
            echo "./FS9/WP/drive_c/Program Files/Microsoft Games/Flight Simulator 9|*.LBK"
            ;;
        MigAlley.sh|MigAlley/migAlley.sh|MigAlley/MigAlley.sh)
            echo "./MigAlley/WP/drive_c/rowan/mig/Videos|*.cam"
            echo "./MigAlley/WP/drive_c/rowan/mig/SaveGame|*.sav"
            ;;
        BattleOfBritain.sh|BattleOfBritain/battleOfBritain.sh|BattleOfBritain/BattleOfBritain.sh)
            echo "./BattleOfBritain/WP/drive_c/Program Files/Rowan Software/Battle Of Britain/VIDEOS|*.cam"
            echo ".|*.bsL"
            echo ".|*.bsR"
            ;;
        # THU - Sim Racing: .rpy replay, .txt setup files
        gpl.sh)
            echo "./WP/drive_c/Sierra/GPL/replay|*.rpy"
            echo "./WP/drive_c/GPLSecrets/GPL Setup Manager|*.txt"
            ;;
        NR2003/NR2003.sh)
            echo ".|*.rpy"
            ;;
        rFactor/rFactor.sh|speedDreams.sh)
            echo ".|*.rpy"
            ;;
        # SAT - Falcon: .acmi/.vhs files, .txt briefing/debrief, .frc/.cam/.his analysis
        freeFalcon.sh)
            echo "./WP/drive_c/FreeFalcon6/acmibin|*.vhs"
            echo "./WP/drive_c/FreeFalcon6|*.txt"
            echo "./WP/drive_c/FreeFalcon6|*.frc"
            echo "./WP/drive_c/FreeFalcon6|*.cam"
            echo "./WP/drive_c/FreeFalcon6|*.his"
            ;;
        FalconAF.sh)
            echo ".|*.acmi"
            echo ".|*.vhs"
            ;;
        BMS432/BMS432.sh)
            echo ".|*.acmi"
            echo ".|*.vhs"
            echo ".|*.txt"
            ;;
        BMS435/BMS435.sh)
            echo ".|*.acmi"
            echo ".|*.vhs"
            ;;
        # SUN - Go: .sgf and .rsgf files (GUIs may save to home config dirs)
        # Users may save directly to afterGameReport/, so also scan there.
        run_katrain.sh|q5go.sh|sabaki.sh|igowin.sh|goreviewpartner.sh)
            echo ".|*.sgf"
            echo "./afterGameReport|*.sgf"
            echo ".|*.rsgf"
            echo ".|*.rsgf.csv"
            echo "HOMESCAN|*.sgf"
            echo "HOMESCAN|*.rsgf"
            ;;
        # FlightGear scenarios: saved state, logs, CSV logging output
        flightgear/*.sh)
            echo "./flightgear/.fgfs/aircraft-data|*.xml"
            echo "./flightgear/.fgfs|fgfs*.log"
            echo ".|fg_log*.csv"
            ;;
        # Tacview
        tacview/tacview.sh)
            echo ".|*.acmi"
            ;;
        *)
            ;;
    esac
}

# Return true (0) if a game's output files should be KEPT in place after collection.
# Most games have files moved (cleaned up); tactical engagement/flight sim saves are exempt.
_exempt_from_cleanup() {
    local script="$1"
    case "$script" in
        # SAT - Falcon tactical engagements: keep ACMI/VHS replays in place
        freeFalcon.sh|FalconAF.sh|BMS432/BMS432.sh|BMS435/BMS435.sh) return 0 ;;
        # TUE - Flight sim saves should persist
        flightgear/*.sh) return 0 ;;
        *) return 1 ;;
    esac
}

# Derive a short game name from the script path for directory naming
_game_short_name() {
    local script="$1"
    local name="${script##*/}"
    name="${name%.sh}"
    name="${name%.py}"
    # For scripts like BMS435/BMS435.sh, use the filename part
    # For run.sh / run_*.sh in subdirs, use the parent dir name
    case "$name" in
        run_*) name="${name#run_}" ;;
        run) name="${script%%/*}" ;;
    esac
    # Sanitize: lowercase, replace spaces with underscores
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd '[:alnum:]_-'
}

# Main collection function called after a game exits
# Args: day script start_epoch
collect_after_game_report() {
    local day="$1"
    local script="$2"
    local start_epoch="$3"
    local day_dir="$REPO_ROOT/$day"

    local game_name
    game_name="$(_game_short_name "$script")"

    # Only collect files if the game script touched the started marker.
    # This ensures installation artifacts are never collected — the marker
    # is only touched after installation completes, right before the game
    # executable launches.
    local marker="$day_dir/.sgl_game_started"
    if [[ ! -f "$marker" ]]; then
        LAST_REPORT_DIR=""
        return 0
    fi
    start_epoch="$(stat -c %Y "$marker")"
    local compare_op="-ge"
    rm -f "$marker"

    # Build timestamp-based subdirectory name: YYMMDD_HHMM_gamename
    local subdir_name
    subdir_name="$(date -d "@$start_epoch" '+%y%m%d_%H%M')_${game_name}"
    local report_dir="$day_dir/afterGameReport/$subdir_name"

    # Always set the report dir path so prompt_self_assessment can find it
    LAST_REPORT_DIR="$report_dir"

    local found_files=false

    # Collect game-specific output files created since game start
    local patterns
    patterns="$(_game_output_patterns "$day" "$script")" || true

    if [[ -n "$patterns" ]]; then
        while IFS='|' read -r search_dir pattern; do
            [[ -z "$search_dir" || -z "$pattern" ]] && continue

            # Determine search directory
            local abs_search_dir max_depth
            if [[ "$search_dir" == "HOMESCAN" ]]; then
                # Broad search across home directory for files that could
                # be saved anywhere (e.g. PokerTH log files)
                abs_search_dir="$HOME"
                max_depth=5
            elif [[ "$search_dir" == ~/* ]]; then
                abs_search_dir="$HOME/${search_dir#\~/}"
                max_depth=5
            else
                abs_search_dir="$day_dir/$search_dir"
                max_depth=5
            fi
            [[ -d "$abs_search_dir" ]] || continue

            # Build find exclusions — skip INSTALL and openingRepertoire always.
            # Skip afterGameReport subdirs unless we're explicitly searching there
            # (users may save SGFs directly to afterGameReport/).
            local -a find_excludes=(
                -not -path "*/INSTALL/*"
                -not -path "*/openingRepertoire/*"
                -not -path "*/.local/share/Trash/*"
                -not -path "*/.Trash*"
                -not -name "*.trashinfo"
            )
            if [[ "$search_dir" != *afterGameReport* ]]; then
                find_excludes+=(-not -path "*/afterGameReport/*")
            else
                # When scanning afterGameReport, only pick up files at the top level
                # (not files already inside a timestamped subdirectory)
                max_depth=1
            fi

            # Find files matching pattern that are newer than start_epoch
            # Non-exempt games: move files to afterGameReport (restoring clean state)
            # Exempt games (tactical engagements) and HOMESCAN paths: copy only
            local use_move=false
            if [[ "$search_dir" != "HOMESCAN" ]] && ! _exempt_from_cleanup "$script"; then
                use_move=true
            fi
            while IFS= read -r -d '' file; do
                local file_epoch
                file_epoch="$(stat -c %Y "$file" 2>/dev/null)" || continue
                # Skip files that existed before the game launched (e.g. MiG Alley
                # install replays whose mtimes get bumped by Wine on startup)
                if [[ -n "${_SGL_PRE_EXISTING_FILES:-}" && -f "$_SGL_PRE_EXISTING_FILES" ]]; then
                    grep -qFx "$file" "$_SGL_PRE_EXISTING_FILES" 2>/dev/null && continue
                fi
                if [ "$file_epoch" $compare_op "$start_epoch" ]; then
                    if [[ "$found_files" == false ]]; then
                        mkdir -p "$report_dir"
                        found_files=true
                    fi
                    if [[ "$use_move" == true ]]; then
                        mv "$file" "$report_dir/"
                    else
                        cp "$file" "$report_dir/"
                    fi
                fi
            done < <(find "$abs_search_dir" -maxdepth "$max_depth" -name "$pattern" -type f \
                        "${find_excludes[@]}" -print0 2>/dev/null)
        done <<< "$patterns"
    fi

    # Check ~/Pictures/Screenshots for screenshots taken during the game
    local screenshots_dir="$HOME/Pictures/Screenshots"
    if [[ -d "$screenshots_dir" ]]; then
        while IFS= read -r -d '' file; do
            local file_epoch
            file_epoch="$(stat -c %Y "$file" 2>/dev/null)" || continue
            if [ "$file_epoch" $compare_op "$start_epoch" ]; then
                if [[ "$found_files" == false ]]; then
                    mkdir -p "$report_dir"
                    found_files=true
                fi
                cp "$file" "$report_dir/"
            fi
        done < <(find "$screenshots_dir" -maxdepth 1 -type f \
                    \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.bmp" \) \
                    -print0 2>/dev/null)
    fi

    if [[ "$found_files" == true ]]; then
        local count
        count="$(find "$report_dir" -type f | wc -l)"
        msg_ok "Collected $count file(s) to $day/afterGameReport/$subdir_name/"
    fi
}

# Prompt the user for a self-assessment after their game session.
# Replaces the old comment system: asks for score 0-1 and an explanation
# referencing the collected game files.
# Args: day script day_idx [--keep-report]
# Returns 1 if cancelled/skipped.
prompt_self_assessment() {
    local day="$1"
    local script="$2"
    local day_idx="$3"
    local keep_report=false
    [[ "${4:-}" == "--keep-report" ]] && keep_report=true

    # Don't prompt for utilities
    is_utility "$script" && return 0

    local day_dir="$REPO_ROOT/$day"

    # Run copyRecentFiles script if it exists (catch files missed by collect)
    local copy_script="$day_dir/copyRecentFilesToAfterGameReport.sh"
    if [[ -f "$copy_script" ]]; then
        (cd "$day_dir" && bash "$copy_script") 2>/dev/null || true
    fi

    # Show files in afterGameReport
    local file_count
    file_count="$(find "$day_dir/afterGameReport" -type f 2>/dev/null | wc -l)"

    echo ""
    if [[ "$file_count" -gt 0 ]]; then
        msg_info "Files in $day/afterGameReport/:"
        find "$day_dir/afterGameReport" -type f -printf "  %P\n" 2>/dev/null
        echo ""
    else
        msg_info "No game output files collected for $day."
        echo ""
    fi

    # Flush keyboard buffer before prompting
    read -r -d '' -t 0.1 -n 10000 2>/dev/null || true

    # Prompt for score
    local score_input
    while true; do
        read -rp "Rate your performance for $day (0 to 1, or 's' to skip): " score_input
        if [[ "$score_input" == "s" || "$score_input" == "S" ]]; then
            echo "Score entry skipped."
            return 1
        fi
        if [[ -z "$score_input" ]]; then
            msg_error "Please enter a score (0 to 1) or 's' to skip."
            continue
        fi
        if echo "$score_input" | grep -qE '^[0-9]*\.?[0-9]+$'; then
            local valid
            valid="$(echo "$score_input <= 1" | bc -l)"
            if [[ "$valid" -eq 1 ]]; then
                break
            fi
        fi
        msg_error "Invalid score. Enter a number between 0 and 1."
    done

    # Prompt for explanation referencing the collected files
    echo ""
    echo "Explain why you gave yourself this score (reference the game files above)."
    echo "Type your explanation (empty line to finish):"
    local explanation=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        if [[ -n "$explanation" ]]; then
            explanation+=$'\n'
        fi
        explanation+="$line"
    done

    # Save self-assessment to report directory
    local report_dir="$LAST_REPORT_DIR"
    if [[ -z "$report_dir" || ! -d "$report_dir" ]]; then
        local game_name
        game_name="$(_game_short_name "$script")"
        local subdir_name
        subdir_name="$(date '+%y%m%d_%H%M')_${game_name}"
        report_dir="$day_dir/afterGameReport/$subdir_name"
        mkdir -p "$report_dir"
    fi

    {
        echo "Score: $score_input"
        echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Game: $(script_display_name "$script")"
        echo ""
        echo "Explanation:"
        echo "$explanation"
    } > "$report_dir/self_assessment.txt"
    msg_ok "Self-assessment saved to $(basename "$report_dir")/self_assessment.txt"

    # Keep afterGameReport intact — it will be collected by export_scores()
    # when the user chooses "Export" from the main menu.

    # Record score to CSV
    if [[ ! -f "$SCORES_FILE" ]]; then
        echo "timeStamp,day,score" > "$SCORES_FILE"
    fi
    local full_ts
    full_ts="$(date '+%Y-%m-%d %H:%M:%S.%N')"
    echo "$full_ts,$day_idx,$score_input" >> "$SCORES_FILE"

    msg_ok "Score $score_input recorded for $day"
    read_scores

    return 0
}

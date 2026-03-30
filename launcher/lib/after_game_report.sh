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
        # FRI - Bridge: .pbn files
        wBridge5.sh)
            echo ".|*.pbn"
            echo "HOMESCAN|*.txt"
            echo "HOMESCAN|*.pbn"
            ;;
        bcalc.sh|benBridge/run.sh|qplus.sh|bb12/bb12.sh|tenace.sh)
            echo ".|*.pbn"
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
        run_katrain.sh|q5go.sh|sabaki.sh|igowin.sh|goreviewpartner.sh)
            echo ".|*.sgf"
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

# Derive a short game name from the script path for directory naming
_game_short_name() {
    local script="$1"
    local name="${script##*/}"
    name="${name%.sh}"
    name="${name%.py}"
    # For scripts like BMS435/BMS435.sh, use the filename part
    # For run.sh / run_*.sh in subdirs, use the parent dir name
    case "$name" in
        run|run_*) name="${script%%/*}" ;;
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
    local report_dir="$day_dir/afterGamesReport/$subdir_name"

    # Always set the report dir path so prompt_game_comment can find it
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
                max_depth=3
            else
                abs_search_dir="$day_dir/$search_dir"
                max_depth=3
            fi
            [[ -d "$abs_search_dir" ]] || continue

            # Find files matching pattern that are newer than start_epoch
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
            done < <(find "$abs_search_dir" -maxdepth "$max_depth" -name "$pattern" -type f \
                        -not -path "*/afterGamesReport/*" \
                        -not -path "*/INSTALL/*" \
                        -not -path "*/openingRepertoire/*" -print0 2>/dev/null)
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
        msg_ok "Collected $count file(s) to $day/afterGamesReport/$subdir_name/"
    fi
}

# Prompt the user for a comment about their game session.
# Only called for games, not utilities.
# Args: day script
prompt_game_comment() {
    local day="$1"
    local script="$2"

    # Don't prompt for utilities
    is_utility "$script" && return 0

    local day_dir="$REPO_ROOT/$day"

    echo ""
    read -rp "Add a comment about this game session? (y/N): " reply
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        return 0
    fi

    echo "Enter your comment (empty line to finish):"
    local comment=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        if [[ -n "$comment" ]]; then
            comment+=$'\n'
        fi
        comment+="$line"
    done

    if [[ -z "$comment" ]]; then
        return 0
    fi

    # Use the report directory from collect_after_game_report, creating if needed
    local report_dir="$LAST_REPORT_DIR"
    if [[ -z "$report_dir" || ! -d "$report_dir" ]]; then
        local game_name
        game_name="$(_game_short_name "$script")"
        local subdir_name
        subdir_name="$(date '+%y%m%d_%H%M')_${game_name}"
        report_dir="$day_dir/afterGamesReport/$subdir_name"
        mkdir -p "$report_dir"
    fi

    local comment_file="$report_dir/session_comment.txt"
    echo "$comment" > "$comment_file"
    msg_ok "Comment saved to $(basename "$(dirname "$comment_file")")/session_comment.txt"
}

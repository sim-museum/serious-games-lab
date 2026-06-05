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
            echo "./bridgeIQ/ben/DATA/LOG|*.bdl"
            echo "./bridgeIQ/ben/DATA/LOG|*.pbn"
            echo "./bridgeIQ/ben/DATA/LOG|*.ppl"
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
        freeFalcon/freeFalcon.sh)
            echo "./WP/drive_c/FreeFalcon6/acmibin|*.vhs"
            echo "./WP/drive_c/FreeFalcon6|*.txt"
            echo "./WP/drive_c/FreeFalcon6|*.frc"
            echo "./WP/drive_c/FreeFalcon6|*.cam"
            echo "./WP/drive_c/FreeFalcon6|*.his"
            ;;
        FalconAF/FalconAF.sh)
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

# Human-readable label for the type of save file a game produces.  Empty
# string means the game does not produce a save file (e.g. utilities, or
# vision-only games like bracelets).  Used in the "no save file" protest.
_game_save_label() {
    local script="$1"
    case "$script" in
        scid.sh|nibbler.sh|banksiaGui.sh|chessmaster/chessmaster.sh) echo "PGN game file" ;;
        wBridge5.sh|qplus.sh|bcalc.sh|tenace.sh)                    echo "PBN/BDL deal file" ;;
        bb12/bb12.sh)                                                echo "PPL deal file" ;;
        bridgeIQ/run.sh)                                            echo "PBN deal file" ;;
        run_katrain.sh|q5go.sh|sabaki.sh|igowin.sh|goreviewpartner.sh) echo "SGF game file" ;;
        pokerth.sh|pokerIQ/run.sh|generalPokerEvaluator.sh|pokerStove.sh) echo "session log" ;;
        *) ;;
    esac
}

# Hint shown alongside the protest, telling the user how to save in this game.
_game_save_hint() {
    local script="$1"
    case "$script" in
        nibbler.sh)                  echo "In Nibbler: File menu > Save PGN before exiting" ;;
        banksiaGui.sh)               echo "In Banksia GUI: Save game as PGN before exiting" ;;
        chessmaster/chessmaster.sh)  echo "In Chessmaster: Save Game from menu before exit (also enables Stockfish annotation pipeline)" ;;
        scid.sh)                     echo "In Scid: File > Save before exit" ;;
        wBridge5.sh)                 echo "In WBridge5: Save current deal as PBN before exit" ;;
        bb12/bb12.sh)                echo "In Bridge Baron 12: File > Save current deal (writes a .ppl file)" ;;
        bridgeIQ/run.sh)            echo "bridgeIQ writes PBN files to ben/DATA/LOG automatically when you finish a hand" ;;
        qplus.sh)                    echo "In Q-Plus Bridge: complete a deal so Q-Plus writes a BDL log to DATA/LOG/" ;;
        run_katrain.sh)              echo "In KaTrain: Save as SGF before exit" ;;
        q5go.sh)                     echo "In q5go: File > Save SGF before exit" ;;
        sabaki.sh)                   echo "In Sabaki: File > Save (Ctrl+S) before exit" ;;
        igowin.sh)                   echo "In Igowin: save the game to disk before exit" ;;
        goreviewpartner.sh)          echo "In GoReviewPartner: File > Save SGF before exit" ;;
        pokerth.sh)                  echo "PokerTH writes session logs automatically; check ~/.pokerth permissions if missing" ;;
        pokerIQ/run.sh)              echo "PokerIQ writes poker_log_*.txt to its run dir per session" ;;
        *) ;;
    esac
}

# Vision-only games: have no useful machine-readable save file, so we run
# Claude vision over screenshots taken during play.
_is_vision_game() {
    local script="$1"
    case "$script" in
        bracelets.sh) return 0 ;;
        *) return 1 ;;
    esac
}

# Run Claude with screenshots in the report dir as input.  The script
# argument selects the coaching prompt.  Writes the response to
# claude_vision_analysis.txt in the report dir.  Silent no-op if claude
# is not on PATH.
_run_vision_analysis() {
    local report_dir="$1"
    local script="$2"
    [[ -d "$report_dir" ]] || return 0
    command -v claude &>/dev/null || return 0

    local -a screenshots=()
    while IFS= read -r -d '' f; do
        screenshots+=("$f")
    done < <(find "$report_dir" -maxdepth 1 -type f \
                \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) -print0 2>/dev/null)
    [[ ${#screenshots[@]} -eq 0 ]] && return 0

    msg_info "Running Claude vision analysis on ${#screenshots[@]} screenshot(s)..."

    local prompt
    case "$script" in
        bracelets.sh)
            prompt='You are a poker coach for amateur Texas Hold'\''em players. You have deep knowledge of these classic instructional poker books:

1. "The Theory of Poker" by David Sklansky
2. "Harrington on Hold'\''em" Vol 1-3 by Dan Harrington
3. "Super System" by Doyle Brunson
4. "Every Hand Revealed" by Gus Hansen
5. "Elements of Poker" by Tommy Angelo
6. "The Mental Game of Poker" by Jared Tendler & Barry Carter
7. "Small Stakes Hold'\''em" by Miller, Sklansky & Malmuth
8. "Applications of No-Limit Hold'\''em" by Matthew Janda
9. "Poker'\''s 1%" by Ed Miller
10. "Modern Poker Theory" by Michael Acevedo

You are given screenshots from a session of "World Series of Poker 2008: Battle for the Bracelets". Read each screenshot with the Read tool, then analyse the hands shown:
- Stage of hand (preflop, flop, turn, river)
- Position, stack sizes, pot odds where visible
- Hand strength relative to board texture
- Whether the action taken (call/raise/fold) was sound
- Reference relevant book concepts (e.g. Sklansky'\''s Fundamental Theorem, Harrington'\''s M-zones, Brunson on aggression)

Be concise. Cover the 3-5 most instructive moments across all screenshots.
Output plain text only — no markdown headings.'
            ;;
        *)
            return 0
            ;;
    esac

    # Embed absolute paths in the prompt and let Claude read each image via
    # its Read tool — claude -p accepts only one positional argument, so we
    # cannot pass images as separate args.
    local file_list=""
    local f
    for f in "${screenshots[@]}"; do
        file_list+="- $f"$'\n'
    done
    local full_prompt
    full_prompt="$prompt"$'\n\nScreenshot files (use the Read tool to view each):\n'"$file_list"

    local out_file="$report_dir/claude_vision_analysis.txt"
    if timeout 240 claude -p --max-turns 8 "$full_prompt" > "$out_file" 2>/dev/null \
        && [[ -s "$out_file" ]]; then
        msg_ok "Vision analysis written to $(basename "$report_dir")/$(basename "$out_file")"
    else
        rm -f "$out_file"
        msg_warn "Claude vision analysis failed or returned empty output."
    fi
}

# Return true (0) if a game's output files should be KEPT in place after collection.
# Most games have files moved (cleaned up); tactical engagement/flight sim saves are exempt.
_exempt_from_cleanup() {
    local script="$1"
    case "$script" in
        # SAT - Falcon tactical engagements: keep ACMI/VHS replays in place
        freeFalcon/freeFalcon.sh|FalconAF/FalconAF.sh|BMS432/BMS432.sh|BMS435/BMS435.sh) return 0 ;;
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
    # Pre-existing files snapshot (game scripts may write a sibling
    # ".pre_existing" file next to the started-marker listing absolute
    # paths to skip during collection — useful for games whose install
    # or startup touches shipped data files in a way that makes them
    # look newer than the marker).
    local pre_existing_path="${marker}.pre_existing"
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
            # Canonicalize so find -printf paths match the snapshot paths in
            # $pre_existing_path. Without this, "$day_dir/./MigAlley/..." and
            # "$day_dir/MigAlley/..." compare unequal under grep -qFx, and the
            # snapshot skip-list silently fails to match.
            abs_search_dir="$(realpath "$abs_search_dir" 2>/dev/null || echo "$abs_search_dir")"

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
                # install replays whose mtimes get bumped by Wine on startup).
                # Game scripts write the absolute paths to a sibling file of
                # the started-marker; see migAlley.sh for an example.
                if [[ -f "$pre_existing_path" ]]; then
                    grep -qFx "$file" "$pre_existing_path" 2>/dev/null && continue
                    local file_canonical
                    file_canonical="$(realpath "$file" 2>/dev/null)"
                    [[ -n "$file_canonical" ]] && grep -qFx "$file_canonical" "$pre_existing_path" 2>/dev/null && continue
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

    rm -f "$pre_existing_path"

    if [[ "$found_files" == true ]]; then
        local count
        count="$(find "$report_dir" -type f | wc -l)"
        msg_ok "Collected $count file(s) to $day/afterGameReport/$subdir_name/"
    fi

    # ----- Post-collection feedback hooks -----
    # 1. Protest if the game expects a save file but none landed anywhere
    #    under afterGameReport during this session (the launcher's
    #    collector OR a script's own exit logic — qplus.sh, the chess
    #    scripts, etc. populate the report dir directly).
    # 2. For vision-only games (bracelets), run Claude vision over any
    #    screenshots collected this session.
    local game_save_label
    game_save_label="$(_game_save_label "$script")"

    if [[ -n "$game_save_label" ]]; then
        local any_save_landed=false
        if [[ -d "$day_dir/afterGameReport" ]]; then
            while IFS= read -r -d '' d; do
                local d_mod
                d_mod="$(stat -c %Y "$d" 2>/dev/null)" || continue
                [ "$d_mod" $compare_op "$start_epoch" ] || continue
                # Look for any "save"-like file in this dir (i.e. not
                # self_assessment, not a screenshot, not the vision
                # analysis we may have just written).
                if find "$d" -maxdepth 1 -type f \
                    -not -name "self_assessment.txt" \
                    -not -name "claude_vision_analysis.txt" \
                    -not -iname "*.png" -not -iname "*.jpg" \
                    -not -iname "*.jpeg" -not -iname "*.bmp" \
                    2>/dev/null | grep -q .; then
                    any_save_landed=true
                    break
                fi
            done < <(find "$day_dir/afterGameReport" -mindepth 1 -maxdepth 1 \
                        -type d -print0 2>/dev/null)
        fi
        if [[ "$any_save_landed" == false ]]; then
            echo ""
            msg_warn "No $game_save_label was saved this session — engine + Claude annotation cannot run."
            local hint
            hint="$(_game_save_hint "$script")"
            [[ -n "$hint" ]] && echo "       $hint"
            echo "       Save your game next time so AI feedback ends up in afterGameReport."
            echo ""
        fi
    fi

    if _is_vision_game "$script"; then
        local screenshot_count=0
        if [[ -d "$report_dir" ]]; then
            screenshot_count="$(find "$report_dir" -maxdepth 1 -type f \
                \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null | wc -l)"
        fi
        if [[ "$screenshot_count" -eq 0 ]]; then
            echo ""
            msg_warn "No screenshots were taken this session — AI poker analysis cannot run."
            echo "       Press Print Screen during play to capture key hands; screenshots"
            echo "       are auto-collected from ~/Pictures/Screenshots into afterGameReport."
            echo ""
        else
            _run_vision_analysis "$report_dir" "$script"
        fi
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

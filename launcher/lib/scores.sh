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
# The initial tar.gz has no score in the filename; only the Claude review
# determines the score, which appears in the final re-archived filename.
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
    local dir_name="${user_name}_seriousGamesLab-24041LTS_${ts}"
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

    # Create tar.gz in player directory (no score in filename)
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

    # Run Claude Code analysis on all exports — produces PDF in archive root
    echo ""
    run_claude_analysis "$player_dir" "$tar_file" "$user_name"

    echo ""
    msg_ok "Export complete. Archive saved to $tar_file"
    exit 0
}

# Run Claude Code CLI to analyze all exports in the player directory.
# Calculates a revised score, provides rationale, trends, and suggestions.
# Saves a PDF report in the root of the archive (not in day subdirectories).
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

    # Collect screenshot paths from afterGameReport for Claude to reference
    local screenshots_list=""
    local img_dir="$tmpdir/_report_images"
    mkdir -p "$img_dir"
    local img_idx=0
    for day in "${DAY_ORDER[@]}"; do
        local agr_dir="$latest_dir/$day/afterGameReport"
        [[ -d "$agr_dir" ]] || continue
        while IFS= read -r -d '' img; do
            ((img_idx++)) || true
            local ext="${img##*.}"
            local img_name="${day}_$(basename "$(dirname "$img")")_${img_idx}.${ext}"
            cp "$img" "$img_dir/$img_name"
            screenshots_list+="  - ${day}: ${img_name}"$'\n'
        done < <(find "$agr_dir" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.bmp" \) -print0 2>/dev/null)
    done

    # Build the analysis prompt
    local prompt_file="$tmpdir/analysis_prompt.txt"

    {
        cat << 'HEADER'
You are analyzing a student's performance in the Serious Games Lab (SGL), a weekly training program spanning 7 strategic domains (MON=Poker, TUE=Historical Flight Sim, WED=Chess, THU=Sim Racing, FRI=Duplicate Bridge, SAT=Modern Flight Sim, SUN=Go).

Output your analysis as **Markdown**. The output will be converted to a PDF report.

Structure your report with these sections:

# SGL Performance Review

## Revised Scores
Calculate a revised per-day score (0-1) and overall average based on the OKR scoring criteria and all available evidence. Present as a table:

| Day | Theme | Score | Justification |
|-----|-------|-------|---------------|

Then state the **Overall Average** score.

## Rationale
Explain your scoring with specific reference to the learning framework:
- **Executive Function & Emotional Regulation** (from fourElementsOfMentalFunctioning.txt)
- **Meta-Learning Principles** (deep processing, desirable difficulty, deliberate practice, interleaving, spaced practice — from metaLearning.txt)
- **OKR Methodology** (committed vs aspirational OKRs, the 0.7 target — from ObjectivesAndKeyResults_OKR.txt)

## Trends
Compare the latest export with any previous ones. Comment on improvement, regression, or consistency across days and overall. If data permits, include a PlantUML diagram showing score trends:

```plantuml
@startsalt
... (use appropriate PlantUML diagram type)
@endsalt
```

## Day-by-Day Analysis
For each day that has game data, provide a subsection (### MON, ### TUE, etc.) with:
- What was played and what files were collected
- Specific strengths demonstrated
- Specific areas for improvement
- If screenshots are available, reference them by filename: ![description](SCREENSHOT_FILENAME)

## Suggestions
Provide both general and concrete day-specific suggestions for improvement. Be actionable. Where appropriate, include a PlantUML activity or mindmap diagram to illustrate a recommended practice workflow:

```plantuml
@startmindmap
* Improvement Areas
** Area 1
** Area 2
@endmindmap
```

HEADER

        if [[ -n "$screenshots_list" ]]; then
            echo ""
            echo "AVAILABLE SCREENSHOTS (reference these in your report using ![desc](FILENAME)):"
            echo "$screenshots_list"
            echo ""
        fi

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

        for doc in "$REPO_ROOT/fourElementsOfMentalFunctioning.txt" \
                   "$REPO_ROOT/metaLearning.txt" \
                   "$REPO_ROOT/ObjectivesAndKeyResults_OKR.txt"; do
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
                ! -name "claude_analysis.pdf" \
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

    # Call Claude Code CLI — output is Markdown
    local analysis_md="$tmpdir/claude_analysis.md"
    local claude_stderr="$tmpdir/claude_stderr.txt"
    if timeout 300 claude -p --max-turns 1 "$(cat "$prompt_file")" > "$analysis_md" 2>"$claude_stderr"; then
        # Print to screen
        cat "$analysis_md"
        echo ""

        # --- Convert Markdown to PDF ---
        local pdf_file="$latest_dir/claude_analysis.pdf"
        local pdf_generated=false

        # Process PlantUML code blocks into PNG images
        if command -v plantuml &>/dev/null; then
            local puml_idx=0
            local processed_md="$tmpdir/processed.md"
            local in_plantuml=false
            local puml_buf=""

            while IFS= read -r line; do
                if [[ "$line" =~ ^\`\`\`plantuml ]]; then
                    in_plantuml=true
                    puml_buf=""
                elif [[ "$in_plantuml" == true && "$line" == '```' ]]; then
                    in_plantuml=false
                    ((puml_idx++)) || true
                    local puml_file="$img_dir/diagram_${puml_idx}.puml"
                    local puml_png="$img_dir/diagram_${puml_idx}.png"
                    echo "$puml_buf" > "$puml_file"
                    if plantuml -tpng "$puml_file" -o "$img_dir" 2>/dev/null; then
                        echo "![Diagram ${puml_idx}](${puml_png})" >> "$processed_md"
                    else
                        echo "(diagram ${puml_idx} could not be rendered)" >> "$processed_md"
                    fi
                elif [[ "$in_plantuml" == true ]]; then
                    puml_buf+="$line"$'\n'
                else
                    echo "$line" >> "$processed_md"
                fi
            done < "$analysis_md"

            analysis_md="$processed_md"
        fi

        # Resolve screenshot references to absolute paths
        if [[ -d "$img_dir" ]]; then
            sed -i "s|!\[\([^]]*\)\](\([^/)][^)]*\))|![\1](${img_dir}/\2)|g" "$analysis_md"
        fi

        # Generate PDF
        if command -v pandoc &>/dev/null; then
            local pdf_engine_flag=""
            if command -v wkhtmltopdf &>/dev/null; then
                pdf_engine_flag="--pdf-engine=wkhtmltopdf"
            fi
            if pandoc "$analysis_md" -o "$pdf_file" \
                --metadata title="SGL Performance Review — ${player_name}" \
                --metadata date="$(date '+%Y-%m-%d')" \
                $pdf_engine_flag 2>/dev/null; then
                pdf_generated=true
                msg_ok "PDF report generated: claude_analysis.pdf"
            else
                msg_warn "PDF generation failed. Saving as markdown instead."
            fi
        fi

        # Fall back to markdown if PDF generation failed
        if [[ "$pdf_generated" == false ]]; then
            cp "$tmpdir/claude_analysis.md" "$latest_dir/claude_analysis.md"
            msg_ok "Analysis saved as claude_analysis.md in archive root."
        fi

        # Re-archive with report in root directory only
        local dir_name
        dir_name="$(basename "$latest_dir")"
        tar -czf "$latest_tar" -C "$tmpdir" "$dir_name"

        # Score is recorded in the Claude analysis report only, not in the filename
        msg_ok "Analysis saved to archive."
    else
        msg_warn "Claude Code analysis could not be completed."
        if [[ -s "$claude_stderr" ]]; then
            echo "  Error: $(head -5 "$claude_stderr")"
        fi
        if [[ -s "$analysis_md" ]]; then
            echo "  Output (first 3 lines): $(head -3 "$analysis_md")"
        fi
    fi

    rm -rf "$tmpdir"
}

# Display the scoring overview and learning framework summary.
# Composes a view from calculatingScore.txt and the three ~/Downloads
# reference documents, explaining how the general principles connect
# to per-day scoring and user-defined OKRs.
read_documentation() {
    local tmpfile
    tmpfile="$(mktemp)"

    {
        if [[ -f "$REPO_ROOT/calculatingScore.txt" ]]; then
            cat "$REPO_ROOT/calculatingScore.txt"
        fi

        cat << 'FRAMEWORK'

================================================================
LEARNING FRAMEWORK — HOW GENERAL PRINCIPLES CONNECT TO SCORING
================================================================

The SGL scoring system is grounded in three documents (in the sgl repo root).
Each one informs how you assess yourself using the per-day "How to
Calculate Score" criteria, especially when creating your own OKR tasks
(Objective #3 on each day).

1. OBJECTIVES AND KEY RESULTS (ObjectivesAndKeyResults_OKR.txt)
   ─────────────────────────────────────────────────────────────
   - Each day has Committed OKRs (expected score 1.0) and an
     Aspirational OKR (target 0.7, high variance)
   - Committed OKRs define the minimum: did you complete the task?
   - Aspirational OKRs define stretch goals: did you exceed expectations?
   - When writing your own OKR (Objective #3), decide whether it is
     committed or aspirational, and set measurable key results
   - Score 0.7 = good aspirational performance (Google standard)
   - Your daily total is capped at 0.7 unless aspirational OKRs push higher

2. META-LEARNING PRINCIPLES (metaLearning.txt)
   ─────────────────────────────────────────────
   Apply these when evaluating the QUALITY of your practice:
   - Deep processing: Did you think critically or just go through motions?
   - Desirable difficulty: Was it challenging enough to promote growth?
   - Deliberate practice: Did you focus on weaknesses with feedback?
   - Interleaving: Did you mix different problem types or drills?
   - Spaced practice: Are you spreading practice across sessions?
   - Dual coding: Did you use both visual and verbal learning?
   - Emotion: Were you engaged and motivated?

   When scoring yourself, a session that applies multiple meta-learning
   principles is worth more than one that merely logs time.

3. FOUR ELEMENTS OF MENTAL FUNCTIONING (fourElementsOfMentalFunctioning.txt)
   ──────────────────────────────────────────────────────────────────────────
   Self-assess across four dimensions during each session:
   - Executive Function: focus, planning, flexibility, problem-solving
   - Emotional Regulation: impulse control, self-soothing, redirecting
   - Memory: encoding new concepts (semantic), procedures (procedural),
     recalling game situations (episodic)
   - Creativity: flow states, lateral thinking, novel approaches

   Reference these when writing Objective #3 explanations — they help
   articulate WHY a session went well or poorly, beyond just the score.

HOW TO USE THIS IN PRACTICE
────────────────────────────
1. Before playing, review "How to Calculate Score" for the day
2. Set an intention based on a specific OKR
3. After the game, assess yourself honestly:
   - Which OKR criteria did you meet?
   - Which meta-learning principles were active?
   - Which mental functions were you exercising?
4. When defining your own OKR (Objective #3), use the framework:
   - Make it measurable (OKR methodology)
   - Make it challenging but achievable (desirable difficulty)
   - Target a specific mental function or meta-learning principle
5. Export scores when ready — Claude Code reviews your work using
   all three frameworks to produce a comprehensive PDF report

FRAMEWORK
    } > "$tmpfile"

    less "$tmpfile"
    rm -f "$tmpfile"
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


#!/usr/bin/env bash
# claude_annotate_sgf.sh — Add English-language annotations to a KataGo-analysed SGF
#
# Source this file, then call:
#   claude_annotate_sgf "/path/to/game_analysed.sgf"
#
# Requires: claude CLI (Claude Code) on PATH.
# If claude is not available the function silently returns 0.
# The annotated SGF replaces the original file.

claude_annotate_sgf() {
    local sgf_file="$1"
    [[ -f "$sgf_file" ]] || return 0
    command -v claude &>/dev/null || return 0

    local base
    base="$(basename "$sgf_file")"
    echo "  Adding English annotations via Claude Code: $base"

    local tmp_out
    tmp_out="$(mktemp --suffix=.sgf)"

    local sgf_content
    sgf_content="$(cat "$sgf_file")"

    local prompt
    prompt="$(cat <<'PROMPT_EOF'
You are a Go teacher for beginner to intermediate players (roughly 20k-10k). You have deep knowledge of these classic instructional Go books:

1. "Lessons in the Fundamentals of Go" by Toshiro Kageyama
2. "The Second Book of Go" by Richard Bozulich
3. "Tesuji" by James Davies (Elementary Go Series)
4. "Life and Death" by James Davies (Elementary Go Series)
5. "Attack and Defense" by Akira Ishida & James Davies (Elementary Go Series)
6. "In the Beginning" by Ikuro Ishigure (Elementary Go Series)
7. "Opening Theory Made Easy" by Otake Hideo
8. "Graded Go Problems for Beginners" by Kano Yoshinori
9. "The Direction of Play" by Takeo Kajiwara
10. "Learn to Play Go" series by Janice Kim & Jeong Soo-hyun

You are given an SGF file that has been annotated by KataGo with win-rate and score estimates in comments (like "B win: 68.5%, Score: B+3.2").

Your task: Add concise English-language explanations that help a beginner understand WHY moves are good or bad. Focus on:
- Fundamental concepts (territory vs influence, thickness, aji, sente/gote)
- Shape (good shape, bad shape, empty triangles, tigers mouth)
- Direction of play and whole-board thinking
- Key tactical patterns (ladders, nets, snapbacks, life & death)
- Joseki deviations and their consequences
- Big mistakes and what to play instead
- Endgame priorities

Rules:
1. Output a COMPLETE, VALID SGF file — preserve ALL headers, moves, and existing KataGo comments exactly
2. Add your English comments by APPENDING to existing KataGo comments within the same C[] property, separated by " | "
   Example: C[B win: 68.5%, Score: B+3.2 | This move builds thickness on the outside — Kageyama emphasises thickness over small territorial gains]
3. You do NOT need to comment on every move — focus on the 10-15 most instructive moments
4. Keep each comment to 1-2 sentences maximum
5. Where relevant, reference which book's concept applies
6. Output ONLY the SGF — no explanations before or after
7. Maintain valid SGF syntax: properties like C[...], B[...], W[...] with square brackets, semicolons between nodes
PROMPT_EOF
)"

    if timeout 120 claude -p --max-turns 1 "${prompt}

Here is the SGF file:

${sgf_content}" > "$tmp_out" 2>/dev/null; then
        # Strip markdown code fences that Claude sometimes wraps around output
        sed -i '/^```/d' "$tmp_out"

        # Validate: must contain SGF header and at least one move
        if grep -q '(;' "$tmp_out" && grep -qE '[BW]\[[a-s][a-s]\]' "$tmp_out"; then
            cp "$tmp_out" "$sgf_file"
            echo "  Done: English annotations added to $base"
        else
            echo "  Claude output was not valid SGF, keeping KataGo-only version."
        fi
    else
        echo "  Claude annotation failed, keeping KataGo-only version."
    fi
    rm -f "$tmp_out"
}

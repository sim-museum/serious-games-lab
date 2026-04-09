#!/usr/bin/env bash
# claude_annotate_pgn.sh — Add English-language annotations to a Stockfish-analysed PGN
#
# Source this file, then call:
#   claude_annotate_pgn "/path/to/game.pgn"
#
# Requires: claude CLI (Claude Code) on PATH.
# If claude is not available the function silently returns 0.
# The annotated PGN replaces the original file.

claude_annotate_pgn() {
    local pgn_file="$1"
    [[ -f "$pgn_file" ]] || return 0
    command -v claude &>/dev/null || return 0

    local base
    base="$(basename "$pgn_file")"
    echo "  Adding English annotations via Claude Code: $base"

    local tmp_out
    tmp_out="$(mktemp --suffix=.pgn)"

    local pgn_content
    pgn_content="$(cat "$pgn_file")"

    local prompt
    prompt="$(cat <<'PROMPT_EOF'
You are a chess coach for players rated ELO 1200-1400. You have deep knowledge of these classic instructional chess books:

1. "Logical Chess: Move by Move" by Irving Chernev
2. "My System" by Aron Nimzowitsch
3. "Chess Fundamentals" by Jose Raul Capablanca
4. "How to Reassess Your Chess" by Jeremy Silman
5. "The Amateur's Mind" by Jeremy Silman
6. "Bobby Fischer Teaches Chess" by Bobby Fischer
7. "Winning Chess Strategies" by Yasser Seirawan
8. "Winning Chess Tactics" by Yasser Seirawan
9. "The Most Instructive Games of Chess Ever Played" by Irving Chernev
10. "Silman's Complete Endgame Course" by Jeremy Silman

You are given a PGN file that has been annotated by Stockfish with evaluation scores (like {+0.25} or {M3}) and best-move variations.

Your task: Add concise English-language comments that EXPLAIN the ideas behind the moves in terms an ELO 1200-1400 player would understand. Focus on:
- Key strategic concepts (pawn structure, piece activity, king safety, space)
- Tactical motifs (pins, forks, skewers, discovered attacks, back-rank threats)
- Critical mistakes and why they're bad
- Turning points in the game
- Opening principles and plans
- Endgame technique where relevant

Rules:
1. Output a COMPLETE, VALID PGN file — preserve ALL headers, moves, evaluations, and variations exactly
2. Add your English comments by APPENDING to existing Stockfish comments within the same curly braces, separated by " | "
   Example: {+0.25 | Good developing move, following Chernev's principle of rapid development}
3. You do NOT need to comment on every move — focus on the 10-15 most instructive moments
4. Keep each comment to 1-2 sentences maximum
5. Where relevant, reference which book's concept applies (e.g., "Nimzowitsch's overprotection")
6. Output ONLY the PGN — no explanations before or after
PROMPT_EOF
)"

    if timeout 120 claude -p --max-turns 1 "${prompt}

Here is the PGN file:

${pgn_content}" > "$tmp_out" 2>/dev/null; then
        # Strip markdown code fences that Claude sometimes wraps around output
        sed -i '/^```/d' "$tmp_out"

        # Validate: must contain at least one PGN header and move text
        if grep -q '^\[Event ' "$tmp_out" && grep -qE '1\.' "$tmp_out"; then
            cp "$tmp_out" "$pgn_file"
            echo "  Done: English annotations added to $base"
        else
            echo "  Claude output was not valid PGN, keeping Stockfish-only version."
        fi
    else
        echo "  Claude annotation failed, keeping Stockfish-only version."
    fi
    rm -f "$tmp_out"
}

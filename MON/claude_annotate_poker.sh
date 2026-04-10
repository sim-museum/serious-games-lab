#!/usr/bin/env bash
# claude_annotate_poker.sh — Add strategic annotations to poker log/output files
#
# Source this file, then call:
#   claude_annotate_poker "/path/to/poker_log.txt"
#
# Requires: claude CLI (Claude Code) on PATH.
# If claude is not available the function silently returns 0.
# Creates an _annotated.txt file alongside the original.

claude_annotate_poker() {
    local log_file="$1"
    [[ -f "$log_file" ]] || return 0
    command -v claude &>/dev/null || return 0

    local base dir stem annotated
    base="$(basename "$log_file")"
    dir="$(dirname "$log_file")"
    stem="${base%.*}"

    # Convert PokerTH .pdb (SQLite) to readable text first
    if file -b "$log_file" | grep -qi "sqlite\|database"; then
        local converter="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pokerth_pdb_to_text.py"
        if [[ -f "$converter" ]]; then
            local text_file="${dir}/${stem}.txt"
            python3 "$converter" "$log_file" "$text_file" 2>/dev/null || return 0
            log_file="$text_file"
            base="$(basename "$text_file")"
            stem="${base%.*}"
        else
            return 0  # No converter available, skip
        fi
    fi
    annotated="${dir}/${stem}_annotated.txt"

    echo "  Adding strategic annotations via Claude Code: $base"

    local log_content
    log_content="$(cat "$log_file")"

    local prompt
    prompt="$(cat <<'PROMPT_EOF'
You are a poker coach specialising in helping intermediate players improve their game. You draw on the strategic wisdom of these top poker books:

1. "The Theory of Poker" by David Sklansky
2. "Harrington on Hold 'em" (Vol 1-3) by Dan Harrington
3. "The Mathematics of Poker" by Bill Chen & Jerrod Ankenman
4. "Applications of No-Limit Hold 'em" by Matthew Janda
5. "Small Stakes Hold 'em" by Ed Miller, David Sklansky & Mason Malmuth
6. "Every Hand Revealed" by Gus Hansen
7. "Kill Everyone" by Lee Nelson, Tysen Streib & Kim Lee
8. "Elements of Poker" by Tommy Angelo
9. "Playing the Player" by Ed Miller
10. "Professional No-Limit Hold 'em" by Matt Flynn, Sunny Mehta & Ed Miller

You are given a poker session log or evaluation output. This could be:
- A PokerTH hand history log
- A PokerIQ training session log
- A PokerStove equity calculation output
- A ps-eval equity evaluation session

Your task: Provide a strategic analysis of the session. Focus on:
- Pre-flop hand selection decisions (position-aware ranges)
- Pot odds and implied odds calculations
- Betting patterns and sizing tells
- Positional play (early, middle, late position, blinds)
- Key decision points and whether the right play was made
- Tournament vs cash game strategy differences (if applicable)
- EV (expected value) analysis of critical hands
- Bankroll management implications
- Common leaks identified in the session

Rules:
1. Start with a brief session summary (2-3 sentences)
2. Then analyse the most important hands/evaluations (up to 10)
3. For each hand/evaluation: state what happened, what was correct, and why (referencing book concepts)
4. End with 3-5 specific improvement suggestions
5. Keep the tone instructive, not judgmental
6. Reference which book's concept applies where relevant (e.g., "Sklansky's Fundamental Theorem of Poker")
7. Output plain text with clear section headings
PROMPT_EOF
)"

    if timeout 120 claude -p --max-turns 1 "${prompt}

Here is the poker session data:

${log_content}" > "$annotated" 2>/dev/null; then
        # Validate: output should have some meaningful content
        local line_count
        line_count="$(wc -l < "$annotated")"
        if [[ "$line_count" -ge 5 ]]; then
            echo "  Done: Strategic annotations saved to ${stem}_annotated.txt"
        else
            echo "  Claude output was too short, removing annotation file."
            rm -f "$annotated"
        fi
    else
        echo "  Claude annotation failed."
        rm -f "$annotated"
    fi
}

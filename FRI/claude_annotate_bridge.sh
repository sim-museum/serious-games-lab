#!/usr/bin/env bash
# claude_annotate_bridge.sh — Compare two BDL files and add English annotations
#
# Usage:
#   claude_annotate_bridge.sh HUMAN.bdl QPLUS.bdl OUTPUT.bdl
#
# Takes two BDL files (human play and Q-Plus computer play for the same hand),
# sends them to Claude Code for comparison and annotation using the top 10
# beginner bridge books, and writes a combined annotated BDL file.
#
# If Claude Code is not available, copies both BDL files into the output
# without annotations.

set -euo pipefail

HUMAN_BDL="${1:-}"
QPLUS_BDL="${2:-}"
OUTPUT_BDL="${3:-}"

if [[ -z "$HUMAN_BDL" || -z "$QPLUS_BDL" || -z "$OUTPUT_BDL" ]]; then
    echo "Usage: $0 HUMAN.bdl QPLUS.bdl OUTPUT.bdl" >&2
    exit 1
fi

if [[ ! -f "$HUMAN_BDL" ]]; then
    echo "Error: Human BDL file not found: $HUMAN_BDL" >&2
    exit 1
fi

if [[ ! -f "$QPLUS_BDL" ]]; then
    echo "Error: Q-Plus BDL file not found: $QPLUS_BDL" >&2
    exit 1
fi

human_content="$(cat "$HUMAN_BDL")"
qplus_content="$(cat "$QPLUS_BDL")"

# If Claude Code is not available, just concatenate both BDL files
if ! command -v claude &>/dev/null; then
    {
        echo "DOCTYPE: BDL 17.1"
        echo ".description.eng = \"combined human + Q-Plus play (no AI annotation)\""
        echo ""
        echo "=========================================="
        echo "HUMAN PLAY"
        echo "=========================================="
        echo ""
        echo "$human_content"
        echo ""
        echo "=========================================="
        echo "Q-PLUS COMPUTER PLAY"
        echo "=========================================="
        echo ""
        echo "$qplus_content"
    } > "$OUTPUT_BDL"
    echo "  Claude Code not available, saved combined BDL without annotations."
    exit 0
fi

echo "  Generating English annotations via Claude Code..."

prompt="$(cat <<'PROMPT_EOF'
You are a bridge teacher for beginner to intermediate players. You have deep knowledge of these classic instructional bridge books:

1. "Bridge Basics 1: An Introduction" by Audrey Grant
2. "Bridge for Dummies" by Eddie Kantar
3. "25 Bridge Conventions You Should Know" by Barbara Seagram & Marc Smith
4. "Points Schmoints!" by Marty Bergen
5. "How to Play a Bridge Hand" by William Root
6. "The Backwash Squeeze and Other Improbable Feats" by Edward McPherson
7. "Larry Cohen's Bidding Challenge" by Larry Cohen
8. "Declarer Play at Bridge: A Quizbook" by Barbara Seagram & David Bird
9. "To Bid or Not to Bid" by Larry Cohen (Law of Total Tricks)
10. "Card Play Technique" by Victor Mollo & Nico Gardener

You are given TWO BDL (Bridge Deal Log) files for the SAME hand:
- BDL #1: How a human player played the hand
- BDL #2: How Q-Plus Bridge (strong computer) played the same hand

The BDL format contains: deal cards, bidding auction, contract, trick-by-trick play, and result.

Your task: Create a SINGLE combined BDL file with English-language annotations comparing both lines of play. The output must:

1. Start with "DOCTYPE: BDL 17.1" and a description line
2. Include BOTH the human play and Q-Plus play sections in full (preserving all original BDL content exactly)
3. After each play section, add a "Commentary" block with annotations using this format:
   Commentary   :  [Your English annotations here]
   .            :  [continuation lines]
4. The Commentary blocks should cover:
   - BIDDING analysis: Was the auction reasonable? What would the books recommend? Reference specific conventions (Stayman, Blackwood, transfers, etc.)
   - OPENING LEAD analysis: Was it the right lead? What does the book say about leads against this contract?
   - DECLARER PLAY analysis: Compare the trick-by-trick play. Where did the human deviate from optimal? What technique applies (finesse, endplay, squeeze, elimination, safety play)?
   - DEFENSIVE analysis: Were the signals correct? Were there missed defensive opportunities?
   - KEY DIFFERENCES: Where the human and computer differed, explain WHY the computer's line was better (or if the human found an equally good line)
   - RESULT comparison: How many tricks difference? What was the cost in points/IMPs?
5. Reference which book's concept applies (e.g., "Bergen's Law of Total Tricks", "Root's principle of leading from length")
6. Keep annotations practical and actionable for a beginner
7. At the end, add a "Summary" block with 3-5 key takeaways

Rules:
- Output ONLY the combined BDL file — no explanations before or after
- Preserve all original BDL formatting exactly
- Commentary lines use the same indentation style as BDL (label : content)
- Keep each annotation point to 1-2 sentences
PROMPT_EOF
)"

tmp_out="$(mktemp --suffix=.bdl)"

if timeout 120 claude -p --max-turns 1 "${prompt}

=== BDL #1: HUMAN PLAY ===

${human_content}

=== BDL #2: Q-PLUS COMPUTER PLAY ===

${qplus_content}" > "$tmp_out" 2>&1; then
    # Strip markdown code fences that Claude sometimes wraps around output
    sed -i '/^```/d' "$tmp_out"

    # Validate: must contain DOCTYPE header and at least one Deal section
    if grep -q 'DOCTYPE' "$tmp_out" && grep -q 'Deal' "$tmp_out"; then
        cp "$tmp_out" "$OUTPUT_BDL"
        echo "  Done: Annotated bridge comparison saved to $(basename "$OUTPUT_BDL")"
    else
        echo "  Claude output was not valid BDL format, saving without annotations."
        {
            echo "DOCTYPE: BDL 17.1"
            echo ".description.eng = \"combined human + Q-Plus play (annotation failed)\""
            echo ""
            echo "=========================================="
            echo "HUMAN PLAY"
            echo "=========================================="
            echo ""
            echo "$human_content"
            echo ""
            echo "=========================================="
            echo "Q-PLUS COMPUTER PLAY"
            echo "=========================================="
            echo ""
            echo "$qplus_content"
        } > "$OUTPUT_BDL"
    fi
else
    echo "  Claude annotation failed, saving combined BDL without annotations."
    {
        echo "DOCTYPE: BDL 17.1"
        echo ".description.eng = \"combined human + Q-Plus play (annotation failed)\""
        echo ""
        echo "=========================================="
        echo "HUMAN PLAY"
        echo "=========================================="
        echo ""
        echo "$human_content"
        echo ""
        echo "=========================================="
        echo "Q-PLUS COMPUTER PLAY"
        echo "=========================================="
        echo ""
        echo "$qplus_content"
    } > "$OUTPUT_BDL"
fi
rm -f "$tmp_out"

#!/usr/bin/env bash
# claude_annotate_bridge_single.sh — Annotate a Q-Plus BDL game log with Claude
#
# Usage:
#   claude_annotate_bridge_single.sh INPUT.bdl OUTPUT.bdl
#
# Takes a Q-Plus BDL log file (which typically contains the human's play
# and the computer's analysis of the same deals) and adds English-language
# annotations drawn from the top 10 beginner bridge books.
#
# If Claude Code is not available, the output is a copy of the input.

set -euo pipefail

INPUT_BDL="${1:-}"
OUTPUT_BDL="${2:-}"

if [[ -z "$INPUT_BDL" || -z "$OUTPUT_BDL" ]]; then
    echo "Usage: $0 INPUT.bdl OUTPUT.bdl" >&2
    exit 1
fi

if [[ ! -f "$INPUT_BDL" ]]; then
    echo "Error: BDL file not found: $INPUT_BDL" >&2
    exit 1
fi

if ! command -v claude &>/dev/null; then
    cp "$INPUT_BDL" "$OUTPUT_BDL"
    echo "  Claude Code not available, saved BDL copy without annotations."
    exit 0
fi

echo "  Generating English annotations via Claude Code..."

bdl_content="$(cat "$INPUT_BDL")"

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

You are given a BDL (Bridge Deal Log) file from Q-Plus Bridge. This log contains one or more deals played by a human against the Q-Plus computer. If multiple deal sections appear for the same hand, the first typically shows the human's play and subsequent ones show the computer's analysis.

The BDL format contains: deal cards, bidding auction, contract, trick-by-trick play, and result. Lines beginning with "Players" indicate human/computer roles.

Your task: Create an annotated version of this BDL file with English-language teaching commentary. The output must:

1. Start with "DOCTYPE: BDL 17.1" and a description line
2. Include ALL original BDL content exactly as-is
3. After each deal's "Result" line (before the **** separator), add a "Commentary" block:
   Commentary   :  [Your English annotations here]
   .            :  [continuation lines]
4. The Commentary blocks should cover:
   - BIDDING: Was the auction sound? What conventions apply? Were there missed opportunities?
   - OPENING LEAD: Correct choice? What does standard theory recommend?
   - DECLARER PLAY: Were the right techniques used (finesse, safety play, elimination, endplay)?
   - DEFENSE: Were signals and discards correct? Missed defensive plays?
   - RESULT: Was the result par? Could more tricks have been made or saved?
   - If two play records exist for the same deal, compare them explicitly
5. Reference which book's concept applies (e.g., "Bergen's Law of Total Tricks", "Kantar's lead principles")
6. Keep annotations practical — 1-2 sentences per point
7. End with a "Summary" block with 3-5 key takeaways for the session

Rules:
- Output ONLY the annotated BDL file — no explanations before or after
- Preserve all original BDL formatting exactly
- Commentary lines use the same indentation style as BDL (label : content)
PROMPT_EOF
)"

tmp_out="$(mktemp --suffix=.bdl)"

if timeout 120 claude -p --max-turns 1 "${prompt}

Here is the Q-Plus BDL game log:

${bdl_content}" > "$tmp_out" 2>&1; then
    # Strip markdown code fences that Claude sometimes wraps around output
    sed -i '/^```/d' "$tmp_out"

    if grep -q 'DOCTYPE' "$tmp_out" && grep -q 'Deal' "$tmp_out"; then
        cp "$tmp_out" "$OUTPUT_BDL"
        echo "  Done: Annotated BDL saved to $(basename "$OUTPUT_BDL")"
    else
        echo "  Claude output was not valid BDL format, saving copy without annotations."
        cp "$INPUT_BDL" "$OUTPUT_BDL"
    fi
else
    echo "  Claude annotation failed, saving copy without annotations."
    cp "$INPUT_BDL" "$OUTPUT_BDL"
fi
rm -f "$tmp_out"

#!/bin/bash

# ps-eval - text mode poker equity calculator
# Builds from source (github.com/andrewprock/pokerstove) if not present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PS_EVAL="$SCRIPT_DIR/ps-eval"

clear

if [[ ! -x "$PS_EVAL" ]]; then
    echo "ps-eval not found. Building from source..."

    # Check build dependencies
    DEPS=(build-essential cmake git libboost-all-dev)
    MISSING=()
    for pkg in "${DEPS[@]}"; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            MISSING+=("$pkg")
        fi
    done
    if [[ ${#MISSING[@]} -gt 0 ]]; then
        echo "Installing build dependencies: ${MISSING[*]}"
        sudo apt-get install -y "${MISSING[@]}"
    fi

    BUILD_DIR="/tmp/pokerstove_build"
    rm -rf "$BUILD_DIR"

    if git clone https://github.com/andrewprock/pokerstove.git "$BUILD_DIR"; then
        cd "$BUILD_DIR"
        cmake -DCMAKE_BUILD_TYPE=Release -S . -B build
        cmake --build build -j "$(nproc)"

        # Find and copy ps-eval binary
        PS_EVAL_BUILT=$(find build -name ps-eval -type f | head -1)
        if [[ -n "$PS_EVAL_BUILT" && -x "$PS_EVAL_BUILT" ]]; then
            rm -f "$PS_EVAL"
            cp "$PS_EVAL_BUILT" "$PS_EVAL"
            chmod +x "$PS_EVAL"
            echo "ps-eval built successfully."
        else
            echo "Build completed but ps-eval binary not found."
            rm -rf "$BUILD_DIR"
            exit 1
        fi
        rm -rf "$BUILD_DIR"
    else
        echo "Failed to clone pokerstove repository."
        exit 1
    fi
fi

echo ""
echo "ps-eval: text mode poker equity calculator"
echo "Works with Texas Hold 'em, Omaha, Stud, Draw"
echo ""
echo "    Allowed options:"
echo "      -? [ --help ]          produce help message"
echo "      -g [ --game ] arg (=h) game to use for evaluation"
echo "      -b [ --board ] arg     community cards for he/o/o8"
echo "      -h [ --hand ] arg      a hand for evaluation"
echo "      -q [ --quiet ]         produce no output"
echo ""
echo "       For the --game option, one of the following games may be"
echo "       specified."
echo "         h     hold'em"
echo "         o     omaha/8"
echo "         O     omaha high"
echo "         r     razz"
echo "         s     stud"
echo "         e     stud/8"
echo "         q     stud high/low no qualifier"
echo "         d     draw high"
echo "         l     lowball (A-5)"
echo "         k     Kansas City lowball (2-7)"
echo "         t     triple draw lowball (2-7)"
echo "         T     triple draw lowball (A-5)"
echo "         b     badugi"
echo "         3     three-card poker"
echo ""
echo "       examples:"
echo "           ./ps-eval acas"
echo "           ./ps-eval AcAs Kh4d --board 5c8s9h"
echo "           ./ps-eval --game l 7c5c4c3c2c"
echo "           ./ps-eval --game k 7c5c4c3c2c"
echo ""
echo "Tip: use --board to specify community cards — this is MUCH faster."
echo "Without --board, ps-eval enumerates all possible 5-card boards."
echo "With a flop, it only needs to check the remaining 2 cards."
echo ""
echo "Type 'exit' to return to the launcher."
echo "(All input and output will be logged.)"
echo ""

cd "$SCRIPT_DIR"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
# This script is a calculator, not a "game" — don't touch the started
# marker (would trigger a launcher self-assessment prompt). capture
# still works via its wall-clock fallback.
capture_marker_epoch

LOG_FILE="$SCRIPT_DIR/ps_eval_log_$(date '+%y%m%d_%H%M').txt"
script -q -c "bash --norc --noprofile -i" "$LOG_FILE"

# Move log into the timestamped afterGameReport subdir BEFORE annotation
# so a concurrent game's collect_after_game_report can't grab it mid-run.
report_subdir="$(post_game_subdir "$SCRIPT_DIR" pseval)"
target="$report_subdir/$(basename "$LOG_FILE")"
mv -f "$LOG_FILE" "$target"

# Annotate session log with Claude Code
source "$SCRIPT_DIR/claude_annotate_poker.sh"
claude_annotate_poker "$target"

echo "  Annotated log saved to afterGameReport/$(basename "$report_subdir")/"

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
echo ""

cd "$SCRIPT_DIR"
exec bash --norc --noprofile -i

#!/usr/bin/bash

# q5Go - Go GUI (SGF editor and game client)
# Uses locally-built q5go, falls back to system-installed.
# Auto-configures KataGo Human SL engine on first launch.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure KataGo + models are present
source "$SCRIPT_DIR/ensure_katago.sh"

# Auto-configure q5go engine if not already set
Q5GO_RC="$HOME/.config/q5go/q5gorc"
if [[ -f "$Q5GO_RC" ]]; then
    if ! grep -q "KataGo Human" "$Q5GO_RC" 2>/dev/null; then
        # Find the next available engine number
        LAST_N=$(grep -oP 'ENGINE\K[0-9]+' "$Q5GO_RC" 2>/dev/null | sort -n | tail -1)
        NEXT_N=$(( ${LAST_N:-0} + 1 ))
        echo "Configuring KataGo Human SL engine in q5go..."
        cat >> "$Q5GO_RC" << EOF
ENGINE${NEXT_N}a [KataGo Human]
ENGINE${NEXT_N}b [$KATAGO_BIN]
ENGINE${NEXT_N}c [gtp -model $MAIN_MODEL -human-model $HUMAN_MODEL -config $DEFAULT_CONFIG]
ENGINE${NEXT_N}d []
ENGINE${NEXT_N}e [0]
ENGINE${NEXT_N}f []
ENGINE${NEXT_N}g [0]
EOF
    fi
else
    # Create config dir and minimal config with engine entry
    mkdir -p "$(dirname "$Q5GO_RC")"
    cat > "$Q5GO_RC" << EOF
ENGINE1a [KataGo Human]
ENGINE1b [$KATAGO_BIN]
ENGINE1c [gtp -model $MAIN_MODEL -human-model $HUMAN_MODEL -config $DEFAULT_CONFIG]
ENGINE1d []
ENGINE1e [0]
ENGINE1f []
ENGINE1g [0]
EOF
    echo "Created q5go config with KataGo Human SL engine."
fi

# Launch q5go — prefer local build, then system-installed
Q5GO_LOCAL="$SCRIPT_DIR/q5go_install/bin/q5go"
if [[ -x "$Q5GO_LOCAL" ]]; then
    "$Q5GO_LOCAL" &
    disown
elif command -v q5go &>/dev/null; then
    q5go &
    disown
else
    echo ""
    echo "q5go not found. Building from source..."

    # Install Qt5 build dependencies if needed
    QT5_DEPS=(qtbase5-dev qt5-qmake qtmultimedia5-dev libqt5svg5-dev)
    QT5_MISSING=()
    for pkg in "${QT5_DEPS[@]}"; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            QT5_MISSING+=("$pkg")
        fi
    done
    if [[ ${#QT5_MISSING[@]} -gt 0 ]]; then
        echo "Installing Qt5 build dependencies: ${QT5_MISSING[*]}"
        sudo apt-get install -y "${QT5_MISSING[@]}"
    fi

    if [[ ! -d "$SCRIPT_DIR/q5go_build" ]]; then
        git clone https://github.com/bernds/q5Go.git "$SCRIPT_DIR/q5go_build"
    fi
    mkdir -p "$SCRIPT_DIR/q5go_build/build"
    cd "$SCRIPT_DIR/q5go_build/build"
    qmake ../src/q5go.pro PREFIX="$SCRIPT_DIR/q5go_install"
    make -j"$(nproc)"
    make install
    cd "$SCRIPT_DIR"
    if [[ -x "$Q5GO_LOCAL" ]]; then
        "$Q5GO_LOCAL" &
        disown
    else
        echo "Build failed. Install Qt5 dev packages and retry:"
        echo "  sudo apt install ${QT5_DEPS[*]}"
    fi
fi

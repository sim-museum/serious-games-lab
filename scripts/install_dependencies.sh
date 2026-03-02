#!/usr/bin/env bash
# install_dependencies.sh - Master apt installer for Serious Games Lab
# Installs all system dependencies needed for source and binary games
# on a clean Ubuntu 24.04 LTS installation.
#
# Merged from:
#   - ese/runThisScriptFirst.sh (game-specific packages)
#   - serious-games-lab original install_dependencies.sh (graphics/audio/font libs)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ERRORS=0

echo "=============================================="
echo "  Serious Games Lab - Dependency Installer"
echo "  Ubuntu 24.04 LTS  (idempotent - safe to re-run)"
echo "=============================================="
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run with sudo."
    echo "Usage: sudo $0"
    exit 1
fi

# --- Check for CD-ROM apt source bug (Ubuntu 22.04/24.04 install bug) ---
if grep -q "^deb cdrom" /etc/apt/sources.list 2>/dev/null; then
    echo "WARNING: Ubuntu is set to install packages from a CD-ROM instead"
    echo "of the internet. To fix this, run:"
    echo "  sudo sed -i 's/deb cdrom/#deb cdrom/g' /etc/apt/sources.list"
    echo "then run this script again."
    exit 1
fi

# --- Check graphics driver (skip on re-runs with --yes flag) ---
if [[ "${1:-}" != "--yes" ]] && lsmod | grep -q nouveau 2>/dev/null; then
    echo "WARNING: the slow open source nouveau graphics driver is detected."
    echo "3D simulations (rFactor, BMS, FlightGear) may run poorly."
    echo ""
    echo "To install proprietary drivers:"
    echo "  sudo ubuntu-drivers devices"
    echo "  sudo ubuntu-drivers autoinstall"
    echo "  sudo reboot"
    echo ""
    read -rp "Continue with nouveau driver? (y/N): " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Install a proprietary graphics driver and rerun this script."
        exit 0
    fi
fi

# --- Detect whether binary (Wine) games are present ---
has_binary_games() {
    compgen -G "$REPO_ROOT/downloads/sglBinaries_*" >/dev/null 2>&1 && return 0
    compgen -G "$REPO_ROOT/downloads/.extracted_sglBinaries_*" >/dev/null 2>&1 && return 0
    for day in MON TUE WED THU FRI SAT SUN; do
        compgen -G "$REPO_ROOT/$day/WP" "$REPO_ROOT/$day/*/WP" >/dev/null 2>&1 && return 0
    done
    return 1
}

INSTALL_WINE=false
if has_binary_games; then
    INSTALL_WINE=true
    echo "Binary game data detected — will install Wine/Lutris."
else
    echo "Source-only install — skipping Wine/Lutris."
fi

# --- Enable 32-bit architecture (only needed for Wine) ---
if $INSTALL_WINE; then
    echo ""
    echo "Enabling 32-bit architecture for Wine..."
    dpkg --add-architecture i386
fi

# Only run apt-get update if package lists are older than 1 hour
APT_LISTS="/var/lib/apt/lists"
if [[ -z "$(find "$APT_LISTS" -maxdepth 0 -mmin -60 2>/dev/null)" ]]; then
    echo "Updating package lists..."
    apt-get update
else
    echo "Package lists are recent, skipping apt-get update."
fi

# --- Core build tools ---
echo ""
echo "Installing build essentials..."
apt-get install -y \
    build-essential cmake pkg-config git curl wget \
    clang ninja-build meson

if $INSTALL_WINE; then
    # --- Wine (32-bit and 64-bit) ---
    echo ""
    echo "Installing Wine..."
    apt-get install -y \
        wine wine32:i386 wine64 winetricks

    # --- Graphics libraries (32-bit support for Wine games) ---
    echo ""
    echo "Installing graphics libraries..."
    apt-get install -y \
        libgl1-mesa-dri:i386 \
        libgl1:i386 \
        mesa-vulkan-drivers \
        mesa-vulkan-drivers:i386 \
        libvulkan1 \
        libvulkan1:i386 \
        vulkan-tools

    # --- NVIDIA 32-bit OpenGL library (needed for GPU-accelerated Wine games) ---
    NVIDIA_VER=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1)
    if [[ -n "$NVIDIA_VER" ]] && ! dpkg -s "libnvidia-gl-${NVIDIA_VER}:i386" &>/dev/null; then
        echo ""
        echo "Installing 32-bit NVIDIA OpenGL library (driver $NVIDIA_VER)..."
        echo "  (Without this, Wine games fall back to software rendering.)"
        apt-get install -y "libnvidia-gl-${NVIDIA_VER}:i386"
    fi

    # --- Audio libraries (32-bit support for Wine games) ---
    echo ""
    echo "Installing audio libraries..."
    apt-get install -y \
        libpulse0:i386 \
        libasound2-plugins:i386 \
        libsdl2-2.0-0:i386

    # --- Font packages (needed by Wine games) ---
    echo ""
    echo "Installing font packages..."
    apt-get install -y \
        fonts-wine \
        fonts-liberation \
        fonts-dejavu-core
fi

# --- Python ---
echo ""
echo "Installing Python dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pyqt6 \
    python3-pandas \
    python3.12-venv \
    libncurses-dev \
    libxcb-cursor0 \
    espeak

# --- Node.js ---
echo ""
echo "Installing Node.js..."
apt-get install -y nodejs npm

# --- Chess & board game tools (FRI/WED) ---
echo ""
echo "Installing chess, board game, and card game packages..."
apt-get install -y \
    scid stockfish xboard \
    tenace deal dealer \
    gnugo kigo \
    pokerth

# --- Libraries for specific games ---
echo ""
echo "Installing game-specific libraries..."
apt-get install -y \
    liblua5.2-dev \
    libqt5widgets5 \
    libqt5multimedia5 \
    libqt5sql5 \
    qtbase5-dev qt5-qmake qtmultimedia5-dev libqt5svg5-dev \
    xclip \
    libopenblas-dev \
    libeigen3-dev \
    libboost-all-dev \
    protobuf-compiler libprotobuf-dev \
    zlib1g-dev libstdc++-14-dev \
    qml-module-qtquick-shapes \
    qml-module-org-kde-kcoreaddons

# --- Simulation and utility packages ---
echo ""
echo "Installing simulation and utility packages..."
apt-get install -y \
    dosbox \
    libfuse2t64 \
    bchunk unrar 7zip innoextract \
    vim okular filelight \
    cabextract p7zip-full unzip xdg-utils

if $INSTALL_WINE; then
    # --- Lutris (for Wine game management) ---
    echo ""
    echo "Installing Lutris..."
    apt-get install -y curl
    if command -v deb-get &>/dev/null; then
        deb-get install lutris || apt-get install -y lutris || true
    else
        if curl -sL https://raw.githubusercontent.com/wimpysworld/deb-get/main/deb-get | bash /dev/stdin install deb-get 2>/dev/null; then
            deb-get install lutris || apt-get install -y lutris || true
        else
            apt-get install -y lutris || true
        fi
    fi

    # --- ProtonUp-Qt (for downloading Wine-GE runners for Lutris) ---
    echo ""
    echo "Installing ProtonUp-Qt..."
    apt-get install -y libfuse2t64  # needed for AppImage
    PROTONUPQT="$REAL_HOME/.local/bin/protonup-qt"
    if [[ ! -x "$PROTONUPQT" ]]; then
        mkdir -p "$REAL_HOME/.local/bin"
        PUPQT_URL=$(curl -sL https://api.github.com/repos/DavidoTek/ProtonUp-Qt/releases/latest \
            | python3 -c "import sys,json; r=json.load(sys.stdin); [print(a['browser_download_url']) for a in r['assets'] if a['name'].endswith('.AppImage')]" \
            | head -1)
        if [[ -n "$PUPQT_URL" ]]; then
            curl -sL -o "$PROTONUPQT" "$PUPQT_URL"
            chmod +x "$PROTONUPQT"
            chown "$REAL_USER:$REAL_USER" "$PROTONUPQT"
            echo "  Installed ProtonUp-Qt to $PROTONUPQT"
        else
            echo "  WARNING: Could not download ProtonUp-Qt (check internet connection)"
        fi
    else
        echo "  ProtonUp-Qt already installed."
    fi

    # --- Install bundled .deb packages from sglBinaries_1 (if present) ---
    echo ""
    echo "Checking for bundled .deb packages..."
    for deb in "$REPO_ROOT"/libssl*.deb "$REPO_ROOT"/libzip*.deb; do
        if [[ -f "$deb" ]]; then
            echo "Installing $(basename "$deb") ..."
            dpkg -i "$deb" || true
        fi
    done
fi

# --- Clone git dependencies (as the invoking user, not root) ---
echo ""
echo "Cloning git dependencies..."

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

if [[ ! -d "$REPO_ROOT/FRI/benBridge/ben" ]]; then
    echo "  Cloning ben (Bridge Engine)..."
    sudo -u "$REAL_USER" git clone https://github.com/lorserker/ben "$REPO_ROOT/FRI/benBridge/ben"
else
    echo "  ben already present, skipping clone."
fi

if [[ ! -d "$REPO_ROOT/SUN/gui/lizgoban" ]]; then
    echo "  Cloning lizgoban (Go GUI)..."
    sudo -u "$REAL_USER" git clone https://github.com/kaorahi/lizgoban "$REPO_ROOT/SUN/gui/lizgoban"
else
    echo "  lizgoban already present, skipping clone."
fi

# --- Create Python virtual environments for PyQt apps ---
echo ""
echo "Creating Python virtual environments..."

create_venv() {
    local dir="$1"
    shift
    if [[ -x "$dir/venv/bin/pip" ]]; then
        echo "  Venv exists in $dir, ensuring packages..."
    else
        echo "  Creating venv in $dir ..."
        sudo -u "$REAL_USER" python3 -m venv "$dir/venv"
    fi
    if sudo -u "$REAL_USER" "$dir/venv/bin/pip" install --quiet "$@"; then
        echo "    Installed: $*"
    else
        echo "    ERROR: pip install failed in $dir"
        ERRORS=$((ERRORS + 1))
    fi
}

# FRI/mathQuiz - adaptive math quiz (PyQt6 + sympy + numpy + matplotlib)
create_venv "$REPO_ROOT/FRI/mathQuiz" -r "$REPO_ROOT/FRI/mathQuiz/requirements.txt"

# FRI/dual_nback - dual n-back trainer (PyQt6 + pyttsx3)
create_venv "$REPO_ROOT/FRI/dual_nback" -r "$REPO_ROOT/FRI/dual_nback/requirements.txt"

# FRI/benBridge - bridge game (PyQt6 + tensorflow + BEN engine)
# Patch ben's pyproject.toml for Linux (upstream targets Windows)
BEN_PYPROJECT="$REPO_ROOT/FRI/benBridge/ben/pyproject.toml"
if [[ -f "$BEN_PYPROJECT" ]]; then
    sed -i \
        -e 's/tensorflow-intel==2.18.0/tensorflow==2.18/' \
        -e 's/numpy==1.26.4/numpy>=1.26.4/' \
        -e 's/keras==3.6.0/keras>=3.6.0/' \
        -e 's/requires-python = "==3.12"/requires-python = ">=3.12"/' \
        "$BEN_PYPROJECT"
fi
create_venv "$REPO_ROOT/FRI/benBridge" PyQt6 colorama
if sudo -u "$REAL_USER" "$REPO_ROOT/FRI/benBridge/venv/bin/pip" install --quiet \
    -e "$REPO_ROOT/FRI/benBridge/ben"; then
    echo "    Installed: PyQt6 colorama ben (editable)"
else
    echo "    ERROR: ben editable install failed"
    ERRORS=$((ERRORS + 1))
fi

# benBridge: create libboost_thread compatibility symlink for libdds.so
# The bundled libdds.so links against libboost_thread.so.1.74.0 but the
# system may have a newer version (e.g. 1.83.0). Create a symlink so
# libdds.so can find it at runtime via LD_LIBRARY_PATH set in run.sh.
BEN_BIN_DIR="$REPO_ROOT/FRI/benBridge/ben/bin"
if [[ -f "$BEN_BIN_DIR/libdds.so" ]] && [[ ! -e "$BEN_BIN_DIR/libboost_thread.so.1.74.0" ]]; then
    SYSTEM_BOOST=$(ldconfig -p | grep 'libboost_thread\.so\.[0-9]' | head -1 | awk '{print $NF}')
    if [[ -n "$SYSTEM_BOOST" ]]; then
        sudo -u "$REAL_USER" ln -sf "$SYSTEM_BOOST" "$BEN_BIN_DIR/libboost_thread.so.1.74.0"
        echo "  Created libboost_thread symlink: $(basename "$SYSTEM_BOOST") -> 1.74.0"
    else
        echo "  WARNING: libboost_thread not found; benBridge DDS solver may not work"
    fi
fi

# WED/openingRepertoire - chess opening trainer (PyQt6 + python-chess)
create_venv "$REPO_ROOT/WED/openingRepertoire" -r "$REPO_ROOT/WED/openingRepertoire/requirements.txt"

# MON/pokerIQ - poker trainer (PyQt6 + eval7)
create_venv "$REPO_ROOT/MON/pokerIQ" -r "$REPO_ROOT/MON/pokerIQ/requirements.txt"

# FRI/guiHarness - Q-plus bridge hand entry automation (pyautogui)
create_venv "$REPO_ROOT/FRI/guiHarness" pyautogui

echo "  All virtual environments processed."

# --- Create deps marker ---
touch "$REPO_ROOT/.deps_installed"

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "=============================================="
    echo "  All dependencies installed successfully!"
    echo ""
    echo "  Next steps:"
    echo "    1. Place sglBinaries_*.tar.gz in downloads/"
    echo "    2. Run: ./launcher/install_binaries.sh"
    echo "    3. Run: ./launcher/main_launcher.sh"
    echo ""
    echo "  ProtonUp-Qt (optional - for additional Wine runners):"
    echo "    If a Wine game doesn't work with the installed runners,"
    echo "    you can download additional ones with ProtonUp-Qt:"
    echo "      1. Run: protonup-qt"
    echo "      2. Set 'Install for' to Lutris"
    echo "      3. Click 'Add version'"
    echo "      4. Select 'Wine-GE' (NOT GE-Proton) and pick a version"
    echo "      5. Update config/wine_runners.csv with the new runner name"
    echo "    Note: Use Wine-GE, not GE-Proton. Proton runners are"
    echo "    incompatible with 32-bit Wine prefixes."
    echo "=============================================="
else
    echo "=============================================="
    echo "  Installation completed with $ERRORS error(s)."
    echo "  Review the output above, fix issues, and re-run."
    echo "=============================================="
    exit 1
fi

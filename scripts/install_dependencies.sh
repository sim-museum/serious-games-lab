#!/usr/bin/env bash
# install_dependencies.sh - Master apt installer for Serious Games Lab
# Installs all system dependencies needed for source and binary games
# on a clean Ubuntu 26.04 LTS installation.
# (For Ubuntu 24.04, use the 24.04 branch.)
#
# Merged from:
#   - ese/runThisScriptFirst.sh (game-specific packages)
#   - serious-games-lab original install_dependencies.sh (graphics/audio/font libs)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ERRORS=0
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "=============================================="
echo "  Serious Games Lab - Dependency Installer"
echo "  Ubuntu 26.04 LTS  (idempotent - safe to re-run)"
echo "=============================================="
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run with sudo."
    echo "Usage: sudo $0"
    exit 1
fi

# --- Check for CD-ROM apt source bug (Ubuntu install-media artifact) ---
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
        # compgen -G only honors a single pattern; check the literal and
        # the glob separately.
        [[ -d "$REPO_ROOT/$day/WP" ]] && return 0
        compgen -G "$REPO_ROOT/$day/*/WP" >/dev/null 2>&1 && return 0
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
    NVIDIA_VER=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1 || true)
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
# Ubuntu 26.04 ships Python 3.14; python3-venv depends on python3.14-venv.
echo ""
echo "Installing Python dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pyqt6 \
    python3-pandas \
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
    libqt5widgets5t64 \
    libqt5multimedia5 \
    libqt5sql5t64 \
    qtbase5-dev qt5-qmake qtmultimedia5-dev libqt5svg5-dev \
    xclip \
    libopenblas-dev \
    libeigen3-dev \
    libboost-all-dev \
    protobuf-compiler libprotobuf-dev \
    zlib1g-dev \
    qml-module-qtquick-shapes \
    qml-module-org-kde-kcoreaddons

# --- Simulation and utility packages ---
# Note: 26.04 dropped p7zip-full (use the 7zip package above) and
# wkhtmltopdf (scores.sh guards its use with command -v).
echo ""
echo "Installing simulation and utility packages..."
apt-get install -y \
    dosbox \
    libfuse2t64 \
    bchunk unrar 7zip innoextract \
    vim okular filelight freeplane \
    cabextract unzip xdg-utils \
    xdotool xautomation \
    plantuml pandoc

if $INSTALL_WINE; then
    # --- Lutris (for Wine game management) ---
    # 26.04 universe ships a current Lutris (0.5.22+); the older deb-get
    # fallback is gone because deb-get itself doesn't recognize Resolute.
    echo ""
    echo "Installing Lutris..."
    apt-get install -y curl lutris

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

if [[ ! -d "$REPO_ROOT/FRI/benBridge/ben/src" ]]; then
    echo "  Cloning ben (Bridge Engine)..."
    sudo -u "$REAL_USER" git clone https://github.com/lorserker/ben "$REPO_ROOT/FRI/benBridge/ben"
else
    echo "  ben already present, skipping clone."
fi

# ben: download config files if missing (not stored in repo, or lost during clone)
BEN_CONFIG_DIR="$REPO_ROOT/FRI/benBridge/ben/src/config"
BEN_GITHUB_RAW="https://raw.githubusercontent.com/lorserker/ben/main"
if [[ ! -f "$BEN_CONFIG_DIR/default.conf" ]]; then
    echo "  Downloading ben config files..."
    for _conf in default.conf BEN-21GF.conf BEN-Sayc.conf GIB-BBO.conf; do
        sudo -u "$REAL_USER" curl -fSL -o "$BEN_CONFIG_DIR/$_conf" \
            "$BEN_GITHUB_RAW/src/config/$_conf" 2>/dev/null \
            && echo "    Downloaded: $_conf" \
            || echo "    WARNING: failed to download $_conf"
    done
fi

# ben: download TF2 neural-network model files if missing (Git LFS objects)
BEN_MODELS_DIR="$REPO_ROOT/FRI/benBridge/ben/models/TF2models"
mkdir -p "$BEN_MODELS_DIR"
_model_count=$(find "$BEN_MODELS_DIR" -name "*.keras" -size +1k 2>/dev/null | wc -l)
if [[ "$_model_count" -lt 16 ]]; then
    echo "  Downloading ben TF2 model files (≈107 MB total)..."
    # Models referenced by default.conf
    _ben_models=(
        Contract_2024-12-09-E50.keras  Tricks_2024-12-09-E50.keras
        GIB-BBO-8730_2025-04-19-E30.keras  GIB-BBOInfo-8730_2025-04-19-E30.keras
        Lead-NT_2024-11-04-E200.keras  Lead-Suit_2024-11-04-E200.keras
        SD_2024-07-08-E20.keras  RPDD_2024-07-08-E02.keras
        lefty_nt_2024-07-08-E20.keras  lefty_suit_2024-07-08-E20.keras
        righty_nt_2024-07-16-E20.keras  righty_suit_2024-07-16-E20.keras
        dummy_nt_2024-07-08-E20.keras  dummy_suit_2024-07-08-E20.keras
        decl_nt_2024-07-08-E20.keras  decl_suit_2024-07-08-E20.keras
    )
    for _m in "${_ben_models[@]}"; do
        if [[ ! -f "$BEN_MODELS_DIR/$_m" ]] || [[ $(stat -c%s "$BEN_MODELS_DIR/$_m" 2>/dev/null) -lt 1024 ]]; then
            sudo -u "$REAL_USER" curl -fSL -o "$BEN_MODELS_DIR/$_m" \
                "https://github.com/lorserker/ben/raw/main/models/TF2models/$_m" 2>/dev/null \
                && echo "    Downloaded: $_m" \
                || echo "    WARNING: failed to download $_m"
        fi
    done
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
# ben's src/ is added to PYTHONPATH in run.sh (no editable install needed).
# TensorFlow's wheels lag behind the latest CPython release — TF 2.18.x
# tops out at Python 3.13. On systems whose default python3 is newer
# (Ubuntu 26.04 ships 3.14, with no other interpreters in the archive),
# we provision a 3.12 interpreter via uv just for this venv. uv installs
# a self-contained CPython into ~/.local/share/uv/python — no system mods.
BENBRIDGE_DIR="$REPO_ROOT/FRI/benBridge"
BENBRIDGE_VENV="$BENBRIDGE_DIR/venv"
BEN_REQUIREMENTS="$BENBRIDGE_DIR/ben/requirements.txt"
TF_MAX_PY="3.13"
SYS_PY=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
SYS_PY_TOO_NEW=false
if [[ "$(printf '%s\n%s\n' "$SYS_PY" "$TF_MAX_PY" | sort -V | tail -1)" == "$SYS_PY" \
      && "$SYS_PY" != "$TF_MAX_PY" ]]; then
    SYS_PY_TOO_NEW=true
fi

if $SYS_PY_TOO_NEW; then
    BEN_PY="3.12"
    UV_BIN="$REAL_HOME/.local/bin/uv"
    if [[ ! -x "$UV_BIN" ]]; then
        echo "  Installing uv (standalone Python manager) for benBridge..."
        sudo -u "$REAL_USER" bash -c \
            'curl -LsSf https://astral.sh/uv/install.sh | sh' >/dev/null 2>&1 \
            || { echo "    ERROR: uv install failed"; ERRORS=$((ERRORS + 1)); }
    fi

    if [[ -x "$UV_BIN" ]]; then
        echo "  Provisioning Python ${BEN_PY} for benBridge via uv (idempotent)..."
        sudo -u "$REAL_USER" "$UV_BIN" python install "$BEN_PY" 2>&1 | tail -1

        # Recreate the venv if it's currently on the wrong interpreter.
        if [[ -x "$BENBRIDGE_VENV/bin/python" ]]; then
            CUR_PY=$(sudo -u "$REAL_USER" "$BENBRIDGE_VENV/bin/python" -c \
                'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' \
                2>/dev/null || echo missing)
            if [[ "$CUR_PY" != "$BEN_PY" ]]; then
                echo "  Recreating benBridge venv on Python ${BEN_PY} (was ${CUR_PY})..."
                rm -rf "$BENBRIDGE_VENV"
            fi
        fi

        if [[ ! -x "$BENBRIDGE_VENV/bin/python" ]]; then
            sudo -u "$REAL_USER" "$UV_BIN" venv --seed --python "$BEN_PY" "$BENBRIDGE_VENV"
        fi

        if sudo -u "$REAL_USER" "$BENBRIDGE_VENV/bin/pip" install --quiet PyQt6 colorama; then
            echo "    Installed: PyQt6 colorama"
        else
            echo "    ERROR: PyQt6/colorama install failed for benBridge"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    create_venv "$BENBRIDGE_DIR" PyQt6 colorama
fi

if [[ -f "$BEN_REQUIREMENTS" ]]; then
    if sudo -u "$REAL_USER" "$BENBRIDGE_VENV/bin/pip" install --quiet \
        -r "$BEN_REQUIREMENTS"; then
        echo "    Installed: ben runtime dependencies"
    else
        echo "    WARNING: some ben dependencies failed"
    fi
fi

# benBridge: ensure libdds.so is available for the DDS solver.
# The upstream ben repo ships a Windows/Mac binary but not a Linux one.
# On Ubuntu the system package libdds0 provides libdds.so.0; we symlink
# it into ben/bin/ so the engine's ctypes loader finds it.
BEN_BIN_DIR="$REPO_ROOT/FRI/benBridge/ben/bin"
mkdir -p "$BEN_BIN_DIR"
if [[ ! -f "$BEN_BIN_DIR/libdds.so" ]]; then
    SYSTEM_DDS=$(ldconfig -p | grep 'libdds\.so' | head -1 | awk '{print $NF}' || true)
    if [[ -n "$SYSTEM_DDS" ]]; then
        sudo -u "$REAL_USER" ln -sf "$SYSTEM_DDS" "$BEN_BIN_DIR/libdds.so"
        echo "  Created libdds.so symlink -> $SYSTEM_DDS"
    else
        echo "  WARNING: libdds not found; install libdds0: apt install libdds0"
    fi
fi

# WED/openingRepertoire - chess opening trainer (PyQt6 + python-chess)
create_venv "$REPO_ROOT/WED/openingRepertoire" -r "$REPO_ROOT/WED/openingRepertoire/requirements.txt"

# MON/pokerIQ - poker trainer (PyQt6 + eval7)
# eval7 has no Python 3.14 wheel and its setup.py imports Cython at
# build time without declaring it as a PEP 517 build-system requires.
# Pre-install Cython+wheel into the venv and build with
# --no-build-isolation so eval7 can see them.
create_venv "$REPO_ROOT/MON/pokerIQ" Cython wheel setuptools
if sudo -u "$REAL_USER" "$REPO_ROOT/MON/pokerIQ/venv/bin/pip" install --quiet \
    --no-build-isolation -r "$REPO_ROOT/MON/pokerIQ/requirements.txt"; then
    echo "    Installed: pokerIQ requirements (eval7 built from source)"
else
    echo "    ERROR: pokerIQ requirements install failed"
    ERRORS=$((ERRORS + 1))
fi

# FRI/guiHarness - Q-plus bridge hand entry and comparison harness (PyQt5 + pyautogui)
create_venv "$REPO_ROOT/FRI/guiHarness" PyQt5 pyautogui

echo "  All virtual environments processed."

# --- Create deps marker ---
touch "$REPO_ROOT/.deps_installed"

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "=============================================="
    echo "  All dependencies installed successfully!"
    echo ""
    echo "  Next steps:"
    echo "    1. Place sglBinaries_*.tar.gz in sgl/downloads/"
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

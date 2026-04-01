#!/usr/bin/env bash
# install.sh - Complete Serious Games Lab installer
#
# Performs a full installation:
#   1. Distributes binaries from downloads/sglBinaries_* to game INSTALL/ directories
#   2. Installs all system dependencies (apt packages, venvs, git clones)
#   3. Installs FlightGear (AppImage)
#   4. Downloads Lutris wine runners for binary games
#   5. Applies Wine fixes for Rowan games (MiG Alley, Battle of Britain)
#
# Usage:
#   sudo ./install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
DOWNLOADS_DIR="$REPO_ROOT/downloads"

# --- Must run as root (for apt-get) ---
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run with sudo."
    echo "Usage: sudo $0"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo ""
echo "=============================================="
echo "  Serious Games Lab - Complete Installer"
echo "=============================================="
echo ""

# ==========================================================
# System Audit
# ==========================================================
echo "=============================================="
echo "  System Audit"
echo "=============================================="
echo ""

AUDIT_WARNINGS=0

# --- OS version ---
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "24.04" ]]; then
        echo "  [OK]   OS: Ubuntu ${VERSION_ID} (${PRETTY_NAME})"
    else
        echo "  [WARN] OS: ${PRETTY_NAME:-$ID $VERSION_ID} — Ubuntu 24.04 expected"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [WARN] OS: could not detect — Ubuntu 24.04 expected"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

# --- Disk space ---
AVAIL_KB=$(df --output=avail "$REPO_ROOT" | tail -1)
AVAIL_GB=$(( AVAIL_KB / 1048576 ))
RECOMMENDED_GB=500
if [[ $AVAIL_GB -lt $RECOMMENDED_GB ]]; then
    echo "  [WARN] Disk space: ${AVAIL_GB} GB available (${RECOMMENDED_GB} GB recommended)"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
else
    echo "  [OK]   Disk space: ${AVAIL_GB} GB available (${RECOMMENDED_GB} GB recommended)"
fi

# --- Graphics driver ---
if lsmod | grep -q nouveau; then
    echo "  [WARN] Graphics: nouveau driver — proprietary NVIDIA recommended (not essential)"
    echo "         Fix: sudo ubuntu-drivers autoinstall && sudo reboot"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
elif NVIDIA_VER=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1) && [[ -n "$NVIDIA_VER" ]]; then
    if [[ $NVIDIA_VER -eq 535 ]]; then
        echo "  [OK]   Graphics: NVIDIA driver $NVIDIA_VER (DXVK compatible)"
    elif [[ $NVIDIA_VER -ge 525 && $NVIDIA_VER -le 575 ]]; then
        echo "  [WARN] Graphics: NVIDIA driver $NVIDIA_VER — driver 535 is recommended"
        echo "         Purge the existing driver before installing 535:"
        echo "         Fix: sudo apt-get purge -y 'nvidia-*-${NVIDIA_VER}*' && sudo apt-get install -y nvidia-driver-535 && sudo reboot"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    else
        echo "  [WARN] Graphics: NVIDIA driver $NVIDIA_VER — not DXVK compatible"
        echo "         Purge the existing driver before installing 535:"
        echo "         Fix: sudo apt-get purge -y 'nvidia-*-${NVIDIA_VER}*' && sudo apt-get install -y nvidia-driver-535 && sudo reboot"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [OK]   Graphics: non-NVIDIA GPU (no action needed)"
fi

# --- 32-bit (i386) NVIDIA GL support ---
# Binary games run under Wine and require 32-bit NVIDIA GL libraries.
# Some NVIDIA driver versions (e.g. 570) do not install i386 libs automatically.
# Running install.sh without 32-bit support breaks binary game installs irreparably.
if dpkg -l 2>/dev/null | grep -q 'nvidia-driver-'; then
    if dpkg --print-foreign-architectures 2>/dev/null | grep -q i386; then
        # i386 arch is enabled — check for the 32-bit GL library
        NVIDIA_VER_32=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1)
        if dpkg -l "libnvidia-gl-${NVIDIA_VER_32}:i386" 2>/dev/null | grep -q '^ii'; then
            echo "  [OK]   32-bit NVIDIA GL: libnvidia-gl-${NVIDIA_VER_32}:i386 installed"
        else
            echo "  [ERROR] 32-bit NVIDIA GL libraries missing!"
            echo "          libnvidia-gl-${NVIDIA_VER_32}:i386 is not installed."
            echo "          Binary games (Wine/DXVK) require 32-bit GL support."
            echo "          Fix: sudo dpkg --add-architecture i386 && sudo apt update && sudo apt install libnvidia-gl-${NVIDIA_VER_32}:i386"
            echo "          Running install.sh without this will break binary game installs."
            exit 1
        fi
    else
        echo "  [ERROR] i386 architecture not enabled — 32-bit support unavailable!"
        echo "          Binary games (Wine/DXVK) require 32-bit GL support."
        echo "          Fix: sudo dpkg --add-architecture i386 && sudo apt update && sudo apt install libnvidia-gl-$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1):i386"
        echo "          Running install.sh without this will break binary game installs."
        exit 1
    fi
fi

# --- Joystick ---
shopt -s nullglob
JS_DEVICES=(/dev/input/js*)
shopt -u nullglob
if [[ ${#JS_DEVICES[@]} -gt 0 ]]; then
    JS_NUM="${JS_DEVICES[0]##*/}"
    JS_NAME="unknown"
    if [[ -f "/sys/class/input/${JS_NUM}/device/name" ]]; then
        JS_NAME=$(cat "/sys/class/input/${JS_NUM}/device/name")
    fi
    echo "  [OK]   Joystick: $JS_NAME"
else
    echo "  [WARN] Joystick: none detected — recommended for flight sims"
    echo "         Logitech Extreme 3D Pro is ideal"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

# --- Display resolution (primary monitor, not combined span) ---
CURRENT_RES=""
if command -v xrandr &>/dev/null; then
    # Pick the highest-resolution connected monitor
    CURRENT_RES=$(sudo -u "$REAL_USER" xrandr 2>/dev/null \
        | grep -oP '\d+x\d+(?=\+)' \
        | sort -t'x' -k1 -rn | head -1)
fi
if [[ -z "$CURRENT_RES" ]]; then
    CURRENT_RES=$(sudo -u "$REAL_USER" xdpyinfo 2>/dev/null | grep -oP 'dimensions:\s+\K[0-9]+x[0-9]+' | head -1)
fi
if [[ -n "$CURRENT_RES" ]]; then
    RES_W="${CURRENT_RES%x*}"
    RES_H="${CURRENT_RES#*x}"
    if (( RES_W >= 1920 && RES_H >= 1080 )); then
        echo "  [OK]   Display: ${CURRENT_RES}"
    else
        echo "  [WARN] Display: ${CURRENT_RES} — 1920x1080 or greater recommended"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [WARN] Display: could not detect resolution — 1920x1080 or greater recommended"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

# --- GPU memory ---
VRAM_MB=""
if command -v nvidia-smi &>/dev/null; then
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
fi
if [[ -z "$VRAM_MB" ]] && [[ -d /sys/class/drm ]]; then
    for card in /sys/class/drm/card[0-9]*/device; do
        mem_file="$card/mem_info_vram_total"
        if [[ -f "$mem_file" ]]; then
            VRAM_BYTES=$(cat "$mem_file" 2>/dev/null)
            if [[ -n "$VRAM_BYTES" && "$VRAM_BYTES" -gt 0 ]] 2>/dev/null; then
                VRAM_MB=$(( VRAM_BYTES / 1048576 ))
                break
            fi
        fi
    done
fi
if [[ -z "$VRAM_MB" ]] && command -v glxinfo &>/dev/null; then
    VRAM_LINE=$(sudo -u "$REAL_USER" glxinfo 2>/dev/null | grep -iP '(video memory|dedicated video|vram)' | grep -oP '[0-9]+' | head -1)
    if [[ -n "$VRAM_LINE" && "$VRAM_LINE" -gt 0 ]] 2>/dev/null; then
        VRAM_MB="$VRAM_LINE"
    fi
fi
if [[ -n "$VRAM_MB" ]]; then
    if (( VRAM_MB >= 1024 )); then
        echo "  [OK]   GPU memory: ${VRAM_MB} MB"
    else
        echo "  [WARN] GPU memory: ${VRAM_MB} MB — 1 GB or greater recommended"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [WARN] GPU memory: could not detect — 1 GB or greater recommended"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

# --- sglBinaries_1.tar.gz ---
shopt -s nullglob
WP_DIRS=("$REPO_ROOT"/*/WP/ "$REPO_ROOT"/*/*/WP/)
shopt -u nullglob
shopt -s nullglob
SGL_BIN_DIRS=("$DOWNLOADS_DIR"/sglBinaries_*/)
shopt -u nullglob
if [[ -f "$DOWNLOADS_DIR/sglBinaries_1.tar.gz" ]]; then
    echo "  [OK]   sglBinaries_1.tar.gz found in downloads/"
elif [[ -f "$DOWNLOADS_DIR/.extracted_sglBinaries_1.tar.gz" ]]; then
    echo "  [OK]   sglBinaries_1.tar.gz (already extracted)"
elif [[ ${#SGL_BIN_DIRS[@]} -gt 0 ]]; then
    echo "  [OK]   sglBinaries data found in downloads/ (${#SGL_BIN_DIRS[@]} dir(s))"
elif [[ ${#WP_DIRS[@]} -gt 0 ]]; then
    echo "  [OK]   Binary game data already distributed"
else
    echo "  [WARN] sglBinaries_1.tar.gz not found in downloads/"
    echo "         Recommended — contains core binary games for all days."
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

echo ""

if [[ $AUDIT_WARNINGS -gt 0 ]]; then
    read -rp "Warnings found. Continue? (y/N) " answer
    if [[ ! "$answer" =~ ^[Yy]$ ]]; then
        echo "Aborting."
        exit 1
    fi
    echo ""
fi

# ============================================================
# PHASE 1: Distribute sglBinaries_* from downloads/ to game INSTALL/ dirs
# ============================================================
echo "PHASE 1: Distributing binary game archives..."
echo ""

mkdir -p "$DOWNLOADS_DIR"
chown "$REAL_USER:$REAL_USER" "$DOWNLOADS_DIR"

# Extract sglBinaries_*.tar.gz archives before distributing
for f in "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"
    marker="$DOWNLOADS_DIR/.extracted_${base}"
    if [[ -f "$marker" ]]; then
        echo "  Already extracted: $base"
    else
        echo "  Extracting $base ..."
        sudo -u "$REAL_USER" tar xzf "$f" -C "$DOWNLOADS_DIR/"
        sudo -u "$REAL_USER" touch "$marker"
        echo "  [OK] Extracted: $base"
    fi
done

# Distribute binary files from downloads/sglBinaries_* to game INSTALL directories
echo "  Distributing binary files to game INSTALL directories..."
sudo -u "$REAL_USER" "$REPO_ROOT/scripts/distribute_binaries.sh"

echo ""

# ============================================================
# PHASE 2: Install system dependencies
# ============================================================
echo "PHASE 2: Installing system dependencies..."
echo ""

"$REPO_ROOT/scripts/install_dependencies.sh" --yes

echo ""

# ============================================================
# PHASE 3: Install FlightGear (as real user, not root)
# ============================================================
echo "PHASE 3: Installing FlightGear..."
echo ""

FG_VERSION="2024.1.4"
FG_DIR="$REAL_HOME/.local/share/flightgear"
FG_BIN="$FG_DIR/bin"
APPIMAGE_NAME="fgfs-${FG_VERSION}.AppImage"
APPIMAGE_PATH="$FG_DIR/$APPIMAGE_NAME"
DOWNLOAD_URL="https://download.flightgear.org/release-2024.1/flightgear-${FG_VERSION}-linux-amd64.AppImage"

if [[ -f "$APPIMAGE_PATH" ]]; then
    echo "  FlightGear $FG_VERSION already installed."
else
    sudo -u "$REAL_USER" mkdir -p "$FG_DIR" "$FG_BIN"
    echo "  Downloading FlightGear $FG_VERSION AppImage..."
    if sudo -u "$REAL_USER" curl -fSL --progress-bar -o "$APPIMAGE_PATH" "$DOWNLOAD_URL"; then
        chmod +x "$APPIMAGE_PATH"
        cat > "$FG_BIN/fgfs" << EOF
#!/bin/bash
exec "$APPIMAGE_PATH" "\$@"
EOF
        chmod +x "$FG_BIN/fgfs"
        chown "$REAL_USER:$REAL_USER" "$FG_BIN/fgfs"
        echo "  FlightGear $FG_VERSION installed."
    else
        echo "  WARNING: FlightGear download failed. Install manually later:"
        echo "    ./scripts/setup_flightgear.sh"
        rm -f "$APPIMAGE_PATH"
    fi
fi

echo ""

# ============================================================
# Check if any binary games were distributed (INSTALL directories exist)
# ============================================================
shopt -s nullglob
_INSTALL_DIRS=("$REPO_ROOT"/*/INSTALL/ "$REPO_ROOT"/*/*/INSTALL/)
shopt -u nullglob
HAS_BINARY_GAMES=${#_INSTALL_DIRS[@]}

# ============================================================
# PHASE 4: Download Lutris wine runners (as real user)
# ============================================================
echo "PHASE 4: Setting up Lutris wine runners..."
echo ""

if [[ $HAS_BINARY_GAMES -eq 0 ]]; then
    echo "  No binary games distributed yet; skipping wine runner setup."
    echo "  Wine runners will be downloaded on first game launch."
else
    CSV_FILE="$REPO_ROOT/config/wine_runners.csv"
    RUNNERS_DIR="$REAL_HOME/.local/share/lutris/runners/wine"

    if [[ -f "$CSV_FILE" ]]; then
        sudo -u "$REAL_USER" mkdir -p "$RUNNERS_DIR"

        # Extract unique runners from CSV (skip header, column 2)
        mapfile -t RUNNERS < <(tail -n +2 "$CSV_FILE" | cut -d',' -f2 | sort -u)

        for runner in "${RUNNERS[@]}"; do
            if [[ -d "$RUNNERS_DIR/$runner" ]]; then
                echo "  [OK] $runner"
                continue
            fi

            # Build download URL
            asset="wine-${runner}.tar.xz"
            base_runner="$runner"
            base_runner="${base_runner%-x86_64}"
            base_runner="${base_runner%-i686}"

            if [[ "$runner" == *GE-Proton* ]]; then
                tag="${base_runner#lutris-}"
                url="https://github.com/GloriousEggroll/wine-ge-custom/releases/download/${tag}/${asset}"
            elif [[ "$runner" == *fshack* ]]; then
                tag="${base_runner//-fshack/}"
                url="https://github.com/lutris/wine/releases/download/${tag}/${asset}"
            else
                tag="$base_runner"
                url="https://github.com/lutris/wine/releases/download/${tag}/${asset}"
            fi

            echo "  [DOWNLOAD] $runner ..."
            tmpfile="$(sudo -u "$REAL_USER" mktemp /tmp/runner-XXXXXX.tar.xz)"
            if sudo -u "$REAL_USER" curl -fSL --progress-bar -o "$tmpfile" "$url"; then
                sudo -u "$REAL_USER" tar -xJf "$tmpfile" -C "$RUNNERS_DIR/"
                rm -f "$tmpfile"
                if [[ -d "$RUNNERS_DIR/$runner" ]]; then
                    echo "  [OK] $runner installed"
                else
                    echo "  [WARN] $runner: extracted but directory name mismatch"
                fi
            else
                echo "  [WARN] Failed to download $runner"
                rm -f "$tmpfile"
            fi
        done
    else
        echo "  No wine_runners.csv found; skipping."
    fi
fi

echo ""

# ============================================================
# PHASE 5: Apply Rowan game Wine fixes (if games are present)
# ============================================================
echo "PHASE 5: Applying Wine fixes for Rowan games..."
echo ""

if [[ -d "$REPO_ROOT/TUE/MigAlley/WP" ]] && [[ -d "$REPO_ROOT/TUE/BattleOfBritain/WP" ]]; then
    sudo -u "$REAL_USER" "$REPO_ROOT/scripts/fix_rowan_games.sh" all || true
else
    echo "  Rowan game Wine prefixes not yet created; skipping."
    echo "  Fixes will be applied on first launch."
fi

echo ""

echo ""
echo "=============================================="
echo "  Installation complete!"
echo ""
echo "  To launch the game menu:"
echo "    ./launcher/main_launcher.sh"
echo ""
echo "  To add more binary game archives:"
echo "    Place sglBinaries_* dirs in sgl/downloads/ and re-run sudo ./install.sh"
echo "=============================================="

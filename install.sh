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
    if [[ $NVIDIA_VER -ge 525 && $NVIDIA_VER -le 575 ]]; then
        echo "  [OK]   Graphics: NVIDIA driver $NVIDIA_VER (DXVK compatible)"
    else
        echo "  [WARN] Graphics: NVIDIA driver $NVIDIA_VER — not DXVK compatible"
        echo "         Fix: sudo apt install nvidia-driver-535 && sudo reboot"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [OK]   Graphics: non-NVIDIA GPU (no action needed)"
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

# --- sglBinaries_1.tar.gz ---
shopt -s nullglob
WP_DIRS=("$REPO_ROOT"/*/WP/ "$REPO_ROOT"/*/*/WP/)
shopt -u nullglob
if [[ -f "$DOWNLOADS_DIR/sglBinaries_1.tar.gz" ]]; then
    echo "  [OK]   sglBinaries_1.tar.gz found in downloads/"
elif [[ -f "$DOWNLOADS_DIR/.extracted_sglBinaries_1.tar.gz" ]]; then
    echo "  [OK]   sglBinaries_1.tar.gz (already extracted)"
elif [[ ${#WP_DIRS[@]} -gt 0 ]]; then
    echo "  [OK]   Binary game data already distributed"
else
    echo "  [WARN] sglBinaries_1.tar.gz not found in downloads/"
    echo "         Recommended — contains core binary games for all days."
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

echo ""

if [[ $AUDIT_WARNINGS -gt 0 ]]; then
    read -rp "Warnings found. Continue? (Y/n) " answer
    if [[ "$answer" =~ ^[Nn]$ ]]; then
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
# Check if any binary games were distributed (WP directories exist)
# ============================================================
shopt -s nullglob
_WP_DIRS=("$REPO_ROOT"/*/WP/ "$REPO_ROOT"/*/*/WP/)
shopt -u nullglob
HAS_BINARY_GAMES=${#_WP_DIRS[@]}

# ============================================================
# PHASE 4: Download Lutris wine runners (as real user)
# ============================================================
echo "PHASE 4: Setting up Lutris wine runners..."
echo ""

if [[ $HAS_BINARY_GAMES -eq 0 ]]; then
    echo "  No binary games installed; skipping wine runner setup."
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
    echo "  Rowan games not yet installed; skipping."
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
echo "    Place sglBinaries_* dirs in downloads/ and re-run sudo ./install.sh"
echo "=============================================="

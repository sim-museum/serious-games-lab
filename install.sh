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
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "26.04" ]]; then
        echo "  [OK]   OS: Ubuntu ${VERSION_ID} (${PRETTY_NAME})"
    else
        echo "  [WARN] OS: ${PRETTY_NAME:-$ID $VERSION_ID} — Ubuntu 26.04 LTS required (use the 24.04 branch for Ubuntu 24.04)"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [WARN] OS: could not detect — Ubuntu 26.04 LTS required"
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

# --- Swap space ---
# Tight swap risks systemd-oomd killing long apt/pip steps in PHASE 2.
SWAP_MB=$(free -m | awk '/^Swap:/ {print $2+0}')
RECOMMENDED_SWAP_GB=8
SWAP_GB=$(( SWAP_MB / 1024 ))
if [[ $SWAP_MB -lt $((RECOMMENDED_SWAP_GB * 1024)) ]]; then
    echo "  [WARN] Swap: ${SWAP_GB} GB available (${RECOMMENDED_SWAP_GB} GB recommended)"
    if [[ -f /swap.img ]]; then
        echo "         Resize /swap.img: sudo swapoff /swap.img && sudo rm /swap.img && sudo fallocate -l ${RECOMMENDED_SWAP_GB}G /swap.img && sudo chmod 600 /swap.img && sudo mkswap /swap.img && sudo swapon /swap.img"
    else
        # No /swap.img — current swap is a too-small partition (or none). Add a swapfile alongside it.
        echo "         Add /swap.img: sudo fallocate -l ${RECOMMENDED_SWAP_GB}G /swap.img && sudo chmod 600 /swap.img && sudo mkswap /swap.img && sudo swapon /swap.img"
        echo "         Persist:       echo '/swap.img none swap sw 0 0' | sudo tee -a /etc/fstab"
    fi
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
else
    echo "  [OK]   Swap: ${SWAP_GB} GB available (${RECOMMENDED_SWAP_GB} GB recommended)"
fi

# --- Graphics driver ---
if lsmod | grep -q nouveau; then
    echo "  [WARN] Graphics: nouveau driver — proprietary NVIDIA recommended (not essential)"
    echo "         Fix: sudo ubuntu-drivers autoinstall && sudo reboot"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
elif NVIDIA_VER=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1) && [[ -n "$NVIDIA_VER" ]]; then
    if [[ $NVIDIA_VER -ge 470 ]]; then
        echo "  [OK]   Graphics: NVIDIA driver $NVIDIA_VER (DXVK compatible)"
    else
        echo "  [WARN] Graphics: NVIDIA driver $NVIDIA_VER — too old for DXVK (need >= 470)"
        echo "         Fix: sudo ubuntu-drivers autoinstall && sudo reboot"
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

# --- Vulkan ---
# DXVK (used by chessmaster.sh and any future D3D-heavy launcher) requires
# a hardware Vulkan ICD. llvmpipe (software-only) "works" but is unusably
# slow for 3D games; without any Vulkan at all, DXVK-installed prefixes
# fail at launch with a cryptic d3d9.dll load error. Surface this now so
# it's visible during install rather than at first DXVK-game launch.
if command -v vulkaninfo &>/dev/null; then
    # Count driverName lines that are NOT llvmpipe — at least one means a
    # hardware Vulkan ICD is registered. (Note: grep -qv on a piped input
    # returns 1 when it should return 0 due to SIGPIPE early-exit; -cv
    # which counts is reliable.)
    HW_VK_COUNT=$(vulkaninfo --summary 2>/dev/null | grep -E '^\s*driverName' | grep -cv llvmpipe)
    if [[ "$HW_VK_COUNT" -gt 0 ]]; then
        HW_DRIVERS=$(vulkaninfo --summary 2>/dev/null \
            | awk -F'=' '/^[[:space:]]*driverName/ {gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); if ($2 != "llvmpipe") print $2}' \
            | sort -u | paste -sd, -)
        echo "  [OK]   Vulkan: ${HW_DRIVERS:-hardware ICD detected}"
    else
        echo "  [WARN] Vulkan: only llvmpipe (software) — DXVK games will be unusably slow"
        echo "         For NVIDIA: ensure libnvidia-gl-\$VER and its :i386 variant are installed"
        echo "         For Mesa:   sudo apt install mesa-vulkan-drivers mesa-vulkan-drivers:i386"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
else
    echo "  [INFO] Vulkan: vulkaninfo not found — installing vulkan-tools + mesa drivers"
    # mesa-vulkan-drivers:i386 needs the i386 foreign arch enabled.
    if ! dpkg --print-foreign-architectures 2>/dev/null | grep -q '^i386$'; then
        echo "         Enabling i386 architecture..."
        dpkg --add-architecture i386
        apt-get update
    fi
    if apt-get install -y vulkan-tools mesa-vulkan-drivers mesa-vulkan-drivers:i386; then
        echo "  [OK]   Vulkan: installed vulkan-tools + mesa-vulkan-drivers (amd64 + i386)"
    else
        echo "  [WARN] Vulkan: auto-install failed — DXVK-installed games will fail at launch"
        echo "         Retry: sudo dpkg --add-architecture i386 && sudo apt update && sudo apt install vulkan-tools mesa-vulkan-drivers mesa-vulkan-drivers:i386"
        AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
    fi
fi

# --- System wine wow64 mode ---
# Ubuntu 26.04 ships wine 10, which runs in wow64 mode and silently rejects
# WINEARCH=win32 — every 32-bit binary game in this repo would fail if it
# resolved to /usr/bin/wine. Detect this so the user knows the installer
# only routes 32-bit work through Lutris runners.
SYS_WINE="$(command -v wine 2>/dev/null || true)"
if [[ -n "$SYS_WINE" ]]; then
    SYS_WINE_VER=$(sudo -u "$REAL_USER" "$SYS_WINE" --version 2>/dev/null | head -1 || true)
    SYS_WINE_MAJOR=$(echo "$SYS_WINE_VER" | grep -oP 'wine-\K[0-9]+' | head -1 || true)
    WINE_WOW64=0
    if sudo -u "$REAL_USER" env WINEARCH=win32 WINEPREFIX=/tmp/.sgl_wine_arch_probe.$$ \
            "$SYS_WINE" --version 2>&1 | grep -q 'not supported in wow64 mode'; then
        WINE_WOW64=1
    fi
    rm -rf "/tmp/.sgl_wine_arch_probe.$$"
    if [[ $WINE_WOW64 -eq 1 ]]; then
        echo "  [INFO] System wine: ${SYS_WINE_VER:-v$SYS_WINE_MAJOR} (wow64 mode — rejects WINEARCH=win32)"
        echo "         All 32-bit games will use Lutris runners; system wine will not be invoked for them."
    else
        echo "  [OK]   System wine: ${SYS_WINE_VER:-installed} (accepts WINEARCH=win32)"
    fi
else
    echo "  [OK]   System wine: not installed (Lutris runners handle all wine launches)"
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

# --- Claude Code CLI ---
# Check as the real user: under sudo, PATH is reset to secure_path and won't
# include per-user install dirs like ~/.local/bin or ~/.npm-global/bin.
CLAUDE_PATH=$(sudo -u "$REAL_USER" -i bash -c 'command -v claude' 2>/dev/null || true)
if [[ -n "$CLAUDE_PATH" ]]; then
    CLAUDE_VER=$(sudo -u "$REAL_USER" -i bash -c 'claude --version 2>/dev/null | head -1' || true)
    echo "  [OK]   Claude Code: ${CLAUDE_VER:-available} ($CLAUDE_PATH)"
else
    echo "  [WARN] Claude Code: not found — post-game AI annotations will be skipped"
    echo "         Install: https://docs.anthropic.com/en/docs/claude-code"
    AUDIT_WARNINGS=$((AUDIT_WARNINGS + 1))
fi

# --- sglBinaries archives ---
shopt -s nullglob
WP_DIRS=("$REPO_ROOT"/*/WP/ "$REPO_ROOT"/*/*/WP/)
SGL_BIN_DIRS=("$DOWNLOADS_DIR"/sglBinaries_*/)
SGL_BIN_ARCHIVES=("$DOWNLOADS_DIR"/sglBinaries_*.tar "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz)
SGL_BIN_MARKERS=("$DOWNLOADS_DIR"/.extracted_sglBinaries_*.tar "$DOWNLOADS_DIR"/.extracted_sglBinaries_*.tar.gz)
shopt -u nullglob
if [[ ${#SGL_BIN_ARCHIVES[@]} -gt 0 ]]; then
    echo "  [OK]   sglBinaries archives found in downloads/ (${#SGL_BIN_ARCHIVES[@]} file(s))"
elif [[ ${#SGL_BIN_MARKERS[@]} -gt 0 ]]; then
    echo "  [OK]   sglBinaries archives (already extracted)"
elif [[ ${#SGL_BIN_DIRS[@]} -gt 0 ]]; then
    echo "  [OK]   sglBinaries data found in downloads/ (${#SGL_BIN_DIRS[@]} dir(s))"
elif [[ ${#WP_DIRS[@]} -gt 0 ]]; then
    echo "  [OK]   Binary game data already distributed"
else
    echo "  [WARN] sglBinaries archives not found in downloads/"
    echo "         Recommended — contains core binary games for all days."
    echo "         Download from https://archive.org/details/sglBinaries_1"
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

# Extract sglBinaries_*.tar and sglBinaries_*.tar.gz archives before distributing.
# `tar xf` auto-detects compression, so the same command handles both.
shopt -s nullglob
for f in "$DOWNLOADS_DIR"/sglBinaries_*.tar "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz; do
    base="$(basename "$f")"
    marker="$DOWNLOADS_DIR/.extracted_${base}"
    if [[ -f "$marker" ]]; then
        echo "  Already extracted: $base"
    else
        echo "  Extracting $base ..."
        sudo -u "$REAL_USER" tar xf "$f" -C "$DOWNLOADS_DIR/"
        sudo -u "$REAL_USER" touch "$marker"
        echo "  [OK] Extracted: $base"
    fi
done
shopt -u nullglob

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

        # Extract unique runners from CSV (skip header, column 2).
        # Some rows have an empty runner (source-only games like freefalcon,
        # CFL, tacview) — drop those so we don't try to "install" "".
        mapfile -t RUNNERS < <(tail -n +2 "$CSV_FILE" | awk -F',' '$2 != "" {print $2}' | sort -u)

        for runner in "${RUNNERS[@]}"; do
            if [[ -d "$RUNNERS_DIR/$runner" ]]; then
                echo "  [OK] $runner"
                continue
            fi

            # Build download URLs (primary + fallback — tag naming varies
            # between lutris-X.Y and lutris-wine-X.Y across releases)
            asset="wine-${runner}.tar.xz"
            base_runner="$runner"
            base_runner="${base_runner%-x86_64}"
            base_runner="${base_runner%-i686}"
            urls=()

            if [[ "$runner" == *GE-Proton* ]]; then
                tag="${base_runner#lutris-}"
                urls+=("https://github.com/GloriousEggroll/wine-ge-custom/releases/download/${tag}/${asset}")
            elif [[ "$runner" == *fshack* ]]; then
                tag="${base_runner//-fshack/}"
                ver="${tag#lutris-}"
                urls+=("https://github.com/lutris/wine/releases/download/${tag}/${asset}")
                urls+=("https://github.com/lutris/wine/releases/download/lutris-wine-${ver}/${asset}")
            else
                tag="$base_runner"
                ver="${tag#lutris-}"
                urls+=("https://github.com/lutris/wine/releases/download/${tag}/${asset}")
                urls+=("https://github.com/lutris/wine/releases/download/lutris-wine-${ver}/${asset}")
            fi

            echo "  [DOWNLOAD] $runner ..."
            tmpfile="$(sudo -u "$REAL_USER" mktemp /tmp/runner-XXXXXX.tar.xz)"
            downloaded=false
            for url in "${urls[@]}"; do
                if sudo -u "$REAL_USER" curl -fSL --progress-bar -o "$tmpfile" "$url"; then
                    downloaded=true
                    break
                fi
            done
            if $downloaded; then
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

        # ----------------------------------------------------------
        # Verify each installed runner can actually write to a WINEPREFIX.
        # Some runners launch but fail silently when a system library is
        # missing (libfreetype, libgnutls, 32-bit GL, etc.) — wineboot
        # returns 0 yet leaves the prefix empty. Catch that here so the
        # game launchers don't appear to "do nothing" later.
        # ----------------------------------------------------------
        echo ""
        echo "  Verifying wine runners can initialize a WINEPREFIX..."

        WINE_TEST_FAIL=0
        for runner in "${RUNNERS[@]}"; do
            runner_dir="$RUNNERS_DIR/$runner"
            if [[ ! -x "$runner_dir/bin/wine" ]]; then
                echo "  [SKIP] $runner: wine binary not found"
                continue
            fi

            test_prefix="$(sudo -u "$REAL_USER" mktemp -d /tmp/wine-test-prefix-XXXXXX)"
            # Create err_log as root (the redirecting shell), not as REAL_USER.
            # Ubuntu's fs.protected_regular sysctl blocks root from opening with
            # O_CREAT a file it doesn't own in a world-writable sticky dir like
            # /tmp, so a sudo-created file would EACCES the redirect on line below.
            err_log="$(mktemp /tmp/wine-test-XXXXXX.log)"

            wine_env=(
                HOME="$REAL_HOME"
                PATH="$runner_dir/bin:/usr/bin:/bin"
                WINE="$runner_dir/bin/wine"
                WINELOADER="$runner_dir/bin/wine"
                WINESERVER="$runner_dir/bin/wineserver"
                LD_LIBRARY_PATH="$runner_dir/lib64:$runner_dir/lib"
                WINEDLLPATH="$runner_dir/lib64/wine/x86_64-unix:$runner_dir/lib/wine/i386-unix"
                WINEPREFIX="$test_prefix"
                WINEDEBUG=-all
                WINEDLLOVERRIDES="mscoree=;mshtml="
            )

            sudo -u "$REAL_USER" env "${wine_env[@]}" \
                timeout 180 "$runner_dir/bin/wine" wineboot --init >"$err_log" 2>&1 || true

            # Tear down the wineserver daemon so prefixes don't pile up across
            # iterations. -k kills the server for this prefix; -w waits for exit
            # (without -w, winedevice.exe children can outlive the rm -rf below
            # and spin at 100% CPU forever, with no prefix dir left to recover).
            sudo -u "$REAL_USER" env "${wine_env[@]}" \
                "$runner_dir/bin/wineserver" -k -w >>"$err_log" 2>&1 || true

            # drive_c/windows/system32 is created synchronously by wineboot;
            # it's a reliable "the runner wrote to the prefix" signal. Don't
            # check *.reg files — those are flushed to disk only when
            # wineserver shuts down, which races the check.
            if [[ -d "$test_prefix/drive_c/windows/system32" ]]; then
                echo "  [OK]   $runner can write to WINEPREFIX"
            else
                echo "  [FAIL] $runner: WINEPREFIX not initialized — runner cannot write to a prefix"
                echo "         Likely a missing system library (32-bit GL, libfreetype, libgnutls, libsdl, ...)."
                echo "         Diagnose with: ldd $runner_dir/bin/wine | grep 'not found'"
                if [[ -s "$err_log" ]]; then
                    echo "         Last lines of wineboot output:"
                    tail -5 "$err_log" | sed 's/^/           /'
                fi
                WINE_TEST_FAIL=$((WINE_TEST_FAIL + 1))
            fi
            rm -rf "$test_prefix" "$err_log"
        done

        if [[ $WINE_TEST_FAIL -gt 0 ]]; then
            echo ""
            echo "  [WARN] $WINE_TEST_FAIL wine runner(s) failed the prefix-write test."
            echo "         Game launchers using these runners may appear to do nothing on launch."
        fi
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

#!/bin/bash
#
# CFL.sh - Installer/launcher for Madden NFL 08 + CFL mod
#
# Builds a working install from original files only:
#   - Madden NFL 08 ISO (extracted via 7z, bypassing the DX9c installer)
#   - X mod 7-18-14 (extracted, applied directly)
#   - CFL 15 V2 (extracted, applied on top of X mod)
#   - NoCD crack mainapp.exe
#   - JSGME.exe (optional mod manager)
#
# No Windows system or pre-installed prefix required.
#
# LESSONS LEARNED (Feb 2026):
#
#   1. VIRTUAL DESKTOP REQUIRED: Wine cannot do fullscreen on multi-monitor
#      setups — the xinerama driver fails to pick a monitor, the D3D
#      swapchain gets a garbage size (e.g. 160x31), and the D3D device
#      reset fails.  Always launch via:
#        wine explorer /desktop=CFL,1024x768 ./mainapp.exe
#
#   2. USE SYSTEM WINE, NOT GE-PROTON: GE-Proton8-26 with the full Lutris
#      WINEDLLOVERRIDES causes a black screen inside the virtual desktop.
#      System wine 9 with DXVK 2.6.2 in the prefix works correctly.
#      The wine_runners.csv entry for CFL must have an empty runner field.
#
#   3. ISO MANUAL EXTRACT WORKS: The ISO installer shows a "DX9c missing"
#      showstopper dialog.  Bypass it by extracting files directly with 7z.
#      The patch can be skipped — the CFL mod overwrites the patched files.
#      The CFL mod installer can also be bypassed by extracting manually.
#      Previous "CD not found" errors were actually graphics failures that
#      are now fixed by the virtual desktop approach.
#
#   4. MATCHMAKING DIALOG AUTO-DISMISS: The game shows a hidden "Online
#      matchmaking is not guaranteed after August 31, 2008" dialog behind
#      the main window on startup.  Without auto-dismissing it, the game
#      hangs forever.  xdotool windowactivate + xte 'key Return' works;
#      plain xdotool key/type does not because Wine ignores XSendEvent.
#
#   5. DO NOT SET "CD Drive" REGISTRY KEY: Setting
#      HKLM\Software\EA SPORTS\Madden NFL 08\CD Drive = D:\ causes the
#      game to actively look for a CD on that drive, defeating the NoCD
#      crack.  The working prefix has no game registry entries beyond a
#      COM typelib registration.
#
# Required files in sglBinaries_2/SAT/CFL/:
#   Madden-NFL-08_Win_EN_US-ISO.zip   (contains the game ISO)
#   Xmod 7-18-14.7z                   (X mod data files)
#   CFL 15 V2.zip                     (CFL mod data files + roster)
#   Madden-NFL-08_NoCD_Win_EN_NoDVD.zip  (NoCD crack)
#   JSGME.exe                         (mod manager)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Wine prefix setup ---
# Use system wine (not a Lutris runner) — GE-Proton causes black screen.
export WINEPREFIX="$SCRIPT_DIR/WP"
export WINEARCH=win32

GAME_DIR="$WINEPREFIX/drive_c/Program Files/EA SPORTS/Madden NFL 08"

# =====================================================================
# Already installed → launch
# =====================================================================
if [[ -d "$GAME_DIR" && -f "$GAME_DIR/mainapp.exe" ]]; then
    # Kill any stale wineserver to avoid BadWindow X errors on relaunch.
    wineserver -k 2>/dev/null || true
    sleep 1

    echo "Launching CFL football ..."
    echo "  Tip: click and drag on the lower right of the CFL splash screen,"
    echo "  then select 'click to begin'."
    cd "$GAME_DIR"

    # Auto-dismiss the EA online matchmaking notice dialog that appears
    # behind the game window.  See lesson #4 above.
    # In virtual desktop mode, all Wine windows are rendered inside one
    # X window, so xdotool cannot find individual dialogs.  We Alt+Tab
    # within Wine to bring the hidden dialog to the front, then Enter.
    (
        sleep 12
        for _i in $(seq 1 15); do
            WID=$(xdotool search --name "CFL" 2>/dev/null | head -1)
            if [[ -n "$WID" ]]; then
                xdotool windowactivate --sync "$WID" 2>/dev/null
                sleep 0.3
                # Alt+Tab within Wine to bring the hidden dialog forward
                xte 'keydown Alt_L' 'key Tab' 'keyup Alt_L' 2>/dev/null
                sleep 0.5
                xte 'key Return' 2>/dev/null
                exit 0
            fi
            sleep 2
        done
    ) &

    # Try DXVK 2.x first, fall back to DXVK-Sarek if GPU lacks Vulkan 1.3
    if [ ! -f "$WINEPREFIX/.dxvk_sarek" ]; then
        WINEDLLOVERRIDES="d3d9,d3d11,dxgi=n,b" \
            wine explorer /desktop=CFL,1024x768 ./mainapp.exe 2>"$WINEPREFIX/.dxvk_log"
        if grep -q "No adapters found\|maintenance5\|DXGIFactory" "$WINEPREFIX/.dxvk_log"; then
            wineserver -k 2>/dev/null || true
            echo "DXVK 2.x not supported on this GPU. Installing DXVK-Sarek fallback..."
            sarek_ver="v1.11.0"
            sarek_tar="/tmp/dxvk-sarek-${sarek_ver}.tar.gz"
            if [ ! -f "$sarek_tar" ]; then
                gh release download "$sarek_ver" -R pythonlover02/DXVK-Sarek \
                    -p "dxvk-sarek-${sarek_ver}.tar.gz" -D /tmp 2>/dev/null
            fi
            sarek_dir="/tmp/dxvk-sarek-${sarek_ver}"
            [ -d "$sarek_dir" ] || tar xzf "$sarek_tar" -C /tmp
            cp "$sarek_dir/x32/d3d9.dll" "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x32/dxgi.dll" "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x32/d3d11.dll" "$WINEPREFIX/drive_c/windows/system32/"
            touch "$WINEPREFIX/.dxvk_sarek"
            echo "DXVK-Sarek installed. Launching CFL..."
            WINEDLLOVERRIDES="d3d9,d3d11,dxgi=n,b" \
                wine explorer /desktop=CFL,1024x768 ./mainapp.exe 2>/dev/null
        fi
    else
        WINEDLLOVERRIDES="d3d9,d3d11,dxgi=n,b" \
            wine explorer /desktop=CFL,1024x768 ./mainapp.exe 2>/dev/null
    fi
    rm -f "$WINEPREFIX/.dxvk_log"
    exit 0
fi

# =====================================================================
# Not installed → build from original files
# =====================================================================

echo "=== CFL (Madden NFL 08 + CFL mod) installer ==="
echo ""

echo "Building from original ISO + mod files (no Windows needed)."
echo ""

# --- Locate install files ---
INSTALL_DIR=""
for search_dir in \
    "$SCRIPT_DIR/INSTALL" \
    "$HOME/sgl/downloads/sglBinaries_2/SAT/CFL" \
    "$HOME/Downloads/sglBinaries_2/SAT/CFL"; do
    if [[ -f "$search_dir/Madden-NFL-08_Win_EN_US-ISO.zip" ]]; then
        INSTALL_DIR="$search_dir"
        break
    fi
done

if [[ -z "$INSTALL_DIR" ]]; then
    echo "ERROR: Install files not found."
    echo ""
    echo "Looked for Madden-NFL-08_Win_EN_US-ISO.zip in:"
    echo "  $SCRIPT_DIR/INSTALL/"
    echo "  ~/sgl/downloads/sglBinaries_2/SAT/CFL/"
    echo "  ~/Downloads/sglBinaries_2/SAT/CFL/"
    echo ""
    echo "Place sglBinaries_2 in ~/sgl/downloads/ and run: sudo ./install.sh"
    exit 1
fi

echo "Found install files in: $INSTALL_DIR"

# Verify all required files exist
MISSING=""
for f in \
    "Madden-NFL-08_Win_EN_US-ISO.zip" \
    "Xmod 7-18-14.7z" \
    "CFL 15 V2.zip" \
    "Madden-NFL-08_NoCD_Win_EN_NoDVD.zip" \
    "JSGME.exe"; do
    if [[ ! -f "$INSTALL_DIR/$f" ]]; then
        MISSING="$MISSING  $f\n"
    fi
done

if [[ -n "$MISSING" ]]; then
    echo "ERROR: Missing required files in $INSTALL_DIR:"
    echo -e "$MISSING"
    exit 1
fi

# --- Step 1: Create Wine prefix ---
echo ""
echo "[1/8] Creating Wine prefix ..."
WINEDEBUG=-all wineboot -i 2>/dev/null

# Set Windows XP (required for this era of game)
WINEDEBUG=-all wine reg add \
    "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion" \
    /v CurrentVersion /t REG_SZ /d "5.1" /f 2>/dev/null
WINEDEBUG=-all wine reg add \
    "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion" \
    /v CSDVersion /t REG_SZ /d "Service Pack 3" /f 2>/dev/null
WINEDEBUG=-all wine reg add \
    "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion" \
    /v CurrentBuildNumber /t REG_SZ /d "2600" /f 2>/dev/null

# --- Step 2: Install winetricks dependencies ---
echo "[2/8] Installing DirectX and DXVK (this takes a few minutes) ..."
# Install DirectX components via winetricks (but NOT dxvk — winetricks
# installs the latest DXVK which requires Vulkan 1.3 / maintenance5,
# not supported by NVIDIA 535.x drivers).
WINEDEBUG=-all winetricks -q d3dcompiler_43 d3dx9 d3dcompiler_47 2>/dev/null

# Install DXVK 2.6.2 from Lutris runtime (compatible with older drivers)
DXVK_DIR="$HOME/.local/share/lutris/runtime/dxvk/v2.6.2"
SYS32="$WINEPREFIX/drive_c/windows/system32"
if [[ -d "$DXVK_DIR/x32" ]]; then
    for dll in d3d9.dll d3d10core.dll d3d11.dll dxgi.dll d3d8.dll; do
        cp "$DXVK_DIR/x32/$dll" "$SYS32/$dll"
    done
    # Set native DLL overrides for DXVK
    for dllname in d3d9 d3d10core d3d11 dxgi; do
        WINEDEBUG=-all wine reg add "HKCU\\Software\\Wine\\DllOverrides" \
            /v "*$dllname" /t REG_SZ /d "native" /f 2>/dev/null
    done
    echo "  Installed DXVK 2.6.2 from Lutris runtime."
else
    echo "  WARNING: DXVK 2.6.2 not found at $DXVK_DIR"
    echo "  Falling back to winetricks dxvk (may require Vulkan 1.3)."
    WINEDEBUG=-all winetricks -q dxvk 2>/dev/null
fi

# --- Step 3: Extract game files from ISO ---
echo "[3/8] Extracting Madden NFL 08 from ISO ..."

# Extract ISO from zip if needed
TMP_DIR="$SCRIPT_DIR/tmp_install"
mkdir -p "$TMP_DIR"
ISO_PATH=""

# Check for already-extracted ISO
for candidate in \
    "$INSTALL_DIR/Madden.iso" \
    "$INSTALL_DIR/Madden NFL 08 (USA).iso"; do
    if [[ -f "$candidate" ]]; then
        ISO_PATH="$candidate"
        break
    fi
done

if [[ -z "$ISO_PATH" ]]; then
    echo "  Extracting ISO from zip (this takes a minute) ..."
    7z e "$INSTALL_DIR/Madden-NFL-08_Win_EN_US-ISO.zip" -o"$TMP_DIR" "*.iso" -y > /dev/null
    # Find the extracted ISO (name may vary)
    ISO_PATH=$(find "$TMP_DIR" -maxdepth 1 -name "*.iso" | head -1)
    if [[ -z "$ISO_PATH" ]]; then
        echo "ERROR: Could not extract ISO from zip."
        rm -rf "$TMP_DIR"
        exit 1
    fi
fi

echo "  Extracting game files from ISO to Wine prefix ..."
mkdir -p "$GAME_DIR"
7z x "$ISO_PATH" -o"$GAME_DIR" -y > /dev/null

# Remove installer-only files that aren't part of the game
rm -f "$GAME_DIR/AutoRun.exe" "$GAME_DIR/AUTORUN.inf" "$GAME_DIR/autorun.inf" \
      "$GAME_DIR/madden_inst.exe" "$GAME_DIR/Updater.exe" \
      "$GAME_DIR/AutoRunGUI.dll" "$GAME_DIR/common_filelist.txt" \
      "$GAME_DIR/LnchUpdt.dat" "$GAME_DIR/mydoc_uninst.exe"
rm -rf "$GAME_DIR/DirectX" "$GAME_DIR/CommonEASO" "$GAME_DIR/Player" \
       "$GAME_DIR/AutoRun"

# Copy StreamedData.db to root (installer normally does this; game may
# not find it in data0/ without it)
cp "$GAME_DIR/data0/StreamedData.db" "$GAME_DIR/" 2>/dev/null || true

# --- Step 4: Apply X mod ---
echo "[4/8] Applying X mod ..."
# X mod files go to the game root directory, overriding data0/data1 originals.
# The game reads root-level .dat files before falling back to data0/data1.
7z e "$INSTALL_DIR/Xmod 7-18-14.7z" -o"$GAME_DIR" -y > /dev/null

# --- Step 5: Apply CFL 15 V2 mod ---
echo "[5/8] Applying CFL 15 V2 mod ..."
# CFL mod has structure: MODS/CFL 15/*.dat and Rosters/CFL 15.ros
# Use 7z x (preserve paths) so the MODS/CFL 15/ structure is intact
7z x "$INSTALL_DIR/CFL 15 V2.zip" -o"$TMP_DIR/cfl_extract" -y > /dev/null
# Copy .dat files from MODS/CFL 15/ to game root (overriding X mod)
cp "$TMP_DIR/cfl_extract/MODS/CFL 15/"*.dat "$GAME_DIR/" 2>/dev/null || true
cp "$TMP_DIR/cfl_extract/MODS/CFL 15/"*.DAT "$GAME_DIR/" 2>/dev/null || true
# Install CFL roster
mkdir -p "$GAME_DIR/Rosters"
cp "$TMP_DIR/cfl_extract/Rosters/"* "$GAME_DIR/Rosters/" 2>/dev/null || true

# --- Step 6: Install NoCD crack + JSGME ---
echo "[6/8] Installing NoCD crack and JSGME ..."
# Extract NoCD mainapp.exe (replaces the DRM-protected original)
7z e "$INSTALL_DIR/Madden-NFL-08_NoCD_Win_EN_NoDVD.zip" -o"$TMP_DIR/nocd" -y > /dev/null
cp "$TMP_DIR/nocd/mainapp.exe" "$GAME_DIR/mainapp.exe"

# Copy JSGME mod manager
cp "$INSTALL_DIR/JSGME.exe" "$GAME_DIR/"

# Set up JSGME config pointing to MODS directory
cat > "$GAME_DIR/JSGME.ini" << 'JSGME_EOF'
[MODS FOLDER]
Name=MODS
[JSGME DETAILS]
FullPath=C:\Program Files\EA SPORTS\Madden NFL 08\JSGME.exe
JSGME_EOF

# Set up MODS directory with mod files for future JSGME use
mkdir -p "$GAME_DIR/MODS/X mod"
mkdir -p "$GAME_DIR/MODS/CFL 15"
7z e "$INSTALL_DIR/Xmod 7-18-14.7z" -o"$GAME_DIR/MODS/X mod" -y > /dev/null
cp -a "$TMP_DIR/cfl_extract/MODS/CFL 15/"* "$GAME_DIR/MODS/CFL 15/" 2>/dev/null || true

# --- Step 7: Register COM typelib (matches working install) ---
echo "[7/8] Configuring Wine registry ..."
WINEDEBUG=-all wine reg add \
    "HKCR\\Typelib\\{542F737C-0B24-4CC5-A499-C450DACC0EB6}\\1.0" \
    /ve /d "Madden Game Interface Type Library" /f 2>/dev/null
WINEDEBUG=-all wine reg add \
    "HKCR\\Typelib\\{542F737C-0B24-4CC5-A499-C450DACC0EB6}\\1.0\\0\\win32" \
    /ve /d "C:\\Program Files\\EA SPORTS\\Madden NFL 08\\mainapp.exe" /f 2>/dev/null
WINEDEBUG=-all wine reg add \
    "HKCR\\Typelib\\{542F737C-0B24-4CC5-A499-C450DACC0EB6}\\1.0\\FLAGS" \
    /ve /d "8" /f 2>/dev/null
WINEDEBUG=-all wine reg add \
    "HKCR\\Typelib\\{542F737C-0B24-4CC5-A499-C450DACC0EB6}\\1.0\\HELPDIR" \
    /ve /d "C:\\Program Files\\EA SPORTS\\Madden NFL 08\\" /f 2>/dev/null

# --- Step 8: Create game directories and config ---
echo "[8/8] Setting up game directories and configuration ..."

# Create empty directories the game expects
for d in Playbooks Replays Saved Scrnshots Spawn Stats Teams Temp Users GLCache; do
    mkdir -p "$GAME_DIR/$d"
done

# Create Documents directory (Madden user data)
DOCS_DIR="$WINEPREFIX/drive_c/users/$USER/Documents/Madden NFL 08"
mkdir -p "$DOCS_DIR"
for d in CustomArt Music Playbooks Replays Rosters Saved Scrnshots Spawn Stats System Teams Temp Users; do
    mkdir -p "$DOCS_DIR/$d"
done

# Write madden.ini (both locations — game dir and Documents)
MADDEN_INI='// *********** Madden INI configuration file ***********
//
//  This file is loaded on program initialization, and
//  automatically re-generated when the program closes.

Restore Default [Yes/No] = No

// Option Group: Gameplay Settings
Accelerated Game Clock [Yes/No] = No
Fatigue [On/Off] = On
Game Mode [Classic/Player/Coach] = Classic
Injuries [On/Off] = On
Playclock [On/Off] = On
Quarter Length [0-14] = 4
Random Weather [On/Off] = On
Skill Level [0-3] = 1

// Option Group: Stat Log Settings
Franchise Log Files [Unique/Overwrite] = Overwrite
Franchise Log [Off/Text/Html] = Off
Game Log Files [Unique/Overwrite] = Overwrite
Game Log [Off/Text/Html] = Text
Stat Report Files [Unique/Overwrite] = Overwrite
Stat Report Format [Csv/Html] = Csv

// Option Group: Visual Settings
Auto Instant Replay [On/Off] = On
Field Lines [0-3] = 2
In-game Screen Transitions [On/Off] = On
Player Tag Info. [0-3] = 3

// Option Group: Penalty Settings
Clipping [0-99] = 50
Def. Pass Interference [0-99] = 50
Face Mask [0-99] = 50
False Start [0-99] = 50
Holding [0-99] = 50
Intentional Grounding [0-99] = 50
KR/PR Catch Interference [0-99] = 50
Off. Pass Interference [0-99] = 50
Offsides [On/Off] = On
Penalties [On/Off] = On
Roughing Kicker [0-99] = 50
Roughing Passer [0-99] = 50

// Option Group: AI Settings
CPU Def. Awareness [0-99] = 50
CPU Def. Break Blocks [0-99] = 50
CPU Def. Interceptions [0-99] = 50
CPU Def. Knockdowns [0-99] = 50
CPU Def. Tackling [0-99] = 50
CPU FG Accuracy [0-99] = 50
CPU FG Length [0-99] = 50
CPU Kickoff Length [0-99] = 50
CPU Pass Blocking [0-99] = 50
CPU Punt Accuracy [0-99] = 50
CPU Punt Length [0-99] = 50
CPU QB Accuracy [0-99] = 50
CPU RB Ability [0-99] = 50
CPU Run Blocking [0-99] = 50
CPU WR Catching [0-99] = 50
Human Def. Awareness [0-99] = 50
Human Def. Break Blocks [0-99] = 50
Human Def. Interceptions [0-99] = 50
Human Def. Knockdowns [0-99] = 50
Human Def. Tackling [0-99] = 50
Human FG Accuracy [0-99] = 50
Human FG Length [0-99] = 50
Human Kickoff Length [0-99] = 50
Human Pass Blocking [0-99] = 50
Human Punt Accuracy [0-99] = 50
Human Punt Length [0-99] = 50
Human QB Accuracy [0-99] = 50
Human RB Ability [0-99] = 50
Human Run Blocking [0-99] = 50
Human WR Catching [0-99] = 50

// Option Group: Sound Settings
Audio Perspective[Classic/OnField/InStands/InBooth/Custom] = Classic
Classic Commentary Volume [0-99] = 99
Classic Commentary [On/Off] = On
Classic Crowd Volume [0-99] = 99
Classic Field Volume [0-99] = 69
Classic MP3 Volume [0-99] = 50
Classic Master Volume [0-99] = 99
Classic Menu SFX Volume [0-99] = 99
Classic Sound Mode [Mono/Stereo] = Stereo
Custom Commentary Volume [0-99] = 99
Custom Commentary [On/Off] = On
Custom Crowd Volume [0-99] = 99
Custom Field Volume [0-99] = 69
Custom MP3 Volume [0-99] = 50
Custom Master Volume [0-99] = 99
Custom Menu SFX Volume [0-99] = 99
Custom Sound Mode [Mono/Stereo] = Stereo
In Booth Commentary Volume [0-99] = 89
In Booth Commentary [On/Off] = On
In Booth Crowd Volume [0-99] = 39
In Booth Field Volume [0-99] = 29
In Booth MP3 Volume [0-99] = 50
In Booth Master Volume [0-99] = 99
In Booth Menu SFX Volume [0-99] = 99
In Booth Sound Mode [Mono/Stereo] = Stereo
In Stands Commentary [On/Off] = Off
In Stands Crowd Volume [0-99] = 99
In Stands Field Volume [0-99] = 59
In Stands MP3 Volume [0-99] = 50
In Stands Master Volume [0-99] = 99
In Stands Menu SFX Volume [0-99] = 99
In Stands PA Volume [0-99] = 99
In Stands Sound Mode [Mono/Stereo] = Stereo
MP3 In Game [On/Off] = Off
MP3 Path String [1024] = "C:\Program Files\EA SPORTS\Madden NFL 08\Music"
MP3 Scan Subdirectories [Yes/No] = No
MP3 Selection [Off/Sequential/Random] = Random
On Field Commentary [On/Off] = Off
On Field Crowd Volume [0-99] = 99
On Field Field Volume [0-99] = 99
On Field MP3 Volume [0-99] = 50
On Field Master Volume [0-99] = 99
On Field Menu SFX Volume [0-99] = 99
On Field PA Volume [0-99] = 99
On Field Sound Mode [Mono/Stereo] = Stereo

// Option Group: In-Game Mouse Settings
Default Distance [0-99] = 50
Invert Mouse [Yes/No] = No
Pitch Clamp Angle [0-90] = 45
Rotate Sensitivity [0-99] = 50
Zoom Sensitivity [0-99] = 50

// Option Group: System Settings
Front-End Rate Limited [Yes/No] = Yes
Hardware Shaders [On/Off] = Off
Helmet Mapping [On/Off] = On
In-game Effects [On/Off] = On
Player Accessories [On/Off] = On
Video Bit Depth [16/32] = 32
Video Refresh Frequency [60-120] = 60
Video Resolution Horizontal [320-1600] = 1024
Video Resolution Vertical [200-1200] = 768
Video Texture Compression [On/Off] = Off
Video Texture Depth [0/16/32] = 0
Video Texture Resolution [Low/Medium/High] = High
Video Vertical Sync [On/Off] = On
Weather Effects [0-4] = 4
Windowed Mode [Yes/No] = No

// Option Group: Detail Settings
Field Detail [Low/Medium/High/Highest] = Highest
Interface Detail [Low/High] = High
Lighting [Off/Low/Medium/High] = High
Player Detail [Lowest/Low/Medium/High/Highest] = Highest
Player Shadows [Off/Circle/Low/Medium/High] = High
Referee Detail [Low/Medium/High] = High
Referee Shadows [Off/Circle/High] = High
Sky Detail [Low/High] = High
Stadium Detail [Medium/High] = High

// Option Group: Sideline Detail Settings
BallBoy Detail [Off/Low/Medium/High] = High
BallBoy Shadows [Off/Circle/High] = High
CamGuy Detail [Off/Low/Medium/High] = High
CamGuy Shadows [Off/Circle/High] = High
Chain Gang Detail [Off/Low/Medium/High] = High
Chain Gang Shadows [Off/Circle/High] = High
Cheerleader Detail [Off/Low/Medium/High] = High
Cheerleader Shadows [Off/Circle/High] = High
Coach Detail [Off/Low/Medium/High] = High
Coach Shadows [Off/Circle/High] = High
Sideline Player Density [16/24/32] = 32
Sideline Player Detail [Off/Low/Medium/High/Highest] = High

// Option Group: Network Settings
Online Connection Method [Internet/LAN] = Internet
Online Connection Timeout (seconds) [10-240] = 15

// Option Group: Debug Settings
Debug Switches String [1023] = ""'

echo "$MADDEN_INI" > "$GAME_DIR/madden.ini"
echo "$MADDEN_INI" > "$DOCS_DIR/madden.ini"

# --- Clean up temp files ---
rm -rf "$TMP_DIR"

echo ""
echo "=== Installation complete ==="
echo ""
echo "Run this script again to play CFL."
echo ""

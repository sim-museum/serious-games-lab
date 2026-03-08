#!/usr/bin/env bash
# distribute_binaries.sh - Move installer files from downloads/sglBinaries_* to game INSTALL/ dirs
#
# Moves binary installer files (ISOs, zips, exes, etc.) from the
# downloads/sglBinaries_* directories to the correct game-specific
# INSTALL/ directories so game scripts can find them.
#
# Uses mv (move, not copy) for disk efficiency.
# Creates INSTALL/ directories as needed.
# After all moves, deletes emptied sglBinaries_* directories.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DL="$REPO_ROOT/downloads"

# move_file SRC_BINARIES_DIR FILENAME DEST_DIR
#   Moves a file from a sglBinaries dir to the given INSTALL directory.
move_file() {
    local src="$DL/$1/$2"
    local dest_dir="$REPO_ROOT/$3"
    if [ -e "$src" ]; then
        mkdir -p "$dest_dir"
        if [ ! -e "$dest_dir/$2" ]; then
            mv "$src" "$dest_dir/" 2>/dev/null || true
        fi
    fi
}

# move_dir SRC_BINARIES_DIR DIRNAME DEST_DIR
#   Moves a directory from a sglBinaries dir into the given INSTALL directory.
move_dir() {
    local src="$DL/$1/$2"
    local dest_dir="$REPO_ROOT/$3"
    if [ -d "$src" ]; then
        mkdir -p "$dest_dir"
        if [ ! -d "$dest_dir/$(basename "$src")" ]; then
            mv "$src" "$dest_dir/" 2>/dev/null || true
        fi
    fi
}

echo "Distributing binary files to game INSTALL directories..."

# --- sglBinaries_1 ---
# Archive day-of-week directories match the repo layout directly:
#   MON=poker, TUE=flight sims, WED=chess, THU=racing,
#   FRI=bridge, SAT=combat/CFL, SUN=go
# Only INSTALL/ directories and game subdirectories contain binary data;
# scripts and DOC files are tracked in the repo.
if [ -d "$DL/sglBinaries_1" ]; then
    echo "  Distributing sglBinaries_1 INSTALL files..."
    for day in MON TUE WED THU FRI SAT SUN; do
        [ -d "$DL/sglBinaries_1/$day/INSTALL" ] || continue
        mkdir -p "$REPO_ROOT/$day/INSTALL"
        rsync -a --ignore-existing "$DL/sglBinaries_1/$day/INSTALL/" "$REPO_ROOT/$day/INSTALL/"
    done
    # Sync non-day files (debs, etc.) directly
    rsync -a --ignore-existing --exclude='MON/' --exclude='TUE/' --exclude='WED/' \
        --exclude='THU/' --exclude='FRI/' --exclude='SAT/' --exclude='SUN/' \
        "$DL/sglBinaries_1/" "$REPO_ROOT/"
fi

# --- sglBinaries_2 ---
move_file "sglBinaries_2/CFL" "Madden-NFL-08_Win_EN_US-ISO.zip"                                "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "Madden-NFL-08_Patch_Win_EN_v3-US.zip"                           "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "Madden-NFL-08_NoCD_Win_EN_NoDVD.zip"                            "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "Madden-NFL-08_Misc_Win_EN_Serial-keys.txt"                      "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "Xmod 7-18-14.7z"                                               "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "CFL 15 V2.zip"                                                 "SAT/CFL/INSTALL"
move_file "sglBinaries_2/CFL" "JSGME.exe"                                                     "SAT/CFL/INSTALL"
move_dir  "sglBinaries_2" "CFLpreinstalled"                                                    "SAT/CFL/INSTALL"
# Move BMS432-v41 contents (INSTALL, docs) into SAT/BMS432/ where the scripts live
# Skip WP — games must be installed from original files, not pre-built prefixes
if [ -d "$DL/sglBinaries_2/BMS432-v41" ]; then
    mkdir -p "$REPO_ROOT/SAT/BMS432"
    for item in "$DL/sglBinaries_2/BMS432-v41"/*; do
        [ -e "$item" ] || continue
        base="$(basename "$item")"
        [[ "$base" == "WP" ]] && continue
        if [ ! -e "$REPO_ROOT/SAT/BMS432/$base" ]; then
            mv "$item" "$REPO_ROOT/SAT/BMS432/" 2>/dev/null || true
        fi
    done
fi
move_file "sglBinaries_2" "Republic-The-Revolution_Win_EN.exe"                                 "SAT/republic/INSTALL"

# --- sglBinaries_3 ---
# rFactorINSTALL/ directory contents go into THU/rFactor/INSTALL/
if [ -d "$DL/sglBinaries_3/rFactorINSTALL" ]; then
    mkdir -p "$REPO_ROOT/THU/rFactor/INSTALL"
    rsync -a --remove-source-files "$DL/sglBinaries_3/rFactorINSTALL/" "$REPO_ROOT/THU/rFactor/INSTALL/"
fi

# --- sglBinaries_4 ---
move_file "sglBinaries_4" "Bridge-Baron-12_Win_EN.zip"                                        "FRI/bb12/INSTALL"
move_file "sglBinaries_4" "Bridge-Deluxe-2-With-Omar-Sharif_Win_EN_RIP-Version.zip"           "FRI/INSTALL"
move_file "sglBinaries_4" "Chessmaster-Grandmaster-Edition_Win_EN-FR.zip"                     "WED/chessmaster/INSTALL"
move_file "sglBinaries_4" "Chessmaster-Grandmaster-Edition_Patch_Win_EN-FR_patch-v102.exe"    "WED/chessmaster/INSTALL"
move_file "sglBinaries_4" "World-Series-of-Poker-2008-Battle-for-the-Bracelets_Win_EN.zip"   "MON/INSTALL"

# --- sglBinaries_5 ---
move_file "sglBinaries_5" "rF.iso"                                                            "THU/rFactor/INSTALL"
move_file "sglBinaries_5" "rFactor.exe"                                                       "THU/rFactor/INSTALL"
move_file "sglBinaries_5" "Fighter_Squadron_SDOE_DVD.iso"                                     "TUE/SDOE/INSTALL"
move_file "sglBinaries_5" "fspatch150.exe"                                                    "TUE/SDOE/INSTALL"
move_file "sglBinaries_5" "Microsoft-Flight-Simulator-2004-A-Century-of-Flight_Win_EN_OEM-version-Updated-to-91.zip" "TUE/FS9/INSTALL"
move_file "sglBinaries_5" "Speed-Dreams-2.2.3-x86_64.AppImage"                               "THU/INSTALL"
move_file "sglBinaries_5" "NASCAR-Racing-2003-Season_Win_EN_ISO-Version.zip"                  "THU/NR2003/INSTALL"
move_file "sglBinaries_5" "NASCAR-Racing-2003-Season_Fix_Win_EN_Fix-for-Version-1201.exe"     "THU/NR2003/INSTALL"
move_file "sglBinaries_5" "NASCAR-Racing-2003-Season_Patch_Win_EN_Patch-1201.exe"             "THU/NR2003/INSTALL"
move_file "sglBinaries_5" "NASCAR-Racing-2003-Season_NoCD_Win_EN.zip"                         "THU/NR2003/INSTALL"
move_file "sglBinaries_5" "AD67_v1.0.exe"                                                     "THU/NR2003/INSTALL"
move_file "sglBinaries_5" "n2003_nurburgring_1970_v1.0.exe"                                   "THU/NR2003/INSTALL"

# --- sglBinaries_6 ---
move_file "sglBinaries_6" "Falcon BMS 4.35 Setup (Full).zip"                                 "SAT/BMS435/INSTALL"
move_file "sglBinaries_6" "Add-On Mideast128 4-35-U3v10.zip"                                 "SAT/BMS435/INSTALL"
move_file "sglBinaries_6" "Balkans_Theater_4.35.3.zip"                                       "SAT/BMS435/INSTALL"
move_file "sglBinaries_6" "Israel_Theater_4.35.3.zip"                                        "SAT/BMS435/INSTALL"

# --- sglBinaries_7 ---
move_file "sglBinaries_7" "falcon4Cd.iso"                                                     "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "FalconAF.iso"                                                      "SAT/INSTALL"
move_file "sglBinaries_7" "Add-On Vietnam 4.35.U1.2.zip"                                     "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Israel Theater 1.05.4v Patch.zip"                                 "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "bms-4.35.3-radar-xml-patch.exe"                                   "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Mission_Commander_0.5.20.685.7z"                                  "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Weapon_Delivery_Planner_3.7.19.208.7z"                           "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Somalia 4.35.3.rar"                                               "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Taiwan 4.35.3.rar"                                                "SAT/BMS435/INSTALL"
move_file "sglBinaries_7" "Tacview187Setup.exe"                                              "SAT/tacview/INSTALL"

# Remove "(copy)" duplicate files left behind in sglBinaries dirs
for d in "$DL"/sglBinaries_*/; do
    [ -d "$d" ] || continue
    find "$d" -name '* (copy)*' -type f -delete 2>/dev/null || true
done

# Clean up emptied sglBinaries_* directories
echo "Cleaning up emptied sglBinaries directories..."
for d in "$DL"/sglBinaries_*/; do
    [ -d "$d" ] || continue
    # Remove empty directories, but leave non-empty ones alone
    find "$d" -depth -type d -empty -delete 2>/dev/null || true
    # If the top-level dir is now empty, remove it
    if [ -d "$d" ] && [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
        rmdir "$d" 2>/dev/null || true
        echo "  Removed empty: $(basename "$d")"
    fi
done

# Remove sglBinaries tar.gz archives from downloads/
for f in "$DL"/sglBinaries_*.tar.gz; do
    [ -f "$f" ] || continue
    echo "  Removing archive: $(basename "$f")"
    rm -f "$f"
done

echo "Binary distribution complete."

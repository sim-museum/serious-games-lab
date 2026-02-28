#!/usr/bin/env bash
# common.sh - Shared variables and helper functions for launcher scripts
# Source this file at the top of other launcher scripts.

# Determine REPO_ROOT from this file's location (lib/ is inside launcher/)
COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER_DIR="$(dirname "$COMMON_DIR")"
REPO_ROOT="$(dirname "$LAUNCHER_DIR")"

# Day-of-week arrays
DAY_ORDER=("MON" "TUE" "WED" "THU" "FRI" "SAT" "SUN")
DAY_NAMES=("Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")
DAY_THEMES=("Poker" "Historical Flight Sim" "Chess" "Sim Racing" "Duplicate Bridge" "Modern Flight Sim" "Go")

# Directories
DOWNLOADS_DIR="$REPO_ROOT/downloads"
CONFIG_DIR="$REPO_ROOT/config"
CSV_FILE="$REPO_ROOT/filesForLauncher/launcherScripts.csv"
DEPS_MARKER="$REPO_ROOT/.deps_installed"
SCORES_FILE="$REPO_ROOT/filesForLauncher/launcherScores.csv"
LAUNCHER_FILES_DIR="$REPO_ROOT/filesForLauncher"

# Terminal colors (only if stdout is a terminal)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'  # No Color
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' NC=''
fi

# --- Helper functions ---

msg_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
msg_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
msg_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
msg_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Check if a binary game's Wine Prefix (WP/) exists for a given script
# Usage: has_binary_data MON gpl.sh       -> checks MON/WP
# Usage: has_binary_data SAT BMS435/BMS435.sh -> checks SAT/BMS435/WP
has_binary_data() {
    local day="$1"
    local script="$2"

    # Check that the required sglBinaries archive has been extracted
    local archive_num
    archive_num="$(game_archive "$script")"
    if [[ "$archive_num" -gt 0 ]]; then
        local marker="$DOWNLOADS_DIR/.extracted_sglBinaries_${archive_num}.tar.gz"
        [[ -f "$marker" ]] || return 1
    fi

    local script_dir="${script%/*}"
    # If no directory in path, script is at day level
    if [[ "$script_dir" == "$script" ]]; then
        script_dir=""
    fi
    [[ -d "$REPO_ROOT/$day/$script_dir/WP" ]] || [[ -d "$REPO_ROOT/$day/$script_dir/INSTALL" ]]
}

# Check if a script file exists (handles subdirectory scripts like BMS435/BMS435.sh)
# Usage: script_exists MON bcalc.sh
script_exists() {
    local day="$1"
    local script="$2"
    [[ -f "$REPO_ROOT/$day/$script" ]]
}

# Determine if a script is a "source" game (doesn't need sglBinaries data)
# These can be installed via apt, pip, download, or are PyQt source apps
is_source_game() {
    local script="$1"
    case "$script" in
        # PyQt source apps
        benBridge/run.sh|mathQuiz/run.sh|dual_nback/run.sh) return 0 ;;
        openingRepertoire/run_opening_repertoire.sh) return 0 ;;
        pokerIQ/run.sh) return 0 ;;
        # Downloadable / pip-installable / apt-installable
        bcalc.sh) return 0 ;;
        run_katrain.sh) return 0 ;;
        pokerth.sh) return 0 ;;
        speedDreams.sh) return 0 ;;
        # FlightGear missions (flightgear installed separately)
        flightgear/*.sh) return 0 ;;
        # apt-installable chess/go/board tools
        scid.sh|nibbler.sh|banksiaGui.sh) return 0 ;;
        q5go.sh|sabaki.sh|goreviewpartner.sh) return 0 ;;
        # Buildable from source
        generalPokerEvaluator.sh) return 0 ;;
        *) return 1 ;;
    esac
}

# Check if a script is a "non-violent" game (shown in submenu)
is_nonviolent_game() {
    local script="$1"
    case "$script" in
        CFL/CFL.sh|republic/republic.sh) return 0 ;;
        *) return 1 ;;
    esac
}

# Which sglBinaries archive provides this binary game?
# Returns 0 for source games, 1 for sglBinaries_1, 2-7 for later archives
game_archive() {
    local script="$1"
    if is_source_game "$script"; then
        echo 0
        return
    fi
    case "$script" in
        # sglBinaries_2: BMS 4.32 + CFL preinstalled + Republic
        BMS432/BMS432.sh|CFL/CFL.sh|republic/republic.sh) echo 2 ;;
        # sglBinaries_4: Chessmaster, Bridge Baron, WSOP/bracelets
        chessmaster/chessmaster.sh|bb12/bb12.sh|bracelets.sh) echo 4 ;;
        # sglBinaries_5: ISOs/installers (NR2003, rFactor, FS9, SDOE)
        NR2003/NR2003.sh|rFactor/rFactor.sh) echo 5 ;;
        FS9/fs9.sh|SDOE/WWI_SDOE.sh|SDOE/WWII_SDOE.sh) echo 5 ;;
        # sglBinaries_6: BMS 4.35
        BMS435/BMS435.sh) echo 6 ;;
        # sglBinaries_7: Falcon AF ISO
        FalconAF.sh) echo 7 ;;
        # Everything else binary is in sglBinaries_1
        *) echo 1 ;;
    esac
}

# Get a human-readable name for a script
script_display_name() {
    local script="$1"
    # Custom display names
    case "$script" in
        # MON - Poker
        pokerth.sh)            echo "Texas hold 'em"; return ;;
        pokerIQ/run.sh)        echo "poker with analysis"; return ;;
        pokerStove.sh)         echo "Texas hold 'em analysis"; return ;;
        generalPokerEvaluator.sh) echo "general analysis"; return ;;
        bracelets.sh)          echo "casino"; return ;;
        # TUE - Historical Flight Sim
        FS9/fs9.sh)            echo "historical civilian"; return ;;
        SDOE/WWI_SDOE.sh)      echo "WWI"; return ;;
        SDOE/WWII_SDOE.sh)     echo "WWII"; return ;;
        # WED - Chess
        nibbler.sh)            echo "neural net engine"; return ;;
        scid.sh)               echo "traditional engine"; return ;;
        banksiaGui.sh)         echo "neural net, stats displays"; return ;;
        chessmaster/chessmaster.sh) echo "training"; return ;;
        openingRepertoire/run_opening_repertoire.sh) echo "opening helper"; return ;;
        # THU - Sim Racing
        gpl.sh)                echo "grand prix"; return ;;
        speedDreams.sh)        echo "simple, physics displays"; return ;;
        NR2003/NR2003.sh)      echo "stock car"; return ;;
        rFactor/rFactor.sh)    echo "advanced"; return ;;
        # FRI - Duplicate Bridge
        bcalc.sh)              echo "double dummy calculator"; return ;;
        benBridge/run.sh)      echo "tensorflow bridge"; return ;;
        mathQuiz/run.sh)       echo "mental math training"; return ;;
        dual_nback/run.sh)     echo "memory training"; return ;;
        wBridge5.sh)           echo "strong, simple GUI"; return ;;
        qplus.sh)              echo "strong, advanced GUI"; return ;;
        bb12/bb12.sh)          echo "simple"; return ;;
        # SAT - Modern Flight Sim
        freeFalcon.sh)         echo "combat"; return ;;
        FalconAF.sh)           echo "simple combat"; return ;;
        BMS432/BMS432.sh)      echo "advanced combat"; return ;;
        BMS435/BMS435.sh)      echo "very advanced"; return ;;
        CFL/CFL.sh)            echo "CFL"; return ;;
        republic/republic.sh)  echo "psychohistory"; return ;;
        # SUN - Go
        run_katrain.sh)        echo "graphics and training"; return ;;
        q5go.sh)               echo "board with training"; return ;;
        sabaki.sh)             echo "polished board"; return ;;
        igowin.sh)             echo "measure rating"; return ;;
        goreviewpartner.sh)    echo "analysis"; return ;;
    esac
    local name="${script##*/}"
    name="${name%.sh}"
    name="${name%.py}"
    # For run.sh / run_*.sh, use the parent directory name instead
    case "$name" in
        run|run_*) name="${script%%/*}" ;;
    esac
    echo "$name"
}

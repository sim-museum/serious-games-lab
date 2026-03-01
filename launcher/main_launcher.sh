#!/usr/bin/env bash
# main_launcher.sh - Dynamic game launcher menu for Serious Games Lab
#
# 3-level menu:
#   Level 1: Day of week + theme
#   Level 2: Games for selected day (FlightGear collapsed to single entry)
#   Level 3: FlightGear scenario picker (if FlightGear selected)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/scores.sh"

# --- Pre-flight checks ---

check_dependencies() {
    if [[ ! -f "$DEPS_MARKER" ]]; then
        echo ""
        msg_warn "System dependencies have not been installed yet."
        echo ""
        echo "  Run:  sudo ./scripts/install_dependencies.sh"
        echo ""
        read -rp "Continue without installing dependencies? (y/N): " reply
        if [[ ! "$reply" =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi
}

check_nvidia_32bit() {
    local nvidia_ver
    nvidia_ver=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1 || true)
    if [[ -n "$nvidia_ver" ]] && ! dpkg -s "libnvidia-gl-${nvidia_ver}:i386" &>/dev/null 2>&1; then
        echo ""
        msg_warn "NVIDIA driver $nvidia_ver detected but 32-bit OpenGL library is missing."
        echo "  Wine games will run with software rendering (very slow)."
        echo ""
        echo "  Fix:  sudo apt install libnvidia-gl-${nvidia_ver}:i386"
        echo ""
    fi
}

check_binaries() {
    local has_any_wp=false
    for day in "${DAY_ORDER[@]}"; do
        if compgen -G "$REPO_ROOT/$day/WP" "$REPO_ROOT/$day/*/WP" >/dev/null 2>&1; then
            has_any_wp=true
            break
        fi
    done
    if [[ "$has_any_wp" == false ]]; then
        echo ""
        msg_warn "No binary game data installed yet."
        echo "  Source-only games are still available."
        echo "  To install binaries: place sglBinaries_*.tar.gz in downloads/"
        echo "  then run: ./launcher/install_binaries.sh"
        echo ""

        local pending=0
        for f in "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz; do
            [[ -f "$f" ]] || continue
            local base
            base="$(basename "$f")"
            if [[ ! -f "$DOWNLOADS_DIR/.extracted_${base}" ]]; then
                pending=1
                break
            fi
        done

        if [[ $pending -eq 1 ]]; then
            echo "  Unextracted archives detected in downloads/."
            read -rp "  Run install_binaries.sh now? (Y/n): " reply
            if [[ ! "$reply" =~ ^[Nn]$ ]]; then
                "$SCRIPT_DIR/install_binaries.sh"
            fi
        fi
    else
        for f in "$DOWNLOADS_DIR"/sglBinaries_*.tar.gz; do
            [[ -f "$f" ]] || continue
            local base
            base="$(basename "$f")"
            if [[ ! -f "$DOWNLOADS_DIR/.extracted_${base}" ]]; then
                msg_info "New archive detected: $base"
                read -rp "  Extract it now? (Y/n): " reply
                if [[ ! "$reply" =~ ^[Nn]$ ]]; then
                    "$SCRIPT_DIR/install_binaries.sh" "$f"
                fi
            fi
        done
    fi
}

# Check if any sglBinaries have been extracted; if so, ensure Wine, Lutris,
# and wine runners are installed.  Runs once per machine (creates a marker).
ensure_wine() {
    # Only relevant if at least one sglBinaries archive has been extracted
    local has_extracted=false
    for marker in "$DOWNLOADS_DIR"/.extracted_sglBinaries_*.tar.gz; do
        [[ -f "$marker" ]] && { has_extracted=true; break; }
    done
    $has_extracted || return 0

    # Skip if Wine is already usable (system wine OR a Lutris wine runner)
    if command -v wine &>/dev/null; then
        # Wine is installed — now ensure Lutris wine runners are set up too
        ensure_wine_runners
        return 0
    fi

    echo ""
    msg_warn "Binary game data is installed but Wine is not available."
    echo "  Wine is required to run Windows-based games."
    echo ""
    msg_info "Installing Wine, Lutris, and wine runners..."
    echo ""

    # Enable 32-bit architecture
    sudo dpkg --add-architecture i386

    # Update package lists
    sudo apt-get update

    # Install Wine
    sudo apt-get install -y \
        wine wine32:i386 wine64 winetricks

    # Install 32-bit graphics/audio/font libraries needed by Wine games
    sudo apt-get install -y \
        libgl1-mesa-dri:i386 \
        libgl1:i386 \
        mesa-vulkan-drivers \
        mesa-vulkan-drivers:i386 \
        libvulkan1 \
        libvulkan1:i386 \
        vulkan-tools \
        libpulse0:i386 \
        libasound2-plugins:i386 \
        libsdl2-2.0-0:i386 \
        fonts-wine \
        fonts-liberation \
        fonts-dejavu-core \
        cabextract p7zip-full unzip xdg-utils

    # Install NVIDIA 32-bit OpenGL if applicable
    local nvidia_ver
    nvidia_ver=$(dpkg -l 2>/dev/null | grep -oP 'nvidia-driver-\K[0-9]+' | head -1 || true)
    if [[ -n "$nvidia_ver" ]] && ! dpkg -s "libnvidia-gl-${nvidia_ver}:i386" &>/dev/null; then
        sudo apt-get install -y "libnvidia-gl-${nvidia_ver}:i386" || true
    fi

    # Install Lutris
    sudo apt-get install -y lutris || true

    # Install bundled .deb packages from sglBinaries_1 (if present)
    for deb in "$REPO_ROOT"/libssl*.deb "$REPO_ROOT"/libzip*.deb; do
        if [[ -f "$deb" ]]; then
            msg_info "Installing $(basename "$deb") ..."
            sudo dpkg -i "$deb" || true
        fi
    done

    if command -v wine &>/dev/null; then
        msg_ok "Wine installed successfully."
    else
        msg_error "Wine installation failed. Install manually: sudo apt install wine"
    fi

    # Set up wine runners
    ensure_wine_runners
}

# Install Lutris wine runners (non-interactive version of setup_lutris.sh)
ensure_wine_runners() {
    local csv="$REPO_ROOT/config/wine_runners.csv"
    local runners_dir="$HOME/.local/share/lutris/runners/wine"
    local marker="$DOWNLOADS_DIR/.wine_runners_installed"

    [[ -f "$csv" ]] || return 0
    [[ -f "$marker" ]] && return 0

    mkdir -p "$runners_dir"

    # Extract unique non-empty runners from CSV (skip header, column 2)
    local -a runners=()
    while IFS=',' read -r _ runner _; do
        [[ -n "$runner" ]] && runners+=("$runner")
    done < <(tail -n +2 "$csv")

    # Deduplicate
    local -A seen=()
    local -a unique_runners=()
    for r in "${runners[@]}"; do
        if [[ -z "${seen[$r]:-}" ]]; then
            seen[$r]=1
            unique_runners+=("$r")
        fi
    done

    local -a missing=()
    for runner in "${unique_runners[@]}"; do
        [[ -d "$runners_dir/$runner" ]] || missing+=("$runner")
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        touch "$marker"
        return 0
    fi

    echo ""
    msg_info "Installing ${#missing[@]} Lutris wine runner(s)..."

    local failed=0
    for runner in "${missing[@]}"; do
        local url asset base arch_suffix
        asset="wine-${runner}.tar.xz"
        base="$runner"
        base="${base%-x86_64}"
        base="${base%-i686}"

        if [[ "$runner" == *GE-Proton* ]]; then
            local tag="${base#lutris-}"
            url="https://github.com/GloriousEggroll/wine-ge-custom/releases/download/${tag}/${asset}"
        elif [[ "$runner" == *fshack* ]]; then
            local tag="${base//-fshack/}"
            url="https://github.com/lutris/wine/releases/download/${tag}/${asset}"
        else
            local tag="$base"
            url="https://github.com/lutris/wine/releases/download/${tag}/${asset}"
        fi

        echo "  Downloading: $(basename "$url")"
        local tmpfile
        tmpfile="$(mktemp /tmp/runner-XXXXXX.tar.xz)"
        if curl -fSL --progress-bar -o "$tmpfile" "$url" 2>/dev/null; then
            tar -xJf "$tmpfile" -C "$runners_dir/" 2>/dev/null
            if [[ -d "$runners_dir/$runner" ]]; then
                msg_ok "  $runner"
            else
                msg_warn "  $runner extracted but directory name differs"
            fi
        else
            msg_warn "  Failed to download $runner"
            ((failed++)) || true
        fi
        rm -f "$tmpfile"
    done

    if [[ $failed -eq 0 ]]; then
        touch "$marker"
        msg_ok "All wine runners installed."
    else
        msg_warn "$failed runner(s) failed. Re-run launcher to retry, or run scripts/setup_lutris.sh"
    fi
}

# --- Data loading ---

# Associative arrays: DAY_GAMES[day] = newline-separated "script|display|available|type|archive"
declare -A DAY_GAMES
# FlightGear scenarios per day: DAY_FG[day] = newline-separated "script|display|available"
declare -A DAY_FG
# Non-violent options per day: DAY_NV[day] = newline-separated "script|display|available|type|archive"
declare -A DAY_NV

load_games() {
    DAY_GAMES=()
    DAY_FG=()
    DAY_NV=()

    local -a header
    local line_num=0

    while IFS= read -r line; do
        ((line_num++)) || true
        if [[ $line_num -eq 1 ]]; then
            IFS=',' read -ra header <<< "$line"
            continue
        fi

        IFS=',' read -ra row <<< "$line"
        for col in "${!row[@]}"; do
            local script="${row[$col]}"
            [[ -z "$script" ]] && continue
            local day="${header[$col]}"

            local available="yes"
            local type_label="binary"

            if is_source_game "$script"; then
                type_label="source"
                if ! script_exists "$day" "$script"; then
                    available="no"
                fi
            else
                if ! script_exists "$day" "$script"; then
                    available="no"
                elif ! has_binary_data "$day" "$script"; then
                    available="missing_data"
                fi
            fi

            local display archive
            display="$(script_display_name "$script")"
            archive="$(game_archive "$script")"

            # Separate FlightGear scenarios and non-violent games from regular games
            if [[ "$script" == flightgear/*.sh ]]; then
                DAY_FG["$day"]+="$script|$display|$available"$'\n'
            elif is_nonviolent_game "$script"; then
                DAY_NV["$day"]+="$script|$display|$available|$type_label|$archive"$'\n'
            else
                DAY_GAMES["$day"]+="$script|$display|$available|$type_label|$archive"$'\n'
            fi
        done
    done < "$CSV_FILE"
}

# --- FlightGear display names ---

fg_display_name() {
    local script="$1"
    local base="${script##*/}"
    base="${base%.sh}"
    case "$base" in
        basicFlightTraining)       echo "Basic Flight Training (Cessna)" ;;
        training_spitfire)         echo "Spitfire" ;;
        training_me109)            echo "Me 109" ;;
        training_p51d_startInAir)  echo "P-51D Mustang" ;;
        training_F86)              echo "F-86 Sabre" ;;
        training_MiG15)            echo "MiG-15" ;;
        training_F16)              echo "F-16 Falcon" ;;
        training_MiG21)            echo "MiG-21" ;;
        *)                         echo "$base" ;;
    esac
}

# --- Menu functions ---

display_top_menu() {
    echo ""
    echo -e "${BOLD}=============================================="
    echo "  Serious Games Lab"
    echo -e "==============================================${NC}"
    echo ""
    echo "  average score for last 7 days: $average_score"
    echo ""

    for i in "${!DAY_ORDER[@]}"; do
        local day="${DAY_ORDER[$i]}"
        local theme="${DAY_THEMES[$i]}"
        local num=$((i + 1))
        printf "    %d)  ${CYAN}${BOLD}%s${NC} - %s\n" "$num" "$day" "$theme"
    done
    echo ""
    echo "    8)  Export Scores and game output files"
    echo "    9)  Read Documentation"
    echo "   10)  Reset Scores"
    echo "   11)  Exit"
}

display_day_menu() {
    local day="$1"
    local day_idx="$2"
    local theme="${DAY_THEMES[$day_idx]}"
    local day_name="${DAY_NAMES[$day_idx]}"

    echo ""
    echo -e "${BOLD}=============================================="
    echo -e "  ${day} - ${day_name}: ${theme}"
    echo -e "==============================================${NC}"
    echo ""
    echo "  Current Score: ${scores[$day_idx]}"
    echo ""

    # Sort games into three groups by data dependency (matching CSV order):
    #   1. Source games (no sglBinaries needed) — includes FlightGear
    #   2. sglBinaries_1 games
    #   3. sglBinaries_2-7 games
    local -a source_games=() bin1_games=() bin2plus_games=()

    if [[ -n "${DAY_GAMES[$day]:-}" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            IFS='|' read -r script display available type_label archive <<< "$entry"
            if is_source_game "$script"; then
                source_games+=("$entry")
            elif [[ "$archive" -le 1 ]]; then
                bin1_games+=("$entry")
            else
                bin2plus_games+=("$entry")
            fi
        done <<< "${DAY_GAMES[$day]}"
    fi

    local has_fg=""
    if [[ -n "${DAY_FG[$day]:-}" ]]; then
        has_fg=1
    fi

    local has_nv=""
    if [[ -n "${DAY_NV[$day]:-}" ]]; then
        has_nv=1
    fi

    # Build menu entries and display
    DAY_MENU_ENTRIES=()
    local -i idx=0

    # Helper to print one entry
    print_entry() {
        local script="$1" display="$2" available="$3" type_label="$4" archive="$5"
        ((idx++)) || true
        DAY_MENU_ENTRIES+=("game|$script|$display|$available|$type_label")
        case "$available" in
            yes)
                printf "    ${GREEN}%2d)${NC} %s\n" "$idx" "$display"
                ;;
            missing_data)
                printf "    ${YELLOW}%2d) %s [sglBinaries_%s]${NC}\n" "$idx" "$display" "$archive"
                ;;
            no)
                printf "    ${RED}%2d) %s [not installed]${NC}\n" "$idx" "$display"
                ;;
        esac
    }

    # Group 1: Source games (no sglBinaries needed)
    # FlightGear (collapsed into single "civilian flight" entry) comes first
    if [[ -n "$has_fg" ]]; then
        ((idx++)) || true
        DAY_MENU_ENTRIES+=("flightgear|||yes|source")
        printf "    ${GREEN}%2d)${NC} %s\n" "$idx" "civilian flight"
    fi
    for entry in "${source_games[@]+"${source_games[@]}"}"; do
        [[ -z "$entry" ]] && continue
        IFS='|' read -r script display available type_label archive <<< "$entry"
        print_entry "$script" "$display" "$available" "$type_label" "$archive"
    done

    # Group 2: sglBinaries_1 games
    for entry in "${bin1_games[@]+"${bin1_games[@]}"}"; do
        IFS='|' read -r script display available type_label archive <<< "$entry"
        print_entry "$script" "$display" "$available" "$type_label" "1"
    done

    # Group 3: sglBinaries_2-7 games
    for entry in "${bin2plus_games[@]+"${bin2plus_games[@]}"}"; do
        IFS='|' read -r script display available type_label archive <<< "$entry"
        print_entry "$script" "$display" "$available" "$type_label" "$archive"
    done

    # Non-violent options submenu (after all regular games)
    if [[ -n "$has_nv" ]]; then
        ((idx++)) || true
        DAY_MENU_ENTRIES+=("nonviolent|||yes|binary")
        printf "    ${GREEN}%2d)${NC} %s\n" "$idx" "Non-violent options"
    fi

    # Score entries before Back
    echo ""
    ((idx++)) || true
    DAY_MENU_ENTRIES+=("calc_score||||")
    printf "    %2d) How to Calculate Score\n" "$idx"

    ((idx++)) || true
    DAY_MENU_ENTRIES+=("enter_score||||")
    printf "    %2d) Enter New Score\n" "$idx"

    # Back option as last numbered entry
    ((idx++)) || true
    DAY_MENU_ENTRIES+=("back||||")
    echo ""
    printf "    %2d) Back\n" "$idx"
}

display_fg_menu() {
    local day="$1"
    local day_idx="$2"
    local theme="${DAY_THEMES[$day_idx]}"

    echo ""
    echo -e "${BOLD}=============================================="
    echo -e "  ${day} - FlightGear Scenarios"
    echo -e "==============================================${NC}"
    echo ""

    FG_MENU_ENTRIES=()
    local -i idx=0

    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        IFS='|' read -r script display available <<< "$entry"
        ((idx++)) || true

        local fg_name
        fg_name="$(fg_display_name "$script")"
        FG_MENU_ENTRIES+=("$script|$fg_name|$available")

        case "$available" in
            yes)
                printf "    ${GREEN}%2d)${NC} %s\n" "$idx" "$fg_name"
                ;;
            no)
                printf "    ${RED}%2d) %s [not installed]${NC}\n" "$idx" "$fg_name"
                ;;
        esac
    done <<< "${DAY_FG[$day]}"

    # Back option as last numbered entry
    ((idx++)) || true
    FG_MENU_ENTRIES+=("back||")
    echo ""
    printf "    %2d) Back\n" "$idx"
}

display_nv_menu() {
    local day="$1"
    local day_idx="$2"

    echo ""
    echo -e "${BOLD}=============================================="
    echo -e "  ${day} - Non-violent Options"
    echo -e "==============================================${NC}"
    echo ""

    NV_MENU_ENTRIES=()
    local -i idx=0

    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        IFS='|' read -r script display available type_label archive <<< "$entry"
        ((idx++)) || true
        NV_MENU_ENTRIES+=("$script|$display|$available|$archive")

        case "$available" in
            yes)
                printf "    ${GREEN}%2d)${NC} %s\n" "$idx" "$display"
                ;;
            missing_data)
                printf "    ${YELLOW}%2d) %s [sglBinaries_%s]${NC}\n" "$idx" "$display" "$archive"
                ;;
            no)
                printf "    ${RED}%2d) %s [not installed]${NC}\n" "$idx" "$display"
                ;;
        esac
    done <<< "${DAY_NV[$day]}"

    # Back option
    ((idx++)) || true
    NV_MENU_ENTRIES+=("back|||")
    echo ""
    printf "    %2d) Back\n" "$idx"
}

# --- Kill leftover wine processes ---

# Runs at startup every time the launcher is invoked. If a previous game
# hung or didn't close cleanly, this cleans up before showing the menu.
kill_stale_wine() {
    # Only kill wine processes whose WINEPREFIX is inside REPO_ROOT.
    # This avoids killing unrelated wine applications (installers, other games).
    local all_pids
    all_pids=$(pgrep -u "$(id -u)" -x 'wine|wine64|wine-preloader|wine64-preloader|wineserver' 2>/dev/null) || true
    [[ -z "$all_pids" ]] && return 0

    local sgl_pids=()
    local pid
    for pid in $all_pids; do
        local prefix=""
        # Read WINEPREFIX from the process environment
        if [[ -r "/proc/$pid/environ" ]]; then
            prefix=$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null \
                     | grep '^WINEPREFIX=' | head -1 | cut -d= -f2-)
        fi
        # Kill if WINEPREFIX is inside our repo, or if we can't determine it
        # (default ~/.wine is not ours, so skip those)
        if [[ -n "$prefix" && "$prefix" == "$REPO_ROOT"/* ]]; then
            sgl_pids+=("$pid")
        fi
    done

    if [[ ${#sgl_pids[@]} -gt 0 ]]; then
        msg_warn "Killing leftover SGL wine processes..."
        kill "${sgl_pids[@]}" 2>/dev/null || true
        sleep 1
        # Check if any survived and force-kill
        local remaining=()
        for pid in "${sgl_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                remaining+=("$pid")
            fi
        done
        if [[ ${#remaining[@]} -gt 0 ]]; then
            kill -9 "${remaining[@]}" 2>/dev/null || true
        fi
        msg_ok "Done."
    fi
}

# --- Game runner ---

run_game() {
    local day="$1"
    local script="$2"
    local day_dir="$REPO_ROOT/$day"

    echo ""
    msg_info "Launching: $day/$script"
    echo ""

    (
        set +euo pipefail
        export REPO_ROOT="$REPO_ROOT"
        export SGL_GAME_SCRIPT="$script"
        FG_BIN="$HOME/.local/share/flightgear/bin"
        [[ -d "$FG_BIN" ]] && export PATH="$FG_BIN:$PATH"
        cd "$day_dir"
        if [[ -f "$REPO_ROOT/launcher/lib/wine_runner.sh" ]]; then
            source "$REPO_ROOT/launcher/lib/wine_runner.sh"
        fi
        if [[ "$script" == *.py ]]; then
            if [[ -z "${VIRTUAL_ENV:-}" ]]; then
                echo "Error: refusing to run $script outside a Python venv." >&2
                echo "Add a venv-activating entry in launcher/run_game.sh for this script." >&2
                exit 1
            fi
            python3 "$script"
        else
            bash "$script"
        fi
    )
}

# --- Main loop ---

main() {
    kill_stale_wine
    check_dependencies
    check_nvidia_32bit
    check_binaries
    ensure_wine
    load_games
    read_scores

    while true; do
        display_top_menu

        echo ""
        read -rp "  Select: " choice

        if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > 11 )); then
            msg_error "Invalid choice: $choice"
            continue
        fi

        # 8 = Export Scores
        if (( choice == 8 )); then
            export_scores
        fi

        # 9 = Read Documentation
        if (( choice == 9 )); then
            read_documentation
            continue
        fi

        # 10 = Reset Scores
        if (( choice == 10 )); then
            reset_scores
        fi

        # 11 = Exit
        if (( choice == 11 )); then
            echo ""
            echo "Goodbye!"
            exit 0
        fi

        local day_idx=$((choice - 1))
        local day="${DAY_ORDER[$day_idx]}"

        # --- Level 2: Day menu ---
        while true; do
            display_day_menu "$day" "$day_idx"

            echo ""
            read -rp "  Select: " game_choice

            if ! [[ "$game_choice" =~ ^[0-9]+$ ]] || (( game_choice < 1 || game_choice > ${#DAY_MENU_ENTRIES[@]} )); then
                msg_error "Invalid choice: $game_choice"
                echo ""
                read -rp "Press Enter to continue..." _
                continue
            fi

            local entry="${DAY_MENU_ENTRIES[$((game_choice-1))]}"
            IFS='|' read -r entry_type script display available type_label <<< "$entry"

            # Back
            if [[ "$entry_type" == "back" ]]; then
                break
            fi

            # Score documentation
            if [[ "$entry_type" == "calc_score" ]]; then
                show_day_score_doc "$day"
                continue
            fi

            # Enter new score
            if [[ "$entry_type" == "enter_score" ]]; then
                enter_score "$day" "$day_idx"
                echo ""
                read -rp "Press Enter to continue..." _
                continue
            fi

            if [[ "$entry_type" == "flightgear" ]]; then
                # --- Level 3: FlightGear submenu ---
                while true; do
                    display_fg_menu "$day" "$day_idx"

                    echo ""
                    read -rp "  Select: " fg_choice

                    if ! [[ "$fg_choice" =~ ^[0-9]+$ ]] || (( fg_choice < 1 || fg_choice > ${#FG_MENU_ENTRIES[@]} )); then
                        msg_error "Invalid choice: $fg_choice"
                        echo ""
                        read -rp "Press Enter to continue..." _
                        continue
                    fi

                    local fg_entry="${FG_MENU_ENTRIES[$((fg_choice-1))]}"
                    IFS='|' read -r fg_script fg_display fg_available <<< "$fg_entry"

                    # Back
                    if [[ "$fg_script" == "back" ]]; then
                        break
                    fi

                    if [[ "$fg_available" == "no" ]]; then
                        msg_error "$fg_display is not installed."
                    else
                        run_game "$day" "$fg_script" || true
                    fi

                    echo ""
                    read -rp "Press Enter to continue..." _
                done
            elif [[ "$entry_type" == "nonviolent" ]]; then
                # --- Level 3: Non-violent options submenu ---
                while true; do
                    display_nv_menu "$day" "$day_idx"

                    echo ""
                    read -rp "  Select: " nv_choice

                    if ! [[ "$nv_choice" =~ ^[0-9]+$ ]] || (( nv_choice < 1 || nv_choice > ${#NV_MENU_ENTRIES[@]} )); then
                        msg_error "Invalid choice: $nv_choice"
                        echo ""
                        read -rp "Press Enter to continue..." _
                        continue
                    fi

                    local nv_entry="${NV_MENU_ENTRIES[$((nv_choice-1))]}"
                    IFS='|' read -r nv_script nv_display nv_available nv_archive <<< "$nv_entry"

                    # Back
                    if [[ "$nv_script" == "back" ]]; then
                        break
                    fi

                    if [[ "$nv_available" == "no" ]]; then
                        msg_error "$nv_display is not installed."
                    elif [[ "$nv_available" == "missing_data" ]]; then
                        msg_warn "$nv_display needs binary data. Install sglBinaries_${nv_archive} first."
                    else
                        run_game "$day" "$nv_script" || true
                    fi

                    echo ""
                    read -rp "Press Enter to continue..." _
                done
            elif [[ "$available" == "no" ]]; then
                msg_error "$display is not installed."
                echo ""
                read -rp "Press Enter to continue..." _
            elif [[ "$available" == "missing_data" ]]; then
                msg_warn "$display needs sglBinaries_${archive}. Place sglBinaries_${archive}.tar.gz in downloads/ and run launcher/install_binaries.sh"
                echo ""
                read -rp "Press Enter to continue..." _
            else
                run_game "$day" "$script" || true
                echo ""
                read -rp "Press Enter to continue..." _
            fi
        done
    done
}

main "$@"

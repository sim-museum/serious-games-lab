# Script Outline:
# 1. Sets Wine prefix to the "WP" folder in the current directory.
# 2. Checks if Chessmaster executable exists and runs it if found, displaying optional scripts.
# 3. Moves installation files to the "INSTALL" directory.
# 4. Checks if Chessmaster installation files are present; if not, prompts the user to download them.
# 5. If ISO file is not found, unpacks Chessmaster ISO file and provides instructions for mounting.
# 6. If setup.exe is found in the mounted ISO directory, provides installation instructions, runs setup.exe using Wine, applies patch, and displays completion message.
# 7. End of script.
#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set the Wine prefix to the current directory's "WP" folder.
# WINEARCH is intentionally unset: wine 10+ on Ubuntu 26.04 ships in wow64
# mode and rejects WINEARCH=win32, which silently broke prefix creation.
export WINEPREFIX="$PWD/WP"
INSTALL_DIR="$PWD/INSTALL"
# Set Windows XP mode silently (no GUI)
mkdir -p "$WINEPREFIX"
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# Locate Chessmaster.exe wherever it landed. wow64 prefixes (default on
# wine 10 / Ubuntu 26.04) install 32-bit apps into "Program Files (x86)";
# pre-wow64 win32 prefixes use "Program Files". Check both so the same
# script works against either layout.
CM_EXE=""
for _pf in "Program Files (x86)" "Program Files"; do
    _cand="$WINEPREFIX/drive_c/$_pf/Ubisoft/Chessmaster Grandmaster Edition/Chessmaster.exe"
    if [ -f "$_cand" ]; then
        CM_EXE="$_cand"
        break
    fi
done

# Check if Chessmaster executable exists
if [ -n "$CM_EXE" ]; then
    CM_DIR="$(dirname "$CM_EXE")"
    CM_USERS_DIR="$CM_DIR/Data/Users"
    SCRIPT_DIR="$PWD"

    # Snapshot existing PGN files and their sizes before launching.
    # This lets us detect both new files and new content appended to
    # cumulative files like "Rated Games.PGN".
    pgn_snapshot=$(mktemp)
    pgn_sizes=$(mktemp)
    find "$CM_USERS_DIR" -name "*.PGN" -o -name "*.pgn" 2>/dev/null | sort > "$pgn_snapshot"
    while IFS= read -r f; do
        echo "$f $(wc -c < "$f" 2>/dev/null || echo 0)" >> "$pgn_sizes"
    done < "$pgn_snapshot"

    # Touch game-started marker for afterGameReport collection
    if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
        touch "$SGL_GAME_STARTED_MARKER"
    fi

    # Capture marker mtime so a concurrent game can't perturb our subdir name.
    REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
    source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
    capture_marker_epoch

    # Launch opening repertoire helper alongside the chess GUI
    WED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    if [[ -x "$WED_DIR/openingRepertoire/run_opening_repertoire.sh" ]]; then
        echo "Launching Opening Repertoire helper..."
        bash "$WED_DIR/openingRepertoire/run_opening_repertoire.sh" &
    fi

    # Navigate to Chessmaster directory and run
    cd "$CM_DIR"
    wine Chessmaster.exe >/dev/null 2>&1

    # Find PGN files created or modified during the game session.
    # For cumulative files (like "Rated Games.PGN") that existed before the
    # session, extract only the newly appended game(s) into a temp file
    # so we don't re-analyze old games.
    pgn_after=$(mktemp)
    find "$CM_USERS_DIR" -name "*.PGN" -o -name "*.pgn" 2>/dev/null | sort > "$pgn_after"
    snapshot_time=$(stat -c %Y "$pgn_snapshot")

    new_pgn_files=""
    # Brand-new files (not in pre-launch snapshot)
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
    done <<< "$(comm -13 "$pgn_snapshot" "$pgn_after")"

    # Modified existing files: extract only content added since snapshot
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
        [[ "$fmod" -le "$snapshot_time" ]] && continue
        # Look up pre-launch size
        pre_size=$(grep -F "$f " "$pgn_sizes" 2>/dev/null | awk '{print $NF}')
        pre_size="${pre_size:-0}"
        cur_size=$(wc -c < "$f" 2>/dev/null || echo 0)
        if [[ "$cur_size" -gt "$pre_size" ]]; then
            # File grew — extract only the new bytes (new games appended)
            new_content=$(mktemp --suffix=.PGN)
            tail -c +"$((pre_size + 1))" "$f" > "$new_content"
            # Only use the extract if it contains a valid PGN header
            if grep -q '^\[Event ' "$new_content" 2>/dev/null; then
                new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$new_content")
            else
                rm -f "$new_content"
                new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
            fi
        else
            new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
        fi
    done < "$pgn_snapshot"
    rm -f "$pgn_snapshot" "$pgn_after" "$pgn_sizes"

    # De-duplicate
    new_pgn_files=$(echo "$new_pgn_files" | sort -u | sed '/^$/d')

    if [[ -n "$new_pgn_files" ]]; then
        echo ""
        echo "Converting and analysing Chessmaster PGN files..."

        # Determine the day directory and write the converted/annotated PGN
        # straight into the timestamped afterGameReport subdir so a
        # concurrent game's collect_after_game_report can't race in.
        day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}/WED"
        report_subdir="$(post_game_subdir "$day_dir" chessmaster)"

        # Set up venv with python-chess for stockfish annotation
        VENV_DIR="$SCRIPT_DIR/../openingRepertoire/venv"
        STOCKFISH="$(command -v stockfish 2>/dev/null || echo /usr/games/stockfish)"

        annotated_files=""
        while IFS= read -r pgn_file; do
            [[ -z "$pgn_file" ]] && continue
            base=$(basename "$pgn_file")
            echo "  Processing: $base"

            # Step 1: Fix Chessmaster hex annotations → standard PGN
            converted=$(mktemp --suffix=.pgn)
            sed 's/\x8b/K/g; s/\x89/Q/g; s/\x86/B/g; s/\x87/N/g; s/\x88/R/g' "$pgn_file" \
                | tr -cd '[:print:]\n\r\t' > "$converted"

            # Step 2: Run Stockfish analysis if venv and engine available.
            # Output lands directly in $report_subdir.
            annotated="$report_subdir/${base%.PGN}.pgn"
            if [[ -d "$VENV_DIR" && -x "$STOCKFISH" ]]; then
                "$VENV_DIR/bin/python3" "$SCRIPT_DIR/stockfish_annotate.py" \
                    "$converted" "$annotated" --engine "$STOCKFISH" --depth 15 \
                    && echo "  Stockfish analysis complete: $(basename "$annotated")" \
                    || { echo "  Stockfish analysis failed, saving converted PGN."; cp "$converted" "$annotated"; }
            else
                echo "  Stockfish or python-chess venv not available, saving converted PGN."
                cp "$converted" "$annotated"
            fi
            rm -f "$converted"
            annotated_files=$(printf '%s\n%s' "$annotated_files" "$annotated")
        done <<< "$new_pgn_files"
        annotated_files=$(echo "$annotated_files" | sed '/^$/d')

        # Add English-language annotations via Claude Code (in-place in $report_subdir)
        source "$SCRIPT_DIR/../claude_annotate_pgn.sh"
        while IFS= read -r pgn_annotated; do
            [[ -z "$pgn_annotated" ]] && continue
            [[ -f "$pgn_annotated" ]] || continue
            claude_annotate_pgn "$pgn_annotated"
        done <<< "$annotated_files"

        echo "PGN files saved to afterGameReport/$(basename "$report_subdir")/"
    fi

    # Sync saved games
    rsync -a "$CM_USERS_DIR/" "$SCRIPT_DIR/savedGames/" 2>/dev/null || true

    restore_marker_epoch
    exit 0
fi

# Check if Chessmaster installation files are present
if [ ! -f "$INSTALL_DIR/Chessmaster-Grandmaster-Edition_Win_EN-FR.zip" ]; then
    # Display instructions for obtaining installation files
    clear
    echo "Chessmaster install files not found in the directory $INSTALL_DIR/"
    echo ""
    echo "Download the following 2 files from the link below:"
    echo "1. Chessmaster-Grandmaster-Edition_Win_EN-FR.zip" 
    echo "2. Chessmaster-Grandmaster-Edition_Patch_Win_EN-FR_patch-v102.exe" 
    echo ""
    echo "Place these files in the $INSTALL_DIR/ directory."
    echo ""
    echo "Then run this script again."
    echo ""
    exit 0
else        
    if [ ! -f "$INSTALL_DIR/itw-cge.iso" ]; then
        # Unpack Chessmaster ISO file
        echo "Unpacking Chessmaster ISO file in $INSTALL_DIR/chessmaster"
        cd "$INSTALL_DIR/"
        unzip Chessmaster-Grandmaster-Edition_Win_EN-FR.zip >/dev/null 2>&1
    fi
    # Auto-mount ISO if not already mounted
    if [ ! -f "$INSTALL_DIR/isoMnt/Chessmaster Grandmaster Edition En/setup.exe" ] && [ -f "$INSTALL_DIR/itw-cge.iso" ]; then
        mkdir -p "$INSTALL_DIR/isoMnt"
        echo "Mounting Chessmaster ISO (requires sudo)..."
        sudo mount -o loop "$INSTALL_DIR/itw-cge.iso" "$INSTALL_DIR/isoMnt" || {
            printf "\nAuto-mount failed. Run manually:\n\nsudo mount -o loop \"%s/itw-cge.iso\" \"%s/isoMnt\"\n\nThen run this script again.\n" "$INSTALL_DIR" "$INSTALL_DIR"
            exit 0
        }
    fi
    if [ -f "$INSTALL_DIR/isoMnt/Chessmaster Grandmaster Edition En/setup.exe" ]; then
        # Navigate to ISO mounted directory
        cd "$INSTALL_DIR/isoMnt/Chessmaster Grandmaster Edition En"
        clear
        # Display installation instructions
        printf "Chessmaster installation instructions:\n\n1. If asked whether to install Mono, do not install it.\n2. Do not install the Adobe PDF reader (clear the checkbox next to Adobe).\n3. After Chessmaster is installed and the update dialog appears, exit from Chessmaster.\n\nPress any key to begin installation.\n\n"
        read replyString
        # Run setup.exe using Wine. Log output so a silent failure is
        # diagnosable rather than masquerading as success.
        WINE_LOG="$INSTALL_DIR/wine-install.log"
        : > "$WINE_LOG"
        wine setup.exe >>"$WINE_LOG" 2>&1
        cd "$INSTALL_DIR/"
        # Re-locate Chessmaster.exe — same wow64-vs-win32 ambiguity as above.
        CM_EXE=""
        for _pf in "Program Files (x86)" "Program Files"; do
            _cand="$WINEPREFIX/drive_c/$_pf/Ubisoft/Chessmaster Grandmaster Edition/Chessmaster.exe"
            if [ -f "$_cand" ]; then
                CM_EXE="$_cand"
                break
            fi
        done
        if [ -z "$CM_EXE" ]; then
            printf "\nChessmaster setup did not complete — Chessmaster.exe is missing.\nSee %s for wine output.\n" "$WINE_LOG"
            exit 1
        fi
        # Install DXVK (D3D → Vulkan translation). The bundled wined3d
        # renders Chessmaster's 3D board via OpenGL and is markedly slow
        # even on modern NVIDIA hardware; DXVK gives a 2–5× speedup.
        # winetricks -q dxvk is idempotent; if already installed it's a no-op.
        echo "Installing DXVK for faster 3D rendering..."
        winetricks -q dxvk >>"$WINE_LOG" 2>&1 || \
            printf "\nWarning: DXVK install failed — Chessmaster will fall back to wined3d (slower). See %s.\n" "$WINE_LOG"
        # Apply patch
        wine Chessmaster-Grandmaster-Edition_Patch_Win_EN-FR_patch-v102.exe >>"$WINE_LOG" 2>&1
        printf "\nInstallation completed. Run this script again to start Chessmaster.\n"
        exit 0
    fi
fi

# End of script


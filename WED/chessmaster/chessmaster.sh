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

# Set the Wine prefix to the current directory's "WP" folder
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
INSTALL_DIR="$PWD/INSTALL"
# Set Windows XP mode silently (no GUI)
mkdir -p "$WINEPREFIX"
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# Check if Chessmaster executable exists
if [ -f "$WINEPREFIX/drive_c/Program Files/Ubisoft/Chessmaster Grandmaster Edition/Chessmaster.exe" ]; then
    CM_DIR="$WINEPREFIX/drive_c/Program Files/Ubisoft/Chessmaster Grandmaster Edition"
    CM_USERS_DIR="$CM_DIR/Data/Users"
    SCRIPT_DIR="$PWD"

    # Snapshot existing PGN files before launching
    pgn_snapshot=$(mktemp)
    find "$CM_USERS_DIR" -name "*.PGN" -o -name "*.pgn" 2>/dev/null | sort > "$pgn_snapshot"

    # Touch game-started marker for afterGamesReport collection
    if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
        touch "$SGL_GAME_STARTED_MARKER"
    fi

    # Launch opening repertoire helper alongside the chess GUI
    WED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    if [[ -x "$WED_DIR/openingRepertoire/run_opening_repertoire.sh" ]]; then
        echo "Launching Opening Repertoire helper..."
        bash "$WED_DIR/openingRepertoire/run_opening_repertoire.sh" &
    fi

    # Navigate to Chessmaster directory and run
    cd "$CM_DIR"
    wine Chessmaster.exe >/dev/null 2>&1

    # Find PGN files created or modified during the game session
    pgn_after=$(mktemp)
    find "$CM_USERS_DIR" -name "*.PGN" -o -name "*.pgn" 2>/dev/null | sort > "$pgn_after"
    new_pgn_files=$(comm -13 "$pgn_snapshot" "$pgn_after")

    # Also check for PGN files modified since game start
    if [[ -f "$pgn_snapshot" ]]; then
        snapshot_time=$(stat -c %Y "$pgn_snapshot")
        while IFS= read -r f; do
            fmod=$(stat -c %Y "$f" 2>/dev/null) || continue
            if [[ "$fmod" -gt "$snapshot_time" ]]; then
                new_pgn_files=$(printf '%s\n%s' "$new_pgn_files" "$f")
            fi
        done < "$pgn_after"
    fi
    rm -f "$pgn_snapshot" "$pgn_after"

    # De-duplicate
    new_pgn_files=$(echo "$new_pgn_files" | sort -u | sed '/^$/d')

    if [[ -n "$new_pgn_files" ]]; then
        echo ""
        echo "Converting and analysing Chessmaster PGN files..."

        # Determine the day directory for afterGamesReport output
        day_dir="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}/WED"

        # Set up venv with python-chess for stockfish annotation
        VENV_DIR="$SCRIPT_DIR/../openingRepertoire/venv"
        STOCKFISH="$(command -v stockfish 2>/dev/null || echo /usr/games/stockfish)"

        while IFS= read -r pgn_file; do
            [[ -z "$pgn_file" ]] && continue
            base=$(basename "$pgn_file")
            echo "  Processing: $base"

            # Step 1: Fix Chessmaster hex annotations → standard PGN
            converted=$(mktemp --suffix=.pgn)
            sed 's/\x8b/K/g; s/\x89/Q/g; s/\x86/B/g; s/\x87/N/g; s/\x88/R/g' "$pgn_file" \
                | tr -cd '[:print:]\n\r\t' > "$converted"

            # Step 2: Run Stockfish analysis if venv and engine available
            annotated="$day_dir/${base%.PGN}.pgn"
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
        done <<< "$new_pgn_files"

        echo "PGN files saved to $day_dir/ for afterGamesReport collection."
    fi

    # Sync saved games
    rsync -a "$CM_USERS_DIR/" "$SCRIPT_DIR/savedGames/" 2>/dev/null || true

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
        # Run setup.exe using Wine
        wine setup.exe >/dev/null 2>&1
        cd "$INSTALL_DIR/"
        # Apply patch
        wine Chessmaster-Grandmaster-Edition_Patch_Win_EN-FR_patch-v102.exe >/dev/null 2>&1
        printf "\nInstallation completed. Run this script again to start Chessmaster.\n"
        exit 0
    fi
fi

# End of script


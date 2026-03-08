#!/bin/bash
# MiG Alley helper: kill, restart, or backup+restart when OCX icons disappear
# after returning from 3D recon view to 2D campaign view.
#
# Usage:
#   migAlleyHelper.sh restart   - Kill + restart (primary use case)
#   migAlleyHelper.sh kill      - Kill only
#   migAlleyHelper.sh backup    - Backup saves, then kill + restart
#   migAlleyHelper.sh status    - Show if Mig.exe is running
#
# Bind "migAlleyHelper.sh restart" to a global keyboard shortcut (e.g. Super+F5)
# for one-key recovery when OCX icons are lost.

cd "$(dirname "${BASH_SOURCE[0]}")"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
GAMEDIR="$WINEPREFIX/drive_c/rowan/mig"
SAVEDIR="$GAMEDIR/SaveGame"
MAX_BACKUPS=5

# Wine runner configuration
LUTRIS_WINE_ROOT="/home/g/.local/share/lutris/runners/wine/lutris-5.21-x86_64"

setup_wine_env() {
    export PATH="$LUTRIS_WINE_ROOT/bin:$PATH"
    export WINE="$LUTRIS_WINE_ROOT/bin/wine"
    export WINELOADER="$LUTRIS_WINE_ROOT/bin/wine"
    export WINESERVER="$LUTRIS_WINE_ROOT/bin/wineserver"
    export LD_LIBRARY_PATH="$LUTRIS_WINE_ROOT/lib64:$LUTRIS_WINE_ROOT/lib"
}

kill_mig() {
    setup_wine_env

    if ! pgrep -xf ".*Mig\.exe.*" &>/dev/null; then
        echo "MiG Alley is not running."
        return 0
    fi

    echo "Killing MiG Alley..."
    "$WINESERVER" -k 2>/dev/null

    # Wait up to 5 seconds for graceful shutdown
    for i in $(seq 1 10); do
        if ! pgrep -xf ".*Mig\.exe.*" &>/dev/null; then
            echo "MiG Alley stopped."
            notify-send "MiG Alley" "Game killed" 2>/dev/null
            return 0
        fi
        sleep 0.5
    done

    # Force kill via wineserver -k9
    echo "Force killing via wineserver..."
    "$WINESERVER" -k9 2>/dev/null
    sleep 1

    # Last resort: directly kill Wine processes for this prefix
    if pgrep -xf ".*Mig\.exe.*" &>/dev/null; then
        echo "Direct kill..."
        pkill -f "explorer /desktop=MigAlley" 2>/dev/null
        pkill -xf ".*Mig\.exe.*" 2>/dev/null
        sleep 1
        "$WINESERVER" -k9 2>/dev/null
    fi

    echo "MiG Alley stopped."
    notify-send "MiG Alley" "Game killed" 2>/dev/null
}

start_mig() {
    setup_wine_env

    # Wait for wineserver to fully exit
    "$WINESERVER" -w 2>/dev/null
    sleep 1

    # Set Windows XP mode
    "$WINE" reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

    # Disable winegstreamer to prevent crash when exiting 3D view
    export WINEDLLOVERRIDES="winegstreamer=d"

    echo "Starting MiG Alley..."
    cd "$GAMEDIR"
    "$WINE" explorer /desktop=MigAlley,1440x1050 "C:\\rowan\\mig\\Mig.exe" &>/dev/null &
    notify-send "MiG Alley" "Game restarted" 2>/dev/null
    echo "MiG Alley started."
}

backup_saves() {
    if [ ! -d "$SAVEDIR" ]; then
        echo "No SaveGame directory found."
        return 1
    fi

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="${SAVEDIR}.backup.${timestamp}"

    cp -r "$SAVEDIR" "$backup_dir"
    echo "Saves backed up to: $(basename "$backup_dir")"
    notify-send "MiG Alley" "Saves backed up ($timestamp)" 2>/dev/null

    # Keep only the most recent backups
    local parent
    parent=$(dirname "$SAVEDIR")
    ls -dt "$parent"/SaveGame.backup.* 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs rm -rf 2>/dev/null
}

show_status() {
    if pgrep -xf ".*Mig\.exe.*" &>/dev/null; then
        echo "MiG Alley is RUNNING"
        local pid
        pid=$(pgrep -xf ".*Mig\.exe.*" | head -1)
        echo "  PID: $pid"
    else
        echo "MiG Alley is NOT running"
    fi

    if [ -f "$SAVEDIR/Auto Save.sav" ]; then
        local age
        age=$(stat -c %Y "$SAVEDIR/Auto Save.sav")
        local now
        now=$(date +%s)
        local diff=$(( (now - age) / 60 ))
        echo "  Last auto-save: ${diff} minutes ago"
    fi

    local backups
    backups=$(ls -d "$(dirname "$SAVEDIR")"/SaveGame.backup.* 2>/dev/null | wc -l)
    echo "  Backups: $backups"
}

case "${1:-}" in
    restart)
        kill_mig
        start_mig
        ;;
    kill)
        kill_mig
        ;;
    backup)
        backup_saves
        kill_mig
        start_mig
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $(basename "$0") {restart|kill|backup|status}"
        echo ""
        echo "  restart  - Kill MiG Alley and restart it"
        echo "  kill     - Kill MiG Alley"
        echo "  backup   - Backup saves, then kill and restart"
        echo "  status   - Show if MiG Alley is running"
        exit 1
        ;;
esac

# Checks if Mig Alley setup exists in the Wine prefix. If found, launches Mig Alley.
# Offers two launch modes:
#   1. Single monitor (default) - virtual desktop hides spurious window, OCX workarounds needed
#   2. Dual monitors (fallback) - no virtual desktop, spurious window goes to 2nd monitor
# Checks if winetricks is installed. If not, displays an error message and exits.
# Checks if Mig Alley setup files exist. If not, provides instructions for mounting the iso and exits.
# Guides the user through Wine configuration for installation.
# Launches Mig Alley and performs post-installation tasks like copying necessary files.
# Finally, launches Mig Alley.

#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# --- Wine runner pin (lutris-fshack-7.2-x86_64, per config/wine_runners.csv) ---
# Use the wine-7.2 fshack runner — confirmed working 2026-04-26 end-to-end in
# both hardware and software rendering modes (Preferences → Rendering in-game).
# wine 4.11 / 5.7 / 6.21 / 7.2-non-fshack all hang or crash; only fshack-7.2
# reaches stable in-flight state. Ubuntu 26.04 ships wine 10 in wow64 mode and
# rejects WINEARCH=win32, so falling through to /usr/bin/wine would silently
# fail every wine call below.
RUNNER_NAME="lutris-fshack-7.2-x86_64"
RUNNER_DIR="$HOME/.local/share/lutris/runners/wine/$RUNNER_NAME"
if [[ ! -x "$RUNNER_DIR/bin/wine" ]]; then
    echo "ERROR: Lutris wine runner '$RUNNER_NAME' not installed at $RUNNER_DIR" >&2
    echo "       Install it: sudo $(cd ../.. && pwd)/install.sh" >&2
    exit 1
fi
export PATH="$RUNNER_DIR/bin:$PATH"
export WINE="$RUNNER_DIR/bin/wine"
export WINELOADER="$RUNNER_DIR/bin/wine"
export WINESERVER="$RUNNER_DIR/bin/wineserver"
export LD_LIBRARY_PATH="$RUNNER_DIR/lib64:$RUNNER_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WINEDLLPATH="$RUNNER_DIR/lib64/wine/x86_64-unix:$RUNNER_DIR/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"

# Mig Alley is a 32-bit Windows app; force a win32 prefix on first creation.
# Safe with the pinned Lutris runner (wine 7.2 fshack, pre-wow64). The wow64
# reject is a system-wine-10 issue only — bypassed because we PATH-prepend
# the runner.
export WINEARCH=win32

# Store commonly used directory paths in variables for readability
export INSTALL_DIR="$PWD/INSTALL"
export WINEPREFIX="$PWD/WP"
mkdir -p "$WINEPREFIX"

# Synchronously wineboot the prefix BEFORE any other wine work. On a fresh
# prefix, `wine reg add` returns before wineserver finishes its implicit
# wineboot — meaning subsequent wine calls (notably `winetricks`, which
# queries %AppData% via `wine cmd.exe`) can race and see an unpopulated
# registry, returning empty and aborting. `wineboot --init` blocks until
# the prefix is fully initialized.
wine wineboot --init >/dev/null 2>&1

# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
# Prevent Wine from grabbing keyboard/mouse exclusively in fullscreen 3D mode
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v GrabFullscreen /t REG_SZ /d N /f &>/dev/null

# Rowan-engine Wine tweaks (mirrors scripts/fix_rowan_games.sh, minus the
# 1024x768 Default virtual desktop — basic mode needs no virtual desktop and
# advanced mode supplies its own via 'wine explorer /desktop=…').
# Decorated=N removes the X11 frame so background clicks don't hit a WM
# minimize/close button. The DirectDraw renderer/surface tweaks reduce the
# Wine-vs-Rowan engine impedance mismatch around exclusive-fullscreen.
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v Decorated /t REG_SZ /d N /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Direct3D" /v DirectDrawRenderer /t REG_SZ /d opengl /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Direct3D" /v OffscreenRenderingMode /t REG_SZ /d fbo /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\DirectDraw" /v DefaultSurfaceType /t REG_SZ /d gdi /f &>/dev/null

# Joystick / DirectInput config — same as FalconAF.sh. Without these, wine 7.2
# fshack maps the Logitech Extreme 3D Pro through xinput's controller-mapper,
# which scrambles the hat switch and Z-axis (twist) — they end up reporting
# as different button/axis indices than the game expects. With Map Controllers=0
# wine passes the raw DInput descriptor through, and the SDL+hidraw paths give
# better hat-switch fidelity than the default udev path.
wine reg add "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\WineBus" \
    /v Start /t REG_DWORD /d 2 /f &>/dev/null
wine reg add "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\WineBus\\Parameters" \
    /v "Enable SDL" /t REG_DWORD /d 1 /f &>/dev/null
wine reg add "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\WineBus\\Parameters" \
    /v "Enable hidraw" /t REG_DWORD /d 1 /f &>/dev/null
wine reg add "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\WineBus\\Parameters" \
    /v "Map Controllers" /t REG_DWORD /d 0 /f &>/dev/null

# Flush the registry to disk before winetricks runs. wineserver buffers reg
# writes in memory until shutdown; winetricks may spawn its own wineserver
# instance and load the registry from disk — if our adds haven't been
# flushed, winetricks sees an incomplete registry and aborts mfc42 install.
wineserver -k 2>/dev/null || true
sleep 1


export MA_ISO="$INSTALL_DIR/MA_iso"

# --- Launch mode selection ---
# Mode is persisted in .migalley_mode (basic or advanced)
MODE_FILE="$PWD/.migalley_mode"

select_mode() {
    echo ""
    echo "=== MiG Alley Launch Mode ==="
    echo ""
    echo "  1. Single monitor (default)"
    echo "     Uses Wine virtual desktop to hide the spurious DirectDraw window."
    echo "     After returning from 3D view, OCX icons may become non-functional."
    echo "     Workaround: click Shape (upper right), resize the window to restore"
    echo "     icons. If fully broken, run: ./migAlleyHelper.sh restart"
    echo "     Then Load Game -> select autosave."
    echo ""
    echo "  2. Dual monitors (fallback if single monitor doesn't work)"
    echo "     Requires dual monitors at the same resolution."
    echo "     The spurious DirectDraw window is pushed to the second monitor,"
    echo "     leaving the 3D view unobstructed on the primary monitor."
    echo "     No workarounds needed."
    echo ""
    while true; do
        read -rp "Select mode (1 or 2) [1]: " choice
        choice="${choice:-1}"
        case "$choice" in
            1) echo "advanced" > "$MODE_FILE"; echo "Mode set to: Single monitor"; return ;;
            2) echo "basic" > "$MODE_FILE"; echo "Mode set to: Dual monitors"; return ;;
            *) echo "Please enter 1 or 2." ;;
        esac
    done
}

# Load saved mode or prompt for selection
if [ -f "$MODE_FILE" ]; then
    MODE=$(cat "$MODE_FILE")
else
    MODE=""
fi

if [[ "$MODE" != "basic" && "$MODE" != "advanced" ]]; then
    select_mode
    MODE=$(cat "$MODE_FILE")
fi

# Allow --select-mode flag to re-choose
if [[ "${1:-}" == "--select-mode" ]]; then
    select_mode
    MODE=$(cat "$MODE_FILE")
fi

launch_mig() {
    # Disable winegstreamer to prevent crash when exiting 3D view
    # winegstreamer=d  → avoids the documented 3D-exit crash
    # ddraw=b;wined3d=b → force the runner's builtin DDraw + wined3d. Must be
    # builtin only because the wine-3.18-built native DLLs that used to ship
    # in INSTALL/"Mig Alley DLL/" hang the loader on every modern wine.
    # Confirmed working on lutris-fshack-7.2-x86_64 in both HW and SW rendering.
    export WINEDLLOVERRIDES="winegstreamer=d;ddraw=b;wined3d=b"
    cd "$WINEPREFIX/drive_c/rowan/mig"

    # Snapshot existing .cam and .sav filenames BEFORE launch.
    # MiG Alley (and the cp loop in this script's install path) touches files
    # in Videos/ and SaveGame/, giving pre-installed replays mtimes that look
    # newer than the game-started marker and trick the afterGameReport
    # collector into moving them. Write the list to a fixed path next to
    # the started-marker so collect_after_game_report (which runs in
    # main_launcher.sh, a parent process) can find it via the filesystem
    # rather than an env var that wouldn't propagate upward.
    local pre_existing_path="${SGL_GAME_STARTED_MARKER:-$WINEPREFIX/.sgl_game_started}.pre_existing"
    {
        find "$WINEPREFIX/drive_c/rowan/mig/Videos" -maxdepth 1 -name "*.cam" -type f \
            -printf '%p\n' 2>/dev/null
        find "$WINEPREFIX/drive_c/rowan/mig/SaveGame" -maxdepth 1 -name "*.sav" -type f \
            -printf '%p\n' 2>/dev/null
    } > "$pre_existing_path"

    if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]]; then
        touch "$SGL_GAME_STARTED_MARKER"
    fi

    if [[ "$MODE" == "advanced" ]]; then
        # Use double-width virtual desktop so the spurious DirectDraw window
        # is pushed to the right half, away from the visible 3D game area.
        wine explorer /desktop=MigAlley,2880x1050 Mig.exe &>/dev/null
    else
        wine Mig.exe &>/dev/null
    fi
    # collect_after_game_report deletes pre_existing_path when it's done.
}

# Check if Mig Alley setup exists in the Wine prefix
if [ -f "$WINEPREFIX/drive_c/rowan/mig/Mig.exe" ]; then
    # ============================================================================
    # EXIT CRASH: null pointer in rstatic.dll (MFC42 window cleanup)
    # ============================================================================
    # Same Rowan engine as Battle of Britain. When exiting the 3D flight view,
    # custom ActiveX controls (rstatic.dll, rbutton.dll, etc.) attempt to access
    # freed MFC42 window handles during cleanup, causing a page fault.
    # This is a bug in the original Rowan engine code, not Wine.
    #
    # IMPACT: If the crash happens during campaign mode, the mission result
    # may not be recorded (the campaign save occurs after the 3D exit).
    #
    # PREVENTION: After a 3D mission, do NOT close the game immediately.
    # Wait for the campaign debrief screen to fully load and the mission
    # result to be recorded before exiting. The crash is triggered by rapid
    # window destruction during the 3D-to-2D transition.
    # ============================================================================
    launch_mig
    exit 0
fi

# ============================================================================
# KNOWN ISSUE: Spurious Window (DirectDraw Overlay Surface)
# ============================================================================
#
# Mig Alley (and Battle of Britain, which shares the same Rowan Software engine)
# exhibits a "spurious window" under Wine: an opaque black rectangle that partially
# overlaps the 3D flight view.
#
# WHAT IT IS:
#   The Rowan engine uses dual rendering:
#     1. DirectDraw primary surface - for 2D UI (menus, HUD, campaign map, OCX controls)
#     2. Direct3D surface - for the 3D flight simulation view
#   On Windows, the DirectDraw primary surface composites transparently over the
#   Direct3D view - the OS handles the layering natively. Under Wine, the DirectDraw
#   surface is rendered as a separate opaque X11 window, appearing as a black box.
#
#   The game loads 13 custom Rowan ActiveX controls (RTabs.ocx, RListBox.ocx,
#   Rbutton.ocx, RCombo.ocx, Redit.ocx, REdtBt.ocx, RJoyCfg.ocx, RRadio.ocx,
#   Rscrlbar.ocx, RSpinBut.ocx, RSpltBar.ocx, RStatic.ocx, RTickBox.ocx) that
#   create Win32 child windows for UI elements.
#
# CUSTOM DLLs (HISTORICAL — DO NOT RE-ENABLE):
#   INSTALL/"Mig Alley DLL/" contains custom-built ddraw.dll, wined3d.dll, and
#   libwine.dll. Strings in libwine.dll show they were built against wine 3.18.
#   They are INCOMPATIBLE with every wine version this repo ships (4.11 through
#   8.0): the engine spins forever on Mig.exe resource remapping during
#   "Loading landscape" and the mission never starts. Removed from the install
#   path 2026-04-25. The earlier "REQUIRED" claim referred to a wine-3.18 era
#   that no longer applies — modern wine's builtin ddraw handles this game's
#   DirectDraw exclusive-fullscreen path.
#
# WORKAROUNDS FOR THE SPURIOUS WINDOW:
#
#   1. Dual monitors at the same resolution (best option - "basic" mode)
#      Wine's DirectDraw positions the overlay surface coordinates beyond the
#      primary display bounds, pushing the spurious window to the second
#      monitor, leaving the 3D view unobstructed on the primary monitor.
#
#   2. Virtual desktop mode (wine explorer /desktop=...) ("advanced" mode)
#      Hides the spurious window, but causes 2D campaign screen icons to
#      become offset after returning from 3D view (recon, mission, etc).
#      The icons are rendered at one position but their click detection
#      areas are at a different position, due to Wine's X11-to-Win32
#      coordinate mapping breaking after DirectDraw mode switches.
#
#      ROOT CAUSE (from source code analysis of SRC/MFC/MAINFRM.CPP,
#      SRC/MFC/RTOOLBAR.CPP, SRC/MFC/RBUTTON.CPP):
#        - OCX controls use GetWindowRect() for positioning
#        - Bitmaps are reloaded via SetDIBitsToDevice() on each WM_PAINT
#        - After 3D exit, Inst3d::RestoreDirectX() -> RecalcLayout() runs
#        - But Wine's virtual desktop coordinate context is stale, so
#          Win32 positions no longer match X11 rendering positions
#        - WM_SIZE / InvalidateRect from external tools cannot fix this
#          because the coordinate bug is in Wine's window management layer
#        - DLL injection (AppInit_DLLs) was tested but the Lutris wine
#          runner (4.11-staging) does not support it
#
#      WORKAROUND:
#        After returning from 3D to 2D campaign view:
#        a) Click "Shape" (upper right) to exit full-screen view
#        b) Resize the window border to refresh icons
#        c) You may get 1-2 icon clicks before they break again;
#           resize again to restore them
#        d) When entering 3D view, ALT+TAB to ensure game has focus
#
#      FALLBACK - migAlleyHelper.sh:
#        If icons are completely non-functional after 3D exit, run:
#          ./migAlleyHelper.sh restart
#        Then Load Game -> select autosave. The game auto-saves before
#        3D missions, so campaign progress is preserved. The helper uses
#        the Lutris wine runner and handles kill/restart automatically.
#
#   3. gamescope compositor - not fully explored, may cause the spurious
#      window to disappear. Shows both surfaces as separate overlapping
#      layers in initial testing.
#
#   4. dgVoodoo2 (DDraw.dll + D3DImm.dll) - bypasses the Wine rendering
#      pathway entirely. In a first attempt, this did not provide colors
#      and textures (black silhouettes for aircraft, black landscape).
#
# WHAT ELSE WAS TRIED AND FAILED:
#   - Wine registry tweaks (DirectDrawRenderer=opengl, OffscreenRenderingMode=fbo,
#     DefaultSurfaceType=gdi) - no effect on spurious window
#   - Removing custom ddraw/wined3d/libwine DLLs (use runner built-in) - game
#     fails to initialize 3D properly, freezes
#   - xdotool/xprop window manipulation - windows vanish from X tree in 3D mode
#   - python-xlib programmatic window hiding - same X tree disappearance issue
#   - Single monitor - spurious window overlaps game window
#
# RESOLUTION:
#   Both games benefit from running at the maximum resolution possible.
#   For Mig Alley, the max resolution appears to be 1440x1050. If you
#   haven't achieved this, ask Claude Code or similar to achieve it for you.
#
# FOR FUTURE DEBUGGING:
#   The fix requires Wine to either:
#   (a) Composite the DirectDraw primary surface transparently over the Direct3D
#       surface (as Windows does natively), rather than creating a separate X11
#       window for it, OR
#   (b) Suppress/hide the DirectDraw primary surface window when Direct3D is
#       rendering in exclusive fullscreen mode
#   The relevant Wine code is in dlls/ddraw/ - specifically how primary surfaces
#   and clipper regions are mapped to X11 windows. See also the detailed analysis
#   in INSTALL/graphicsArtifact.txt and ../BattleOfBritain/battleOfBritain.sh.
#
# SOURCE CODE AVAILABILITY:
#   The source code for both Mig Alley and Battle of Britain is publicly
#   available, which may aid in debugging the DirectDraw/Direct3D compositing
#   issue by understanding the engine's rendering architecture:
#     Mig Alley:         https://github.com/gondur/mig_src
#     Battle of Britain: https://github.com/gondur/BOB_Src
#   A local copy of the Mig Alley source is at ../migAlleySource/
# ============================================================================

# Check if winetricks is installed
if [ ! -f "/usr/bin/winetricks" ]; then
    echo "\nERROR: winetricks not found. This program is needed to install a wine library "
    echo "during Mig Alley installation.  If using Ubuntu 20.04 LTS install winetricks via:"
    echo "sudo apt install -y winetricks\n"
    exit 1
fi

# Check if Mig Alley setup files exist; auto-mount ISO if needed
if [ ! -f "$MA_ISO/setup.EXE" ]; then
    mkdir -p "$MA_ISO"
    if [ -f "$INSTALL_DIR/Mig Alley V1.1.iso" ]; then
        echo "Mounting Mig Alley ISO (requires sudo)..."
        sudo mount -o loop "$INSTALL_DIR/Mig Alley V1.1.iso" "$MA_ISO" || {
            printf "\nAuto-mount failed. Run manually:\n\nsudo mount -o loop \"$INSTALL_DIR/Mig Alley V1.1.iso\" \"$MA_ISO\"\n\nThen run this script again.\n"
            exit 1
        }
    else
        clear
        echo "Mig Alley ISO not found: $INSTALL_DIR/Mig Alley V1.1.iso"
        echo "Place the ISO in the INSTALL directory and run this script again."
        exit 1
    fi
fi

# Install prerequisites — mfc42 is required for the Rowan engine's ActiveX
# OCX controls (rstatic, rbutton, etc). Without it the game crashes ~1s
# after launch. We install in two passes:
#   1. Fast path: if the winetricks cache from a previous run has the inner
#      vcredist.exe, cabextract mfc42 directly. This avoids both winetricks
#      itself (which fails on wine 4.11 fresh prefixes — see (2)) and the
#      VC6RedistSetup.exe wine-launch step (which needs DISPLAY).
#   2. Fallback: full winetricks -q mfc42. wine 4.11's `wineboot --init`
#      doesn't always create %AppData% or HKCU\Volatile Environment\APPDATA,
#      so we pre-create the dir and pre-set the registry value before
#      calling winetricks.
clear
echo "Installing prerequisites (mfc42)..."

VCREDIST_CACHE="$HOME/.cache/winetricks/vcrun6/vcredist.exe"
if [[ -f "$VCREDIST_CACHE" ]]; then
    echo "  Using cached vcredist.exe → cabextract mfc42*.dll into system32"
    cabextract -q "$VCREDIST_CACHE" \
        -d "$WINEPREFIX/drive_c/windows/system32" \
        -F 'mfc42*.dll' 2>/dev/null || true
fi

if [[ ! -f "$WINEPREFIX/drive_c/windows/system32/mfc42.dll" ]]; then
    echo "  No cached vcredist; falling back to winetricks."
    mkdir -p "$WINEPREFIX/drive_c/users/$USER/AppData/Roaming"
    wine reg add "HKEY_CURRENT_USER\\Volatile Environment" /v APPDATA /t REG_SZ \
        /d "C:\\users\\$USER\\AppData\\Roaming" /f &>/dev/null || true
    wineserver -k 2>/dev/null || true
    sleep 1
    winetricks -q mfc42 || true
fi

if [[ ! -f "$WINEPREFIX/drive_c/windows/system32/mfc42.dll" ]]; then
    echo "ERROR: mfc42.dll was not installed into $WINEPREFIX/drive_c/windows/system32/."
    echo "       The Rowan engine's OCX controls need mfc42 — without it, the game"
    echo "       crashes ~1s after launch (black screen flash, then back to shell)."
    echo ""
    echo "       Tried two install paths (cabextract from cache, then winetricks)."
    echo "       Diagnose by running winetricks manually:"
    echo "         WINEPREFIX=\"$WINEPREFIX\" winetricks mfc42"
    echo "       Current DISPLAY=${DISPLAY:-(unset)}"
    exit 1
fi
# Auto-dismiss the bogus "not enough disk space" dialogs from InstallShield.
# The old 32-bit GetDiskFreeSpace() overflows on large modern filesystems,
# producing an absurd "requires 1.6 TB" message.  The dialog appears multiple
# times during install, so keep dismissing it until setup.EXE exits.
(   while true; do
        WID=$(xdotool search --name "^Install$" 2>/dev/null | head -1)
        if [[ -n "$WID" ]]; then
            sleep 0.3
            xdotool windowactivate --sync "$WID" key Tab Tab Return 2>/dev/null
        fi
        sleep 0.5
    done
) &
_DISMISS_PID=$!
wine "$MA_ISO/setup.EXE" &>/dev/null
kill "$_DISMISS_PID" 2>/dev/null; wait "$_DISMISS_PID" 2>/dev/null
clear
echo "Select 'CANCEL' in the DirectX(R) Setup dialog box, then press ENTER to continue."
read -r replyString
clear
echo "When Mig Alley starts, select PREFERENCES and set graphics resolution to 1440x1050."
echo "If 1440x1050 is not listed, use an agent like Claude Code to add it for you."
echo "Higher resolution is better! Max resolution for Mig Alley is 1440x1050."
echo "Set all other graphics options to maximum values."

# Launch Mig Alley and copy necessary files
wine "$INSTALL_DIR/Mig-Alley_Patch_Win_EN_Patch-123/MIG123.EXE" &>/dev/null
wine "$INSTALL_DIR/bdg_migalley_0.85f/BDG_MiGAlley_0.85F.exe" &>/dev/null
cp "$INSTALL_DIR/bdg.txt" "$WINEPREFIX/drive_c/rowan/mig"
cp -r "$MA_ISO/smacker" "$WINEPREFIX/drive_c/rowan/mig"
cp "$INSTALL_DIR/roots.dir" "$WINEPREFIX/drive_c/rowan/mig"
cp "$INSTALL_DIR/SaveGame/"*.* "$WINEPREFIX/drive_c/rowan/mig/SaveGame"
cp "$INSTALL_DIR/Videos/"*.* "$WINEPREFIX/drive_c/rowan/mig/Videos"
cp "$INSTALL_DIR/keys.xml" "$WINEPREFIX/drive_c/rowan/mig/KEYBOARD"

# Custom ddraw.dll/wined3d.dll/libwine.dll in INSTALL/"Mig Alley DLL/" are
# wine-3.18-built (libwine.dll embeds the version string) and break the 3D
# resource loader on every wine we currently bundle (4.11, 5.7, 6.21, 7.2,
# 8.0). With them present the engine spins on Mig.exe resource remap during
# "Loading landscape"; the runner's builtin ddraw + wined3d work better.
# The rsync is intentionally NOT done here. Sync the small `mfc42.dll` only
# so the local copy doesn't shadow the vcrun6-installed one in system32.
rm "$WINEPREFIX/drive_c/rowan/mig/mfc42.dll" &>/dev/null
cd "$WINEPREFIX/drive_c/rowan/mig"

# Launch Mig Alley
launch_mig

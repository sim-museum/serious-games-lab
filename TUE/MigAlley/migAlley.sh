# Checks if Mig Alley setup exists in the Wine prefix. If found, launches Mig Alley.
# Checks the number of connected monitors and prompts the user if not 2.
# Checks if winetricks is installed. If not, displays an error message and exits.
# Checks if Mig Alley setup files exist. If not, provides instructions for mounting the iso and exits.
# Guides the user through Wine configuration for installation.
# Launches Mig Alley and performs post-installation tasks like copying necessary files.
# Finally, launches Mig Alley.

#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Store commonly used directory paths in variables for readability
export INSTALL_DIR="$PWD/INSTALL"
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


export MA_ISO="$INSTALL_DIR/MA_iso"

# Check if Mig Alley setup exists in the Wine prefix
if [ -f "$WINEPREFIX/drive_c/rowan/mig/Mig.exe" ]; then
    # Disable winegstreamer to prevent crash when exiting 3D view
    export WINEDLLOVERRIDES="winegstreamer=d"
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
    cd "$WINEPREFIX/drive_c/rowan/mig"
    wine Mig.exe &>/dev/null
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
# CUSTOM DLLs:
#   The game directory contains custom Wine-built ddraw.dll, wined3d.dll, and
#   libwine.dll (from INSTALL/"Mig Alley DLL/"). These are REQUIRED - removing
#   them causes the game to flash 3D briefly, show the preferences screen, then
#   freeze on a black splash screen. The runner's built-in ddraw cannot properly
#   initialize DirectDraw exclusive fullscreen mode for this game.
#
# WORKAROUNDS FOR THE SPURIOUS WINDOW:
#
#   1. Dual monitors at the same resolution (best option)
#      Wine's DirectDraw positions the overlay surface coordinates beyond the
#      primary display bounds, pushing the spurious window to the second
#      monitor, leaving the 3D view unobstructed on the primary monitor.
#
#   2. Virtual desktop mode (wine explorer /desktop=...)
#      Hides the spurious window, but causes 2D campaign screen icons to
#      disappear (OCX controls position relative to screen origin, not
#      virtual desktop origin). Workaround: when the 2D campaign window
#      appears, immediately click "Shape" at upper right to deselect
#      full-screen view. Now every time you resize the window, the icons
#      will be redrawn and activated - useful if they've disappeared or
#      become inactive. Save the game at this point - return to this
#      snapshot if the campaign 2D window goes full-screen and the icons
#      disappear, as will likely happen if you enter the 3D view to recon
#      a target. When entering 3D view, ALT+TAB to make sure the game
#      window has the focus.
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

# Check the number of connected monitors no longer needed, thanks to Mig Alley DLL files and wine improvements
#numMonitors=$(xrandr -q | grep connected | grep -v disconnected | wc -l)
#if [ "$numMonitors" -ne 2 ]; then
#    echo -e "\nTo avoid graphics glitches, a dual monitor setup is recommended for Mig Alley."
#    echo -e "\n$numMonitors monitors were detected."
#    echo -e "\nTo stop this script and set up dual monitors, press <CTRL> C."
#    echo -e "To continue with your current monitor setup, press Enter\n"
#    read -r replyString
#fi

# Check if winetricks is installed
if [ ! -f "/usr/bin/winetricks" ]; then
    echo "\nERROR: winetricks not found. This program is needed to install a wine library "
    echo "during Mig Alley installation.  If using Ubuntu 20.04 LTS install winetricks via:"
    echo "sudo apt install -y winetricks\n"
    exit 1
fi

# Check if Mig Alley setup files exist
if [ ! -f "$MA_ISO/setup.EXE" ]; then
    clear
    echo "Before you can install Mig Alley, you must mount the Mig Alley iso."
    echo "\nMount the Mig Alley CD-ROM iso using this command:"
    echo "\nsudo mount -o loop $INSTALL_DIR/'Mig Alley V1.1.iso' $MA_ISO\n"
    echo "Then run this script again."
    exit 1
fi

# Install prerequisites
clear
echo "Installing prerequisites..."
winetricks vcrun6 &>/dev/null
wine "$MA_ISO/setup.EXE" &>/dev/null
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

rsync -a "$INSTALL_DIR/Mig Alley DLL/" "$WINEPREFIX/drive_c/rowan/mig/"
rm "$WINEPREFIX/drive_c/rowan/mig/mfc42.dll" &>/dev/null
cd "$WINEPREFIX/drive_c/rowan/mig"

# Launch Mig Alley
wine Mig.exe &>/dev/null



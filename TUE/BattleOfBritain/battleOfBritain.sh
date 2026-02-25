
# Script outline
#    This script checks for the presence of the Battle of Britain installation and Wine version compatibility.
#    If Battle of Britain is installed, it launches the game.
#    If not, it checks the monitor setup for graphics compatibility.
#    If all requirements are met, it proceeds to mount the installation ISO and configures Wine for installation.
#    Once the installation is complete, it applies necessary patches and launches the game.

#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment
setup_wine_runner() {
    local runner_name="lutris-5.7-x86_64"
    local runner_dir="$HOME/.local/share/lutris/runners/wine/$runner_name"
    if [[ -d "$runner_dir" && -x "$runner_dir/bin/wine" ]]; then
        export PATH="$runner_dir/bin:$PATH"
        export WINE="$runner_dir/bin/wine"
        export WINELOADER="$runner_dir/bin/wine"
        export WINESERVER="$runner_dir/bin/wineserver"
        export LD_LIBRARY_PATH="$runner_dir/lib64:$runner_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export WINEDLLPATH="$runner_dir/lib64/wine/x86_64-unix:$runner_dir/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"
    fi
}

# Set up runner unless already configured by the launcher
if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner
fi

# Define variables for readability
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
wine winecfg -v winxp  2>/dev/null 1>/dev/null

export BoB_INSTALL="$PWD/INSTALL"

# Check if BoB is installed
if [ -f "$WINEPREFIX/drive_c/Program Files/Rowan Software/Battle Of Britain/bob.exe" ]; then
    # Disable winegstreamer to prevent crash on video playback
    export WINEDLLOVERRIDES="winegstreamer=d"
    wine start /d "C:\\Program Files\\Rowan Software\\Battle Of Britain" bob.exe 2>/dev/null 1>/dev/null
    exit 0
fi

# ============================================================================
# KNOWN ISSUE: Spurious Window (DirectDraw Overlay Surface)
# ============================================================================
#
# Battle of Britain (and Mig Alley, which shares the same Rowan Software engine)
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
#   The game also loads 13 custom Rowan ActiveX controls (RTabs.ocx, RListBox.ocx,
#   Rbutton.ocx, etc.) that create Win32 child windows for UI elements. These
#   compound the compositing problem under Wine.
#
# OBSERVED BEHAVIOR:
#   - In 3D flight mode, the spurious window covers ~70-80% of the screen
#   - The window disappears from the X11 window tree when DirectDraw takes
#     exclusive fullscreen control, making it impossible to manipulate via
#     xdotool, xprop, or python-xlib
#   - In gamescope compositor, both surfaces are visible as separate layers:
#     a fixed cockpit 2D view (the spurious surface) with the live 3D view
#     overlapping ~70% of it, confirming it IS the game's 2D overlay surface
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
#      Note: on some Wine versions, virtual desktop crashes BoB with a null
#      pointer at 004EA1E9 (DirectInputCreateA call).
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
#     DefaultSurfaceType=gdi) - no effect
#   - xdotool/xprop window manipulation - windows vanish from X tree in 3D mode
#   - python-xlib programmatic window hiding - same X tree disappearance issue
#   - Single monitor with second display disabled - spurious window overlaps game
#
# WINE RUNNER CONSTRAINTS:
#   - lutris-5.7-x86_64: Best overall (fullscreen mode switch, joystick, good FPS)
#     but exhibits the spurious window
#   - lutris-GE-Proton8-26-x86_64: Best joystick support (all axes including
#     twist/throttle) but doesn't do proper DirectDraw exclusive fullscreen mode
#     switches - game renders at low resolution in corner of display
#   - lutris-fshack-7.2-x86_64: Good FPS/textures but severe fullscreen flickering;
#     windowed mode works but limits resolution to 1024x768
#   - Wine 5.7 properly handles DirectDraw exclusive fullscreen mode switches
#     (actually changes monitor resolution), while newer Wine versions don't
#
# RESOLUTION:
#   Both games benefit from running at the maximum resolution possible.
#   For Battle of Britain, the max resolution is limited only by your monitor
#   resolution - 3840x2160 has been achieved. If you haven't achieved this,
#   ask Claude Code or similar to achieve it for you.
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
#   in ../MigAlley/INSTALL/graphicsArtifact.txt which covers the same engine.
#
# SOURCE CODE AVAILABILITY:
#   The source code for both Battle of Britain and Mig Alley is publicly
#   available, which may aid in debugging the DirectDraw/Direct3D compositing
#   issue by understanding the engine's rendering architecture:
#     Battle of Britain: https://github.com/gondur/BOB_Src
#     Mig Alley:         https://github.com/gondur/mig_src
#   A local copy of the Mig Alley source is at ../migAlleySource/
# ============================================================================

# Check number of monitors
#numMonitors=$(xrandr -q | grep connected | grep -v disconnected | wc -l)
#if [ "$numMonitors" -ne 2 ]; then
#    echo " "
#    echo "To avoid graphics glitches, a dual monitor setup is recommended for Battle of Britain."
#    echo " "; echo "$numMonitors monitor(s) detected."; echo " "
#    echo "If using 1 monitor, run ./setWineDisplayResolution.sh, select the graphics"
#    echo "tab, and enable virtual desktop, using your maximum monitor resolution."
#    echo "this will cause many campaign screen 2D icons to disappear, but campaign is"
#    echo "still playable. It has the advantage of allowing 3D view at higher resolution"
#    echo "than 1024x768."
#    echo "To stop this script and set up dual monitors, press <CTRL> C."
#    echo "To continue with your current monitor setup, press Enter"; echo " "
#    read -r replyString
#fi

# Check if BoB installation ISO exists
if [ ! -f "$BoB_INSTALL/BoB_iso/Setup.exe" ]; then
    clear;
#    if wine --version | grep "wine-6.0"; then
#        clear
#        printf "Version 6.0 of wine detected.\nWine version 7 is recommended for installing Battle of Britain.\n\nFrom the ese directory, run \n\n./wine_experimental.sh\n\nto install wine 7.\n\nThen run this script again.\n\n"
#        exit 0
#    fi
    echo "Before you can install Battle of Britain, you must mount the Battle of Britain iso."
    echo " "
    echo "Mount the Battle of Britain CD-ROM iso using this command:"
    echo " "; echo "sudo mount -o loop $PWD/INSTALL/BATTLEOFBRITAIN.iso $PWD/INSTALL/BoB_iso"; echo " "
    echo "Then run this script again."
    exit 1
fi

# Configuration before installation
clear; 
echo "In the Wine configuration dialog box, which appears next, select Windows XP as the Windows version."
echo "Next, select the 'Graphics' tab."
echo "In the Graphics tab, unselect 'Allow the window manager to decorate the windows'" 
echo "Then select OK to continue the installation."; echo " "
echo "Press enter to display the Wine configuration dialog box."
read -r replyString
winecfg 2>/dev/null 1>/dev/null
echo " "; echo "Setting resolution on monitors to maximum resolution to avoid Battle of Britain graphics problems";
./delayedMonitorReset.sh 0
wine "Z:$(echo "$BoB_INSTALL/BoB_iso/Setup.exe" | sed 's|/|\\|g')" 2>/dev/null 1>/dev/null

# Installation instructions
echo "When Battle of Britain starts, select PC CONFIG and set graphics resolutions to 1280x1024 or 1024x768."
echo "Set all other graphics options to maximum values. If the mouse cursor disappears, hold down"
echo "CTRL F6 to show the mouse cursor. To view online documentation, install wine gecko when"
echo "prompted. If asked to wait or force quit, use <ALT> TAB to find this gecko prompt dialog."
echo " "
echo " "; echo "Applying patch 1 of 2"; echo " "
wine "Z:$(echo "$BoB_INSTALL/RR ROWANBOB GRAPHICS MOD/bob_v099.exe" | sed 's|/|\\|g')" 2>/dev/null 1>/dev/null
echo " "; echo "Applying patch 2 of 2"; echo " "
rsync -a "$BoB_INSTALL/RR ROWANBOB GRAPHICS MOD/bobMain/" "$WINEPREFIX/drive_c/Program Files/Rowan Software/Battle Of Britain/"
cp "$BoB_INSTALL/keys.xml" "$WINEPREFIX/drive_c/Program Files/Rowan Software/Battle Of Britain/KEYBOARD"
# skip videos to prevent quartz VMR7 crash under Wine
sed -i 's/SKIP_QUICKVIDEOS=OFF/SKIP_QUICKVIDEOS=ON/g; s/SKIP_VIDEOS=OFF/SKIP_VIDEOS=ON/g' "$WINEPREFIX/drive_c/Program Files/Rowan Software/Battle Of Britain/bdg.txt"
WINEDLLOVERRIDES="winegstreamer=d" wine start /d "C:\\Program Files\\Rowan Software\\Battle Of Britain" bob.exe 2>/dev/null 1>/dev/null


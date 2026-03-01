#!/bin/bash
# Script Outline:
#
# Set the Wine prefix.
# Check if the game executable exists. If yes, run it and display game overview.
# Move the game files if not found.
# Check if the game files are not found. Provide instructions for downloading.
# Check if pro-wsp08.iso file is not found. If not, extract the game files.
# Check if SETUP.exe file is not found. If not, provide instructions for mounting the ISO.
# Display instructions for Wine configuration.
# Install Battle of the Bracelets.

# Check that Wine is available
if ! command -v wine &>/dev/null; then
    echo "Error: Wine is not installed. Install it with:"
    echo "  sudo apt install wine wine32:i386 wine64 winetricks"
    echo "Or re-run the launcher — it will auto-install Wine when sglBinaries are present."
    exit 1
fi

# Set the Wine prefix
export WINEPREFIX=$PWD/WP
export WINEARCH=win32

# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


# Define frequently used directory paths
export game_dir="$WINEPREFIX/drive_c/Program Files/Activision Value/WSOP 2008"
export install_dir="$WINEPREFIX/../INSTALL"

# Check if the game executable exists
if [ -f "$game_dir/WSOPBFTB.exe" ]; then
    cd "$game_dir"
    wine WSOPBFTB.exe &>/dev/null
    cd "$WINEPREFIX/.."

    # Clear the screen and display game overview
    clear
    echo "GAME OVERVIEW"
    echo ""
    echo "World Series of Poker 2008: Battle for the Bracelets features the following gameplay modes: "
    echo ""
    echo "Career - Play through a full calendar of WSOP Events based on the real WSOP held in Las Vegas each year! "
    echo "Also take part in invitational cash games and a Heads Up tournament against the best."
    echo ""
    echo "Multiplayer - Test your skills against other people online in all of the different game types."
    echo ""
    echo "Quickplay and Custom Games - Define your own poker experience from number of players to buy-ins "
    echo "in all of the different game types."
    echo ""
    echo "Training - Learn from the pros, practice your hands and view unlocked video poker tips."
    echo ""
    echo "Note: To select menu options, use the arrow keys on your keyboard or the mouse. Highlight the desired option and press spacebar or click the left mouse button to accept. "
    echo ""
    echo "CONTROLS"
    echo ""
    echo "ESC                  Pause Menu"
    echo "Directional Keys     Control betting interface"
    echo "Spacebar             Confirm"
    echo ""
    echo "CTRL key             Peek at your cards"
    echo "ALT key              Reveal Cards (Online only)"
    echo "                     Pre-move (Online only)"
    echo ""
    echo "Shift key            Poker Tools"
    echo "F2                   Blackjack/Video Poker"
    echo "F1                   Hand Rankings/Help Screen"
    exit 0
fi

# Check if the game files are not found
if [ ! -f "$install_dir/World-Series-of-Poker-2008-Battle-for-the-Bracelets_Win_EN.zip" ]; then
    clear
    printf "World-Series-of-Poker-2008-Battle-for-the-Bracelets_Win_EN.zip files not found in the directory $install_dir\n\n"
    echo "Download the file from this link:"
    echo "https://www.myabandonware.com/game/world-series-of-poker-2008-battle-for-the-bracelets-h4g"
    echo "Place these files in the $install_dir directory."
    echo "Then run this script again."
    exit 0
fi

# Check if pro-wsp08.iso file is not found
if [ ! -f "$install_dir/pro-wsp08.iso" ]; then
    cd "$install_dir"
    unzip World-Series-of-Poker-2008-Battle-for-the-Bracelets_Win_EN.zip
fi    

# Check if SETUP.exe file is not found
if [ ! -f "$install_dir/isoMnt/SETUP.exe" ]; then
    clear
    printf "To install Battle of the Bracelets, run the following command in a terminal:\n\n"
    echo "sudo mount -o loop $install_dir/pro-wsp08.iso $install_dir/isoMnt"
    echo ""
    echo "Then run this script again."
    exit 0     
fi

# Pre-install DirectX 9c via winetricks (the game's bundled DX installer
# fails inside Wine with "An internal system error occurred")
if ! [ -f "$WINEPREFIX/.dx9c_installed" ]; then
    echo "Installing DirectX 9c via winetricks (required by the game)..."
    winetricks -q d3dx9 2>/dev/null
    touch "$WINEPREFIX/.dx9c_installed"
fi

# Install Battle of the Bracelets
cd "$install_dir/isoMnt"
printf "Installing Battle of the Bracelets.\n"
printf "Choose default options. When prompted about DirectX 9c, DECLINE it\n"
printf "(it has already been installed via winetricks above).\n\n"
echo "After installation is complete, run this script again."
echo ""
printf "Press return to continue ...\n"
read -r replyString
wine SETUP.exe 2>/dev/null 1>/dev/null
cd "$WINEPREFIX/../.."



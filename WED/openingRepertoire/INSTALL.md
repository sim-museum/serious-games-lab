# OpeningRepertoire - Installation Guide

## Overview

OpeningRepertoire is a chess opening study tool that displays move statistics from
a database of 25,000 grandmaster games. It can run as a GUI application or in
text-only mode for terminal use.

## System Requirements

- Ubuntu 24.04 (or compatible Linux distribution)
- Python 3.12+
- Display server (X11 or Wayland) for GUI mode

## Quick Start (Current Machine)

```bash
cd /home/g/ese/WED/openingRepertoire
source venv/bin/activate
python3 OpeningRepertoire.py
```

## Packaging for Another Ubuntu 24.04 PC

### Step 1: Create the package on your current machine

```bash
cd /home/g/ese/WED/openingRepertoire

# Create package directory
mkdir -p OpeningRepertoire-package

# Copy application files
cp OpeningRepertoire.py OpeningRepertoire-package/
cp requirements.txt OpeningRepertoire-package/

# Copy the PGN database
cp /home/g/ese/WED/INSTALL/25000grandmasterGames.pgn OpeningRepertoire-package/

# Copy the cache file (optional but recommended - saves 10 min on first run)
cp /home/g/ese/WED/INSTALL/25000grandmasterGames.pgn.book_cache.pkl OpeningRepertoire-package/

# Create the tarball
tar -czvf OpeningRepertoire-package.tar.gz OpeningRepertoire-package/

# Clean up
rm -rf OpeningRepertoire-package/
```

The resulting file `OpeningRepertoire-package.tar.gz` contains everything needed.

### Step 2: Transfer to target PC

Copy `OpeningRepertoire-package.tar.gz` to the target Ubuntu 24.04 PC using:
- USB drive
- SCP: `scp OpeningRepertoire-package.tar.gz user@target-pc:~/`
- Network share
- etc.

### Step 3: Install on target Ubuntu 24.04 PC

```bash
# Extract the package
cd ~
tar -xzvf OpeningRepertoire-package.tar.gz
cd OpeningRepertoire-package

# Install system dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv python3-pyqt6

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Update the PGN path in the script (IMPORTANT!)
# Edit line 88 of OpeningRepertoire.py to match your path:
#   DEFAULT_PGN_PATH = "/home/YOUR_USERNAME/OpeningRepertoire-package/25000grandmasterGames.pgn"
nano OpeningRepertoire.py
# Or use sed:
sed -i 's|/home/g/ese/WED/INSTALL/|/home/YOUR_USERNAME/OpeningRepertoire-package/|g' OpeningRepertoire.py

# Test that it works
python3 OpeningRepertoire.py --help
```

## Running the Application

### GUI Mode (default)

```bash
cd ~/OpeningRepertoire-package
source venv/bin/activate
python3 OpeningRepertoire.py
```

With preset color:
```bash
python3 OpeningRepertoire.py --white   # Play as White
python3 OpeningRepertoire.py --black   # Play as Black
```

### Text Mode (terminal only)

```bash
python3 OpeningRepertoire.py --textmode --white
python3 OpeningRepertoire.py --textmode --black
```

## Creating a Desktop Launcher

### Option 1: Shell script launcher

```bash
mkdir -p ~/bin
cat > ~/bin/openingrepertoire << 'EOF'
#!/bin/bash
cd ~/OpeningRepertoire-package
source venv/bin/activate
python3 OpeningRepertoire.py "$@"
EOF
chmod +x ~/bin/openingrepertoire

# Add ~/bin to PATH if not already (add to ~/.bashrc)
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Now run with:
openingrepertoire
openingrepertoire --white
openingrepertoire --textmode --black
```

### Option 2: Desktop menu entry

```bash
cat > ~/.local/share/applications/openingrepertoire.desktop << 'EOF'
[Desktop Entry]
Name=OpeningRepertoire
Comment=Chess opening study tool with grandmaster statistics
Exec=bash -c "cd $HOME/OpeningRepertoire-package && source venv/bin/activate && python3 OpeningRepertoire.py"
Icon=chess
Terminal=false
Type=Application
Categories=Game;BoardGame;Education;
Keywords=chess;opening;repertoire;study;
EOF

# Update desktop database
update-desktop-database ~/.local/share/applications/
```

The app will now appear in your application menu under Games.

## Running After PC Restart

The virtual environment must be activated each time:

```bash
cd ~/OpeningRepertoire-package
source venv/bin/activate
python3 OpeningRepertoire.py
```

Or use the launcher script/desktop entry created above.

## Troubleshooting

### "No module named 'chess'" or similar

Ensure the virtual environment is activated:
```bash
source venv/bin/activate
```

### Cache not loading (slow startup)

If you didn't copy the cache file, the first run will take ~10 minutes to build
the opening book. The cache is saved automatically for fast subsequent starts.

To rebuild the cache manually:
```bash
rm *.book_cache.pkl
python3 OpeningRepertoire.py  # Will rebuild cache
```

### Display errors in GUI mode

Ensure you have a display server running:
```bash
echo $DISPLAY  # Should show :0 or :1 or similar
```

For remote/SSH use, either:
- Use text mode: `--textmode`
- Set up X11 forwarding: `ssh -X user@host`

### PGN path error

Edit `OpeningRepertoire.py` line 88 to match your actual PGN file location.

## File Sizes

- `OpeningRepertoire.py`: ~55 KB
- `requirements.txt`: ~50 bytes
- `25000grandmasterGames.pgn`: ~180 MB
- `*.book_cache.pkl`: ~37 MB
- Total package: ~220 MB

## License

This application is provided as-is for personal use.

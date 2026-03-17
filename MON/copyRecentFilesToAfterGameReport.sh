#!/bin/bash
# Copy PokerTH log files and poker_log_*.txt files created in the last 2 hours to afterGamesReport
# Also copy recent screenshots from ~/Pictures/Screenshots

# PokerTH log files (saved anywhere under $HOME: ~/Documents, ~/.pokerth/log-files, etc.)
# Formats: pokerth-log-YYYY-MM-DD_HHMMSS.{txt,html,pdb}, PokerTH - Logfile-Analysis.pdf
find "$HOME" -maxdepth 5 -type f \( -name "pokerth-log*" -o -name "PokerTH*Log*" \) \
    -mmin -120 -not -path "*/afterGamesReport/*" -exec cp {} ./afterGamesReport \; 2>/dev/null

# pokerIQ log files
find ./pokerIQ -maxdepth 1 -name "poker_log_*.txt" -type f -mmin -120 -exec cp {} ./afterGamesReport \; 2>/dev/null

# Screenshots
if [ -d "$HOME/Pictures/Screenshots" ]; then
    find "$HOME/Pictures/Screenshots" -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) -mmin -120 -exec cp {} ./afterGamesReport \; 2>/dev/null
fi

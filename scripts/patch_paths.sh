#!/bin/bash
# patch_paths.sh - Fix download paths in scripts copied before the path bug was corrected.
#
# The sed replacement of ../../tar/ -> ../downloads/ was one level too short
# for scripts at the day-directory root level (bracelets.sh, speedDreams.sh, CFL.sh).
# Those need $WINEPREFIX/../../downloads/ (two levels up from WP to reach repo root),
# not $WINEPREFIX/../downloads/ (one level up, which stays inside the day dir).
#
# Also fixes two minor bugs in ese scripts:
#   - SUN/copyRecentFilesToAfterGameReport.sh had Python syntax in a .sh file
#   - THU/uninstall.sh used Python input() instead of bash read
#
# Usage: cd ~/sgl && bash scripts/patch_paths.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

echo "Patching download paths in scripts..."
echo ""

# Fix 1: SUN/bracelets.sh - download path one level too short
if grep -q 'WINEPREFIX/../downloads/' SUN/bracelets.sh 2>/dev/null; then
    sed -i 's|\$WINEPREFIX/../downloads/|\$WINEPREFIX/../../downloads/|g' SUN/bracelets.sh
    echo "  Fixed: SUN/bracelets.sh"
else
    echo "  OK:    SUN/bracelets.sh (already patched)"
fi

# Fix 2: THU/speedDreams.sh - download path one level too short
if grep -q 'WINEPREFIX/../downloads/' THU/speedDreams.sh 2>/dev/null; then
    sed -i 's|\$WINEPREFIX/../downloads/|\$WINEPREFIX/../../downloads/|g' THU/speedDreams.sh
    echo "  Fixed: THU/speedDreams.sh"
else
    echo "  OK:    THU/speedDreams.sh (already patched)"
fi

# Fix 3: SAT/CFL.sh - download path one level too short (multiple occurrences)
if grep -q 'WINEPREFIX/../downloads/' SAT/CFL.sh 2>/dev/null; then
    sed -i 's|\$WINEPREFIX/../downloads/|\$WINEPREFIX/../../downloads/|g' SAT/CFL.sh
    echo "  Fixed: SAT/CFL.sh"
else
    echo "  OK:    SAT/CFL.sh (already patched)"
fi

# Fix 4: SUN/copyRecentFilesToAfterGameReport.sh - Python syntax in a .sh file
if grep -q '^print(' SUN/copyRecentFilesToAfterGameReport.sh 2>/dev/null; then
    cat > SUN/copyRecentFilesToAfterGameReport.sh << 'EOF'
#!/bin/bash
echo "Copy screenshots in ~/Pictures and other game output to ./afterGameReport manually."
EOF
    echo "  Fixed: SUN/copyRecentFilesToAfterGameReport.sh"
else
    echo "  OK:    SUN/copyRecentFilesToAfterGameReport.sh (already patched)"
fi

# Fix 5: THU/uninstall.sh - Python input() used instead of bash read
if grep -q 'input("Press Enter' THU/uninstall.sh 2>/dev/null; then
    sed -i 's|replyString=input("Press Enter to uninstall or <CTRL> C to cancel.")|read -rp "Press Enter to uninstall or <CTRL> C to cancel."|' THU/uninstall.sh
    echo "  Fixed: THU/uninstall.sh"
else
    echo "  OK:    THU/uninstall.sh (already patched)"
fi

echo ""
echo "Patch complete. Verifying no buggy paths remain..."
count=$(grep -rn 'WINEPREFIX/../downloads/' --include='*.sh' \
  --exclude-dir='.git' --exclude-dir='freeFalconSource' --exclude='patch_paths.sh' . 2>/dev/null | wc -l)
if [ "$count" -eq 0 ]; then
    echo "  All download paths correct."
else
    echo "  WARNING: $count files still have the short download path."
    grep -rn 'WINEPREFIX/../downloads/' --include='*.sh' \
      --exclude-dir='.git' --exclude-dir='freeFalconSource' --exclude='patch_paths.sh' . 2>/dev/null
fi

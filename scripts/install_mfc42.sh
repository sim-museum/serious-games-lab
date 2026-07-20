#!/usr/bin/env bash
# install_mfc42.sh — install mfc42.dll / mfc42u.dll into a wine prefix.
#
# Usage:  install_mfc42.sh [WINEPREFIX]      (falls back to $WINEPREFIX)
#
# Why this exists instead of a bare `winetricks mfc42`:
#
# The Rowan-engine games (Mig Alley, Battle of Britain) need mfc42 for their
# ActiveX OCX controls — without it the game crashes ~1s after launch. So does
# f4doghouse (SAT/plotAircraftFlightPerformanceDiagrams.sh).
#
# winetricks needs wine for exactly one step: running VC6RedistSetup_deu.exe to
# unpack the inner vcredist.exe. That step is fragile on a *fresh* prefix — its
# first act is to probe %AppData% via `wine cmd.exe`, which can come back empty
# and abort the whole install with a "returned empty string" warning (observed
# on a fresh Ubuntu 26.04 box, 2026-07-19).
#
# But VC6RedistSetup_deu.exe is a plain self-extracting cabinet, so cabextract
# unpacks it directly — no wine, no wineserver, no DISPLAY, no prefix state,
# nothing to race:
#
#     VC6RedistSetup_deu.exe -> vcredist.exe -> mfc42.dll + mfc42u.dll
#
# The installer is vendored at vendor/vcrun6/ so this also works with no
# network. winetricks stays as a last-resort fallback.
#
# Exit 0 on success (or if mfc42 was already present), 1 on failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

PREFIX="${1:-${WINEPREFIX:-}}"
if [[ -z "$PREFIX" ]]; then
    echo "install_mfc42: no wine prefix given (pass one or set WINEPREFIX)" >&2
    exit 1
fi
if [[ ! -d "$PREFIX" ]]; then
    echo "install_mfc42: wine prefix not found: $PREFIX" >&2
    exit 1
fi

# 32-bit DLLs go in system32 on a win32 prefix, syswow64 on a win64 one.
if [[ -d "$PREFIX/drive_c/windows/syswow64" ]]; then
    DLL_DIR="$PREFIX/drive_c/windows/syswow64"
else
    DLL_DIR="$PREFIX/drive_c/windows/system32"
fi
mkdir -p "$DLL_DIR"

if [[ -f "$DLL_DIR/mfc42.dll" ]]; then
    echo "  mfc42 already present in $(basename "$DLL_DIR")"
    exit 0
fi

VCRUN6_CACHE="$HOME/.cache/winetricks/vcrun6"
VCREDIST_CACHE="$VCRUN6_CACHE/vcredist.exe"
VC6_SETUP="$VCRUN6_CACHE/VC6RedistSetup_deu.exe"
VC6_VENDORED="$REPO_ROOT/vendor/vcrun6/VC6RedistSetup_deu.exe"
# URL and sha256 match winetricks' own recipe (winetricks_vcrun6_helper).
VC6_URL="https://download.microsoft.com/download/vc60pro/Update/2/W9XNT4/EN-US/VC6RedistSetup_deu.exe"
VC6_SHA256="c2eb91d9c4448d50e46a32fecbcc3b418706d002beab9b5f4981de552098cee7"

mkdir -p "$VCRUN6_CACHE"

# --- Stage the outer installer: vendored copy first, then download ---
if [[ ! -f "$VCREDIST_CACHE" ]]; then
    if [[ ! -f "$VC6_SETUP" && -f "$VC6_VENDORED" ]]; then
        echo "  Using vendored VC6RedistSetup"
        cp "$VC6_VENDORED" "$VC6_SETUP"
    fi
    if [[ ! -f "$VC6_SETUP" ]]; then
        echo "  Downloading VC6RedistSetup (1.8 MB)..."
        wget -q -O "$VC6_SETUP.part" "$VC6_URL" && mv "$VC6_SETUP.part" "$VC6_SETUP" \
            || rm -f "$VC6_SETUP.part"
    fi
    # Checksum-gate both sources: catches a truncated download and a corrupted
    # vendored file alike, rather than producing a silently broken prefix.
    if [[ -f "$VC6_SETUP" ]]; then
        if [[ "$(sha256sum "$VC6_SETUP" | cut -d' ' -f1)" == "$VC6_SHA256" ]]; then
            echo "  Unpacking vcredist.exe (cabextract, no wine needed)"
            cabextract -q -F 'vcredist.exe' -d "$VCRUN6_CACHE" "$VC6_SETUP" 2>/dev/null || true
        else
            echo "  WARNING: VC6RedistSetup checksum mismatch — discarding."
            rm -f "$VC6_SETUP"
        fi
    fi
fi

# --- Extract the DLLs ---
if [[ -f "$VCREDIST_CACHE" ]]; then
    echo "  Extracting mfc42*.dll into $(basename "$DLL_DIR")"
    cabextract -q "$VCREDIST_CACHE" -d "$DLL_DIR" -F 'mfc42*.dll' 2>/dev/null || true
fi

# --- Last resort: winetricks (needs a working wine + prefix) ---
if [[ ! -f "$DLL_DIR/mfc42.dll" ]] && command -v winetricks &>/dev/null; then
    echo "  Direct extraction failed; falling back to winetricks."
    WINEPREFIX="$PREFIX" winetricks -q mfc42 || true
fi

if [[ ! -f "$DLL_DIR/mfc42.dll" ]]; then
    echo "ERROR: mfc42.dll was not installed into $DLL_DIR/." >&2
    echo "       Rowan-engine games crash ~1s after launch without it." >&2
    echo "       Tried: vendored installer, download, then winetricks." >&2
    echo "       Check that cabextract is installed: sudo apt install cabextract" >&2
    exit 1
fi

exit 0

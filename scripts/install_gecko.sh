#!/usr/bin/env bash
# install_gecko.sh — install wine-gecko into a wine prefix.
#
# Usage:  install_gecko.sh [WINEPREFIX] [GECKO_VERSION]
#           WINEPREFIX     — defaults to $WINEPREFIX
#           GECKO_VERSION  — defaults to 2.47.1 (what wine 5.x/6.x expect;
#                            newer wine wants a newer gecko, see below)
#
# The caller must already have the right wine runner on PATH — unlike
# install_mfc42.sh, this one needs wine to run msiexec.
#
# WHY NOT JUST LET WINE DOWNLOAD IT
# Wine's own gecko downloader is broken as of 2026-07-19, and not because of
# anything local: winehq's redirect service ignores the version and arch it is
# given and serves a 2008-era file to everyone.
#
#   http://source.winehq.org/winegecko.php?ver=2.47.1&arch=x86
#     -> Location: http://dl.winehq.org/wine/wine-gecko/0.0.1/wine_gecko-0.0.1.cab
#
# Wine downloads that, its sha1 does not match the version it asked for, and
# the install aborts with a dialog reading:
#
#   "Unexpected checksum of downloaded file. Aborting installation of
#    corrupted file."
#
# Both query spellings (ver= and version=) return the same wrong file, so
# there is no way to coax the right one out of it. Instead we fetch the real
# MSI straight from dl.winehq.org, verify it, and install it with msiexec —
# wine's downloader is never involved.
#
# Feeding wine's own cache does NOT work: it re-verifies the cached file
# against a sha1 compiled into appwiz.cpl, and that hash does not match the
# published MSI for this build. msiexec bypasses that path entirely.
#
# NOT VENDORED, unlike vendor/vcrun6: the MSI is ~50 MB, too big for the repo.
# A fresh install therefore needs network for this step — acceptable because
# gecko is only used for in-game online documentation. Nothing else depends
# on it, so failure here is a warning, not a fatal error.
#
# VERSION: each wine release pins a gecko version (5.x/6.x -> 2.47.1,
# wine 8 -> 2.47.4). To find what a runner wants:
#   strings -el <runner>/lib/wine/appwiz.cpl.so | grep 'wine-gecko.*\.msi'
#
# Exit 0 on success or if gecko is already installed, 1 on failure.

set -uo pipefail

PREFIX="${1:-${WINEPREFIX:-}}"
GECKO_VERSION="${2:-2.47.1}"

if [[ -z "$PREFIX" ]]; then
    echo "install_gecko: no wine prefix given (pass one or set WINEPREFIX)" >&2
    exit 1
fi
if [[ ! -d "$PREFIX" ]]; then
    echo "install_gecko: wine prefix not found: $PREFIX" >&2
    exit 1
fi

# Already installed? wine unpacks the MSI to system32/gecko/<ver>/wine_gecko/.
if [[ -f "$PREFIX/drive_c/windows/system32/gecko/$GECKO_VERSION/wine_gecko/VERSION" ]]; then
    echo "  gecko $GECKO_VERSION already installed"
    exit 0
fi

MSI_NAME="wine-gecko-${GECKO_VERSION}-x86.msi"
CACHE_DIR="$HOME/.cache/wine"
MSI="$CACHE_DIR/$MSI_NAME"
URL="https://dl.winehq.org/wine/wine-gecko/${GECKO_VERSION}/${MSI_NAME}"
# sha256 of the published 2.47.1 x86 MSI. Only checked for the default
# version — a caller asking for a different one gets a size sanity check.
SHA256_2_47_1="f00b0e2892404827e8ce6811dedfc25ae699a09955bb3df1bbb31753e51da051"

mkdir -p "$CACHE_DIR"

if [[ ! -f "$MSI" ]]; then
    echo "  Downloading wine-gecko $GECKO_VERSION (~50 MB)..."
    if ! curl -sL --max-time 600 -o "$MSI.part" "$URL"; then
        echo "  WARNING: download failed (offline?). Gecko not installed." >&2
        rm -f "$MSI.part"
        exit 1
    fi
    mv "$MSI.part" "$MSI"
fi

if [[ "$GECKO_VERSION" == "2.47.1" ]]; then
    if [[ "$(sha256sum "$MSI" | cut -d' ' -f1)" != "$SHA256_2_47_1" ]]; then
        echo "  WARNING: gecko checksum mismatch — discarding download." >&2
        rm -f "$MSI"
        exit 1
    fi
elif [[ "$(stat -c%s "$MSI" 2>/dev/null || echo 0)" -lt 1000000 ]]; then
    # No pinned hash for this version; at least reject an error page.
    echo "  WARNING: downloaded gecko is implausibly small — discarding." >&2
    rm -f "$MSI"
    exit 1
fi

echo "  Installing gecko $GECKO_VERSION via msiexec (bypasses wine's downloader)"
WINEPREFIX="$PREFIX" wine msiexec /i "$MSI" /qn >/dev/null 2>&1
WINEPREFIX="$PREFIX" wineserver -w 2>/dev/null

if [[ ! -f "$PREFIX/drive_c/windows/system32/gecko/$GECKO_VERSION/wine_gecko/VERSION" ]]; then
    echo "  WARNING: gecko install did not land in the prefix." >&2
    echo "           In-game online documentation will not work; nothing else is affected." >&2
    exit 1
fi

exit 0

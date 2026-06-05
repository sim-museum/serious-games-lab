#!/bin/bash
# Plan 3 setup helper — run two Q-Plus instances on this PC to
# capture the Q-NET TCP protocol with `tools/qnet_proxy.py`.
#
# Architecture:
#
#   [Q-Plus A (server)] ←(local TCP)→ [proxy] ←(local TCP)→ [Q-Plus B (client)]
#                                       |
#                                       └→ tools/runs/qnet_session.log
#
# Q-Plus A binds to a port (we'll use 5555). The proxy listens on
# a different port (5556) and forwards to 5555. Q-Plus B connects
# to the proxy (5556) believing it's the server.
#
# Each Q-Plus instance needs its own Wine prefix because they share
# config files in the install directory. We clone the existing
# prefix once into WP_client/.
#
# Usage:
#   tools/qplus_dual_instance.sh setup   # clone Wine prefix (once)
#   tools/qplus_dual_instance.sh server  # launch instance A
#   tools/qplus_dual_instance.sh client  # launch instance B
#   tools/qplus_dual_instance.sh proxy   # start the sniffer
#
# Run them in 3 separate terminals: proxy first, then server,
# then client. In Q-Plus A: Network → Start bridge server (port 5555).
# In Q-Plus B: Network → Connect to local bridge server →
# 127.0.0.1 → port 5556. Play one deal. Stop the proxy. Inspect
# tools/runs/qnet_session.log.

set -e

BIQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRI_ROOT="$(cd "$BIQ_ROOT/../.." && pwd)"
WP_SERVER="$FRI_ROOT/WP"
WP_CLIENT="$FRI_ROOT/WP_client"
SERVER_PORT=5555
PROXY_PORT=5556
LOG_DIR="$BIQ_ROOT/tools/runs"
LOG_FILE="$LOG_DIR/qnet_session.log"

# The interactive CLIENT needs the TkG runner to render bridge suit
# characters (♠♥♦♣); default Ubuntu wine (9.x) shows empty boxes.
# Use the same runner the corpus tools use (per
# bridgeIQ/config/wine_runners.csv).
WINE_BIN="${WINE_BIN:-$HOME/.local/share/lutris/runners/wine/lutris-6.21-6-x86_64/bin/wine}"
if [ ! -x "$WINE_BIN" ]; then
    echo "WARN: $WINE_BIN not executable; falling back to 'wine'" >&2
    WINE_BIN="wine"
fi

# The SERVER must use system wine-9.0, NOT the TkG runner: under TkG
# 6.21 the q-net.exe networking module accepts TCP connections but
# never reads them (broken async socket-event delivery on kernel
# 6.17+), so the bridge server silently never answers the handshake.
# system wine-9.0 services connections correctly. Suit glyphs don't
# render under it, but that's irrelevant for the headless biq client /
# automated measurement. See backend/QNET_PROTOCOL.md.
WINE_BIN_SERVER="${WINE_BIN_SERVER:-/usr/bin/wine}"
if [ ! -x "$WINE_BIN_SERVER" ]; then
    echo "WARN: $WINE_BIN_SERVER not executable; falling back to \$WINE_BIN ($WINE_BIN)" >&2
    WINE_BIN_SERVER="$WINE_BIN"
fi

cmd="${1:-help}"

case "$cmd" in
  setup)
    if [ ! -d "$WP_SERVER" ]; then
      echo "ERROR: $WP_SERVER not found. Q-Plus must already be installed." >&2
      exit 1
    fi
    if [ -d "$WP_CLIENT" ]; then
      echo "$WP_CLIENT already exists. Delete it first if you want to re-clone."
      exit 0
    fi
    echo "Cloning Wine prefix → $WP_CLIENT (~431 MB)..."
    cp -r "$WP_SERVER" "$WP_CLIENT"
    echo "Done. Two prefixes ready:"
    echo "  server: $WP_SERVER"
    echo "  client: $WP_CLIENT"
    ;;

  server)
    cd "$FRI_ROOT"
    export WINEPREFIX="$WP_SERVER"
    export WINEARCH=win32
    echo "Launching Q-Plus SERVER instance..."
    echo "  Wine prefix: $WINEPREFIX"
    echo "  Wine runner: $WINE_BIN_SERVER (system wine — required for q-net networking)"
    echo ""
    echo "Inside Q-Plus, do:"
    echo "  1. Menu Network → Start bridge server on this PC"
    echo "  2. Pick port $SERVER_PORT when asked"
    echo "  3. Click Start (leave South=Local; a joining client makes its seat Extern)"
    echo ""
    cd "$WP_SERVER/drive_c/games/qbridge17"
    exec "$WINE_BIN_SERVER" QBRIDGE.EXE
    ;;

  client)
    cd "$FRI_ROOT"
    if [ ! -d "$WP_CLIENT" ]; then
      echo "ERROR: $WP_CLIENT missing. Run: $0 setup" >&2
      exit 1
    fi
    export WINEPREFIX="$WP_CLIENT"
    export WINEARCH=win32
    echo "Launching Q-Plus CLIENT instance..."
    echo "  Wine prefix: $WINEPREFIX"
    echo ""
    echo "Inside Q-Plus, do:"
    echo "  1. Menu Network → Connect to local bridge server"
    echo "  2. Address: 127.0.0.1"
    echo "  3. Port: $PROXY_PORT  (the PROXY, not the server)"
    echo "  4. Click Connect → Join game"
    echo ""
    cd "$WP_CLIENT/drive_c/games/qbridge17"
    exec "$WINE_BIN" QBRIDGE.EXE
    ;;

  proxy)
    mkdir -p "$LOG_DIR"
    # Kill any process already listening on $PROXY_PORT. Without
    # this, restarting the proxy after a previous run (or after
    # leaving a backgrounded instance running) hits
    # "Address already in use" on bind().
    holders=$(ss -tlnp 2>/dev/null | grep ":$PROXY_PORT " \
              | grep -oP 'pid=\K\d+' | sort -u)
    if [ -n "$holders" ]; then
        echo "[proxy] port $PROXY_PORT held by pid(s): $holders — killing"
        for pid in $holders; do
            kill "$pid" 2>/dev/null
        done
        sleep 1
        # Force-kill any survivors
        survivors=$(ss -tlnp 2>/dev/null | grep ":$PROXY_PORT " \
                    | grep -oP 'pid=\K\d+' | sort -u)
        if [ -n "$survivors" ]; then
            echo "[proxy] forcing kill -9 on: $survivors"
            for pid in $survivors; do
                kill -9 "$pid" 2>/dev/null
            done
            sleep 1
        fi
    fi
    # Archive any existing log so we don't overwrite a useful
    # capture — the Python proxy opens the log with 'w' mode.
    if [ -s "$LOG_FILE" ]; then
        archived="${LOG_FILE%.log}_$(date +%Y%m%d_%H%M%S).log"
        echo "[proxy] archiving existing log → $(basename "$archived")"
        mv "$LOG_FILE" "$archived"
    fi
    echo "Starting Q-NET proxy: listening on $PROXY_PORT → forwarding to 127.0.0.1:$SERVER_PORT"
    echo "Log: $LOG_FILE"
    cd "$BIQ_ROOT"
    exec python3 tools/qnet_proxy.py \
      --listen-port "$PROXY_PORT" \
      --forward-host 127.0.0.1 \
      --forward-port "$SERVER_PORT" \
      --log "$LOG_FILE"
    ;;

  capture-with-tcpdump)
    # Backup option: passive packet capture instead of in-line proxy.
    mkdir -p "$LOG_DIR"
    echo "Capturing TCP traffic on lo:$SERVER_PORT with tcpdump"
    echo "Log: $LOG_DIR/qnet.pcap"
    echo ""
    echo "This is a passive capture — Q-Plus client connects DIRECTLY"
    echo "to port $SERVER_PORT (not the proxy). Use this if the in-line"
    echo "proxy approach has timing issues with Q-Plus's handshake."
    echo ""
    sudo tcpdump -i lo -w "$LOG_DIR/qnet.pcap" \
      "tcp port $SERVER_PORT"
    ;;

  *)
    cat <<EOF
Usage: $0 {setup|server|client|proxy|capture-with-tcpdump}

Quick start (3 terminals):
  Terminal 1: $0 setup     # one-time clone of Wine prefix
              $0 proxy     # start the byte-logging proxy
  Terminal 2: $0 server    # launch Q-Plus instance A
              Configure: Network → Start bridge server, port $SERVER_PORT
  Terminal 3: $0 client    # launch Q-Plus instance B
              Configure: Network → Connect to 127.0.0.1:$PROXY_PORT

Then play one deal. All bytes captured to $LOG_FILE.
EOF
    ;;
esac

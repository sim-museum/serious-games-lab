#!/bin/bash
# One-paste Closed-Room teams match driver: starts the proxy + biq, waits
# for you to deal the first board, runs the event-driven autoclicker for
# N deals, then points you at the .qss aggregation.
#
# PREREQ: the Q-Plus SERVER is already running under wine-9.0 and Started
# on :5555, with your Extern seat + N/E/W = Computer, all set to SAYC.
#
# Usage:  tools/qplus_run_match.sh [DEALS] [SEAT]     (defaults: 50  S)
set -u

BIQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BIQ_ROOT"
DEALS="${1:-50}"
SEAT="${2:-S}"
SERVER_PORT=5555
PROXY_PORT=5556
BIQLOG="tools/runs/biq_session.log"
QSS_DIR="$(cd "$BIQ_ROOT/../.." && pwd)/WP/drive_c/games/qbridge17/DATA/LOCAL-MATCHES"

# 0. server must be listening
if ! ss -tln 2>/dev/null | grep -q ":$SERVER_PORT "; then
  echo "ERROR: nothing listening on :$SERVER_PORT — start the server first:" >&2
  echo "  WINE_BIN=/usr/bin/wine tools/qplus_dual_instance.sh server" >&2
  echo "  then in Q-Plus: Network -> Start bridge server -> $SERVER_PORT -> Start" >&2
  exit 1
fi

# 1. clear any stale proxy/biq (bracket = no self-match)
pkill -f 'qnet[_]proxy' 2>/dev/null
pkill -f 'biq[_]qnet_client' 2>/dev/null
sleep 1

cleanup() {
  echo; echo "[run-match] stopping proxy + biq…"
  pkill -f 'qnet[_]proxy' 2>/dev/null
  pkill -f 'biq[_]qnet_client' 2>/dev/null
}
trap cleanup EXIT

# 2. proxy (background)
echo "[run-match] starting proxy :$PROXY_PORT -> :$SERVER_PORT …"
setsid bash tools/qplus_dual_instance.sh proxy >/tmp/qplus_proxy.out 2>&1 </dev/null &
sleep 2

# 3. biq (background)
echo "[run-match] starting biq as $SEAT (auto-system, log -> $BIQLOG) …"
setsid python3 tools/biq_qnet_client.py --host 127.0.0.1 --port "$PROXY_PORT" \
  --seat "$SEAT" --auto-system --log "$BIQLOG" >/tmp/qplus_biq.out 2>&1 </dev/null &
sleep 8

# 4. confirm join
if grep -qa "handshake complete" "$BIQLOG" 2>/dev/null; then
  echo "[run-match] biq $(grep -a 'joined as' "$BIQLOG" | tail -1 | sed 's/.*\(joined as.*\)/\1/')"
else
  echo "[run-match] WARN: biq may not have joined — last log lines:"; tail -5 "$BIQLOG"
fi

# 5. GUI step
cat <<EOF

>>> On the SERVER table, click 'Closed Room' to deal board 1 in teams mode.
>>> Leave the seat config ALONE — biq plays both N/S when your side declares.
EOF
read -r -p ">>> Then press Enter to start the autoclicker for $DEALS deals… " _

# 6. autoclicker (foreground; shows Deal N/$DEALS on every click)
python3 tools/qplus_button_loop.py --deals "$DEALS" --watch tools/runs/qnet_session.log

# 7. how to score the complete result
cat <<EOF

[run-match] Match finished. To score the COMPLETE result (teams .qss, not
the proxy log — Q-Plus relays only some scores over the network):
  1. In Q-Plus, open the Score dialog -> 'Save and send' (for local usage) -> Ok.
  2. Aggregate the newest export:
       QSS=\$(ls -t "$QSS_DIR"/*.qss | head -1)
       python3 tools/qss_score_aggregate.py --qss "\$QSS" --our-seat $SEAT
EOF

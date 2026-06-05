#!/bin/bash
# Two-biq partnership launcher: biq plays BOTH North and South (a fair
# test of biq's partnership bidding, vs the biq+bot mismatch). North goes
# through the proxy (so the autoclicker can watch the deal flow); South
# connects direct to :5555.
#
# PREREQ: Q-Plus server up under wine-9.0, Started on :5555, with
#   Configuration -> Players: North=Extern, South=Extern, East=Computer,
#   West=Computer (Local radio on East or West). Match Control -> new
#   Closed-Room teams match.
#
# Usage:  tools/qplus_two_biq.sh [DEALS]      (default 50)
set -u
BIQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BIQ_ROOT"
DEALS="${1:-50}"
SERVER_PORT=5555
PROXY_PORT=5556
RUNS="tools/runs"
QSS_DIR="$(cd "$BIQ_ROOT/../.." && pwd)/WP/drive_c/games/qbridge17/DATA/LOCAL-MATCHES"

if ! ss -tln 2>/dev/null | grep -q ":$SERVER_PORT "; then
  echo "ERROR: nothing listening on :$SERVER_PORT — start the server first." >&2
  exit 1
fi

pkill -f 'qnet[_]proxy' 2>/dev/null
pkill -f 'biq[_]qnet_client' 2>/dev/null
sleep 1

cleanup() {
  echo; echo "[two-biq] stopping proxy + both biq…"
  pkill -f 'qnet[_]proxy' 2>/dev/null
  pkill -f 'biq[_]qnet_client' 2>/dev/null
}
trap cleanup EXIT

echo "[two-biq] proxy :$PROXY_PORT -> :$SERVER_PORT …"
setsid bash tools/qplus_dual_instance.sh proxy >/tmp/qplus_proxy.out 2>&1 </dev/null &
sleep 2

echo "[two-biq] biq North (proxied) + biq South (direct), auto-system …"
setsid python3 tools/biq_qnet_client.py --host 127.0.0.1 --port "$PROXY_PORT" \
  --seat N --auto-system --pair --log "$RUNS/biq_N.log" >/tmp/qplus_biqN.out 2>&1 </dev/null &
sleep 1
setsid python3 tools/biq_qnet_client.py --host 127.0.0.1 --port "$SERVER_PORT" \
  --seat S --auto-system --pair --log "$RUNS/biq_S.log" >/tmp/qplus_biqS.out 2>&1 </dev/null &
sleep 9

for s in N S; do
  if grep -qa "handshake complete" "$RUNS/biq_$s.log" 2>/dev/null; then
    echo "[two-biq] biq $s: $(grep -a 'joined as' "$RUNS/biq_$s.log" | tail -1 | sed 's/.*\(joined as.*\)/\1/')"
  else
    echo "[two-biq] WARN: biq $s may not have joined — last lines:"; tail -4 "$RUNS/biq_$s.log"
  fi
done

cat <<EOF

>>> On the SERVER, click 'Closed Room' to deal board 1 (teams mode).
EOF
read -r -p ">>> Then press Enter to start the autoclicker for $DEALS deals… " _

python3 tools/qplus_button_loop.py --deals "$DEALS" --watch "$RUNS/qnet_session.log"

cat <<EOF

[two-biq] Done. Score the complete result:
  1. Q-Plus Score dialog -> 'Save and send' (for local usage) -> Ok.
  2. QSS=\$(ls -t "$QSS_DIR"/*.qss | head -1)
     python3 tools/qss_score_aggregate.py --qss "\$QSS" --our-seat S
EOF

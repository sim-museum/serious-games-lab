#!/bin/bash
# Loop N self-contained 64-deal biq-vs-Q-Plus sessions, unattended.
#
# Each session relaunches Q-Plus FRESH and, at the end, KILLS ALL WINE —
# which closes Q-Plus's listen socket and clears the CLOSE-WAIT backlog that
# otherwise clogs after a run (the root cause of the "biq can't rejoin"
# failures). So every iteration starts from a clean socket.
#
# One session = launch Q-Plus → start server → biq joins (direct) → deal
# board 1 → autoclicker plays DEALS deals (systems per --sys) → aggregate →
# kill all wine. Results land in tools/runs/loop_results/.
#
# PREREQUISITES (one-time):
#   * Q-Plus config saved with N/S = Extern, E/W = Computer and a deal
#     source set in Match Control (Q-Plus restores these on launch).
#   * Calibrations present: ~/.qplus_server_buttons.json (closed_room +
#     start_item), ~/.qplus_button_loop.json (cycle), and (for random/fixed
#     systems) ~/.qplus_mixed_corpus.json.
#
# NOTE: the Q-Plus *launch + Start-server* click is the only part that
# needs live verification — it assumes the Local-bridge-server dialog is
# reachable via the calibrated `start_item` after launch. Everything else
# (biq, autoclicker, aggregate, kill-wine) is proven. Tune START_WAIT /
# the start click if the first session doesn't come up.
#
# Usage: tools/qplus_loop_sessions.sh [N_SESSIONS] [DEALS] [SYS]
#   SYS: 'random' (default) | 'SAYC,TwoOverOne' (fixed NS,EW)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
N="${1:-4}"; DEALS="${2:-64}"; SYS="${3:-random}"
WP_SERVER="${WP_SERVER:-/home/h/sgl/FRI/WP}"
SRV_BTN="$HOME/.qplus_server_buttons.json"
SYS_CAL="$HOME/.qplus_mixed_corpus.json"
RESULTS="$ROOT/tools/runs/loop_results"; mkdir -p "$RESULTS"
START_WAIT="${START_WAIT:-25}"     # seconds to wait for Q-Plus to load

# system flags for the autoclicker
sys_args() {
  if [ "$SYS" = "random" ]; then
    echo "--randomize-systems --system-buttons $SYS_CAL"
  else
    echo "--ns-system ${SYS%,*} --ew-system ${SYS#*,} --system-buttons $SYS_CAL"
  fi
}

kill_all_wine() {
  echo "[loop] killing Q-Plus + ALL wine (clears the listen socket)…"
  WINEPREFIX="$WP_SERVER" wineserver -k 2>/dev/null
  sleep 1
  pkill -9 -f 'biq[_]qnet_client' 2>/dev/null
  pkill -9 -f 'win[e]'      2>/dev/null
  pkill -9 -f 'syste[m]32'  2>/dev/null
  pkill -9 -f 'deskto[p]'   2>/dev/null
  pkill -9 -f 'QBRIDG[E]'   2>/dev/null
  pkill -9 -f 'Q-NE[T]'     2>/dev/null
  sleep 2
}

pos() { python3 -c "import json;d=json.load(open('$1'));print(*d['$2'])" 2>/dev/null; }
click() { xdotool mousemove "$1" "$2"; sleep 0.3; xdotool click 1; sleep 0.6; }

run_session() {
  local idx="$1"
  echo "================= [loop] session $idx / $N ================="
  kill_all_wine
  echo "[loop] launching Q-Plus server (system wine-9.0)…"
  WINE_BIN_SERVER=/usr/bin/wine setsid bash tools/qplus_dual_instance.sh server \
    >/tmp/qplus_server_$idx.out 2>&1 </dev/null &
  sleep "$START_WAIT"
  # Start the bridge server via the calibrated Start button (the Local
  # bridge-server dialog should be up after launch).
  local sx sy; read -r sx sy < <(pos "$SRV_BTN" start_item)
  [ -n "${sx:-}" ] && { echo "[loop] clicking Start ($sx,$sy)"; click "$sx" "$sy"; }
  # wait for the server to listen
  local up=0
  for _ in $(seq 1 30); do ss -tln 2>/dev/null | grep -q ':5555 ' && { up=1; break; }; sleep 1; done
  if [ "$up" -ne 1 ]; then echo "[loop] WARN: :5555 never listened — skipping $idx"; kill_all_wine; return 1; fi

  echo "[loop] launching biq (direct, fresh logs)…"
  : > tools/runs/biq_N.log; : > tools/runs/biq_S.log; rm -f tools/runs/pair_ipc/*.card 2>/dev/null
  setsid python3 tools/biq_qnet_client.py --host 127.0.0.1 --port 5555 --seat N \
    --num-samples 40 --log tools/runs/biq_N.log --auto-system --pair >/dev/null 2>&1 </dev/null &
  sleep 3
  setsid python3 tools/biq_qnet_client.py --host 127.0.0.1 --port 5555 --seat S \
    --num-samples 40 --log tools/runs/biq_S.log --auto-system --pair >/dev/null 2>&1 </dev/null &
  for _ in $(seq 1 30); do
    [ "$(grep -c 'handshake complete' tools/runs/biq_N.log 2>/dev/null)" -ge 1 ] && \
    [ "$(grep -c 'handshake complete' tools/runs/biq_S.log 2>/dev/null)" -ge 1 ] && break
    sleep 1
  done

  echo "[loop] dealing board 1 (Closed Room) + running $DEALS deals…"
  local cx cy; read -r cx cy < <(pos "$SRV_BTN" closed_room)
  [ -n "${cx:-}" ] && click "$cx" "$cy"
  sleep 2
  # shellcheck disable=SC2046
  python3 tools/qplus_button_loop.py --watch tools/runs/biq_N.log --client-log \
    --deals "$DEALS" $(sys_args) >/tmp/clicker_$idx.out 2>&1

  echo "[loop] aggregating session $idx…"
  cp tools/runs/biq_N.log "$RESULTS/biq_N_session_$idx.log"
  python3 tools/qnet_score_aggregate.py --log tools/runs/biq_N.log --our-seat S \
    > "$RESULTS/session_$idx.txt" 2>&1
  grep -E 'Net IMPs/deal|Total IMPs' "$RESULTS/session_$idx.txt"
}

for i in $(seq 1 "$N"); do run_session "$i" || true; done
kill_all_wine
echo "================= [loop] $N sessions done ================="
echo "Per-session results: $RESULTS/session_*.txt"
echo
echo "Combined over all sessions:"
cat "$RESULTS"/biq_N_session_*.log > /tmp/loop_combined.log 2>/dev/null
python3 tools/qnet_score_aggregate.py --log /tmp/loop_combined.log --our-seat S 2>&1 | head -7

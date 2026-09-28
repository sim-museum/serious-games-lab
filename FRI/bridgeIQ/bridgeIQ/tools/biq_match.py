#!/usr/bin/env python3
"""biq vs Q-Plus: the minimal match driver.

You set Q-Plus up by hand (bridge server running, Players N/S = Extern,
E/W = Computer, Local seat East, deck + Match Control). This script does
only two things:

  1. When you press Enter, connect two biq clients as North and South
     (they leave their seats cleanly on exit or Ctrl-C).
  2. Press Q-Plus's lower-left button by KEYBOARD (Return by default) at
     each step of each board: deal, start bidding, start play, after each
     trick, next deal. No mouse, no screen positions, no virtual desktop.

Keys go to whichever window has keyboard focus, and a script cannot simply
move that focus on this GNOME/Wayland desktop. So the script only sends a key
while the Q-Plus main window really has focus. Once per deal Q-Plus's own
"Information about the bids done" window takes the focus; the script closes it
with Escape (only when it is the focused window), which hands focus back to
Q-Plus. If focus goes anywhere else it tries a title-bar click, and only if
that fails asks you to click into Q-Plus. After the first click the run is
unattended; don't click or type elsewhere on this PC during a run.

Usage (from FRI/bridgeIQ/bridgeIQ):
    python3 tools/biq_match.py                  # 64 deals, signalling on
    python3 tools/biq_match.py --deals 16 --signalling off
    python3 tools/biq_match.py --launch         # also start Q-Plus first

Logs: tools/runs/biq_N.log, biq_S.log (the clients), tools/runs/match.log.
After the last board: in Q-Plus View > View scoring table > Save and send,
then  python3 tools/whole_system_analyze.py <that .qss>
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # FRI/bridgeIQ/bridgeIQ
RUNS = ROOT / "tools" / "runs"
QPLUS_DIR = ROOT.parent.parent / "WP" / "drive_c" / "games" / "qbridge17"
_CARD_OR_BID = re.compile(r'(?:<<|>>) "(bid|card)" \[(\w+)\] \[([^\]]*)\]')


# ------------------------------------------------------------ small helpers
def say(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(RUNS / "match.log", "a") as fh:
        fh.write(line + "\n")


def xdo(*args) -> str:
    try:
        return subprocess.run(["xdotool", *args], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


class _Keys:
    """Sends keys to whatever window has keyboard focus.

    Preferred: a kernel virtual keyboard (/dev/uinput via python-evdev). The
    compositor treats it as a real keyboard, so it needs no GNOME
    "remote desktop" consent and never lapses. Needs /dev/uinput writable
    access to /dev/uinput (a one-time system setting). Falls back
    to xdotool (XTest), which works only while that consent is granted."""

    _CODES = {"Return": "KEY_ENTER", "Escape": "KEY_ESC", "space": "KEY_SPACE"}

    def __init__(self):
        self.dev = None
        try:
            from evdev import UInput, ecodes
            self.ecodes = ecodes
            self.dev = UInput({ecodes.EV_KEY: [getattr(ecodes, c)
                                               for c in self._CODES.values()]},
                              name="biq-match-keys")
            time.sleep(0.8)          # let the compositor pick the device up
        except Exception:
            self.dev = None

    @property
    def method(self) -> str:
        return "virtual keyboard (uinput)" if self.dev else "xdotool (needs remote-desktop consent)"

    def press(self, key: str) -> None:
        code = self._CODES.get(key)
        if self.dev is not None and code:
            e = self.ecodes
            k = getattr(e, code)
            self.dev.write(e.EV_KEY, k, 1)
            self.dev.syn()
            time.sleep(0.03)
            self.dev.write(e.EV_KEY, k, 0)
            self.dev.syn()
            return
        xdo("key", "--clearmodifiers", key)


_KEYS: "_Keys | None" = None


def keys() -> _Keys:
    global _KEYS
    if _KEYS is None:
        _KEYS = _Keys()
    return _KEYS


class QPlusGone(Exception):
    """Q-Plus's main window has disappeared (it crashed or was closed)."""


def qplus_focused() -> bool:
    """True only while Q-Plus's MAIN window has keyboard focus. Under
    GNOME/Xwayland the X focus names an X window only when an X client really
    has the compositor's focus (never call `xdotool windowactivate` — it sets X
    focus artificially and makes this lie)."""
    wid = xdo("getwindowfocus")
    return bool(wid) and "Q-plus Bridge 17" in xdo("getwindowname", wid)


def qplus_main_window() -> str | None:
    """X id of Q-Plus's MAIN window. Windows with the same title owned by
    mutter-x11-frames are decoration frames, and the closed-room helper runs
    as `QBRIDGE.EXE -c N`; skip both."""
    for wid in xdo("search", "--name", "Q-plus Bridge 17").split():
        pid = xdo("getwindowpid", wid)
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
                errors="replace").upper()
        except (OSError, ValueError):
            continue
        if "QBRIDGE" in cmd and " -C " not in cmd:
            return wid
    return None


BID_INFO_TITLE = "Information about the bids"


def dismiss_bid_info() -> bool:
    """Q-Plus opens its "Information about the bids done" window once per
    deal and it TAKES the keyboard focus, so the next Return would never reach
    the main window. Escape closes it and Wine hands focus back to the main
    window (verified live 2026-09-25). Only acts when that window really has
    focus, so the Escape cannot land anywhere else."""
    wid = xdo("getwindowfocus")
    if not wid or not xdo("getwindowname", wid).startswith(BID_INFO_TITLE):
        return False
    keys().press("Escape")
    time.sleep(0.5)
    return True


def refocus_qplus() -> bool:
    """Give Q-Plus's main window keyboard focus with one real (XTest) click on
    its TITLE BAR, then put the pointer back. The title bar holds no cards or
    buttons, so the click only focuses. Needed because the "Q Closed Room"
    helper window takes focus when it starts playing each board, right after
    the auction. Q-Plus's title bar must not be covered by another window
    (keep the terminal on the other monitor)."""
    wid = qplus_main_window()
    if not wid:
        return False
    geo = subprocess.run(["xwininfo", "-id", wid], capture_output=True, text=True).stdout
    try:
        x = int(re.search(r"Absolute upper-left X:\s+(-?\d+)", geo).group(1))
        y = int(re.search(r"Absolute upper-left Y:\s+(-?\d+)", geo).group(1))
        w = int(re.search(r"Width:\s+(\d+)", geo).group(1))
    except AttributeError:
        return False
    ext = subprocess.run(["xprop", "-id", wid, "_NET_FRAME_EXTENTS"],
                         capture_output=True, text=True).stdout
    m = re.search(r"=\s*\d+,\s*\d+,\s*(\d+),", ext)
    top = int(m.group(1)) if m else 0
    if top < 10:
        return False                      # no title bar to click safely
    # 60 % across: clear of the closed-room window (top-left) and of the
    # minimise/maximise/close buttons (top-right).
    tx, ty = x + int(w * 0.6), y - top // 2
    pos = xdo("getmouselocation", "--shell")
    px = re.search(r"X=(\d+)", pos)
    py = re.search(r"Y=(\d+)", pos)
    xdo("mousemove", str(tx), str(ty))
    time.sleep(0.05)
    xdo("click", "1")
    time.sleep(0.05)
    if px and py:
        xdo("mousemove", px.group(1), py.group(1))
    time.sleep(0.4)
    return qplus_focused()


def _press(key: str, why: str, autofocus: bool = True) -> None:
    """Send one key to Q-Plus once it has focus. If something else took the
    focus (normally the Q Closed Room window, after every auction), click
    Q-Plus's title bar to take it back; ask the human only if that fails."""
    lost_at = None
    tries, warned = 0, False
    gone_since = None
    while not qplus_focused():
        # Q-Plus crashed or was closed: no point asking for a click.
        if qplus_main_window() is None:
            gone_since = gone_since or time.time()
            if time.time() - gone_since > 5:
                raise QPlusGone()
        else:
            gone_since = None
        if dismiss_bid_info():
            say(f"  (closed the 'Information about the bids' window, {why})")
            continue
        now = time.time()
        lost_at = lost_at or now
        # Brief grace period, then retry the click every 3 s.
        if autofocus and now - lost_at > 1.0 and (tries == 0 or now - lost_at > 3 * tries):
            tries += 1
            if refocus_qplus():
                say(f"  (re-focused Q-Plus by title-bar click, {why})")
                break
        if not warned and (not autofocus or tries >= 3):
            say(f"  … waiting for you to click into the Q-Plus window ({why})"
                + ("  [automatic click isn't taking: is Q-Plus's title bar "
                   "covered, or has the remote-desktop permission lapsed?]"
                   if autofocus else ""))
            warned = True
        time.sleep(0.3)
    keys().press(key)
    say(f"  [{key}] {why}")


def server_port() -> int | None:
    """Port Q-Plus's bridge server listens on (it may be 1100 or 5555)."""
    out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "wineserver" in line or "QBRIDGE" in line.upper():
            m = re.search(r":(\d+)\s", line)
            if m:
                return int(m.group(1))
    return None


# ------------------------------------------------------------ biq clients
def start_clients(port: int, samples: int, signalling: bool,
                  rules_only: bool = False) -> list:
    env = dict(os.environ, BIQ_SIGNALLING="1" if signalling else "0")
    if rules_only:
        # Paired comparison: the same deck with every simulation layer off.
        env.update(BIQ_BID_SIM="0", BIQ_LEAD_SIM="0", BIQ_PLAY_AUCTION="0")
    procs = []
    for seat in ("N", "S"):
        log = RUNS / f"biq_{seat}.log"
        # Keep the previous run's log (it records every simulation override).
        if log.exists() and log.stat().st_size > 0:
            keep = RUNS / "ab" / time.strftime(
                f"%y%m%d_%H%M%S_{seat}.log", time.localtime(log.stat().st_mtime))
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_bytes(log.read_bytes())
        log.write_text("")
        procs.append(subprocess.Popen(
            [sys.executable, "tools/biq_qnet_client.py", "--host", "127.0.0.1",
             "--port", str(port), "--seat", seat, "--num-samples", str(samples),
             "--log", str(log), "--auto-system", "--pair", "--nopeek", "--quiet"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True))
        time.sleep(2)                     # join one at a time
    return procs


def wait_joined(timeout: float = 60.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        joined = [s for s in ("N", "S")
                  if "handshake complete" in (RUNS / f"biq_{s}.log").read_text(errors="replace")]
        if len(joined) == 2:
            return True
        time.sleep(1)
    for s in ("N", "S"):
        txt = (RUNS / f"biq_{s}.log").read_text(errors="replace")
        if "handshake complete" not in txt:
            last = [l for l in txt.splitlines() if l.strip()][-1:] or ["(empty log)"]
            say(f"  {s} did not join. Last log line: {last[0][:120]}")
    return False


def stop_clients(procs: list) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()                 # client sends leave_game on SIGTERM
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


# ------------------------------------------------------------ the run
def run(deals: int, key: str, idle: float, autofocus: bool = True) -> int:
    """Follow biq_N.log and press `key` at each phase boundary. A deal counts
    as done at its 13th trick (or a pass-out); the next deal is dealt on
    Q-Plus's score message, or after 6 s if that message never comes (Q-Plus
    doesn't always relay it). Returns the number of deals completed."""
    log = open(RUNS / "biq_N.log", errors="replace")
    log.seek(0, os.SEEK_END)
    done, passes, any_call, auction_over, cards, tricks = 0, 0, False, False, 0, 0
    last = time.time()
    await_next = None                     # time the deal finished; next deal pending

    seen, finished, cur_board = set(), set(), None   # Q-Plus board numbers

    def finish(tag):
        nonlocal done, await_next
        done += 1
        if cur_board is not None:
            finished.add(cur_board)
        say(f"Deal {done}/{deals} finished ({tag})")
        await_next = time.time() if done < deals else None

    def press(k, why):                    # bind the autofocus choice
        _press(k, why, autofocus)

    press(key, "deal board 1")
    while done < deals or await_next:
        line = log.readline()
        if not line:
            time.sleep(0.1)
            if await_next and time.time() - await_next > 6:
                await_next = None
                press(key, "next deal (no score message)")
                last = time.time()
            elif not await_next and time.time() - last > idle:
                press(key, f"nothing happened for {idle:.0f}s, nudging")
                last = time.time()
            continue
        last = time.time()
        if '<< "new_deal_pbn"' in line:
            passes, any_call, auction_over, cards, tricks = 0, False, False, 0, 0
            await_next = None
            m = re.search(r'new_deal_pbn" \[F O (\d+)', line)
            bno = int(m.group(1)) if m else None
            if bno is not None and bno in seen:
                # Seen once (FRESH64G): Q-Plus went back and re-dealt the
                # previous board in the middle of the next auction. The
                # replay doesn't count as a new deal.
                if bno in finished:
                    done -= 1
                say(f"*** Q-Plus RE-DEALT board {bno} (already dealt). "
                    f"Following Q-Plus; check this board in its score table.")
            if bno is not None:
                seen.add(bno)
                cur_board = bno
            say(f"Deal {done + 1}/{deals} dealt"
                + (f" (board {bno})" if bno is not None else ""))
            press(key, "start bidding")
            continue
        if '<< "report_score"' in line:
            if await_next:
                await_next = None
                press(key, "next deal")
            continue
        m = _CARD_OR_BID.search(line)
        if not m:
            continue
        kind, _seat, val = m.groups()
        if kind == "bid" and not auction_over:
            if val.strip().lower() in ("p", "pass"):
                passes += 1
            else:
                any_call, passes = True, 0
            if (any_call and passes >= 3) or (not any_call and passes >= 4):
                auction_over = True
                if any_call:
                    press(key, "start play")
                else:
                    finish("passed out")
        elif kind == "card":
            cards += 1
            if cards == 4:
                cards = 0
                tricks += 1
                press(key, f"trick {tricks} done")
                if tricks == 13:
                    finish("13 tricks")
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deals", type=int, default=64)
    ap.add_argument("--signalling", choices=("on", "off"), default="on")
    ap.add_argument("--samples", type=int, default=50, help="biq MC samples")
    ap.add_argument("--key", default="Return",
                    help="key that presses Q-Plus's lower-left button (default Return)")
    ap.add_argument("--idle", type=float, default=90.0,
                    help="seconds of silence before a nudge key (keep above biq's think time)")
    ap.add_argument("--rules-only", action="store_true",
                    help="turn off simulation bidding, simulated leads and "
                         "auction-aware card play (for a paired comparison "
                         "on the same deck)")
    ap.add_argument("--no-autofocus", action="store_true",
                    help="never click Q-Plus's title bar; wait for a human click instead")
    ap.add_argument("--launch", action="store_true",
                    help="start Q-Plus (system wine32, no virtual desktop) first")
    a = ap.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)

    if a.launch:
        subprocess.Popen(["bash", "tools/qplus_dual_instance.sh", "server"], cwd=ROOT,
                         env=dict(os.environ, QPLUS_VDESKTOP="0"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        say("Q-Plus launching. Set it up, start the bridge server, then come back here.")

    print("\nSet up Q-Plus by hand: bridge server running (Network > Start bridge server),"
          "\nPlayers N/S = Extern, E/W = Computer, Local seat = East, deck + Match Control."
          f"\nbiq signalling: {a.signalling}.  Deals: {a.deals}.\n")
    input("Press Enter here to connect biq to North and South… ")
    port = server_port()
    if not port:
        say("No bridge server is listening. Start it in Q-Plus (Network > Start bridge server) and rerun.")
        return 1
    say(f"Bridge server on port {port}; connecting biq North and South…")
    procs = start_clients(port, a.samples, a.signalling == "on", a.rules_only)
    say("biq mode: " + ("RULES ONLY (simulation off)" if a.rules_only
                         else "hybrid (simulation on)"))

    def _quit(*_):
        say("Stopping biq clients…")
        stop_clients(procs)
        sys.exit(0)
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)

    if not wait_joined():
        say("biq did not join both seats. Usual cause: a leftover seat in Q-Plus — "
            "Network > Stop bridge server, Start again, then rerun this script.")
        stop_clients(procs)
        return 1
    say("biq joined as North and South.")
    print("\nClick once into the Q-Plus window; from then on the run is unattended."
          "\nWhen Q-Plus's 'Information about the bids' window takes the focus"
          "\n(once per deal) the script closes it with Escape, which returns focus"
          "\nto Q-Plus. Don't click or type elsewhere on this PC during the run."
          "\nCtrl-C here stops it.\n")
    say(f"Keys are sent by: {keys().method}")
    try:
        done = run(a.deals, a.key, a.idle, autofocus=not a.no_autofocus)
    except QPlusGone:
        say("Q-Plus has EXITED (crashed or was closed) — this match is "
            "incomplete. Stopping biq. Restart Q-Plus and the match; the "
            "boards played so far are not in a saved scoring table.")
        stop_clients(procs)
        return 2
    say(f"Match finished: {done} deals. In Q-Plus: View > View scoring table > Save and send.")
    stop_clients(procs)
    return 0


if __name__ == "__main__":
    sys.exit(main())

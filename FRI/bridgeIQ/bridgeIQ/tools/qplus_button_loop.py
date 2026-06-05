"""Auto-click the lower-left Q-Plus button — same calibrated
position cycles through Next deal / Start bidding / Start play /
Next card / (repeat) across a session.

When Q-Plus's network mode is configured with E=Extern (biq) and
the other 3 seats as Computer (achieved via the S=Human → take
Hint → switch S to Computer workaround the user found), each
deal advances through ~17 clicks of the same lower-left button.
Greyed-out clicks are no-ops; active clicks advance the state.

Usage:
    python3 tools/qplus_button_loop.py --deals 50

On first run calibrates the button position (one Enter prompt
when you hover the mouse over the lower-left button), persists
the position to ~/.qplus_button_loop.json. Force re-calibrate
with --recalibrate.

Companion to `tools/qplus_network_autoplay.py` (which clicks
just "Next deal"). Use this one for the cycle-through-states
workflow where the same button advances every state.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple


def _xdo(*args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["xdotool", *args],
        capture_output=True, text=True, check=check)
    return out.stdout.strip()


def _get_mouse() -> Tuple[int, int, int]:
    out = _xdo("getmouselocation", "--shell")
    env = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return int(env["X"]), int(env["Y"]), int(env.get("WINDOW", 0))


def _click_at(x: int, y: int, *, delay_ms: int = 80) -> None:
    _xdo("mousemove", str(x), str(y))
    time.sleep(delay_ms / 1000.0)
    _xdo("click", "1")


def calibrate(save_path: Path) -> Tuple[int, int, int]:
    print("[button-loop] Calibration — hover the MOUSE POINTER "
          "over the lower-left button in Q-Plus (it'll cycle "
          "through Next deal / Start bidding / Start play / Next "
          "card). Press Enter when positioned.")
    input("  ready? press Enter… ")
    x, y, win = _get_mouse()
    print(f"    → button at ({x}, {y})  (window id {win})")
    save_path.write_text(json.dumps(
        {"button": [x, y], "window": win}, indent=2))
    return (x, y, win)


def load_position(path: Path) -> Tuple[int, int, int]:
    raw = json.loads(path.read_text())
    btn = raw["button"]
    return (int(btn[0]), int(btn[1]), int(raw.get("window", 0)))


# ---- score-table clear ("segment transition") ------------------------
# Q-Plus's teams score sheet caps at ~64 boards, after which it stops
# scoring (report_score stops firing). To run >64 boards we periodically
# clear the table mid-run via Deal → Match Control → set the next deal
# number → OK → deal next board. biq stays connected throughout (verified
# in a manual run), so report_score keeps firing for every board and we
# score the whole run from the proxy log — no .qss needed.

_TRANS_TARGETS = ["deal_menu", "match_control", "minor_field",
                  "ok_button", "deal_button"]
_TRANS_PROMPT = {
    "deal_menu":     "the 'Deal' menu in the top menu bar",
    "match_control": "the 'Match Control' item INSIDE the open Deal menu",
    "minor_field":   "the deal-number 'minor' field (open Deal → Match "
                     "Control so it's visible)",
    "ok_button":     "the 'OK' button of the Match Control dialog",
    "deal_button":   "the button that deals the next board after OK "
                     "(e.g. 'Closed Room' / the lower-left cycle button)",
}


def _type(text: str, dry_run: bool) -> None:
    if dry_run:
        print(f"      [dry] type '{text}'")
        return
    _xdo("type", "--clearmodifiers", "--delay", "40", text)


def calibrate_transition(save_path: Path, countdown: int = 6) -> dict:
    """Capture the 5 transition targets by COUNTDOWN (not Enter): menu
    items close the moment the keyboard is touched, so we count down and
    grab the live mouse position — keep one hand on the mouse, hover the
    target, and let it capture. You set up the UI state (open the menu /
    dialog) before each capture fires."""
    print("[button-loop] Transition calibration — 5 click targets for the "
          "every-N-deals score-table clear.\n"
          "  Keep one hand on the MOUSE; don't touch the keyboard. For each "
          "target, get it on-screen (open the menu/dialog as noted) and "
          "hover the pointer over it before the countdown ends.\n"
          "  Make sure 'Keep scoring table' is UNCHECKED in the dialog.\n")
    targets: dict = {}
    for name in _TRANS_TARGETS:
        print(f"  >>> {name}: {_TRANS_PROMPT[name]}")
        for s in range(countdown, 0, -1):
            print(f"      capturing in {s}s … (hover now)   ",
                  end="\r", flush=True)
            time.sleep(1)
        x, y, win = _get_mouse()
        targets[name] = [x, y]
        targets.setdefault("window", win)
        print(f"      → {name} captured at ({x}, {y})            ")
    save_path.write_text(json.dumps(targets, indent=2))
    print(f"[button-loop] transition targets saved → {save_path}")
    return targets


def load_transition(path: Path) -> dict:
    return json.loads(path.read_text())


_SERVER_BTN_FILE = Path.home() / ".qplus_server_buttons.json"
_SERVER_TARGETS = ["stop_item", "start_item"]
_SERVER_PROMPT = {
    "stop_item":  "the 'Stop' button on the 'Local bridge server' dialog",
    "start_item": "the 'Start' button on the 'Local bridge server' dialog",
}


def calibrate_server_buttons(countdown: int = 6) -> dict:
    """Capture network_menu / stop_item / start_item by countdown,
    merged into ~/.qplus_server_buttons.json (preserving closed_room).
    These drive the every-N-deals Network stop/start reset."""
    print("[button-loop] Network-button calibration (for the >64-deal "
          "reset). Keep one hand on the MOUSE; don't touch the keyboard. "
          "For the Stop/Start items, OPEN the Network menu before the "
          "countdown ends.\n")
    try:
        d = json.loads(_SERVER_BTN_FILE.read_text())
    except Exception:
        d = {}
    for name in _SERVER_TARGETS:
        print(f"  >>> {name}: {_SERVER_PROMPT[name]}")
        for s in range(countdown, 0, -1):
            print(f"      capturing in {s}s … (hover now)   ",
                  end="\r", flush=True)
            time.sleep(1)
        x, y, win = _get_mouse()
        d[name] = [x, y]
        d.setdefault("window", win)
        print(f"      → {name} captured at ({x}, {y})            ")
    _SERVER_BTN_FILE.write_text(json.dumps(d, indent=2))
    print(f"[button-loop] saved → {_SERVER_BTN_FILE}")
    return d


def do_transition(targets: dict, next_minor: int, *,
                  dry_run: bool = False, settle: float = 1.0) -> None:
    """Deal menu → Match Control → set 'minor' to next board → OK → deal.
    Clears the score table so report_score keeps firing; biq is untouched.
    Does NOT touch the 'major' seed or the 'Keep scoring table' box (leave
    that unchecked at calibration time)."""
    win = int(targets.get("window", 0))
    print(f"\n[watch] === score-table clear → continue at board "
          f"{next_minor} ===", flush=True)

    def tap(name, pause):
        x, y = targets[name]
        _do_click(x, y, win, dry_run)
        print(f"    [trans] clicked {name} ({x},{y})", flush=True)
        time.sleep(pause)

    tap("deal_menu", settle)
    tap("match_control", settle * 1.5)          # dialog must render
    x, y = targets["minor_field"]               # set the minor field
    _do_click(x, y, win, dry_run)
    if not dry_run:
        # Clear any existing value first. ctrl+a does NOT select-all in
        # Wine edit fields (it appended: "4" + typing "44" -> "44"), so
        # go to End and BackSpace it out, then type the new number.
        _xdo("key", "--clearmodifiers", "End")
        _xdo("key", "--clearmodifiers", "--repeat", "8", "--delay", "30",
             "BackSpace")
        time.sleep(0.1)
    _type(str(next_minor), dry_run)
    print(f"    [trans] minor := {next_minor}", flush=True)
    time.sleep(0.3)
    tap("ok_button", settle * 1.5)              # table clears
    tap("deal_button", settle)                  # deal next board


# ---- full reset: Network stop/start + biq relaunch -------------------
# Clearing the score table alone does NOT reset Q-Plus's 64-board teams
# scoring buffer (confirmed: a 200-deal run with table-clears still capped
# at 64). The buffer only resets on a fresh session: Network → Stop server
# → Start server, then biq reconnects. So a true "past-64" reset is:
#   Network stop/start  +  relaunch biq  +  Match Control (new minor)  +  deal.
# Verified live: after the cycle + biq relaunch, scoring resumed (64→67).

def _load_server_buttons(path):
    return json.loads(Path(path).read_text())


def _biq_cmdlines():
    """The currently-running biq client commands, so a reset can relaunch
    them identically regardless of who launched them (panel or script)."""
    out = subprocess.run(["pgrep", "-af", "biq[_]qnet_client"],
                         capture_output=True, text=True).stdout
    cmds = []
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and "biq_qnet_client" in parts[1]:
            cmds.append(parts[1])
    return cmds


def do_network_cycle(srv, *, dry_run=False, settle=2.5):
    """Stop then Start the Local-bridge-server — the 2-click sequence
    that frees Q-Plus's teams-scoring buffer. stop_item / start_item are
    the Stop / Start BUTTONS on Q-Plus's always-open 'Local bridge
    server' dialog (no Network-menu navigation: that just dropped a
    spurious dropdown over the buttons). The clients drop when the
    server stops, so we settle generously before/after Start."""
    win = int(srv.get("window", 0))
    print("\n[watch] === Stop → Start bridge server (free buffer) ===",
          flush=True)

    def tap(name, pause):
        xy = srv.get(name)
        if not xy:
            print(f"    [reset] WARN: '{name}' not calibrated", flush=True)
            return
        _do_click(int(xy[0]), int(xy[1]), win, dry_run)
        print(f"    [reset] clicked {name} ({xy[0]},{xy[1]})", flush=True)
        time.sleep(pause)

    tap("stop_item", settle)        # Stop button — clients disconnect
    tap("start_item", settle)       # Start button — server re-listens


def _relaunch_biq(cmdlines, *, dry_run=False, timeout=45.0):
    """Kill + relaunch the biq clients and wait (poll their logs) for the
    re-handshake. After a Network stop/start the dead seats are freed, so
    a fresh biq join re-initialises the teams match (resetting the 64
    buffer). pkill uses the bracketed pattern so it never self-matches."""
    logs = [m.group(1) for c in cmdlines
            if (m := re.search(r'--log\s+(\S+)', c))]
    before = {}
    for lg in logs:
        try:
            before[lg] = Path(lg).read_text(errors='replace').count(
                "handshake complete")
        except OSError:
            before[lg] = 0
    print(f"    [reset] relaunching {len(cmdlines)} biq client(s)…",
          flush=True)
    if dry_run:
        for c in cmdlines:
            print(f"      [dry] kill+relaunch: {c}")
        return
    subprocess.run(["pkill", "-f", "biq[_]qnet_client"])
    time.sleep(2)
    for c in cmdlines:
        subprocess.Popen(["setsid", "bash", "-c", f"exec {c}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    # wait until every client's log shows a NEW "handshake complete"
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok = True
        for lg in logs:
            try:
                now = Path(lg).read_text(errors='replace').count(
                    "handshake complete")
            except OSError:
                now = 0
            if now <= before[lg]:
                ok = False
        if ok:
            print("    [reset] biq re-joined.", flush=True)
            time.sleep(1.5)
            return
        time.sleep(1.0)
    print("    [reset] WARN: biq rejoin not confirmed within "
          f"{timeout:.0f}s — continuing anyway.", flush=True)


# ---- per-deal NS+EW bidding-system randomization (Q-Plus GUI clicks) --
# biq sets its own N/S via --auto-system (it follows whatever Q-Plus
# reports each deal), but the E/W bots only obey Q-Plus's internal config
# (set_config is server→client — biq can't change E/W). So to randomise
# BOTH sides per deal we drive Q-Plus's Configuration ▸ Bidding-system
# dialog with the SAME calibrated positions the corpus GUI captured
# (~/.qplus_mixed_corpus.json). The robust double-clicks + dialog-open
# verification are essential — a naive version mis-set ~97% of deals
# (see tools/qplus_mixed_corpus.py:_set_systems_for_deal).
_SYS_FAMILY = {"SAYC": "american", "TwoOverOne": "american",
               "StandardAcol": "british", "StandardFrench": "french",
               "Precision90M": "precision"}
_SYS_NAMES = list(_SYS_FAMILY)
_RADIO_FOR_FAMILY = {"american": "radio_american", "british": "radio_british",
                     "french": "radio_french", "precision": "radio_precision"}
_SYS_STEP = 0.20
_SYS_CLOSE = 0.30


def _dialog_visible(names):
    for n in names:
        try:
            if subprocess.run(["xdotool", "search", "--name", n],
                              capture_output=True, text=True).stdout.strip():
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def do_set_systems(pos, ns, ew, *, window_id=0, dry_run=False):
    """Set Q-Plus's N/S then E/W bidding system via the Configuration ▸
    Bidding-system dialog: open (verified, 3 tries) → family radio +
    list entry + Set-for-N/S → same for E/W → Close. `pos` is the
    corpus-GUI calibration dict (key → [x, y]). A side passed as None is
    left untouched ('auto') — only the other side is set."""
    if ns is None and ew is None:
        return
    print(f"    [sys] N/S←{ns or '(auto)'}  E/W←{ew or '(auto)'}", flush=True)
    if dry_run:
        print("      [dry] (would drive Configuration ▸ Bidding-system "
              "dialog)")
        return

    def tap(key, pause):
        xy = pos.get(key)
        if not xy:
            print(f"      [sys] WARN: position '{key}' not calibrated",
                  flush=True)
            return
        _do_click(int(xy[0]), int(xy[1]), window_id, False)
        time.sleep(pause)

    if window_id:
        _xdo("windowactivate", str(window_id), check=False)
    if pos.get("simulation_close_btn") and _dialog_visible(["Simulation"]):
        tap("simulation_close_btn", 0.3)
    # open the dialog with verification
    opened = False
    for _ in range(3):
        tap("config_menu", _SYS_STEP)
        tap("bidding_system_item", _SYS_CLOSE)
        time.sleep(0.2)
        if _dialog_visible(["Bidding system", "Bidding-system",
                            "idding system"]):
            opened = True
            break
    if not opened:
        print("      [sys] WARN: dialog never opened — last deal's "
              "systems persist", flush=True)
        return

    def set_side(name, set_btn):
        rkey = _RADIO_FOR_FAMILY[_SYS_FAMILY[name]]
        tap(rkey, _SYS_STEP)                       # radio: double-click +
        tap(rkey, _SYS_STEP)                       #   repaint settle, so the
        time.sleep(_SYS_STEP * 3)                  #   family list redraws
        tap(f"list_{name}", _SYS_STEP)             # list entry: double-click
        tap(f"list_{name}", _SYS_STEP)
        tap(set_btn, _SYS_STEP)

    if ns is not None:
        set_side(ns, "set_ns_btn")
    if ew is not None:
        set_side(ew, "set_ew_btn")
    # Close, and VERIFY the dialog is actually gone before returning — a
    # lingering modal dialog blocks every later click (East-reset, deal,
    # network). Retry the Close up to 5×, then settle.
    tap("close_btn", _SYS_CLOSE)
    _titles = ["Bidding system", "Bidding-system", "idding system"]
    for _ in range(5):
        if not _dialog_visible(_titles):
            break
        time.sleep(0.4)
        tap("close_btn", 0.3)
    else:
        print("      [sys] WARN: bidding-system dialog may still be open",
              flush=True)
    time.sleep(0.6)   # let Q-Plus settle before the next dialog


def loop(pos: Tuple[int, int], *,
          deals: int,
          clicks_per_deal: int,
          click_interval: float,
          window_id: int = 0,
          dry_run: bool = False) -> None:
    x, y = pos
    total_clicks = deals * clicks_per_deal
    print(f"[button-loop] starting — {deals} deals × "
          f"{clicks_per_deal} clicks @ {click_interval:.1f}s "
          f"= {total_clicks} clicks "
          f"({total_clicks * click_interval / 60:.0f} min)")
    print("[button-loop] (greyed-button clicks are no-ops; "
          "active clicks advance the state)")
    for i in range(1, total_clicks + 1):
        if i % clicks_per_deal == 1:
            deal_num = (i - 1) // clicks_per_deal + 1
            print(f"\n[button-loop] === deal {deal_num}/{deals} ===",
                  flush=True)
        if not dry_run:
            if window_id:
                try:
                    _xdo("windowactivate", "--sync", str(window_id))
                except subprocess.CalledProcessError:
                    pass
            _click_at(x, y)
        sub_step = ((i - 1) % clicks_per_deal) + 1
        print(f"  click {sub_step:>2}/{clicks_per_deal}  "
              f"(total {i}/{total_clicks})", flush=True)
        time.sleep(click_interval)
    print("\n[button-loop] done.")


def _do_click(x: int, y: int, window_id: int, dry_run: bool) -> None:
    if dry_run:
        return
    if window_id:
        try:
            _xdo("windowactivate", "--sync", str(window_id))
        except subprocess.CalledProcessError:
            pass
    _click_at(x, y)


_HDR = re.compile(r"\[\s*\d+ ms\]\s+(C2S|S2C)\s+len=")
_HEX = re.compile(r"\s+[0-9a-f]{4}\s+((?:[0-9a-f]{2} )+)")
_MSG = re.compile(r'"([^"]+)"((?:\s*\[[^\]]*\])*)')
_ARG = re.compile(r"\[([^\]]*)\]")


def _parse_qnet_messages(data: bytes):
    """Pull every `"<cmd>" [arg] [arg]…` message out of one proxy packet
    (a single TCP read may bundle several newline-separated messages)."""
    text = data.decode("latin-1", "replace")
    out = []
    for m in _MSG.finditer(text):
        out.append((m.group(1), _ARG.findall(m.group(2))))
    return out


_CLIENT_BC = re.compile(r'(?:>>|<<) "(bid|card)" \[(\w+)\] \[\s*([^\]]*?)\s*\]')


def _parse_client_line(line: str):
    """Parse one plain-text biq CLIENT-log line into (cmd, args) or None.
    In pair mode `>>` carries biq's own seats (N+S) and `<<` the received
    ones (E+W); biq's own cards are NOT echoed back, so taking BOTH gives
    all four seats exactly once. new_deal_pbn / report_score are always
    received (`<<`)."""
    m = _CLIENT_BC.search(line)
    if m:
        return (m.group(1), [m.group(2), m.group(3)])
    if '<< "new_deal_pbn"' in line:
        return ("new_deal_pbn", [])
    if '<< "report_score"' in line:
        return ("report_score", [])
    return None


def _pick_sys(mode, seed, idx):
    """Resolve one side's system for deal index `idx`.
      mode 'auto'   → None (leave Q-Plus's default untouched)
      mode 'random' → a system; SEEDED by (seed, idx) when seed is not None
                      so two runs with the same --system-seed draw the SAME
                      sequence (reproducible random for an A/B); else free.
      else          → the fixed system name in `mode`.
    """
    if mode == "auto":
        return None
    if mode == "random":
        if seed is not None:
            return random.Random(f"{seed}-{idx}").choice(_SYS_NAMES)
        return random.choice(_SYS_NAMES)
    return mode


def watch_loop(pos: Tuple[int, int], *,
                deals: int,
                log_path: str,
                idle_secs: float,
                window_id: int = 0,
                dry_run: bool = False,
                clear_every: int = 0,
                start_board: int = 1,
                transition: dict = None,
                server_buttons: dict = None,
                system_positions: dict = None,
                ns_mode: str = "auto",
                ew_mode: str = "auto",
                system_seed: int = None,
                client_log: bool = False) -> None:
    """Event-driven: tail the Q-NET proxy log and click the lower-left
    button the instant the protocol says a phase is complete — no
    waiting. The proxy flushes every packet, so the log is real-time.

    Deterministic triggers (read straight off the wire):
      * `new_deal_pbn`          → a deal was dealt   → click (start bidding)
      * `bid` … 3 passes after a call (or 4 from the
        opening) end the auction                    → click (start play)
        (a pass-out — 4 passes, no call — has no play; we just wait)
      * `card` … every 4th card completes a trick    → click (next trick)
      * `report_score`          → deal scored        → click (next deal)

    `idle_secs` is only a SAFETY BACKSTOP for anything the state machine
    doesn't model (e.g. a pass-out, or a missed parse): if the wire goes
    silent that long with no event, click once. Set it ABOVE biq's worst
    per-move think time so a biq-is-thinking pause isn't clicked into.
    """
    x, y = pos
    path = Path(log_path)
    src = "biq client log" if client_log else "proxy log"
    print(f"[watch] waiting for {src} {path} …", flush=True)
    for _ in range(120):
        if path.exists():
            break
        time.sleep(0.5)
    if not path.exists():
        print(f"[watch] {src} never appeared — is biq/the proxy running?")
        return
    fh = open(path, "r", errors="replace")
    fh.seek(0, 2)  # start at EOF — only react to NEW traffic
    # For full resets we relaunch whatever biq clients are running now.
    biq_cmds = _biq_cmdlines() if server_buttons else []
    if server_buttons:
        print(f"[watch] full-reset mode: {len(biq_cmds)} biq client(s) "
              f"will be relaunched every {clear_every} deals", flush=True)
    deals_done = 0
    pending: list = []
    in_packet = False
    last_activity = time.time()
    # per-deal auction/play state
    st = {"passes": 0, "any_call": False, "auction_done": False,
          "trick_cards": 0, "tricks": 0, "counted": False}

    def cur_deal() -> int:
        return min(deals_done + 1, deals)

    def click(reason: str) -> None:
        nonlocal last_activity
        _do_click(x, y, window_id, dry_run)
        print(f"  [watch] Deal {cur_deal()}/{deals}  click — {reason}",
              flush=True)
        last_activity = time.time()

    def reset_deal() -> None:
        st.update(passes=0, any_call=False, auction_done=False,
                   trick_cards=0, tricks=0, counted=False)

    def finish_deal(tag: str) -> None:
        # Count a deal complete on the FIRST of {13 tricks, report_score,
        # pass-out} — report_score alone is unreliable in teams/Closed-
        # Room mode (Q-Plus relays only some), so we don't depend on it.
        # De-duped per deal via st['counted'].
        nonlocal deals_done
        if not st["counted"]:
            st["counted"] = True
            deals_done += 1
            print(f"\n[watch] === Deal {deals_done}/{deals} complete "
                  f"({tag}) ===", flush=True)

    print(f"[watch] watching {path.name} ({src}) — clicking on protocol "
          f"events (3 passes / 4 cards / new deal / score), "
          f"{idle_secs:.0f}s idle backstop, until {deals} deals. "
          f"Ctrl-C to stop.", flush=True)

    # Per-side system modes: "auto" (leave Q-Plus default), "random"
    # (re-roll that side each deal), or a specific system name. Drive the
    # dialog only if at least one side isn't auto; re-set every deal only if
    # a side is random (otherwise set once).
    drive_systems = bool(system_positions) and (ns_mode != "auto"
                                                 or ew_mode != "auto")
    any_random = ns_mode == "random" or ew_mode == "random"
    set_once = not any_random
    sys_set = False

    def react(cmd, args):
        """One protocol event → state-machine + clicks. Source-agnostic
        (proxy hex packets or plain client-log lines both feed this)."""
        nonlocal last_activity, sys_set
        if cmd == "new_deal_pbn":
            reset_deal()
            print("[watch]   (new deal dealt)", flush=True)
            click("start bidding")
        elif cmd == "bid" and not st["auction_done"]:
            val = args[1].strip().lower() if len(args) >= 2 else ""
            if val in ("p", "pass"):
                st["passes"] += 1
            else:
                st["any_call"] = True
                st["passes"] = 0
            ended = ((st["any_call"] and st["passes"] >= 3) or
                     (not st["any_call"] and st["passes"] >= 4))
            if ended:
                st["auction_done"] = True
                if st["any_call"]:
                    click("auction over (3 passes) → play")
                else:
                    print("[watch]   (passed out — no play)", flush=True)
                    finish_deal("passed out")
        elif cmd == "card":
            st["trick_cards"] += 1
            if st["trick_cards"] >= 4:
                st["trick_cards"] = 0
                st["tricks"] += 1
                click(f"trick {st['tricks']}/13 complete")
                if st["tricks"] >= 13:
                    finish_deal("13 tricks")
        elif cmd == "report_score":
            finish_deal("score")
            reset_deal()
            if deals_done < deals:
                # Set the systems for the NEXT deal (Q-Plus GUI clicks)
                # BEFORE dealing it, so the new board's set_config carries
                # them. Each side independently: auto (skip), random
                # (re-roll), or fixed. Fixed/auto-only → set once; any
                # random side → re-set each deal. A side that's "auto"
                # passes None so do_set_systems leaves it untouched.
                if drive_systems and not (set_once and sys_set):
                    nsv = _pick_sys(ns_mode, system_seed, deals_done)
                    ewv = _pick_sys(ew_mode, system_seed, deals_done)
                    do_set_systems(system_positions, nsv, ewv,
                                   window_id=window_id, dry_run=dry_run)
                    if set_once:
                        sys_set = True
                # Segment boundary every `clear_every` deals: full reset
                # (Stop/Start + biq relaunch + MC) frees Q-Plus's 64-board
                # buffer; the deal_button click deals the next board, which
                # arrives as new_deal_pbn and the loop picks it up.
                if (transition and clear_every
                        and deals_done % clear_every == 0):
                    nxt = start_board + deals_done
                    if server_buttons:
                        do_network_cycle(server_buttons, dry_run=dry_run)
                        _relaunch_biq(biq_cmds, dry_run=dry_run)
                    do_transition(transition, nxt, dry_run=dry_run)
                    last_activity = time.time()
                else:
                    click("next deal")

    while deals_done < deals:
        line = fh.readline()
        if line:
            if client_log:
                ev = _parse_client_line(line)
                if ev:
                    last_activity = time.time()
                    react(*ev)
                continue
            if _HDR.search(line):
                in_packet = True
                pending = []
                last_activity = time.time()
                continue
            m = _HEX.match(line)
            if m and in_packet:
                pending.append(
                    bytes(int(b, 16) for b in m.group(1).split()))
                continue
            if line.strip() == "" and pending:
                data = b"".join(pending)
                in_packet = False
                pending = []
                for cmd, args in _parse_qnet_messages(data):
                    last_activity = time.time()
                    react(cmd, args)
        else:
            idle = time.time() - last_activity
            if idle >= idle_secs:
                click(f"idle backstop ({idle:.0f}s silent)")
            time.sleep(0.2)
    print(f"\n[watch] done — {deals_done}/{deals} deals complete.", flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Auto-click Q-Plus lower-left cycle button")
    p.add_argument("--deals", type=int, default=50,
                   help="number of deals to play (default 50)")
    p.add_argument("--clicks-per-deal", type=int, default=20,
                   help="estimated button clicks per deal: "
                        "1 Next-deal + 1 Start-bidding + 1 "
                        "Start-play + 13 Next-card + slack "
                        "(default 20)")
    p.add_argument("--click-interval", type=float, default=4.0,
                   help="seconds between clicks (default 4)")
    p.add_argument("--calibration", type=Path,
                   default=Path.home() / ".qplus_button_loop.json")
    p.add_argument("--recalibrate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--watch", type=Path, default=None,
                   help="event-driven mode: tail this log (a Q-NET proxy "
                        "hex log, or a biq CLIENT log with --client-log) "
                        "and click on protocol events")
    p.add_argument("--client-log", action="store_true",
                   help="[--watch] the watched file is a biq CLIENT log "
                        "(plain text, e.g. tools/runs/biq_N.log) rather "
                        "than the proxy hex log. Lets biq connect direct "
                        "(no proxy) so it survives the reset cleanly.")
    p.add_argument("--idle", type=float, default=10.0,
                   help="[--watch] SAFETY BACKSTOP only: seconds of "
                        "proxy silence before a fallback click (the "
                        "state machine handles normal transitions). "
                        "Keep ABOVE biq's worst per-move think time "
                        "(default 10)")
    p.add_argument("--clear-every", type=int, default=0,
                   help="[--watch] clear the Q-Plus score table every N "
                        "completed deals (Deal→Match Control→OK) so "
                        "report_score keeps firing past the ~64-board "
                        "sheet cap. 0 = never (default).")
    p.add_argument("--start-board", type=int, default=1,
                   help="board number the run starts at (the 'minor'); "
                        "the clear sets minor = start-board + deals-done "
                        "(default 1)")
    p.add_argument("--transition-calibration", type=Path,
                   default=Path.home() / ".qplus_transition.json")
    p.add_argument("--server-buttons", type=Path, default=None,
                   help="[--watch + --clear-every] JSON with network_menu / "
                        "stop_item / start_item positions. When given, each "
                        "clear becomes a FULL reset (Network stop/start + "
                        "biq relaunch + Match Control) that frees Q-Plus's "
                        "64-board scoring buffer — required for runs >64.")
    p.add_argument("--randomize-systems", action="store_true",
                   help="[--watch] randomise BOTH N/S and E/W bidding "
                        "systems each deal by driving Q-Plus's Configuration "
                        "▸ Bidding-system dialog. Run biq with --auto-system "
                        "so it follows the per-deal N/S system.")
    p.add_argument("--system-buttons", type=Path,
                   default=Path.home() / ".qplus_mixed_corpus.json",
                   help="bidding-system dialog calibration JSON (default: "
                        "the corpus GUI's ~/.qplus_mixed_corpus.json)")
    p.add_argument("--ns-system", default="auto",
                   choices=["auto", "random"] + _SYS_NAMES,
                   help="[--watch] N/S bidding system: 'auto' (leave Q-Plus's "
                        "default untouched), 'random' (re-roll each deal), or "
                        "a specific system. Set via Q-Plus's Bidding-system "
                        "dialog. Run biq with --auto-system to follow N/S.")
    p.add_argument("--ew-system", default="auto",
                   choices=["auto", "random"] + _SYS_NAMES,
                   help="[--watch] E/W bidding system: auto / random / a "
                        "specific system (independent of N/S).")
    p.add_argument("--system-seed", type=int, default=None,
                   help="Seed the 'random' system choice by deal index so two "
                        "runs with the SAME seed draw the SAME per-deal NS/EW "
                        "systems (reproducible random for an A/B). Omit for "
                        "free random.")
    p.add_argument("--set-systems-once", action="store_true",
                   help="Drive the Bidding-system dialog ONCE for the given "
                        "--ns-system/--ew-system (verified open+close), then "
                        "EXIT. Lets the panel apply deal-1 systems before the "
                        "East-reset + dealing board 1. A 'random' side rolls "
                        "one value here.")
    p.add_argument("--recalibrate-transition", action="store_true")
    p.add_argument("--recalibrate-server", action="store_true",
                   help="capture the Network menu / Stop / Start button "
                        "positions (for the >64-deal reset), then exit")
    p.add_argument("--test-transition", type=int, metavar="MINOR",
                   default=None,
                   help="do ONE score-table clear setting minor=MINOR, "
                        "then exit (for testing calibration)")
    args = p.parse_args(argv)

    if args.recalibrate_server:
        calibrate_server_buttons()
        return 0

    # Transition calibration / standalone test
    trans = None
    if (args.clear_every or args.test_transition is not None
            or args.recalibrate_transition):
        if (args.recalibrate_transition
                or not args.transition_calibration.exists()):
            calibrate_transition(args.transition_calibration)
        trans = load_transition(args.transition_calibration)
    if args.test_transition is not None:
        print("[button-loop] test transition in 3s — Ctrl-C to abort.")
        time.sleep(3)
        do_transition(trans, args.test_transition, dry_run=args.dry_run)
        print("[button-loop] test transition done.")
        return 0

    if args.recalibrate or not args.calibration.exists():
        calibrate(args.calibration)
    pos = load_position(args.calibration)
    print(f"[button-loop] using ({pos[0]}, {pos[1]}), window {pos[2]}")
    srv = None
    if args.server_buttons and args.server_buttons.exists():
        srv = _load_server_buttons(args.server_buttons)
    syspos = None
    ns_mode, ew_mode = args.ns_system, args.ew_system
    if args.randomize_systems:           # back-compat shorthand for both
        ns_mode = ew_mode = "random"
    if ns_mode != "auto" or ew_mode != "auto":
        try:
            syspos = json.loads(args.system_buttons.read_text())
        except Exception as e:
            print(f"[button-loop] system-setting: can't read "
                  f"{args.system_buttons}: {e}", file=sys.stderr)
            return 1
        print(f"[button-loop] systems: N/S={ns_mode}  E/W={ew_mode}",
              flush=True)

    # One-shot: set the systems once (deal-1 systems) and exit. The panel
    # runs this BEFORE the East-reset + dealing board 1.
    if args.set_systems_once:
        if syspos is None:
            print("[button-loop] --set-systems-once: both sides are 'auto' — "
                  "nothing to set.", flush=True)
            return 0
        nsv = _pick_sys(ns_mode, args.system_seed, 0)
        ewv = _pick_sys(ew_mode, args.system_seed, 0)
        do_set_systems(syspos, nsv, ewv, window_id=pos[2],
                       dry_run=args.dry_run)
        print(f"[button-loop] one-shot systems set: N/S={nsv} E/W={ewv}",
              flush=True)
        return 0

    if args.watch:
        try:
            watch_loop((pos[0], pos[1]), deals=args.deals,
                       log_path=str(args.watch), idle_secs=args.idle,
                       window_id=pos[2], dry_run=args.dry_run,
                       clear_every=args.clear_every,
                       start_board=args.start_board, transition=trans,
                       server_buttons=srv, system_positions=syspos,
                       ns_mode=ns_mode, ew_mode=ew_mode,
                       system_seed=args.system_seed,
                       client_log=args.client_log)
        except KeyboardInterrupt:
            print("\n[button-loop] interrupted.")
        return 0
    print("[button-loop] starting in 3s — Ctrl-C to abort.")
    time.sleep(3)
    try:
        loop((pos[0], pos[1]),
              deals=args.deals,
              clicks_per_deal=args.clicks_per_deal,
              click_interval=args.click_interval,
              window_id=pos[2],
              dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n[button-loop] interrupted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

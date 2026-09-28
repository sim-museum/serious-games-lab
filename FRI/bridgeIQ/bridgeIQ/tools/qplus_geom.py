"""Q-Plus window-relative click geometry.

Every harness click position is captured as an ABSOLUTE screen point, but
Q-Plus's main window does not always come up in the same place (2026-09-23:
top-left of the left monitor twice, then on the right monitor). This module
stores the window position the captures were made at (the calibration
ORIGIN, ~/.qplus_cal_origin.json) and shifts every click by however far the
window has moved since — and normalises new captures back into the origin
frame, so old and new points stay consistent. Wine dialogs and menus are
positioned relative to the main window, so one offset covers them all.
If the window can't be found, clicks pass through unchanged."""
from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

ORIGIN_FILE = Path.home() / ".qplus_cal_origin.json"
_cache: Tuple[float, Optional[Tuple[int, int]]] = (0.0, None)


def _xdo(*args) -> Optional[str]:
    try:
        r = subprocess.run(["xdotool", *args], capture_output=True,
                           text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def qplus_window_pos(max_age: float = 1.5) -> Optional[Tuple[int, int]]:
    """Top-left of Q-Plus's MAIN window ("Q-plus Bridge 17…", not the Login
    splash), cached for `max_age` seconds; None if not on screen."""
    global _cache
    t, pos = _cache
    if time.time() - t < max_age:
        return pos
    pos = None
    # xdotool's getwindowgeometry position is unreliable under mutter (it
    # mixes frame and client offsets); xwininfo's ABSOLUTE upper-left of the
    # CLIENT window is stable, so measure that.
    wid = qplus_client_id()
    if wid:
        try:
            r = subprocess.run(["xwininfo", "-id", wid], capture_output=True,
                               text=True, timeout=5)
            ax = ay = None
            for line in r.stdout.splitlines():
                if "Absolute upper-left X:" in line:
                    ax = int(line.split(":")[1])
                elif "Absolute upper-left Y:" in line:
                    ay = int(line.split(":")[1])
            if ax is not None and ay is not None:
                pos = (ax, ay)
        except (OSError, subprocess.SubprocessError, ValueError):
            pos = None
    _cache = (time.time(), pos)
    return pos


_wid_cache: Tuple[float, Optional[str]] = (0.0, None)


def qplus_window_id(max_age: float = 3.0) -> Optional[str]:
    """X window id of Q-Plus's MAIN window (not the Login splash / IME)."""
    global _wid_cache
    t, wid = _wid_cache
    if wid and time.time() - t < max_age:
        return wid
    out = _xdo("search", "--onlyvisible", "--name", "Q-plus Bridge 17") or ""
    best, best_area = None, -1
    for cand in out.split():
        # Q-Plus spawns a helper instance for the closed room with a window
        # of the same title; the MAIN window is the largest one.
        geo = _xdo("getwindowgeometry", cand) or ""
        area = 0
        for line in geo.splitlines():
            if "Geometry:" in line:
                try:
                    w, h = line.split("Geometry:")[1].strip().split("x")
                    area = int(w) * int(h)
                except ValueError:
                    area = 0
        if area > best_area:
            best, best_area = cand, area
    wid = best
    _wid_cache = (time.time(), wid)
    return wid


def qplus_client_id() -> Optional[str]:
    """Q-Plus's own (client) main window — the one to FOCUS. Under mutter the
    largest 'Q-plus Bridge 17' window is the window manager's FRAME (owned by
    mutter-x11-frames); positions are measured against that frame, but focus
    must go to the client window inside it: the visible same-title window
    whose owning process is QBRIDGE.EXE."""
    out = _xdo("search", "--onlyvisible", "--name", "Q-plus Bridge 17") or ""
    fallback = None
    for cand in out.split():
        pid = (_xdo("getwindowpid", cand) or "").strip()
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode("latin-1")
        except (OSError, ValueError):
            cmd = ""
        if "QBRIDGE" in cmd.upper():
            if " -c " not in cmd:          # skip the closed-room helper instance
                return cand
            fallback = fallback or cand
    return fallback


def activate_qplus() -> bool:
    """Formerly focused Q-Plus via xdotool windowactivate. Under GNOME/Xwayland
    that never moves the COMPOSITOR's focus (keystrokes still go elsewhere)
    and it corrupts the focus detector below by setting X focus artificially,
    so it now only checks that Q-Plus is on screen. Clicks don't need focus."""
    return bool(qplus_client_id() or qplus_window_id())


def cal_origin() -> Optional[Tuple[int, int]]:
    try:
        d = json.loads(ORIGIN_FILE.read_text())
        return int(d["x"]), int(d["y"])
    except Exception:
        return None


def ensure_origin() -> Optional[Tuple[int, int]]:
    """Origin for captures: the stored one, else the window's position now
    (recorded so later runs can compensate)."""
    o = cal_origin()
    if o:
        return o
    pos = qplus_window_pos()
    if pos:
        try:
            ORIGIN_FILE.write_text(json.dumps({"x": pos[0], "y": pos[1]}))
        except OSError:
            pass
    return pos


def delta() -> Tuple[int, int]:
    """(dx, dy) = where the window is now minus where it was at capture."""
    o, p = cal_origin(), qplus_window_pos()
    if not o or not p:
        return (0, 0)
    return (p[0] - o[0], p[1] - o[1])


def shift(x: int, y: int) -> Tuple[int, int]:
    """Capture-frame point -> screen point for the window's current place."""
    dx, dy = delta()
    return (int(x) + dx, int(y) + dy)


def norm(x: int, y: int) -> Tuple[int, int]:
    """Screen point (a capture) -> capture-frame point."""
    ensure_origin()
    dx, dy = delta()
    return (int(x) - dx, int(y) - dy)


# ---------------------------------------------------------------- menus
# Under GNOME/Xwayland a synthetic mouse click on Q-Plus's MENU BAR opens
# nothing (buttons and dialogs do take clicks), so menus are driven by
# keyboard: Alt+<menu mnemonic>, then the item's mnemonic letter or Return
# for the first item. Mnemonics from LIB/STRINGS/QP-S-E.INP (verified live
# 2026-09-25): Network=n ("Start bridge &server on this PC" = s), View=v
# ("View &scoring table" = s), Configuration=c (1st item = Players, so
# Return; "&Bidding system" = b), Deal=d ("&Match control" = m).
MENU = {
    "network_start_server": ("n", "s"),
    "view_scoring_table":   ("v", "s"),
    "config_players":       ("c", "Return"),
    "config_bidding_system": ("c", "b"),
    "deal_match_control":   ("d", "m"),
}


on_hint = None          # optional callable(str): the panel shows these to the user


def qplus_has_focus() -> bool:
    """True when the COMPOSITOR's keyboard focus is on Q-Plus. Under GNOME/
    Xwayland `xdotool getwindowfocus` names the focused X window only while
    an X client (Q-Plus, its dialogs, the Wine desktop) really has focus; it
    returns a nameless window when a GNOME app (terminal, the panel) has it."""
    wid = (_xdo("getwindowfocus") or "").strip()
    if not wid:
        return False
    name = _xdo("getwindowname", wid) or ""
    return any(k in name for k in ("Q-plus", "Wine Desktop", "Q Closed Room"))


def wait_for_qplus_focus(timeout: float = 8.0, hint: str = "") -> bool:
    """Keystrokes go to whatever the compositor has focused and xdotool
    CANNOT move that focus (verified 2026-09-25: windowactivate, a synthetic
    click, and --window keys all fail). So: if Q-Plus isn't focused, ask the
    user to click into it and wait up to `timeout`."""
    if qplus_has_focus():
        return True
    if on_hint:
        on_hint(hint or "Click once into the Q-Plus window (menu step needs "
                        "keyboard focus there)…")
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.4)
        if qplus_has_focus():
            time.sleep(0.3)
            return True
    return False


def menu_keys(menu_letter: str, *item_keys: str, settle: float = 0.7,
              focus_timeout: float = 8.0) -> bool:
    """Open a Q-Plus top-level menu with Alt+<letter> and pick an item by
    key(s). Returns False if Q-Plus's window can't be found or doesn't get
    keyboard focus in time (nothing is sent then — a stray Return would
    press Q-Plus's default button or land in another app)."""
    if not activate_qplus():
        return False
    if not wait_for_qplus_focus(focus_timeout):
        if on_hint:
            on_hint("Q-Plus never got focus — menu step skipped; click into "
                    "Q-Plus and retry the step.")
        return False
    _xdo("key", "--clearmodifiers", f"alt+{menu_letter}")
    time.sleep(settle)
    for k in item_keys:
        _xdo("key", "--clearmodifiers", k)
        time.sleep(settle)
    return True


def menu_pick(name: str) -> bool:
    """menu_keys() by symbolic name (see MENU)."""
    m, k = MENU[name]
    return menu_keys(m, k)

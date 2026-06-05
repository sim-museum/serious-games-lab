"""Q-Plus deal-autoplay harness — click "Next deal" → "Start
bidding" → "Autoplay" N times automatically.

For long diff runs (e.g. 100 deals), pressing the same three
buttons after every deal is the only manual work; this script
captures the screen positions once and then loops, leaving you
free to do other things.

Workflow:

  1. In Q-Plus, finish the FIRST deal manually (so the window is
     in the "next deal available" state) and switch focus to
     this terminal.
  2. Run `python3 tools/qplus_autoplay.py --deals 100`.
  3. Follow the calibration prompts — hover over each button in
     turn and press Enter. The script reads the mouse position
     via `xdotool getmouselocation`.
  4. The loop fires: click → wait → click → wait → click → wait
     for the deal to play out, then repeat.

Detection of "deal finished": Q-Plus only writes the session BDL
on "Save match and exit", so we can't poll a file. We use a
configurable per-deal delay (`--per-deal-seconds`, default 25).
If a deal takes longer (slow auto-play with many tricks), bump
the delay.

Stopping early: Ctrl-C interrupts the loop cleanly.

No networking required — this is purely local X11 automation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# xdotool wrappers
# ---------------------------------------------------------------------------


def _xdo(*args: str, check: bool = True) -> str:
    """Run `xdotool args…` and return stdout (str)."""
    out = subprocess.run(
        ["xdotool", *args],
        capture_output=True, text=True, check=check)
    return out.stdout.strip()


def _get_mouse() -> Tuple[int, int, int]:
    """Return (x, y, window_id) of the current mouse pointer."""
    out = _xdo("getmouselocation", "--shell")
    env = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return int(env["X"]), int(env["Y"]), int(env.get("WINDOW", 0))


def _click_at(x: int, y: int, *, delay_ms: int = 100):
    """Move pointer to (x, y) and click button 1."""
    # `mousemove` + `click 1` is more reliable than `click --clearmodifiers`
    # because the latter sometimes fires before the window receives focus.
    _xdo("mousemove", str(x), str(y))
    time.sleep(delay_ms / 1000.0)
    _xdo("click", "1")


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


# Q-Plus shows three action buttons at different stages of a deal.
# In some layouts "Next deal" and "Start bidding" cycle in the same
# screen region while "Autoplay" sits separately on the right, so
# we record all three positions independently — if two coincide,
# the user just hovers over the same spot twice.
BUTTON_NAMES = ("next_deal", "start_bidding", "autoplay")
BUTTON_LABELS = {
    "next_deal":     "Next deal",
    "start_bidding": "Start bidding",
    "autoplay":      "Autoplay",
}


def _prompt_position(label: str) -> Tuple[int, int]:
    input(f"  Hover over the '{label}' button, then press Enter… ")
    x, y, _ = _get_mouse()
    print(f"    → '{label}' at ({x}, {y})")
    return (x, y)


def calibrate(save_path: Path) -> Dict[str, Tuple[int, int]]:
    """Prompt the user to hover over each of the three Q-Plus action
    buttons in turn and press Enter; persist the positions to JSON.
    """
    print("[autoplay] Calibration — for each prompt, move the MOUSE "
          "POINTER over the named button in Q-Plus, then press "
          "Enter in this terminal.")
    print("[autoplay] (don't click in Q-Plus during this step — we "
          "read the pointer position, no click needed.)")
    positions: Dict[str, Tuple[int, int]] = {}
    for key in BUTTON_NAMES:
        positions[key] = _prompt_position(BUTTON_LABELS[key])
    save_path.write_text(json.dumps(
        {k: list(v) for k, v in positions.items()}, indent=2))
    print(f"[autoplay] Saved positions to {save_path}.")
    return positions


def load_positions(path: Path) -> Dict[str, Tuple[int, int]]:
    raw = json.loads(path.read_text())
    if all(k in raw for k in BUTTON_NAMES):
        return {k: tuple(raw[k]) for k in BUTTON_NAMES}
    raise KeyError("missing one of: " + ", ".join(BUTTON_NAMES))


# ---------------------------------------------------------------------------
# The autoplay loop
# ---------------------------------------------------------------------------


def _wait_with_heartbeat(seconds: float, label: str,
                         heartbeat: float = 10.0):
    """Sleep `seconds` while printing a heartbeat every `heartbeat`s."""
    remaining = seconds
    while remaining > 0:
        chunk = min(heartbeat, remaining)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:
            print(f"  …{label} (~{int(remaining)}s left)",
                  flush=True)


def autoplay(positions: Dict[str, Tuple[int, int]], *,
             deals: int,
             after_next_deal: float,
             after_start_bidding: float,
             per_deal_seconds: float,
             window_id: int = 0,
             dry_run: bool = False):
    """Click the three action buttons in sequence per deal, with
    waits sized for what Q-Plus shows at each stage.

    Per-step delays are CLI-configurable; the defaults are sized
    for Precision90M auctions on moderate hardware. If a deal's
    cardplay sometimes outlasts the wait, bump
    `--per-deal-seconds` (the previous default of 30 wasn't
    safe — 60 catches most variations).
    """
    steps = (
        ("next_deal",     after_next_deal,     "bidding ready"),
        ("start_bidding", after_start_bidding, "auction in progress"),
        ("autoplay",      per_deal_seconds,    "playing tricks"),
    )
    for i in range(1, deals + 1):
        print(f"[autoplay] deal {i}/{deals}…", flush=True)
        for key, wait_after, label in steps:
            x, y = positions[key]
            print(f"  click '{BUTTON_LABELS[key]}' at ({x}, {y}), "
                  f"then wait {wait_after:.0f}s for {label}",
                  flush=True)
            if not dry_run:
                if window_id:
                    try:
                        _xdo("windowactivate", "--sync", str(window_id))
                    except subprocess.CalledProcessError:
                        pass
                _click_at(x, y)
            _wait_with_heartbeat(wait_after, label)
        print(f"[autoplay] deal {i} done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--deals", type=int, default=4,
                   help="number of deals to play after the first "
                        "manual one (default 4 — finishes a 5-deal "
                        "session)")
    p.add_argument("--positions",
                   default=str(Path.home() / ".qplus_autoplay.json"),
                   help="cache file for calibrated button "
                        "coordinates (default ~/.qplus_autoplay.json)")
    p.add_argument("--recalibrate", action="store_true",
                   help="ignore cached positions and recalibrate")
    p.add_argument("--after-next-deal", type=float, default=2.0,
                   help="seconds to wait after clicking 'Next deal' "
                        "before clicking 'Start bidding' (default "
                        "2.0; the new hand is dealt out during "
                        "this gap)")
    p.add_argument("--after-start-bidding", type=float, default=20.0,
                   help="seconds to wait after clicking 'Start "
                        "bidding' before clicking 'Autoplay' "
                        "(default 20; this is the full auction time "
                        "— bump on slow machines or if your system "
                        "produces long auctions)")
    p.add_argument("--per-deal-seconds", type=float, default=60.0,
                   help="seconds to wait after Autoplay click before "
                        "starting the next deal (default 60 — Q-Plus's "
                        "card-play time varies a lot; 30s was unsafe "
                        "on harder hands)")
    p.add_argument("--window-id", type=int, default=0,
                   help="X11 window ID for Q-Plus (use `xdotool "
                        "search --name Q-Plus` to find it); when "
                        "provided, each click re-focuses the window "
                        "first")
    p.add_argument("--dry-run", action="store_true",
                   help="print the click plan but don't actually "
                        "click — useful for testing the calibration")
    args = p.parse_args(argv)

    cache = Path(args.positions)
    if args.recalibrate or not cache.is_file():
        positions = calibrate(cache)
    else:
        try:
            positions = load_positions(cache)
        except Exception as ex:
            print(f"[autoplay] couldn't parse {cache}: {ex!r}; "
                  "recalibrating.")
            positions = calibrate(cache)

    for key in BUTTON_NAMES:
        print(f"[autoplay] '{BUTTON_LABELS[key]}' at {positions[key]}")
    if args.window_id == 0:
        # Try to find Q-Plus's window automatically.
        try:
            out = _xdo("search", "--name", "Q-Plus", check=False)
            ids = [int(t) for t in out.split() if t.isdigit()]
            if ids:
                args.window_id = ids[0]
                print(f"[autoplay] auto-detected Q-Plus window id "
                      f"{args.window_id}")
        except Exception:
            pass

    print(f"[autoplay] starting {args.deals} deals in 3 seconds — "
          "Ctrl-C to abort.")
    time.sleep(3)
    try:
        autoplay(positions,
                 deals=args.deals,
                 after_next_deal=args.after_next_deal,
                 after_start_bidding=args.after_start_bidding,
                 per_deal_seconds=args.per_deal_seconds,
                 window_id=args.window_id,
                 dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n[autoplay] interrupted by user.")
        return 1
    print("[autoplay] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

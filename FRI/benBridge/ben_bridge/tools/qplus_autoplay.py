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


BUTTONS = ("next_deal", "start_bidding", "autoplay")
PRETTY = {
    "next_deal":     "Next deal",
    "start_bidding": "Start bidding",
    "autoplay":      "Autoplay",
}


def calibrate(save_path: Path) -> Dict[str, Tuple[int, int]]:
    """Prompt the user to hover over each Q-Plus button and press
    Enter; record each position. Returns a {name: (x, y)} dict
    and persists it to `save_path` as JSON for re-use.
    """
    positions: Dict[str, Tuple[int, int]] = {}
    print("[autoplay] Calibration — hover the MOUSE POINTER over "
          "each button, then press Enter in this terminal.")
    print("[autoplay] (don't click in Q-Plus during this step — "
          "we read the pointer position, no click needed.)")
    for name in BUTTONS:
        input(f"  Position the pointer over the '{PRETTY[name]}' "
              "button, then press Enter… ")
        x, y, _ = _get_mouse()
        positions[name] = (x, y)
        print(f"    → {PRETTY[name]} at ({x}, {y})")
    save_path.write_text(json.dumps(
        {k: list(v) for k, v in positions.items()}, indent=2))
    print(f"[autoplay] Saved positions to {save_path}.")
    return positions


def load_positions(path: Path) -> Dict[str, Tuple[int, int]]:
    raw = json.loads(path.read_text())
    return {k: tuple(v) for k, v in raw.items()}


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
    """Click Next deal → wait → Start bidding → wait for bidding →
    Autoplay → wait for tricks, `deals` times.

    Q-Plus's buttons appear in sequence:
      * "Next deal" is shown when the previous deal finished.
      * "Start bidding" appears a beat after Next deal is clicked
        (the new hand has to be dealt out first).
      * "Autoplay" only appears once the BIDDING phase has
        finished — that's the longest wait (the bidder + 4
        seats running through the auction).

    Per-step delays are configurable; the defaults assume a
    moderately fast machine and need bumping on slow hardware.
    """
    delays = (
        ("next_deal",     after_next_deal,     "bidding ready"),
        ("start_bidding", after_start_bidding, "auction in progress"),
    )
    for i in range(1, deals + 1):
        print(f"[autoplay] deal {i}/{deals}…", flush=True)
        for name, wait_after, label in delays:
            x, y = positions[name]
            print(f"  click {PRETTY[name]} at ({x}, {y}), "
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
        # Final click: Autoplay.
        x, y = positions["autoplay"]
        print(f"  click {PRETTY['autoplay']} at ({x}, {y}), "
              f"then wait {per_deal_seconds:.0f}s for tricks",
              flush=True)
        if not dry_run:
            if window_id:
                try:
                    _xdo("windowactivate", "--sync", str(window_id))
                except subprocess.CalledProcessError:
                    pass
            _click_at(x, y)
        _wait_with_heartbeat(per_deal_seconds, "playing tricks")
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
    p.add_argument("--per-deal-seconds", type=float, default=30.0,
                   help="seconds to wait after Autoplay click before "
                        "starting the next deal (default 30; tricks "
                        "phase length)")
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
            missing = [b for b in BUTTONS if b not in positions]
            if missing:
                print(f"[autoplay] cached positions missing "
                      f"{missing}; recalibrating.")
                positions = calibrate(cache)
        except Exception as ex:
            print(f"[autoplay] couldn't parse {cache}: {ex!r}; "
                  "recalibrating.")
            positions = calibrate(cache)

    print(f"[autoplay] positions: "
          f"{', '.join(f'{PRETTY[k]}=({x},{y})' for k, (x, y) in positions.items())}")
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

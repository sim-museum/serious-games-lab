#!/usr/bin/env python3
"""Auto-click Q-Plus through a CARDPLAY-ONLY network game (vs biq).

In a forced-contract cardplay-only game each deal shows a "Play only" button
(middle) instead of bidding, then steps the play via the lower-left "Next card"
button, and finally "Next deal" (same lower-left position). This clicker drives
that loop, GATED by biq's client log so it is safe:

  * on each "NEW DEAL" in the log  -> click PLAY ONLY (middle) to start cardplay
  * only AFTER "begin_play"/"FORCED CONTRACT" (play has started) -> click the
    lower-left STEP button every --card-delay s (Next card ... then Next deal)

Because STEP clicks fire ONLY while a deal is in play, the clicker can never hit
the lower-left "Start bidding" button that sits there before play begins. When
the board finishes, a STEP click lands on "Next deal", Q-Plus loads the next
board, biq logs the new deal, and the cycle repeats.

  # one-time calibration (hover over each button when prompted):
  python3 tools/qplus_cardplay_clicker.py --recalibrate
  # then run, watching the South client's log:
  python3 tools/qplus_cardplay_clicker.py --watch tools/runs/biq_S.log --deals 32
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

_CFG = Path.home() / ".qplus_cardplay_clicker.json"
_TARGETS = ["play_only", "step"]
_PROMPT = {
    "play_only": "the 'Play only' button (MIDDLE, bottom) of the table",
    "step": "the lower-left button (it shows 'Next card' during play / "
            "'Next deal' when the board is done)",
}


def _xdo(*a):
    return subprocess.run(["xdotool", *a], capture_output=True, text=True)


def _get_mouse():
    out = _xdo("getmouselocation", "--shell").stdout
    d = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return int(d["X"]), int(d["Y"]), int(d.get("WINDOW", 0))


def _click(x, y, win, dry):
    if dry:
        print(f"    [dry] click ({x},{y})", flush=True)
        return
    if win:
        _xdo("windowactivate", "--sync", str(win))
    _xdo("mousemove", "--sync", str(x), str(y))
    time.sleep(0.05)
    _xdo("click", "1")


def calibrate(countdown: int = 6) -> dict:
    print("[cardplay-clicker] Calibration — keep one hand on the MOUSE.\n"
          "Hover over each button as its countdown ends.\n")
    d = {}
    for name in _TARGETS:
        print(f"  >>> {name}: {_PROMPT[name]}")
        for s in range(countdown, 0, -1):
            print(f"      capturing in {s}s … (hover now)   ", end="\r",
                  flush=True)
            time.sleep(1)
        x, y, win = _get_mouse()
        d[name] = [x, y]
        d.setdefault("window", win)
        print(f"      -> {name} at ({x}, {y})                      ")
    _CFG.write_text(json.dumps(d, indent=2))
    print(f"[cardplay-clicker] saved -> {_CFG}")
    return d


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--watch", type=Path,
                   help="biq client log to gate clicks on (e.g. "
                        "tools/runs/biq_S.log)")
    p.add_argument("--deals", type=int, default=32)
    p.add_argument("--card-delay", type=float, default=1.5,
                   help="seconds between Next-card clicks during play")
    p.add_argument("--play-settle", type=float, default=1.5,
                   help="wait after a new deal before clicking Play only")
    p.add_argument("--max-steps", type=int, default=25,
                   help="runaway guard: stop if one deal needs more than this "
                        "many step clicks with no new deal (a stuck client)")
    p.add_argument("--recalibrate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    if a.recalibrate or not _CFG.exists():
        cfg = calibrate()
        if a.recalibrate and not a.watch:
            return 0
    else:
        cfg = json.loads(_CFG.read_text())
    win = int(cfg.get("window", 0))
    play_only, step = cfg["play_only"], cfg["step"]

    if not a.watch:
        print("error: --watch <biq log> is required to run", file=sys.stderr)
        return 2
    log = a.watch
    while not log.exists():
        print(f"[cardplay-clicker] waiting for {log} …", flush=True)
        time.sleep(1)

    fh = open(log, "r", errors="replace")
    fh.seek(0, 2)                              # only NEW lines from here
    _NEW = re.compile(r"NEW DEAL")

    deals_done = 0
    playing = False
    last_step = 0.0
    steps_this_deal = 0

    def begin_deal(n):
        nonlocal steps_this_deal
        steps_this_deal = 0
        # Per deal: Play only (MIDDLE) brings up the auction + the lower-left
        # "Start play" button; click that (lower-left "step" position) to
        # actually start the cardplay. We then start Next-card stepping right
        # away (time-based) rather than waiting on the log — the opening lead is
        # biq's, so the table is ready within --card-delay.
        nonlocal last_step, playing
        print(f"[cardplay-clicker] deal {n}/{a.deals} — Play only + Start play",
              flush=True)
        time.sleep(a.play_settle)
        _click(*play_only, win, a.dry_run)         # Play only (middle)
        time.sleep(a.play_settle)
        _click(*step, win, a.dry_run)              # Start play (lower-left)
        playing = True
        last_step = time.time()

    # The deal currently on screen is already loaded & waiting at Play only:
    print("[cardplay-clicker] starting on the current deal", flush=True)
    begin_deal(1)
    deals_done = 1

    while deals_done <= a.deals:
        line = fh.readline()
        if line:
            if _NEW.search(line):
                deals_done += 1
                if deals_done > a.deals:
                    break
                playing = False           # stop stepping until next Start play
                begin_deal(deals_done)     # Play only + Start play (sets playing)
            continue
        # no new line: step the play (only while a deal is actually in play)
        now = time.time()
        if playing and now - last_step >= a.card_delay:
            _click(*step, win, a.dry_run)
            last_step = now
            steps_this_deal += 1
            # RUNAWAY GUARD: a deal is ~13 tricks + Next-deal. If we have
            # clicked far more than that with no new deal, something is stuck
            # (e.g. a stalled client) — STOP clicking so we don't grab the
            # mouse forever. The user can fix it and re-run.
            if steps_this_deal > a.max_steps:
                print(f"[cardplay-clicker] STOPPING — {steps_this_deal} clicks "
                      f"on one deal with no progress (stuck?). Re-run after "
                      f"fixing.", flush=True)
                return 1
        time.sleep(0.25)

    print(f"[cardplay-clicker] done — {a.deals} deals", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

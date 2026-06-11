#!/usr/bin/env python3
"""Auto-click Q-Plus through a CARDPLAY-ONLY network game (vs biq).

Each deal: "Play only" (middle) brings up the auction; "Start play" (lower-left)
begins the cardplay; then either ONE "Autoplay" click rips the whole deal at
full speed (preferred), or — if Autoplay isn't calibrated — "Next card"
(lower-left) is stepped per trick. When the board finishes, "Next deal"
(lower-left) advances. The whole loop is GATED by biq's client log so it is
safe and can't run away: it stops stepping the moment a deal stalls.

  # one-time: calibrate the two always-visible buttons
  python3 tools/qplus_cardplay_clicker.py --recalibrate
  # one-time (for the fast path): start a deal playing, then capture Autoplay
  python3 tools/qplus_cardplay_clicker.py --recalibrate-autoplay
  # run:
  python3 tools/qplus_cardplay_clicker.py --watch tools/runs/biq_S.log --deals 64
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
_PROMPT = {
    "play_only": "the 'Play only' button (MIDDLE, bottom) of the table",
    "step": "the lower-left button ('Start play' / 'Next card' / 'Next deal')",
    "autoplay": "the 'Autoplay' button (visible DURING play — start a deal "
                "first: Play only then Start play, then hover Autoplay)",
}


def _xdo(*a):
    return subprocess.run(["xdotool", *a], capture_output=True, text=True)


def _get_mouse():
    out = _xdo("getmouselocation", "--shell").stdout
    d = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return int(d["X"]), int(d["Y"]), int(d.get("WINDOW", 0))


def _click(xy, win, dry):
    x, y = xy
    if dry:
        print(f"    [dry] click ({x},{y})", flush=True)
        return
    if win:
        _xdo("windowactivate", "--sync", str(win))
    _xdo("mousemove", "--sync", str(x), str(y))
    time.sleep(0.05)
    _xdo("click", "1")


def calibrate(names, countdown=6):
    try:
        d = json.loads(_CFG.read_text())
    except Exception:
        d = {}
    print("[cardplay-clicker] Calibration — keep one hand on the MOUSE.\n")
    for name in names:
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
    p.add_argument("--watch", type=Path)
    p.add_argument("--no-log", action="store_true",
                   help="all-Q-Plus baseline (session B): no biq log to gate "
                        "on, so drive purely by time — Play only/Start play/"
                        "Autoplay, wait --deal-time, Next deal. Needs Autoplay "
                        "calibrated (--recalibrate-autoplay).")
    p.add_argument("--deal-time", type=float, default=25.0,
                   help="[--no-log] seconds to let Autoplay finish a deal "
                        "before clicking Next deal (bump if deals run long)")
    p.add_argument("--deals", type=int, default=64)
    p.add_argument("--card-delay", type=float, default=0.8,
                   help="seconds between Next-card clicks (stepping fallback)")
    p.add_argument("--play-settle", type=float, default=1.2,
                   help="wait between Play only / Start play / Autoplay clicks")
    p.add_argument("--autoplay-timeout", type=float, default=25.0,
                   help="if Autoplay yields no score in this long, fall back to "
                        "Next-card stepping for that deal")
    p.add_argument("--max-steps", type=int, default=25,
                   help="runaway guard: stop if a deal needs more step clicks "
                        "than this with no new deal (stuck client)")
    p.add_argument("--recalibrate", action="store_true",
                   help="capture play_only + step (the two always-visible "
                        "buttons)")
    p.add_argument("--recalibrate-autoplay", action="store_true",
                   help="capture the Autoplay button (have a deal IN PLAY)")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    if a.recalibrate_autoplay:
        calibrate(["autoplay"])
        if not a.watch:
            return 0
    if a.recalibrate or not _CFG.exists():
        calibrate(["play_only", "step"])
        if a.recalibrate and not a.watch:
            return 0
    cfg = json.loads(_CFG.read_text())
    win = int(cfg.get("window", 0))
    play_only, step = cfg["play_only"], cfg["step"]
    autoplay = cfg.get("autoplay")
    use_auto = autoplay is not None
    print(f"[cardplay-clicker] mode: "
          f"{'AUTOPLAY (fast)' if use_auto else 'Next-card stepping'}"
          + ("" if use_auto else " — run --recalibrate-autoplay for the fast "
             "path"), flush=True)

    if not a.watch and not a.no_log:
        print("error: --watch <biq log> (or --no-log) is required",
              file=sys.stderr)
        return 2
    fh = None
    if not a.no_log:
        while not a.watch.exists():
            print(f"[cardplay-clicker] waiting for {a.watch} …", flush=True)
            time.sleep(1)
        fh = open(a.watch, "r", errors="replace")
        fh.seek(0, 2)
    _NEW = re.compile(r"NEW DEAL")
    _SCORE = re.compile(r"report_score|SCORE:")

    deals_done = 0
    playing = False          # stepping mode: a deal is in play
    awaiting = False         # autoplay mode: waiting for this deal's score
    last_step = 0.0
    deal_t0 = 0.0
    steps_this_deal = 0
    scored = False           # already advanced (Next deal) this deal

    def begin_deal(n):
        nonlocal playing, awaiting, last_step, deal_t0, steps_this_deal, scored
        print(f"[cardplay-clicker] deal {n}/{a.deals} — Play only + Start play"
              + (" + Autoplay" if use_auto else ""), flush=True)
        steps_this_deal = 0
        scored = False
        time.sleep(a.play_settle)
        _click(play_only, win, a.dry_run)             # Play only (middle)
        time.sleep(a.play_settle)
        _click(step, win, a.dry_run)                  # Start play (lower-left)
        if use_auto:
            time.sleep(a.play_settle)
            _click(autoplay, win, a.dry_run)          # Autoplay — plays it all
            awaiting, playing = True, False
            deal_t0 = time.time()
        else:
            playing, awaiting = True, False
            last_step = time.time()

    # --- no-log time-based mode: session B (all-Q-Plus baseline) ---
    if a.no_log:
        if not use_auto:
            print("error: --no-log needs Autoplay calibrated — run "
                  "--recalibrate-autoplay during a live deal first",
                  file=sys.stderr)
            return 2
        for n in range(1, a.deals + 1):
            begin_deal(n)                                 # Play only/Start/Autoplay
            time.sleep(a.deal_time)                       # let the deal play out
            _click(step, win, a.dry_run)                  # Next deal
        print(f"[cardplay-clicker] done — {a.deals} deals (no-log)", flush=True)
        return 0

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
                begin_deal(deals_done)
            elif _SCORE.search(line) and use_auto and awaiting and not scored:
                scored, awaiting = True, False
                time.sleep(0.4)
                _click(step, win, a.dry_run)          # Next deal
            continue
        now = time.time()
        if use_auto and awaiting and now - deal_t0 > a.autoplay_timeout:
            print("[cardplay-clicker] Autoplay produced no score in "
                  f"{a.autoplay_timeout:.0f}s — falling back to stepping",
                  flush=True)
            awaiting, playing, last_step = False, True, now
        if playing and now - last_step >= a.card_delay:
            _click(step, win, a.dry_run)
            last_step = now
            steps_this_deal += 1
            if steps_this_deal > a.max_steps:
                print(f"[cardplay-clicker] STOPPING — {steps_this_deal} clicks "
                      f"on one deal, no progress (stuck?). Re-run after fixing.",
                      flush=True)
                return 1
        time.sleep(0.2)

    print(f"[cardplay-clicker] done — {a.deals} deals", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

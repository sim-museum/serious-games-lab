#!/usr/bin/env python3
"""All-computer Q-Plus autoclicker — drives a 4-bot run with NO network log.

The biq-run autoclicker (qplus_button_loop.py --watch) times its clicks off
biq's client log: it knows a card was played / a deal ended because the wire
told it. An all-Q-Plus run has no biq client, so no log, so no timing signal.

This driver replaces that signal with the SCREEN. Q-Plus advances through the
whole hand from a single contextual "cycle" button (Next deal → Start bidding
→ Start play → Next card → … → score → Next deal) — the same button the watch
clicker uses (~/.qplus_button_loop.json). Here we click it whenever the play
area has gone STILL (Q-Plus finished animating the previous step and is now
waiting): poll a small screen region, and when it stops changing for
--settle-ms, click. A large frame change (the table redrawn) is counted as a
new deal, so we stop after --deals.

This is timing-robust (it waits for Q-Plus rather than guessing an interval),
but the thresholds and the watch region depend on your display — tune them
once with --dry-run (it prints the diff each poll so you can read off good
--settle / --change / --deal-change values), then run for real.

Setup before running:
  * Q-Plus: all four seats = Computer; load the deck (File ▸ Open Own deals)
    and navigate to board 1.
  * Calibrate the cycle button once (shared with the watch clicker):
      python3 tools/qplus_button_loop.py --recalibrate     # or via the panel
  * Calibrate the watch region with --calibrate-region (or pass --region).

Usage:
  python3 tools/qplus_4computer_clicker.py --deals 64
  python3 tools/qplus_4computer_clicker.py --deals 64 --region 600,300,500,360
  python3 tools/qplus_4computer_clicker.py --calibrate-region
  python3 tools/qplus_4computer_clicker.py --deals 4 --dry-run   # tune thresholds
  python3 tools/qplus_4computer_clicker.py --deals 64 --fixed --interval 0.8
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from tools.qplus_button_loop import load_position, _do_click   # noqa: E402

CYCLE_BTN_FILE = Path.home() / ".qplus_button_loop.json"
REGION_FILE = Path.home() / ".qplus_watch_region.json"


# ---------- screen capture (PIL ImageGrab primary, scrot fallback) ----------
def _make_grabber(region):
    """region = (x, y, w, h). Return a fn() -> small grayscale bytes, or None
    if no backend works."""
    x, y, w, h = region
    bbox = (x, y, x + w, y + h)
    small = (48, 48)
    try:
        from PIL import ImageGrab, Image
        ImageGrab.grab(bbox=bbox)   # probe it works on this display
        def grab():
            im = ImageGrab.grab(bbox=bbox).convert("L").resize(
                small, Image.BILINEAR)
            return im.tobytes()
        return grab
    except Exception:                                  # noqa: BLE001
        pass
    # Fallback: scrot to a temp PNG then PIL-read it.
    import shutil
    import subprocess
    import tempfile
    if shutil.which("scrot"):
        from PIL import Image
        def grab():
            f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            f.close()
            subprocess.run(["scrot", "-o", "-a",
                            f"{x},{y},{w},{h}", f.name],
                           check=True, capture_output=True)
            im = Image.open(f.name).convert("L").resize(small, Image.BILINEAR)
            Path(f.name).unlink(missing_ok=True)
            return im.tobytes()
        return grab
    return None


def _diff(a, b):
    """Mean absolute per-pixel difference (0..255) of two equal byte buffers."""
    if a is None or b is None or len(a) != len(b):
        return 255.0
    return sum(abs(p - q) for p, q in zip(a, b)) / len(a)


# ---------- region calibration ----------
def calibrate_region():
    """Capture a watch region by reading the mouse at two corners."""
    import subprocess

    def mouse():
        out = subprocess.run(["xdotool", "getmouselocation", "--shell"],
                             capture_output=True, text=True).stdout
        d = dict(line.split("=") for line in out.strip().splitlines())
        return int(d["X"]), int(d["Y"])

    print("Hover the TOP-LEFT corner of the card/trick area, press Enter…")
    input()
    x1, y1 = mouse()
    print("Hover the BOTTOM-RIGHT corner, press Enter…")
    input()
    x2, y2 = mouse()
    region = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
    REGION_FILE.write_text(json.dumps({"region": region}))
    print(f"saved watch region {region} → {REGION_FILE}")
    return region


def _load_region(arg):
    if arg:
        x, y, w, h = (int(v) for v in arg.split(","))
        return (x, y, w, h)
    if REGION_FILE.exists():
        return tuple(json.loads(REGION_FILE.read_text())["region"])
    return None


# ---------- the idle-driven click loop ----------
def run_idle(btn, region, deals, *, settle_ms, change, deal_change,
             poll_ms, post_click_ms, deal_min_gap_s, max_clicks,
             idle_timeout_s, dry_run):
    x, y, win = btn
    grab = _make_grabber(region)
    if grab is None:
        print("[4cc] no screen-capture backend (need PIL ImageGrab or scrot). "
              "Use --fixed for timed clicking instead.", file=sys.stderr)
        return 1
    print(f"[4cc] idle-driven: click ({x},{y}) when region {region} is still "
          f"for {settle_ms}ms; big change (>{deal_change}) = new deal. "
          f"Target {deals} deals. Ctrl-C to stop.", flush=True)
    prev = grab()
    last_change = time.time()
    last_deal_t = 0.0
    deals_done = 0
    clicks = 0
    poll = poll_ms / 1000.0
    while deals_done < deals and clicks < max_clicks:
        time.sleep(poll)
        cur = grab()
        d = _diff(prev, cur)
        prev = cur
        now = time.time()
        if dry_run:
            print(f"  [diff] {d:6.2f}  (still={now - last_change:4.1f}s "
                  f"deals={deals_done} clicks={clicks})", flush=True)
        if d >= deal_change and (now - last_deal_t) >= deal_min_gap_s:
            deals_done += 1
            last_deal_t = now
            last_change = now
            print(f"[4cc] === deal {deals_done}/{deals} (big redraw "
                  f"diff={d:.0f}) ===", flush=True)
            continue
        if d >= change:
            last_change = now                 # still animating; reset stillness
            continue
        if (now - last_change) * 1000 >= settle_ms:
            if not dry_run:
                _do_click(x, y, win, False)
            clicks += 1
            print(f"[4cc] click {clicks} (still {(now - last_change):.1f}s, "
                  f"deal {deals_done + 1})", flush=True)
            time.sleep(post_click_ms / 1000.0)
            prev = grab()
            last_change = time.time()
            continue
        if (now - last_change) > idle_timeout_s:
            print(f"[4cc] no activity for {idle_timeout_s}s — Q-Plus may be "
                  f"done or stuck; stopping. ({deals_done} deals, "
                  f"{clicks} clicks)", flush=True)
            break
    print(f"[4cc] done — {deals_done} deals, {clicks} clicks. Now Export the "
          f".qss in Q-Plus (or via the panel) for the baseline run.", flush=True)
    return 0


def run_fixed(btn, deals, interval, clicks_per_deal, dry_run):
    """Dumb fallback: click on a fixed interval, no screen feedback."""
    x, y, win = btn
    total = deals * clicks_per_deal
    print(f"[4cc] FIXED mode: {total} clicks @ {interval}s "
          f"({clicks_per_deal}/deal). No screen feedback — drops a click if "
          f"Q-Plus isn't ready. Ctrl-C to stop.", flush=True)
    for i in range(1, total + 1):
        if not dry_run:
            _do_click(x, y, win, False)
        if i % clicks_per_deal == 0:
            print(f"[4cc] ~deal {i // clicks_per_deal}/{deals}", flush=True)
        time.sleep(interval)
    return 0


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deals", type=int, default=64)
    p.add_argument("--region", default=None,
                   help="watch area X,Y,W,H (default: ~/.qplus_watch_region.json)")
    p.add_argument("--calibrate-region", action="store_true",
                   help="capture the watch region from two mouse corners")
    p.add_argument("--button", default=str(CYCLE_BTN_FILE),
                   help="cycle-button calibration JSON (shared with the watch "
                        "clicker)")
    p.add_argument("--settle-ms", type=int, default=450,
                   help="region must be still this long before a click")
    p.add_argument("--change", type=float, default=2.0,
                   help="mean-pixel-diff above this = still animating")
    p.add_argument("--deal-change", type=float, default=22.0,
                   help="mean-pixel-diff above this = table redrawn (new deal)")
    p.add_argument("--poll-ms", type=int, default=120)
    p.add_argument("--post-click-ms", type=int, default=300)
    p.add_argument("--deal-min-gap", type=float, default=3.0,
                   help="ignore another deal-detection within this many seconds")
    p.add_argument("--max-clicks", type=int, default=0,
                   help="safety cap (default deals*40)")
    p.add_argument("--idle-timeout", type=float, default=25.0,
                   help="stop if nothing happens for this long")
    p.add_argument("--fixed", action="store_true",
                   help="dumb fixed-interval clicking (no screen capture)")
    p.add_argument("--interval", type=float, default=0.8,
                   help="[--fixed] seconds between clicks")
    p.add_argument("--clicks-per-deal", type=int, default=20,
                   help="[--fixed] clicks budgeted per deal")
    p.add_argument("--dry-run", action="store_true",
                   help="don't actually click; idle mode prints the live diff "
                        "so you can tune --settle/--change/--deal-change")
    a = p.parse_args()

    if a.calibrate_region:
        calibrate_region()
        return 0

    btn = load_position(Path(a.button))
    if a.fixed:
        return run_fixed(btn, a.deals, a.interval, a.clicks_per_deal, a.dry_run)

    region = _load_region(a.region)
    if region is None:
        print("[4cc] no watch region — run --calibrate-region first, pass "
              "--region X,Y,W,H, or use --fixed.", file=sys.stderr)
        return 2
    max_clicks = a.max_clicks or a.deals * 40
    return run_idle(btn, region, a.deals,
                    settle_ms=a.settle_ms, change=a.change,
                    deal_change=a.deal_change, poll_ms=a.poll_ms,
                    post_click_ms=a.post_click_ms,
                    deal_min_gap_s=a.deal_min_gap, max_clicks=max_clicks,
                    idle_timeout_s=a.idle_timeout, dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())

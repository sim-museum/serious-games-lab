"""Q-Plus deal-loop autoplay for NETWORK mode (Q-Plus bots vs biq).

Companion to `tools/qplus_autoplay.py` for the local-only case,
but stripped down to one button — "Next deal" — because in
network mode the Q-Plus Computer seats auto-bid and auto-play
without further clicks, and biq plays its claimed seat via TCP.

Workflow:
  1. Start Q-Plus server (`tools/qplus_dual_instance.sh server`).
     Configure Players: 3 Computer + 1 Extern (e.g. East).
     Start bridge server on port 5555.
  2. Start the proxy in another terminal:
     `tools/qplus_dual_instance.sh proxy`
  3. Start biq client in a third terminal:
     `python3 tools/biq_qnet_client.py --port 5556 --seat E`
  4. In Q-Plus, click First deal to play deal #1 manually
     (so the window settles into the "Next deal" state).
  5. Run this script:
     `python3 tools/qplus_network_autoplay.py --deals 50`
  6. Calibrate by hovering over the "Next deal" button when
     prompted, then press Enter.
  7. Loop fires N times.

Detection of "deal finished" is purely time-based here. Each deal
in network mode takes roughly:
   8-30s for the auction (Q-Plus bot ~1-2s per bid, biq ~0.5s)
   + 20-60s for the play (biq MC+DDS @ samples=40 ~1-2s per card,
     Q-Plus bots ~0.2-1s per card; 13 tricks × ~3-5s = 40-65s).
Total typical: 40-90s. Default `--per-deal-seconds=90` is safe.

Stopping early: Ctrl-C.

If a deal hangs (e.g., biq's MC fails and the seat just sits),
the timer will fire anyway and click "Next deal", which Q-Plus
should accept and start fresh.
"""

from __future__ import annotations

import argparse
import json
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


def _click_at(x: int, y: int, *, delay_ms: int = 100) -> None:
    _xdo("mousemove", str(x), str(y))
    time.sleep(delay_ms / 1000.0)
    _xdo("click", "1")


def _wait_with_heartbeat(seconds: float, label: str,
                           heartbeat: float = 10.0) -> None:
    remaining = seconds
    while remaining > 0:
        chunk = min(heartbeat, remaining)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:
            print(f"  …{label} (~{int(remaining)}s left)",
                  flush=True)


def calibrate(save_path: Path) -> Tuple[int, int]:
    print("[autoplay-net] Calibration — hover the MOUSE POINTER "
          "over the 'Next deal' button in Q-Plus, then press "
          "Enter in this terminal. (Don't click in Q-Plus.)")
    input("  ready? press Enter… ")
    x, y, win = _get_mouse()
    print(f"    → 'Next deal' at ({x}, {y})  (window id {win})")
    save_path.write_text(json.dumps({"next_deal": [x, y],
                                       "window": win}, indent=2))
    print(f"[autoplay-net] saved to {save_path}")
    return (x, y)


def load_position(path: Path) -> Tuple[int, int]:
    raw = json.loads(path.read_text())
    nd = raw["next_deal"]
    return (int(nd[0]), int(nd[1]))


def autoplay_loop(pos: Tuple[int, int], *,
                    deals: int,
                    per_deal_seconds: float,
                    window_id: int = 0,
                    dry_run: bool = False) -> None:
    x, y = pos
    for i in range(1, deals + 1):
        print(f"[autoplay-net] deal {i}/{deals}: clicking Next "
              f"deal at ({x}, {y})", flush=True)
        if not dry_run:
            if window_id:
                try:
                    _xdo("windowactivate", "--sync", str(window_id))
                except subprocess.CalledProcessError:
                    pass
            _click_at(x, y)
        _wait_with_heartbeat(per_deal_seconds,
                              f"deal {i}/{deals} playing out")
        print(f"[autoplay-net] deal {i} done.", flush=True)
    print("[autoplay-net] all deals done.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Q-Plus network-mode deal-loop autoplay "
                     "(biq vs Q-Plus bots, only Next-deal button "
                     "needs clicking)")
    p.add_argument("--deals", type=int, default=50,
                   help="how many deals to play (default 50)")
    p.add_argument("--per-deal-seconds", type=float, default=90.0,
                   help="time budget per deal in seconds "
                        "(default 90; bump for slow MC sampling)")
    p.add_argument("--calibration", type=Path,
                   default=Path.home() / ".qplus_net_autoplay.json",
                   help="path for the Next-deal button position")
    p.add_argument("--recalibrate", action="store_true",
                   help="force re-prompt for the Next-deal position")
    p.add_argument("--dry-run", action="store_true",
                   help="don't actually click; just print timings")
    args = p.parse_args(argv)
    if args.recalibrate or not args.calibration.exists():
        calibrate(args.calibration)
    pos = load_position(args.calibration)
    raw = json.loads(args.calibration.read_text())
    window_id = int(raw.get("window", 0))
    print(f"[autoplay-net] using ({pos[0]}, {pos[1]}), "
          f"window {window_id}; "
          f"{args.deals} deals @ {args.per_deal_seconds:.0f}s each "
          f"(~{args.deals * args.per_deal_seconds / 60:.0f} min total)")
    print("[autoplay-net] starting in 3s — Ctrl-C to abort.")
    time.sleep(3)
    try:
        autoplay_loop(pos, deals=args.deals,
                        per_deal_seconds=args.per_deal_seconds,
                        window_id=window_id,
                        dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n[autoplay-net] interrupted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

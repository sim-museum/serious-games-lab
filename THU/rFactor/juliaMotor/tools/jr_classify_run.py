#!/usr/bin/env python3
"""BNDWRECK-1 S3 (2026-09-16) -- classify what happened in a juliaMotor run log.

The autodrive loses a large fraction of its races and, from outside, every loss looks the
same: exit=124 on a harness timeout. Three distinct modes hide behind that, and a fourth
outcome ("the run never started") was silently pooled with them until this script counted
the corpus. Run it over a directory of logs to get the loss rate with its breakdown:

    python3 tools/jr_classify_run.py ~/jr-standings/*.log

Modes:
  finished    -- the final classification table printed
  boundary    -- [WRECK] whose cause is BOUNDARY penetration (the invisible fence/wall test)
  solid       -- [WRECK] whose cause is a CLOSING impact into a solid object
  wreck       -- [WRECK] with some other cause
  stuck       -- [STUCK] from the S2 watchdog, OR (pre-watchdog logs) a run that stops
                 completing laps and then re-contacts every frame to the end of the log
  no-race     -- the process never got past start-up (harness timeout, GL lock, crash)

The inferred-stuck rule exists only because the one stuck run in the corpus predates the
watchdog. It is marked `stuck?` in the output so it is never mistaken for a watchdog hit.
"""
import re, sys, os

FINISH = "final classification"
DMG    = "[damage]"
LAP    = re.compile(r"^\s*lap \d+:")

def classify(path):
    try:
        text = open(path, "rb").read().decode("utf-8", "replace")
    except OSError as e:
        return ("error", str(e))
    lines = text.splitlines()
    if any(FINISH in l for l in lines):
        return ("finished", "")
    if any("[STUCK]" in l for l in lines):
        return ("stuck", "watchdog")
    wreck = [l for l in lines if "cause:" in l and "[WRECK]" in l]
    if wreck:
        c = wreck[0].split("cause:", 1)[1].strip()
        if c.startswith("BOUNDARY"):   return ("boundary", c[:60])
        if c.startswith("CLOSING"):    return ("solid", c[:60])
        return ("wreck", c[:60])
    if any("[WRECK]" in l for l in lines):
        return ("wreck", "no cause line")
    # no finish, no wreck: did it ever race, and did it end pinned?
    last_lap = max((i for i, l in enumerate(lines) if LAP.match(l)), default=-1)
    dmg_tail = sum(1 for l in lines[last_lap + 1:] if DMG in l)
    if last_lap >= 0 and dmg_tail >= 200:
        return ("stuck?", "%d contacts after the last lap, no lap since" % dmg_tail)
    if last_lap >= 0:
        return ("no-finish", "%d lap(s), no classification, no wreck" % 0)
    return ("no-race", "never reached the grid")

def main(argv):
    if not argv:
        print(__doc__); return 2
    rows = [(os.path.basename(p),) + classify(p) for p in argv]
    w = max(len(r[0]) for r in rows)
    for name, mode, note in rows:
        print("%-*s  %-9s %s" % (w, name, mode, note))
    counts = {}
    for _, mode, _ in rows:
        counts[mode] = counts.get(mode, 0) + 1
    raced = sum(n for m, n in counts.items() if m not in ("no-race", "error"))
    lost  = sum(n for m, n in counts.items()
                if m in ("boundary", "solid", "wreck", "stuck", "stuck?", "no-finish"))
    print("-" * (w + 40))
    print("  " + "  ".join("%s=%d" % kv for kv in sorted(counts.items())))
    if raced:
        print("  races that reached the grid: %d   lost: %d (%.0f%%)" % (raced, lost, 100.0 * lost / raced))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

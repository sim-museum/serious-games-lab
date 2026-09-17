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
MODE   = re.compile(r"mode:\s*(\w+)")
SPREAD = re.compile(r"AI pace spread.*Cooper (\d+)%")


def run_config(lines):
    """RACEMODE-1 S2: the two things that silently split a corpus.

    STANDINGS-1 S3 found every one of the first 24 runs was JM_MODE=practice while the
    gold is a race -- and nothing in this tool said so, so a census could pool two modes
    and report one rate. The same sprint found the corpus also mixes two AI field
    spreads. Both are one regex away from being visible, so make them visible."""
    mode = "?"
    spread = "-"
    for l in lines[:400]:
        m = MODE.search(l)
        if m and mode == "?":
            mode = m.group(1)
        m = SPREAD.search(l)
        if m and spread == "-":
            spread = m.group(1) + "%"
    return mode, spread

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
    rows = []
    for p in argv:
        try:
            lines = open(p, "rb").read().decode("utf-8", "replace").splitlines()
        except OSError:
            lines = []
        rows.append((os.path.basename(p),) + classify(p) + run_config(lines))
    w = max(len(r[0]) for r in rows)
    for name, outcome, note, mode, spread in rows:
        print("%-*s  %-9s %-9s %-5s %s" % (w, name, mode, outcome, spread, note))
    counts = {}
    for _, outcome, _, _, _ in rows:
        counts[outcome] = counts.get(outcome, 0) + 1
    # RACEMODE-1 S2: a rate per mode, because one pooled rate over two modes is the
    # mistake this column exists to prevent.
    bymode = {}
    for _, outcome, _, mode, _ in rows:
        if outcome in ("no-race", "error"):
            continue
        d = bymode.setdefault(mode, [0, 0])
        d[0] += 1
        if outcome != "finished":
            d[1] += 1
    raced = sum(n for m, n in counts.items() if m not in ("no-race", "error"))
    lost  = sum(n for m, n in counts.items()
                if m in ("boundary", "solid", "wreck", "stuck", "stuck?", "no-finish"))
    print("-" * (w + 40))
    print("  " + "  ".join("%s=%d" % kv for kv in sorted(counts.items())))
    if raced:
        print("  races that reached the grid: %d   lost: %d (%.0f%%)" % (raced, lost, 100.0 * lost / raced))
    for mode in sorted(bymode):
        n, l = bymode[mode]
        print("    mode %-9s n=%-3d lost %d (%.0f%%)" % (mode, n, l, 100.0 * l / n if n else 0))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

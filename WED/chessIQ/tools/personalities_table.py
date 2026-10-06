"""Print the opponents chessIQ would offer: Chessmaster's personalities from the local install, or its own roster.
python3 tools/personalities_table.py [--all]      (from WED/chessIQ)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import personalities as P  # noqa: E402

ps = sorted(P.roster(), key=lambda p: p.rating)
print("%d personalities from %s" % (len(ps), ps[0].source if ps else "-"))
bands = {}
for p in ps:
    bands.setdefault(p.rating // 400 * 400, []).append(p)
for b in sorted(bands):
    print("  %4d-%4d: %3d" % (b, b + 399, len(bands[b])))
for p in (ps if "--all" in sys.argv else ps[:: max(1, len(ps) // 8)]):
    print("  %-14s %4d  str %3d%% rnd %3d depth %2d contempt %4d attack %4d | %s"
          % (p.name, p.rating, p.strength, p.randomness, p.max_depth, p.contempt, p.attack, p.style[:50]))

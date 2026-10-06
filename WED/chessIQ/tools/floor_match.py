"""Below the ladder's floor (CM-14): two blunder rates at 16 nodes play GAMES through chessIQ's PersonalityEngine.
python3 tools/floor_match.py P_A P_B GAMES [SEED]     e.g. 0.15 0.3 40"""
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from chessiq.personalities import FLOOR, Personality  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402
from uci_match import elo, opening, play  # noqa: E402


class Adapt:                       # uci_match.play() calls .best(moves) and .name
    def __init__(self, p, seed):
        self.e, self.name = PersonalityEngine(Personality("p%.2f" % p, FLOOR, blunder=p), seed=seed), "p%.2f" % p

    def best(self, moves):
        return self.e.choose(moves)

    def new_game(self):
        self.e.new_game()


pa, pb, games = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 17
a, b = Adapt(pa, seed), Adapt(pb, seed + 1)
rnd, score = random.Random(seed), 0.0
for g in range(games):
    if g % 2 == 0:
        start = opening(rnd)
    a.new_game(); b.new_game()
    score += play(a, b, start) if g % 2 == 0 else 1 - play(b, a, start)
d, ci = elo(score / games, games)
print("p%.2f vs p%.2f: %.1f / %d (%.0f%%), Elo difference %+.0f +/- %.0f" % (pa, pb, score, games, 100 * score / games, d, ci))

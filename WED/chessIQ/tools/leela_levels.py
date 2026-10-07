"""Leela levels on the ladder (CM, during NN-15/16 GPU waits): a Leela opponent from the roster, through chessIQ's own
LeelaEngine, plays GAMES against a neutral Fairy-Stockfish personality at an exact ladder point (no interpolation).
python3 tools/leela_levels.py "<Leela name>"|T=<temperature> LADDER_RATING GAMES [SEED]"""
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from chessiq import personalities as P  # noqa: E402
from chessiq.uci_engine import LeelaEngine, PersonalityEngine  # noqa: E402
from uci_match import elo, opening, play  # noqa: E402


class A:
    def __init__(self, e, name):
        self.e, self.name = e, name

    def best(self, moves):
        return self.e.choose(moves)

    def new_game(self):
        self.e.new_game()


name, ladder, games = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 81
assert any(r == ladder for _, r in P.LADDER), "use an exact ladder point: %s" % [r for _, r in P.LADDER]
if name.startswith("T="):                  # a bare temperature, for finding new levels: T=0.6
    t = float(name[2:])
    person = P.Personality(name, 0, engine="leela", net=P.by_name()["Leela (Kramnik network)"].net, nodes=1,
                           randomness=round(100 * t))
else:
    person = P.by_name()[name]
lee = A(LeelaEngine(person, seed=seed), name)
fsf = A(PersonalityEngine(P.Personality("ladder %d" % ladder, ladder), seed=seed + 1), "ladder")
rnd, score = random.Random(seed), 0.0
for g in range(games):
    if g % 2 == 0:
        start = opening(rnd)
    lee.new_game(); fsf.new_game()
    score += play(lee, fsf, start) if g % 2 == 0 else 1 - play(fsf, lee, start)
lee.e.close(); fsf.e.close()
d, ci = elo(score / games, games)
print("%s vs ladder %d: %.1f/%d (%.0f%%), %+.0f +/- %.0f -> rating %.0f" % (name, ladder, score, games,
                                                                              100 * score / games, d, ci, ladder + d))

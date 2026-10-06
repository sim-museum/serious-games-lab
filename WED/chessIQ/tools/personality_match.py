"""Two neutral-style personalities, rated HI and LO, play GAMES through chessIQ's own PersonalityEngine (CM-9).
python3 tools/personality_match.py HI LO GAMES"""
import sys
import os; R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, 'tools'))
from chessiq.personalities import Personality
from chessiq.uci_engine import PersonalityEngine
from uci_match import play, opening, elo
import random
class Adapt:                       # uci_match.play() calls .best(moves) and .name
    def __init__(self, p): self.e, self.name = PersonalityEngine(p), p.name
    def best(self, moves): return self.e.choose(moves)
    def new_game(self): self.e.new_game()
hi, lo, games = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
a, b = Adapt(Personality("R%d" % hi, hi)), Adapt(Personality("R%d" % lo, lo))
rnd, score = random.Random(17), 0.0
for g in range(games):
    if g % 2 == 0: start = opening(rnd)
    a.new_game(); b.new_game()
    score += play(a, b, start) if g % 2 == 0 else 1 - play(b, a, start)
d, ci = elo(score / games, games)
exp = 1 / (1 + 10 ** (-(hi - lo) / 400))
print("%d vs %d through PersonalityEngine: %.1f / %d (%.0f%%; Elo formula expects %.0f%%), measured %+.0f +/- %.0f" % (hi, lo, score, games, 100 * score / games, 100 * exp, d, ci))

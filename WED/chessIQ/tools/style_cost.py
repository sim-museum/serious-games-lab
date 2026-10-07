"""What a style costs in strength (CM-17): a Chessmaster personality plays GAMES against a neutral opponent of the same
rating through chessIQ's PersonalityEngine, with or without compensation. Personalities come from the player's own
installation at run time; only anonymous numbers are printed (rating, style features, score) -- no names or texts.
python3 tools/style_cost.py fit|check GAMES [--compensate]
  fit: 16 personalities rated 1163-2700 (the 4 most random + a seeded sample); check: 6 others."""
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from dataclasses import replace  # noqa: E402
from chessiq import personalities as P  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402
from uci_match import elo, opening, play  # noqa: E402


class Adapt:
    def __init__(self, p, seed):
        self.e, self.name = PersonalityEngine(p, seed=seed), "x"

    def best(self, moves):
        return self.e.choose(moves)

    def new_game(self):
        self.e.new_game()


def sample():
    pool = sorted((p for p in P.roster() if p.engine == "fsf" and p.source != "chessIQ" and P.FLOOR <= p.rating <= 2700),
                  key=lambda p: p.name)
    by_rnd = sorted(pool, key=lambda p: (-p.randomness, p.name))[:5]      # randomness is rare: stratify it in
    rest = [p for p in pool if p not in by_rnd]
    picks = random.Random(7).sample(rest, 17)
    return by_rnd[:4] + picks[:12], by_rnd[4:] + picks[12:]


def main():
    which, games = sys.argv[1], int(sys.argv[2])
    comp = "--compensate" in sys.argv
    fit, check = sample()
    for i, p in enumerate(fit if which == "fit" else check):
        styled = replace(p, compensate=comp)
        neutral = P.Personality("neutral", p.rating)
        a, b = Adapt(styled, 11 + i), Adapt(neutral, 101 + i)
        rnd, score = random.Random(i), 0.0
        for g in range(games):
            if g % 2 == 0:
                start = opening(rnd)
            a.new_game(); b.new_game()
            score += play(a, b, start) if g % 2 == 0 else 1 - play(b, a, start)
        a.e.close(); b.e.close()
        d, ci = elo(score / games, games)
        f = P.style_features(p)
        print("%s #%02d rating %4d nodes %5d | attack %.2f positional %.2f material %.2f randomness %.2f | %.1f/%d  %+.0f +/- %.0f"
              % (which, i, p.rating, styled.search_nodes(), *f, score, games, d, ci), flush=True)


if __name__ == "__main__":
    main()

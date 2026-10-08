"""KS-2: a self-capture specialist against a neutral opponent of its own (label) rating, every move checked against
chessIQ's rules. A calibrated specialist scores about 50% and self-captures more than the neutral side.
python3 tools/specialist_check.py NAME GAMES [SEED]      (NAME "neutral@RATING" plays a neutral twin, as a baseline;
                                                         "NAME:field=value,..." overrides fields, e.g.
                                                         Mirela:reach=60,adjust=-80 or Ada:motif=promotion+reposition)
Also prints the specialist's self-captures by motif (chessiq.kansas.motif)."""
import dataclasses
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from collections import Counter  # noqa: E402
from chessiq.personalities import Personality, by_name  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402
from style_signature import game  # noqa: E402
from uci_match import elo, opening  # noqa: E402


def main():
    name, games = sys.argv[1], int(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 13
    base, _, kv = name.partition(":")
    sp = Personality("neutral", int(base.split("@")[1])) if base.startswith("neutral@") else by_name()[base]
    if kv:
        sp = dataclasses.replace(sp, **{k: int(v) if v.lstrip("-").isdigit() else v.replace("+", ",")
                                        for k, v in (x.split("=") for x in kv.split(","))})
    se, ne = PersonalityEngine(sp, seed=seed), PersonalityEngine(Personality("neutral", sp.rating), seed=seed + 1)
    rnd, score, sc, moves, motifs = random.Random(seed), 0.0, 0, 0, Counter()
    for g in range(games):
        if g % 2 == 0:
            start = opening(rnd)
        se.new_game(); ne.new_game()
        res, _, f = game(se, ne, "w" if g % 2 == 0 else "b", start)
        score += res; sc += f["sc"]; moves += f["moves"]; motifs += f["motifs"]
    se.close(); ne.close()
    d, ci = elo(score / games, games)
    print("%-12s %4d: %.1f / %d (%.0f%%), Elo %+.0f +/- %.0f; self-captures %.1f per 100 of %d moves; motifs %s"
          % (name, sp.rating, score, games, 100 * score / games, d, ci, 100.0 * sc / max(1, moves), moves,
             " ".join("%s %d" % kv for kv in motifs.most_common())), flush=True)


if __name__ == "__main__":
    main()

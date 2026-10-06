"""Style signatures in play (CM-16): a styled personality plays GAMES against a neutral one of the same rating through
chessIQ's PersonalityEngine (nodes from the ladder), every move checked against chessIQ's rules. Per move of the
styled side: moves into the enemy king's zone (within two squares of it), checks, enemy material taken (pawns), own
material given away by self-capture; per game: score, draws, length.
python3 tools/style_signature.py RATING GAMES STYLE [SEED]
  STYLE: neutral | attack=80 | contempt=300 | greedy (enemy material valued x2) | ...  (key=value, comma-separated)"""
import math
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from chessiq import engine as E  # noqa: E402
from chessiq.personalities import BASE, PIECES, Personality  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402
from uci_match import opening, uci_of  # noqa: E402

VAL = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 0}


def styled(rating, spec):
    p = Personality(spec, rating)
    for kv in filter(None, spec.split(",")):
        if kv == "neutral":
            continue
        if kv == "greedy":                      # enemy material counts double in its eyes
            p.material = {q: (BASE[q], 2 * BASE[q]) for q in PIECES}
            continue
        k, v = kv.split("=")
        setattr(p, k, int(v))
    return p


def king_zone(b, colour):
    k = next(i for i, x in enumerate(b) if x == colour + "k")
    return {i for i in range(64) if max(abs(i % 8 - k % 8), abs(i // 8 - k // 8)) <= 2}


def game(styled_e, neutral_e, styled_colour, start):
    b, turn, ep, moves, seen, half = E.init_board(), "w", None, [], {}, 0
    f = dict(moves=0, zone=0, checks=0, taken=0, given=0)
    for u in start:
        m = next(m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u)
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn); moves.append(u)
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            res = 0.5 if not E.in_check(b, turn) else (0.0 if turn == styled_colour else 1.0)
            return res, len(moves), f
        key = E.pos_key(b, turn, ep); seen[key] = seen.get(key, 0) + 1
        if E.insufficient_material(b) or seen[key] >= 3 or half >= 100 or len(moves) >= 400:
            return 0.5, len(moves), f
        e = styled_e if turn == styled_colour else neutral_e
        u = e.choose(moves)
        m = next(m for m in legal if uci_of(m) == u)
        if turn == styled_colour:
            enemy = E.opp(turn)
            f["moves"] += 1
            f["zone"] += m.to in king_zone(b, enemy)
            target = b[m.to]
            if target and target[0] == enemy:
                f["taken"] += VAL[target[1]]
            elif target and target[0] == turn:
                f["given"] += VAL[target[1]]
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn); moves.append(u)
        if turn != styled_colour and E.in_check(b, turn):
            f["checks"] += 1


def main():
    rating, games, spec = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    se = PersonalityEngine(styled(rating, spec), seed=seed)
    ne = PersonalityEngine(Personality("neutral", rating), seed=seed + 1)
    rnd = random.Random(seed)
    per_game, score, draws, plies = [], 0.0, 0, 0
    for g in range(games):
        if g % 2 == 0:
            start = opening(rnd)
        se.new_game(); ne.new_game()
        res, n, f = game(se, ne, "w" if g % 2 == 0 else "b", start)
        score += res; draws += res == 0.5; plies += n
        per_game.append(f)
    se.close(); ne.close()

    def rate(k):                                # per 100 styled moves, with a 95% interval over games
        xs = [100.0 * f[k] / max(1, f["moves"]) for f in per_game]
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1))
        return "%5.1f +/- %4.1f" % (m, 1.96 * sd / math.sqrt(len(xs)))
    print("%-14s r%d %3d games: score %4.1f%% draws %2d avg plies %3.0f | per 100 moves: zone %s  checks %s  "
          "taken %s  given %s" % (spec, rating, games, 100 * score / games, draws, plies / games, rate("zone"),
                                  rate("checks"), rate("taken"), rate("given")))


if __name__ == "__main__":
    main()

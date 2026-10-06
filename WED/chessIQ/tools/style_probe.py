"""Style without strength or chance: the same positions, fixed depth, no Elo limit -- which move does each
personality choose? Positions are sampled from neutral self-play (every 6th ply from 12 to 90).
python3 tools/style_probe.py <personality> [<personality> ...] [--positions N] [--depth D]   (from WED/chessIQ)
'neutral' is the engine with every knob at its default."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from chessiq import engine as E  # noqa: E402
from chessiq import personalities as P  # noqa: E402
from style_match import Engine, uci_of  # noqa: E402


def sample_positions(n, ms=30):
    eng, out, game = Engine(), [], 0
    while len(out) < n:
        game += 1
        eng.new_game()
        b, turn, ep, moves = E.init_board(), "w", None, []
        while len(moves) < 90:
            legal = E.legal_moves(b, turn, ep)
            if not legal or E.insufficient_material(b):
                break
            if len(moves) >= 12 and len(moves) % 6 == 0:
                out.append(list(moves))
            if game > 1 and len(moves) == 1:          # vary the games: a different first reply each time
                u = uci_of(legal[game % len(legal)])
            else:
                u = eng.best(moves, ms)
            m = next(m for m in legal if uci_of(m) == u)
            b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
            moves.append(u)
    eng.close()
    return out[:n]


def replay(moves):
    b, turn, ep = E.init_board(), "w", None
    for u in moves:
        m = next(m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u)
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return b, turn, ep


def features(moves, u):
    b, turn, ep = replay(moves)
    m = next(m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u)
    nb = E.apply_move(b, m)
    ek = E.king_sq(nb, E.opp(turn))
    dist = max(abs((m.to >> 3) - (ek >> 3)), abs((m.to & 7) - (ek & 7)))
    return {"capture": m.kind in ("enemy", "ep"), "pawn": m.kind == "ep" or (m.kind == "enemy" and b[m.to][1] == "p"),
            "check": E.in_check(nb, E.opp(turn)), "self": m.kind == "self", "kingdist": dist}


def probe(person, positions, depth):
    opts = person.engine_options() if person else {}
    opts["UCI_LimitStrength"] = "false"
    eng = Engine(opts)
    out = []
    for moves in positions:
        eng.new_game()
        eng.send("position startpos moves " + " ".join(moves))
        eng.send("go depth %d" % depth)
        out.append(eng.wait("bestmove").split()[1])
    eng.close()
    return out


if __name__ == "__main__":
    args, n, depth = sys.argv[1:], 120, 9
    if "--positions" in args:
        i = args.index("--positions"); n = int(args[i + 1]); del args[i:i + 2]
    if "--depth" in args:
        i = args.index("--depth"); depth = int(args[i + 1]); del args[i:i + 2]
    by = P.by_name()
    pos = sample_positions(n)
    base = probe(None, pos, depth)
    for name in ["neutral"] + args:
        mv = base if name == "neutral" else probe(by[name], pos, depth)
        f = [features(m, u) for m, u in zip(pos, mv)]
        k = len(f)
        print("%-10s differs from neutral %3d%% | captures %3d%%  pawn captures %3d%%  checks %3d%%  self %2d%%  "
              "mean distance to enemy king %.2f"
              % (name, 100 * sum(a != b for a, b in zip(mv, base)) // k, 100 * sum(x["capture"] for x in f) // k,
                 100 * sum(x["pawn"] for x in f) // k, 100 * sum(x["check"] for x in f) // k,
                 100 * sum(x["self"] for x in f) // k, sum(x["kingdist"] for x in f) / k), flush=True)

"""Training data for a Kramnik-chess Leela network (EPIC NN, sprint NN-3), from Kramnik Fairy-Stockfish self-play.

One JSON line per game:
  {"moves": [uci, ...], "policy": [[[uci, p], ...] per ply], "eval": [cp for the side to move per ply],
   "result": 1 | 0 | -1 (White's view), "end": reason}   (eval: the engine's best score; None where no policy)
Positions come from varied openings: a random grandmaster book line (0-16 plies, cut at castling -- legal Kramnik
chess), then 0-4 random moves (self-captures favoured), then engine play sampled with temperature for the first 20
plies. At every ply the engine's best MultiPV lines become a soft policy target: softmax(score / 100 cp) over up to 8
moves. Games end by mate, stalemate, insufficient material, threefold repetition, the 50-move rule, resignation
(|eval| >= 1000 cp for 6 consecutive plies, adjudicated to the side ahead) or 300 plies (a draw).
python3 tools/gen_training_data.py OUT.jsonl GAMES [--nodes N] [--seed S]      (from WED/chessIQ)"""
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402
from chessiq.game import book, strip_checks  # noqa: E402

FSF = os.environ.get("FSF", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))
INI = os.path.join(ROOT, "engine", "kramnik.ini")
MULTIPV, TEMP_CP, RESIGN_CP, RESIGN_PLIES, CAP = 8, 100.0, 1000, 6, 300


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


class Engine:
    def __init__(self, nodes):
        self.nodes = nodes
        self.p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        for c in ("uci", "setoption name VariantPath value " + INI, "setoption name UCI_Variant value kramnik",
                  "setoption name MultiPV value %d" % MULTIPV, "setoption name Threads value 1", "isready"):
            self.p.stdin.write(c + "\n")
        self.wait("readyok")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line
        raise RuntimeError("engine ended")

    def lines(self, moves):
        """{move: score in cp from the side to move} for the final depth's MultiPV lines."""
        self.p.stdin.write("position startpos" + (" moves " + " ".join(moves) if moves else "") + "\n")
        self.p.stdin.write("go nodes %d\n" % self.nodes)
        by_pv = {}
        for line in self.p.stdout:
            if line.startswith("info") and " multipv " in line and " pv " in line and " score " in line:
                t = line.split()
                k = int(t[t.index("multipv") + 1])
                kind, v = t[t.index("score") + 1], int(t[t.index("score") + 2])
                cp = v if kind == "cp" else (30000 - abs(v)) * (1 if v > 0 else -1)
                by_pv[k] = (t[t.index("pv") + 1], cp)
            elif line.startswith("bestmove"):
                break
        return dict(by_pv.values())

    def new_game(self):
        self.p.stdin.write("ucinewgame\nisready\n")
        self.wait("readyok")


def softmax(scores):
    top = max(scores.values())
    w = {m: math.exp((s - top) / TEMP_CP) for m, s in scores.items()}
    z = sum(w.values())
    return {m: x / z for m, x in w.items()}


def opening(rnd):
    """A grandmaster book line (weighted by games), cut at a random length, then a few random moves."""
    b, turn, ep, moves, sans = E.init_board(), "w", None, [], []
    target = rnd.randint(0, 16)
    bk = book()
    while len(sans) < target:
        opts = bk.get(" ".join(sans))
        if not opts:
            break
        r, pick = rnd.random() * sum(opts.values()), None
        for pick, n in sorted(opts.items()):
            r -= n
            if r < 0:
                break
        m = next((m for m in E.legal_moves(b, turn, ep) if strip_checks(E.san_of(b, m, ep)) == pick), None)
        if m is None:
            break
        sans.append(pick); moves.append(uci_of(m))
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    for _ in range(rnd.randint(0, 4)):
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            break
        selfs = [m for m in legal if m.kind == "self"]
        m = rnd.choice(selfs) if selfs and rnd.random() < 0.25 else rnd.choice(legal)
        moves.append(uci_of(m))
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return b, turn, ep, moves


def play(eng, rnd):
    eng.new_game()
    b, turn, ep, moves = opening(rnd)
    start = len(moves)
    policy, seen, half, streak, lead = [None] * start, Counter(), 0, 0, 0
    evals = [None] * start
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            res = (-1 if turn == "w" else 1) if E.in_check(b, turn) else 0
            return moves, policy, evals, res, "mate" if res else "stalemate"
        if E.insufficient_material(b):
            return moves, policy, evals, 0, "material"
        key = E.pos_key(b, turn, ep); seen[key] += 1
        if seen[key] >= 3:
            return moves, policy, evals, 0, "repetition"
        if half >= 100:
            return moves, policy, evals, 0, "fifty"
        if len(moves) >= CAP:
            return moves, policy, evals, 0, "cap"
        sc = eng.lines(moves)
        legal_u = {uci_of(m): m for m in legal}
        sc = {m: s for m, s in sc.items() if m in legal_u}
        if not sc:
            raise RuntimeError("engine returned no legal line at ply %d" % len(moves))
        pol = softmax(sc)
        policy.append(sorted(([m, round(p, 4)] for m, p in pol.items()), key=lambda x: -x[1]))
        best = max(sc, key=sc.get)
        stm_eval = sc[best]                                   # side to move's view
        evals.append(stm_eval)
        white_eval = stm_eval if turn == "w" else -stm_eval
        if abs(white_eval) >= RESIGN_CP and (streak == 0 or (white_eval > 0) == (lead > 0)):
            streak, lead = streak + 1, white_eval
        else:
            streak, lead = 0, 0
        if streak >= RESIGN_PLIES:
            return moves, policy, evals, 1 if lead > 0 else -1, "resign"
        if len(moves) - start < 20:                            # temperature: sample from the policy early on
            r, u = rnd.random(), best
            for u, p in sorted(pol.items(), key=lambda kv: -kv[1]):
                r -= p
                if r < 0:
                    break
        else:
            u = best
        m = legal_u[u]
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        moves.append(u)
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)


def main():
    args = sys.argv[1:]
    nodes, seed = 4000, 1
    if "--nodes" in args:
        i = args.index("--nodes"); nodes = int(args[i + 1]); del args[i:i + 2]
    if "--seed" in args:
        i = args.index("--seed"); seed = int(args[i + 1]); del args[i:i + 2]
    out, games = args[0], int(args[1])
    rnd, eng = random.Random(seed), Engine(nodes)
    positions = 0
    with open(out, "a") as f:
        for g in range(games):
            moves, policy, evals, res, end = play(eng, rnd)
            f.write(json.dumps({"moves": moves, "policy": policy, "eval": evals, "result": res, "end": end},
                               separators=(",", ":")) + "\n")
            f.flush()
            positions += sum(p is not None for p in policy)
            if (g + 1) % 10 == 0:
                print("%d games, %d positions" % (g + 1, positions), flush=True)


if __name__ == "__main__":
    main()

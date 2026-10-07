"""A match between two UCI engines at Kramnik chess (EPIC NN, sprint NN-5). Openings: grandmaster book lines of
random length (seeded, the same pair for both colours), every move checked against chessIQ's rules.
python3 tools/uci_match.py GAMES 'A: <cmd> | <setoption name=value;...> | <go args>' 'B: ...' [--seed S]
  e.g. 'lc0r1: engine/lc0-kramnik --weights=net.pb.gz --backend=blas --threads=1 | | nodes 400'
       'fsf1k: engine/fairy-stockfish-kramnik | VariantPath=engine/kramnik.ini;UCI_Variant=kramnik | nodes 1000'
Prints the score of A and an Elo difference with a 95% interval."""
import math
import os
import random
import shlex
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402
from chessiq.game import book, strip_checks  # noqa: E402


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


class Engine:
    def __init__(self, spec):
        name, rest = spec.split(":", 1)
        cmd, opts, go = (p.strip() for p in rest.split("|"))
        self.name, self.go = name.strip(), go
        self.p = subprocess.Popen([os.path.join(ROOT, a) if a.startswith("engine/") else a for a in shlex.split(cmd)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                  bufsize=1, cwd=ROOT)
        self.send("uci"); self.wait("uciok")
        for kv in filter(None, opts.split(";")):
            k, v = kv.split("=", 1)
            self.send("setoption name %s value %s" % (k.strip(), v.strip()))
        self.send("isready"); self.wait("readyok")

    def send(self, s):
        self.p.stdin.write(s + "\n")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line
        raise RuntimeError(self.name + " ended")

    def best(self, moves):
        self.send("position startpos" + (" moves " + " ".join(moves) if moves else ""))
        self.send("go " + self.go)
        return self.wait("bestmove").split()[1]

    def new_game(self):
        self.send("ucinewgame"); self.send("isready"); self.wait("readyok")

    def close(self):
        self.send("quit")
        self.p.wait()


def opening(rnd):
    b, turn, ep, moves, sans = E.init_board(), "w", None, [], []
    target = rnd.randint(2, 12)
    while len(sans) < target:
        opts = book().get(" ".join(sans))
        if not opts:
            break
        r, pick = rnd.random() * sum(opts.values()), None
        for pick, n in sorted(opts.items()):
            r -= n
            if r < 0:
                break
        m = next(m for m in E.legal_moves(b, turn, ep) if strip_checks(E.san_of(b, m, ep)) == pick)
        sans.append(pick); moves.append(uci_of(m))
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return moves


def play(white, black, start):
    b, turn, ep, moves, seen, half = E.init_board(), "w", None, [], Counter(), 0
    for u in start:
        m = next(m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u)
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn); moves.append(u)
    eng = {"w": white, "b": black}
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            return (0.0 if turn == "w" else 1.0) if E.in_check(b, turn) else 0.5
        key = E.pos_key(b, turn, ep); seen[key] += 1
        if E.insufficient_material(b) or seen[key] >= 3 or half >= 100 or len(moves) >= 400:
            return 0.5
        u = eng[turn].best(moves)
        m = next((m for m in legal if uci_of(m) == u), None)
        if m is None:
            raise SystemExit("%s played an illegal move %s" % (eng[turn].name, u))
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn); moves.append(u)


def elo(score, n):
    s = min(max(score, 0.5 / n), 1 - 0.5 / n)
    d = -400 * math.log10(1 / s - 1)
    se = math.sqrt(s * (1 - s) / n) / (s * (1 - s) * math.log(10) / 400)
    return d, 1.96 * se


def main():
    args = sys.argv[1:]
    seed = 1
    if "--seed" in args:
        i = args.index("--seed"); seed = int(args[i + 1]); del args[i:i + 2]
    games, a, b = int(args[0]), Engine(args[1]), Engine(args[2])
    rnd, score = random.Random(seed), 0.0
    for g in range(games):
        if g % 2 == 0:
            start = opening(rnd)
        a.new_game(); b.new_game()
        r = play(a, b, start) if g % 2 == 0 else 1 - play(b, a, start)
        score += r
        print("game %d: %s %.1f, total %.1f / %d" % (g + 1, a.name, r, score, g + 1), flush=True)
    d, ci = elo(score / games, games)
    print("%s vs %s: %.1f / %d (%.0f%%), Elo difference %+.0f +/- %.0f" % (a.name, b.name, score, games,
                                                                         100 * score / games, d, ci))
    a.close(); b.close()


if __name__ == "__main__":
    main()

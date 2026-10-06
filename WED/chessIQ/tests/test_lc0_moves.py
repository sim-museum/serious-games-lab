"""The Kramnik lc0 build (EPIC NN, sprint NN-1) against chessIQ's rules (themselves proven equal to the HTML gold).

lc0 has no perft, so every root move it considers is listed instead (VerboseMoveStats, one-node search) and compared
with chessIQ's legal moves, in positions reached by random Kramnik play -- which is full of self-captures,
promotions and en passant. The position goes in as "startpos moves ...", so lc0's move parsing and ApplyMove are
exercised on every move of every game.
LC0=<binary> LC0_WEIGHTS=<network>; skipped when either is missing."""
import os
import random
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402

LC0 = os.environ.get("LC0", os.path.join(ROOT, "engine", "lc0-kramnik"))   # engine/build_lc0.sh
WEIGHTS = os.environ.get("LC0_WEIGHTS", os.path.join(os.path.dirname(os.path.dirname(ROOT)), "WED", "INSTALL",
                                                     "tinygyal-8.pb.gz"))


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def random_positions(n_games, seed=1, max_plies=120):
    """(moves so far, set of legal UCI moves) at every ply of random games; self-captures are favoured."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n_games):
        b, turn, ep, moves = E.init_board(), "w", None, []
        while len(moves) < max_plies:
            legal = E.legal_moves(b, turn, ep)
            if not legal or E.insufficient_material(b):
                break
            out.append((list(moves), {uci_of(m) for m in legal}))
            special = [m for m in legal if m.kind in ("self", "ep") or m.promo]
            m = rnd.choice(special) if special and rnd.random() < 0.35 else rnd.choice(legal)
            b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
            moves.append(uci_of(m))
    return out


class Lc0:
    def __init__(self):
        self.p = subprocess.Popen([LC0, "--weights=" + WEIGHTS, "--backend=blas", "--threads=1"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        self.send("uci"); self.wait("uciok")
        self.send("setoption name VerboseMoveStats value true")
        self.send("setoption name SmartPruningFactor value 0")
        self.send("isready"); self.wait("readyok")

    def send(self, s):
        self.p.stdin.write(s + "\n")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line
        raise RuntimeError("lc0 ended")

    def root_moves(self, moves):
        self.send("position startpos" + (" moves " + " ".join(moves) if moves else ""))
        self.send("go nodes 1")
        out = set()
        for line in self.p.stdout:
            if line.startswith("info string ") and "(" in line:
                tok = line.split()[2]
                if tok != "node" and len(tok) in (4, 5):
                    out.add(tok)
            elif line.startswith("bestmove"):
                return out
        raise RuntimeError("lc0 ended")

    def close(self):
        self.send("quit")
        self.p.wait()
        self.p.stdin.close()
        self.p.stdout.close()


@unittest.skipUnless(os.access(LC0, os.X_OK) and os.path.exists(WEIGHTS), "Kramnik lc0 build or network missing")
class Lc0Moves(unittest.TestCase):
    def test_root_moves_match_chessiq(self):
        positions = random_positions(int(os.environ.get("LC0_GAMES", "12")))
        lc = Lc0()
        bad = []
        try:
            for moves, legal in positions:
                got = lc.root_moves(moves)
                if got != legal:
                    bad.append((moves, sorted(legal - got)[:5], sorted(got - legal)[:5]))
        finally:
            lc.close()
        self.assertEqual(bad[:3], [], "%d of %d positions differ" % (len(bad), len(positions)))


if __name__ == "__main__":
    unittest.main()

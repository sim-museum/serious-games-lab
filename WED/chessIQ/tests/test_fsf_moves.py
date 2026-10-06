"""The Kramnik Fairy-Stockfish against chessIQ's rules in many positions (EPIC CM; the check run on lc0 in NN-1).

Every root move Fairy-Stockfish lists (`go perft 1`) is compared with chessIQ's legal moves (themselves proven equal
to the HTML gold) at every ply of random Kramnik games full of self-captures, promotions and en passant. Positions
go in as "startpos moves ...", so the engine's move parsing and do_move are exercised on every move.
FSF=<binary>  KRAMNIK_INI=<variants file>  FSF_GAMES=<n>; skipped when the engine is missing."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from test_lc0_moves import random_positions  # noqa: E402

FSF = os.environ.get("FSF", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))
INI = os.environ.get("KRAMNIK_INI", os.path.join(ROOT, "engine", "kramnik.ini"))


class Fsf:
    def __init__(self, variant="kramnik"):
        self.p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        for c in ("uci", "setoption name VariantPath value " + INI, "setoption name UCI_Variant value " + variant,
                  "isready"):
            self.p.stdin.write(c + "\n")
        for line in self.p.stdout:
            if line.startswith("readyok"):
                break

    def root_moves(self, moves):
        self.p.stdin.write("position startpos" + (" moves " + " ".join(moves) if moves else "") + "\ngo perft 1\n")
        out = set()
        for line in self.p.stdout:
            if line.startswith("Nodes searched"):
                return out
            if ":" in line:
                tok = line.split(":")[0].strip()
                if 4 <= len(tok) <= 5:
                    out.add(tok)
        raise RuntimeError("engine ended")

    def close(self):
        self.p.stdin.write("quit\n")
        self.p.wait()
        self.p.stdin.close()
        self.p.stdout.close()


@unittest.skipUnless(os.access(FSF, os.X_OK) and os.path.exists(INI), "Kramnik Fairy-Stockfish missing")
class FsfMoves(unittest.TestCase):
    def test_root_moves_match_chessiq(self):
        positions = random_positions(int(os.environ.get("FSF_GAMES", "12")))
        e = Fsf()
        bad = []
        try:
            for moves, legal in positions:
                got = e.root_moves(moves)
                if got != legal:
                    bad.append((moves[-3:], sorted(legal - got)[:5], sorted(got - legal)[:5]))
        finally:
            e.close()
        self.assertEqual(bad[:3], [], "%d of %d positions differ" % (len(bad), len(positions)))


    def test_random_mover_plays_legal_moves(self):                                # CM-14: blunders come from perft
        sys.path.insert(0, ROOT)
        from chessiq.personalities import Personality
        from chessiq.uci_engine import PersonalityEngine
        moves, legal = random_positions(1)[30]
        e = PersonalityEngine(Personality("R", 1163, blunder=1.0), seed=3)
        try:
            picks = {e.choose(moves) for _ in range(30)}
        finally:
            e.close()
        self.assertTrue(picks <= legal)
        self.assertGreater(len(picks), 5)                                           # really random


if __name__ == "__main__":
    unittest.main()

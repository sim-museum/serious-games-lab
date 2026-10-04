"""chessIQ's engine against the gold: the original JavaScript engine in WED/kramnik_chess.html, run under node.
python3 -m unittest -v tests.test_parity   (from WED/chessIQ)"""
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from chessiq import engine as E  # noqa: E402


def board_from(rows):
    """8 strings of 8 chars, rank 8 first: KQRBNP white, kqrbnp black, '.' empty."""
    b = []
    for row in rows:
        for ch in row:
            b.append(None if ch == "." else ("w" if ch.isupper() else "b") + ch.lower())
    return b


CASES = [
    dict(name="start", board=E.init_board(), turn="w", ep=None, perft=3, depth=4),
    # open middlegame, both sides with self-capture options
    dict(name="middlegame", turn="w", ep=None, perft=2, depth=3, board=board_from([
        "r.bqk..r", "pp...ppp", "..np.n..", "..b.p...", "..B.P...", "..NP.N..", "PPP..PPP", "R.BQK..R"])),
    # white three pawns up: the self-capture drive is ON
    dict(name="ahead-bias", turn="w", ep=None, perft=2, depth=3, board=board_from([
        "r...k..r", "...q.ppp", "..n.....", "........", "...PP...", "..N..N..", "PPPQ.PPP", "R...KB.R"])),
    # en passant available (black just played d7-d5), promotion threats
    dict(name="ep-promo", turn="w", ep=19, perft=3, depth=4, board=board_from([
        "....k...", ".P......", "........", "...pP...", "........", "........", "......p.", "....K..."])),
    # mate in one exists via a self-capture-cleared line
    dict(name="mating", turn="w", ep=None, perft=2, depth=3, board=board_from([
        "......k.", ".....ppp", "........", "........", "........", "........", ".....PPP", "R.....K."])),
]


def run_oracle(cases):
    payload = [dict(board=c["board"], turn=c["turn"], ep=c["ep"], perft=c.get("perft"), depth=c.get("depth"))
               for c in cases]
    out = subprocess.run(["node", os.path.join(HERE, "oracle.js")], input=json.dumps(payload),
                         capture_output=True, text=True, timeout=900)
    if out.returncode:
        raise RuntimeError(out.stderr)
    return json.loads(out.stdout)


def perft(b, color, ep, d):
    if d == 0:
        return 1
    return sum(perft(E.apply_move(b, m), E.opp(color), m.dbl, d - 1) for m in E.legal_moves(b, color, ep))


@unittest.skipUnless(shutil.which("node"), "node is needed to run the gold engine")
class ParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold = run_oracle(CASES)

    def test_legal_moves_and_san(self):
        for c, g in zip(CASES, self.gold):
            sans = [E.san_of(c["board"], m, c["ep"]) for m in E.legal_moves(c["board"], c["turn"], c["ep"])]
            self.assertEqual(sans, g["sans"], c["name"])

    def test_evaluation(self):
        for c, g in zip(CASES, self.gold):
            self.assertAlmostEqual(E.evaluate(c["board"]), g["eval"], places=6, msg=c["name"])

    def test_perft(self):
        for c, g in zip(CASES, self.gold):
            self.assertEqual(perft(c["board"], c["turn"], c["ep"], c["perft"]), g["perft"], c["name"])

    def test_search_is_identical(self):
        """Same best move, same root score, same node count: the searches walk the same tree."""
        for c, g in zip(CASES, self.gold):
            st = {}
            m = E.best_move(c["board"], c["turn"], c["ep"], t=1e9, d=c["depth"], stats=st)
            mine = [m.frm, m.to, m.promo, m.kind, m.v]
            self.assertEqual(mine[:4], g["best"][:4], c["name"])
            if g["best"][4] is not None:
                self.assertAlmostEqual(mine[4], g["best"][4], places=6, msg=c["name"])
            self.assertEqual(st.get("nodes"), g["nodes"], c["name"])


if __name__ == "__main__":
    unittest.main()

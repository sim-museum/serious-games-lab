"""Fairy-Stockfish's `kramnik` variant (self-capture patch) against the gold: the original JavaScript engine in
WED/kramnik_chess.html under node. Same perft counts on every position, or the engine is not playing Kramnik chess.
Skipped when the engine binary or node is missing.  FSF=<path to binary>  KRAMNIK_INI=<path to variants file>"""
import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FSF = os.environ.get("FSF", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))   # engine/build_engine.sh
INI = os.environ.get("KRAMNIK_INI", os.path.join(ROOT, "engine", "kramnik.ini"))

POSITIONS = [   # (name, FEN, depth)
    ("start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1", 4),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w - - 0 1", 3),
    ("rook-endgame", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4),
    ("promotions", "n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1", 3),
    ("en-passant", "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w - f6 0 3", 3),
    ("pins", "r6r/1b2k1bq/8/8/7B/8/8/R3K2R b - - 3 2", 3),
]


def fen_to_case(fen, depth):
    parts = fen.split()
    board = []
    for row in parts[0].split("/"):
        for ch in row:
            if ch.isdigit():
                board += [None] * int(ch)
            else:
                board.append(("w" if ch.isupper() else "b") + ch.lower())
    ep = None
    if parts[3] != "-":
        col, rank = ord(parts[3][0]) - 97, int(parts[3][1])
        ep = (8 - rank) * 8 + col
    return dict(board=board, turn=parts[1], ep=ep, perft=depth, depth=None)


def oracle(cases):
    out = subprocess.run(["node", os.path.join(HERE, "oracle.js")], input=json.dumps(cases),
                         capture_output=True, text=True, timeout=3600)
    if out.returncode:
        raise RuntimeError(out.stderr)
    return [r["perft"] for r in json.loads(out.stdout)]


def fsf_perft(fen, depth):
    cmds = ("uci\nsetoption name VariantPath value %s\nsetoption name UCI_Variant value kramnik\n"
            "position fen %s\ngo perft %d\nquit\n" % (INI, fen, depth))
    out = subprocess.run([FSF], input=cmds, capture_output=True, text=True, timeout=600).stdout
    for line in out.splitlines():
        if line.startswith("Nodes searched:"):
            return int(line.split()[-1])
    raise RuntimeError("no perft result:\n" + out[-500:])


@unittest.skipUnless(os.path.exists(FSF) and os.path.exists(INI) and shutil.which("node"), "engine or node missing")
class FsfPerft(unittest.TestCase):
    def test_perft_matches_gold(self):
        gold = oracle([fen_to_case(f, d) for _, f, d in POSITIONS])
        for (name, fen, depth), g in zip(POSITIONS, gold):
            with self.subTest(position=name, depth=depth):
                self.assertEqual(fsf_perft(fen, depth), g)


if __name__ == "__main__":
    unittest.main()

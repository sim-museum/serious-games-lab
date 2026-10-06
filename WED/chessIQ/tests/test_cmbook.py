"""Chessmaster .OBK reader (EPIC CM, sprint CM-10) on a synthetic book -- no Chessmaster data needed."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import cmbook  # noqa: E402

SQ = {f + r: (int(r) - 1) * 8 + "abcdefgh".index(f) for f in "abcdefgh" for r in "12345678"}


def entry(frm, to, sibling_follows=False, ends_line=False):
    return bytes([SQ[frm] | (0 if sibling_follows else 0x40) | (0x80 if ends_line else 0), SQ[to] | 0xC0])


class Obk(unittest.TestCase):
    def test_tree_and_castling_cut(self):
        moves = [entry("e2", "e4", sibling_follows=True),       # 1.e4 ...          (1.d4 follows later)
                 entry("e7", "e5", sibling_follows=True),       #   1...e5 2.Nf3    (1...c5 follows)
                 entry("g1", "f3", ends_line=True),
                 entry("c7", "c5"),                              #   1...c5 2.Nf3 Nc6 3.Bb5 g6 4.O-O (cut)
                 entry("g1", "f3"), entry("b8", "c6"), entry("f1", "b5"), entry("g7", "g6"),
                 entry("e1", "g1", ends_line=True),
                 entry("d2", "d4", ends_line=True)]               # 1.d4
        data = b"BOO!" + struct.pack("<II", len(moves), 0) + b"".join(moves)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.obk")
            open(p, "wb").write(data)
            book = cmbook.read_obk(p)
        self.assertEqual(book[""], {"e4": 2, "d4": 1})
        self.assertEqual(book["e4"], {"e5": 1, "c5": 1})
        self.assertEqual(book["e4 c5 Nf3 Nc6 Bb5 g6"] if "e4 c5 Nf3 Nc6 Bb5 g6" in book else None, None)  # castling cut
        self.assertEqual(book["e4 c5 Nf3 Nc6 Bb5"], {"g6": 1})

    def test_other_formats(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.obk")
            open(p, "wb").write(b"XXXX" + bytes(20))
            self.assertIsNone(cmbook.read_obk(p))


if __name__ == "__main__":
    unittest.main()

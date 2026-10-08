"""EPIC KS: Kramnik-rules helpers and the self-capture specialists' move choice (KS-1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import kansas as K  # noqa: E402
from chessiq.personalities import Personality  # noqa: E402
from chessiq.uci_engine import SC_BONUS, PersonalityEngine  # noqa: E402

AZ38 = "r2q1rk1/p2nbpp1/5n2/2p4p/2N2B1P/5Q2/P3NPP1/3R1RK1 b - - 0 19"     # paper game AZ-38: 19...Rxa7


class Helpers(unittest.TestCase):
    def test_fen_round_trip(self):
        for fen in (K.START, AZ38):
            self.assertEqual(K.to_fen(*K.from_fen(fen)), fen)

    def test_replay_counts_and_en_passant(self):
        b, turn, ep, half, full = K.replay(["e2e4", "a7a6", "e4e5", "d7d5"])
        self.assertEqual(K.to_fen(b, turn, ep, half, full),
                         "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w - d6 0 3")
        b, turn, ep, half, full = K.replay(["g1f3", "g8f6", "f3g1"])
        self.assertEqual((half, full), (3, 2))

    def test_self_capture_replays_and_is_recognised(self):
        b, turn, *_ = K.from_fen(AZ38)
        self.assertTrue(K.is_self_capture(b, turn, "a8a7"))
        self.assertFalse(K.is_self_capture(b, turn, "a8b8"))
        b2, turn2, *_ = K.replay(["a8a7"], AZ38)
        self.assertEqual(b2[8], "br")          # a7 now holds the rook
        self.assertEqual(turn2, "w")

    def test_illegal_move_raises(self):
        with self.assertRaises(ValueError):
            K.replay(["e2e5"])


def stub(kansas, off):
    """A PersonalityEngine with no processes: _off_scores answers from `off`."""
    e = object.__new__(PersonalityEngine)
    e.p, e.kansas, e.nodes, e.last_kansas = Personality("t", 1600, kansas=kansas), kansas, 100, None
    e._off_scores = lambda fen, cands: {m: off[m] for m in cands if m in off}
    return e


class Appetite(unittest.TestCase):
    MOVES = ["e2e4", "e7e5", "g1f3", "b8c6"]        # White to move

    def test_prefers_the_move_that_gains_from_kramnik_rules(self):
        lines = {1: (40, "b1c3"), 2: (30, "d2d4"), 3: (25, "f1c4")}
        # off-rules: b1c3 is just as good without self-capture, d2d4 is 60 cp worse without it
        e = stub(100, {"b1c3": 40, "d2d4": -30, "f1c4": 25})
        self.assertEqual(e._kansas_pick(self.MOVES, lines, "b1c3"), "d2d4")
        self.assertEqual(e.last_kansas, ("d2d4", "b1c3", 60))

    def test_never_leaves_the_margin(self):
        lines = {1: (40, "b1c3"), 2: (-200, "d2d4")}
        e = stub(100, {"b1c3": 40, "d2d4": -1000})
        self.assertIsNone(e._kansas_pick(self.MOVES, lines, "b1c3"))     # only one candidate within 60 cp

    def test_a_self_capture_gets_the_bonus(self):
        moves = ["e2e4", "e7e5", "f1e2", "d7d6"]    # Bf1-e2; now Qd1xe2 is a self-capture
        lines = {1: (35, "b1c3"), 2: (20, "d1e2")}
        e = stub(50, {"b1c3": 35})
        self.assertEqual(e._kansas_pick(moves, lines, "b1c3"), "d1e2")    # 20 + 0.5 * SC_BONUS > 35
        self.assertGreater(20 + 0.5 * SC_BONUS, 35)

    def test_zero_appetite_changes_nothing(self):
        lines = {1: (40, "b1c3"), 2: (30, "d2d4")}
        e = stub(0, {"b1c3": 40, "d2d4": -500})
        self.assertEqual(e._kansas_pick(self.MOVES, lines, "b1c3"), "b1c3")


if __name__ == "__main__":
    unittest.main()

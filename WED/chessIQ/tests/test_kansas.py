"""EPIC KS: Kramnik-rules helpers and the self-capture specialists' move choice (KS-1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import kansas as K  # noqa: E402
from chessiq.personalities import Personality  # noqa: E402
from chessiq.uci_engine import BINARY, SC_BONUS, VARIANTS, PersonalityEngine  # noqa: E402

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


@unittest.skipUnless(os.access(BINARY, os.X_OK), "Kramnik Fairy-Stockfish missing")
class NoEndlessSearch(unittest.TestCase):         # found in KS-7: tournament quick results give no clock
    def test_full_strength_without_a_clock_answers(self):
        import time
        from chessiq.personalities import by_name
        e = PersonalityEngine(by_name()["The Engine"])
        try:
            t = time.monotonic()
            self.assertIsNotNone(e.choose([]))
            self.assertLess(time.monotonic() - t, 5)
        finally:
            e.close()


@unittest.skipUnless(os.access(BINARY, os.X_OK), "Kramnik Fairy-Stockfish missing")
class Moments(unittest.TestCase):                 # KS-3
    def setUp(self):
        self.rs = K.RuleSwitch(BINARY, VARIANTS, nodes=20000)

    def tearDown(self):
        self.rs.close()

    def test_a_played_self_capture_is_found_and_described(self):
        ms = K.moments(["e2e4", "e7e5", "f1e2", "d7d6", "d1e2"], self.rs)       # 3.Qxe2: the queen takes its bishop
        played = [m for m in ms if m["kind"] == "played"]
        self.assertEqual([(m["ply"], m["san"]) for m in played], [(4, "Qxe2")])
        self.assertGreaterEqual(played[0]["loss"], 200)                         # it gives a bishop away for nothing
        self.assertIn("3.Qxe2", K.describe(played[0]))

    def test_the_kings_escape_is_labelled(self):
        fen = "r5k1/1p3p2/p1pn3r/3p4/PP1P2P1/3BPQ2/5PP1/R1R3Kq w - - 0 39"
        ms = K.moments(["g1f2"], self.rs, start=fen)           # the paper's AZ-33: the king takes its own pawn
        self.assertEqual([m["kind"] for m in ms], ["played"])
        self.assertEqual(ms[0]["motif"], "escape")

    def test_cancel_returns_none(self):
        self.assertIsNone(K.moments(["e2e4"], self.rs, cancel=lambda: True))


@unittest.skipUnless(os.access(BINARY, os.X_OK), "Kramnik Fairy-Stockfish missing")
class Coach(unittest.TestCase):                   # KS-6
    @classmethod
    def setUpClass(cls):
        cls.rs = K.RuleSwitch(BINARY, VARIANTS, nodes=200000)

    @classmethod
    def tearDownClass(cls):
        cls.rs.close()

    def test_warns_about_the_ordinary_chess_move_without_giving_the_answer(self):
        word = K.coach("4kb1r/1Qp2p2/p4nnp/2q1p1p1/4P3/2P2NNP/PP3PK1/R1B4r w - - 0 19", self.rs)
        self.assertEqual(word[0], "warning")
        self.assertIn("Qc8+", word[1])
        self.assertNotIn("Be3", word[1])

    def test_points_to_a_strong_self_capture(self):
        word = K.coach("8/3P1p1k/3R4/6R1/p6P/5Pp1/6P1/1r4K1 w - - 1 41", self.rs)    # only Kxg2 saves White
        self.assertEqual(word[0], "chance")
        self.assertIn("king", word[1])

    def test_quiet_when_nothing_hinges_on_it(self):
        self.assertIsNone(K.coach(K.START, self.rs))


if __name__ == "__main__":
    unittest.main()

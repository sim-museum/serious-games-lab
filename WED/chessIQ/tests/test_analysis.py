"""Post-game analysis (EPIC CM, CM-19): the manual's game types on constructed evaluation sequences, and a real game."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import analysis as A  # noqa: E402
from chessiq import engine as E  # noqa: E402
from chessiq.personalities import Personality  # noqa: E402


class Types(unittest.TestCase):
    def test_dominated(self):                     # White ahead from early on, never behind
        ev = [0, 20, 60, 120, 150, 200, 260, 400, 900, A.MATE]
        self.assertEqual(A.classify(ev, 1.0), "Dominated")

    def test_blunder(self):                       # level until Black's 4th move (ply 8) throws it; never recovers
        ev = [0, 10, -20, 30, 0, 40, 20, 30, 480, 500, 700, A.MATE]
        self.assertEqual(A.classify(ev, 1.0), "Blunder")
        self.assertEqual(A.blunders(ev), [(8, 450)])

    def test_moves_in_a_decided_game_are_not_blunders(self):
        ev = [0, 10, -20, 30, 500, 1200, 1300, A.MATE - 3, A.MATE - 2]     # Black throws it at ply 4; then lost anyway
        self.assertEqual(A.blunders(ev), [(4, 470)])
        self.assertEqual(A.classify(ev, 1.0), "Blunder")

    def test_a_blunder_by_the_winner_is_not_the_cause(self):
        ev = [0, -350, -300, -280, -100, 50, 200, 400, 600, A.MATE]   # White blundered at once, then outplayed Black
        self.assertEqual(A.classify(ev, 1.0), "Disputed")

    def test_disputed(self):
        ev = [0, 150, 120, -200, -180, 60, 250, 300, -400, -A.MATE]
        self.assertEqual(A.classify(ev, 0.0), "Disputed")

    def test_balanced_draw(self):
        ev = [0, 10, -20, 30, 0, 40, 20, -10, 60, 0]
        self.assertEqual(A.classify(ev, 0.5), "Balanced")

    def test_disputed_draw(self):
        self.assertEqual(A.classify([0, 150, 100, -200, -50, 0], 0.5), "Disputed")

    def test_suggestion_follows_the_result(self):
        people = [Personality(n, r) for n, r in (("A", 1200), ("B", 1300), ("C", 1380), ("D", 1450))]
        self.assertEqual(A.suggest_opponent(people, "C", 1300, 1.0).name, "D")      # win: target 1400, C just played
        self.assertEqual(A.suggest_opponent(people, "C", 1300, 0.0).name, "A")      # loss: target 1200
        self.assertEqual(A.suggest_opponent(people, "B", 1300, 0.5).name, "C")      # draw: nearest other than B

    def test_gm_plies(self):
        self.assertGreaterEqual(A.gm_plies(["e4", "e5", "Nf3"]), 2)
        self.assertEqual(A.gm_plies([]), 0)
        self.assertEqual(A.gm_plies(["e4", "e5", "Ke2", "Ke7", "Ke3"]), 2)            # nobody plays the king walk


@unittest.skipUnless(A.available(), "Kramnik Fairy-Stockfish missing")
class RealGame(unittest.TestCase):
    def test_a_decisive_engine_game(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        from chessiq.uci_engine import PersonalityEngine
        strong, weak = PersonalityEngine(Personality("S", 2000), seed=1), PersonalityEngine(Personality("W", 1163),
                                                                                             seed=2)
        b, turn, ep, moves, sans = E.init_board(), "w", None, [], []
        try:
            while E.legal_moves(b, turn, ep) and len(moves) < 160:
                u = (strong if turn == "w" else weak).choose(moves)
                m = next(m for m in E.legal_moves(b, turn, ep) if A._uci(m) == u)
                sans.append(E.san_of(b, m, ep))
                moves.append(u); b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        finally:
            strong.close(); weak.close()
        ev = A.evaluate_game(moves, nodes=20000)
        self.assertEqual(len(ev), len(moves) + 1)
        self.assertLess(abs(ev[0]), 150)                   # the start is about level
        if not E.legal_moves(b, turn, ep) and E.in_check(b, turn):
            self.assertEqual(ev[-1], A.MATE if turn == "b" else -A.MATE)
        kind, text = A.summary(ev, 1.0 if ev[-1] > 0 else 0.0, sans, "Strong", "Weak")
        self.assertIn(kind, ("Blunder", "Dominated", "Disputed", "Balanced"))
        self.assertIn("Game type", text)


if __name__ == "__main__":
    unittest.main()

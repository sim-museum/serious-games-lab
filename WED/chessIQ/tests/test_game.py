"""chessIQ game layer, headless: python3 -m unittest -v tests.test_game   (from WED/chessIQ)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import engine as E  # noqa: E402
from chessiq.game import Game, load_pgn, book  # noqa: E402


def play(g, *sans):
    for s in sans:
        m = g.move_from_san(s)
        assert m is not None, s
        g.do_move(m)


class GameTest(unittest.TestCase):
    def test_no_castling_and_self_capture_is_legal(self):
        g = Game("human", seed=1, book_mem={})
        play(g, "e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5")
        self.assertIsNone(g.move_from_san("O-O"))
        self.assertIsNone(g.move_from_san("Kg1"))
        m = g.move_from_san("Nxe5")                 # enemy capture
        self.assertEqual(m.kind, "enemy")
        m = g.move_from_san("Bxf7")
        self.assertEqual(m.kind, "enemy")
        m = g.move_from_san("Rxh2")                 # rook takes its own pawn
        self.assertEqual(m.kind, "self")

    def test_threefold_by_shuffling_knights(self):
        g = Game("human", seed=1, book_mem={})
        play(g, "Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8")
        self.assertEqual(g.over, {"type": "draw", "reason": "threefold repetition"})

    def test_fools_mate_is_not_mate_here(self):
        """A king may capture its own pieces: after 1.f3 e5 2.g4 Qh4+ White escapes (the gold agrees)."""
        g = Game("human", seed=1, book_mem={})
        play(g, "f3", "e5", "g4", "Qh4")
        self.assertIsNone(g.over)
        self.assertEqual(sorted(E.san_of(g.board, m, g.ep) for m in g.legal()), ["Kxd1", "Kxd2", "Kxe2", "Kxf1"])
        text = g.pgn("Ann", "Bob")
        self.assertIn("1. f3 e5 2. g4 Qh4+ *", text)
        g2, bad = load_pgn(text)
        self.assertIsNone(bad)
        self.assertEqual([h["san"] for h in g2.history], ["f3", "e5", "g4", "Qh4+"])
        self.assertEqual(g2.mode, "human")

    def test_mate_is_detected(self):
        g = Game("human", seed=1, book_mem={})
        g.board = [None] * 64
        g.board[7], g.board[22], g.board[13] = "bk", "wk", "wq"     # Kh8; Kg6, Qf7
        g.turn = "w"
        g.check_end()
        g.do_move(g.move_from_san("Qg7"))
        self.assertEqual(g.over, {"type": "mate", "winner": "w"})
        self.assertEqual(g.history[-1]["san"], "Qg7#")

    def test_pgn_restores_who_played_whom(self):
        g = Game("ai", human="b", seed=1, book_mem={})
        play(g, "e4")
        g2, _ = load_pgn(g.pgn(*g.names()))
        self.assertEqual((g2.mode, g2.human, g2.turn), ("ai", "b", "b"))

    def test_undo_vs_computer_returns_to_players_turn(self):
        g = Game("ai", human="w", seed=1, book_mem={})
        play(g, "e4", "e5")
        g.undo()
        self.assertEqual((len(g.history), g.turn), (0, "w"))

    def test_book_follows_grandmasters_and_varies(self):
        mem = {}
        g = Game("self", seed=7, book_mem=mem)
        m = g.book_move()
        self.assertIn(E.san_of(g.board, m, g.ep), set(book()[""]))
        first = mem[""]
        g2 = Game("self", seed=7, book_mem=mem)    # same seed: only the variety rule can change the choice
        m2 = g2.book_move()
        self.assertNotEqual(E.san_of(g2.board, m2, g2.ep), first)
        self.assertTrue(Game("human", book_mem={}).book_hints())

    def test_computer_moves_out_of_book(self):
        g = Game("ai", human="b", seed=3, book_mem={})
        play(g, "a3", "h6", "h3", "a6")            # a line no grandmaster played: no book
        self.assertIsNone(g.book_move())
        m = g.think(t=0.5)
        self.assertIn(m.frm, [x.frm for x in g.legal()])


if __name__ == "__main__":
    unittest.main()

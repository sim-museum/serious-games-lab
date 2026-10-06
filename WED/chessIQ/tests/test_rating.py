"""Rating arithmetic (EPIC CM, sprint CM-4)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import rating as R  # noqa: E402


class Arithmetic(unittest.TestCase):
    def test_chessmaster_manual_example(self):
        # "loss: -424, draw: -24, win: +376" -- a new player facing someone ~21 points weaker
        loss, draw, win = R.changes(1500, 1479, 0)
        self.assertEqual((loss, draw, win), (-424, -24, 376))

    def test_k_settles(self):
        self.assertEqual(R.k_factor(0), 800)
        self.assertEqual(R.k_factor(19), 40)
        self.assertEqual(R.k_factor(100), 16)

    def test_symmetry(self):
        loss, draw, win = R.changes(1500, 1500, 30)
        self.assertEqual((loss, draw, win), (-round(R.k_factor(30) / 2), 0, round(R.k_factor(30) / 2)))


class Profile(unittest.TestCase):
    def test_record_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "profile.json")
            p = R.Profile("Ana", 1400, path=path)
            self.assertTrue(p.provisional)
            win = p.preview(1600)[2]
            self.assertEqual(p.record("Tomas", 1600, 1, "w", 80), win)
            q = R.Profile.load(path)
            self.assertEqual((q.name, q.rating, q.games), ("Ana", 1400 + win, 1))
            self.assertEqual(q.history[0]["opponent"], "Tomas")
            for _ in range(R.PROVISIONAL - 1):
                q.record("Pip", 800, 1)
            self.assertFalse(q.provisional)

    def test_missing_profile(self):
        self.assertIsNone(R.Profile.load("/nonexistent/profile.json"))


if __name__ == "__main__":
    unittest.main()

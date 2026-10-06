"""Clock arithmetic (EPIC CM, sprint CM-5), driven by a fake time source."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import clock as C  # noqa: E402


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Fischer(unittest.TestCase):
    def test_ten_plus_three(self):
        ft = FakeTime()
        c = C.Clock("fischer", (10, 3), now=ft)
        c.start("w")
        ft.t += 5000; c.moved("w")             # white spends 5 s, gains 3 s
        ft.t += 12000; c.moved("b")            # black spends 12 s, gains 3 s
        self.assertEqual(c.remaining("w"), 600000 - 5000 + 3000)
        self.assertEqual(c.remaining("b"), 600000 - 12000 + 3000)
        ft.t += 1000
        self.assertEqual(c.remaining("w"), 598000 - 1000)      # white's clock runs live
        self.assertEqual(c.uci(), {"wtime": 597000, "btime": 591000, "winc": 3000, "binc": 3000})

    def test_flag(self):
        ft = FakeTime()
        c = C.Clock("fischer", (1, 0), now=ft)
        c.start("w")
        ft.t += 30000; c.moved("w")
        ft.t += 60001
        self.assertEqual(c.check_flag(), "b")
        self.assertEqual(c.remaining("b"), 0)
        self.assertEqual(c.moved("b"), "b")    # a move after the flag fell does not save it

    def test_pause_does_not_spend(self):
        ft = FakeTime()
        c = C.Clock("game", (5,), now=ft)
        c.start("w"); ft.t += 1000; c.stop()
        ft.t += 50000
        self.assertEqual(c.remaining("w"), 299000)


class MovesPerTime(unittest.TestCase):
    def test_block_added_after_n_moves(self):
        ft = FakeTime()
        c = C.Clock("moves", (2, 1), now=ft)    # 2 moves in 1 minute, repeating
        c.start("w")
        for _ in range(2):
            ft.t += 10000; c.moved("w"); ft.t += 1000; c.moved("b")
        self.assertEqual(c.remaining("w"), 60000 - 20000 + 60000)


class Untimed(unittest.TestCase):
    def test_no_clock(self):
        c = C.Clock()
        c.start("w")
        self.assertFalse(c.timed)
        self.assertIsNone(c.remaining("w"))
        self.assertIsNone(c.moved("w"))


class Format(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(C.fmt(600000), "10:00")
        self.assertEqual(C.fmt(9500), "9.5")


class ThinkTime(unittest.TestCase):              # CM-15: personalities pause like players, never into a flag
    def test_think_time(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from chessiq.app import think_time
        clk = {"wtime": 600000, "btime": 600000, "winc": 3000, "binc": 3000}
        mid = think_time(clk, "w", 0, 0.5)
        self.assertTrue(10 < mid < 30, mid)                                     # about 19 s early in 10+3
        self.assertLess(think_time(clk, "w", 0, 0.0), think_time(clk, "w", 0, 0.99))
        low = {"wtime": 5000, "btime": 5000, "winc": 3000, "binc": 3000}
        self.assertLessEqual(think_time(low, "b", 80, 0.99), 0.4 + 1e-9)         # 8% of 5 s, floored at 0.4 s
        self.assertTrue(0.8 <= think_time(None, "w", 10, 0.5) <= 3.0)            # untimed


if __name__ == "__main__":
    unittest.main()

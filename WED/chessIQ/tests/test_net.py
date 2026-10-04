"""chessIQ network play: two real windows in one process, talking over localhost TCP (offscreen Qt, no squeak).
QT_QPA_PLATFORM=offscreen python3 -m unittest -v tests.test_net   (from WED/chessIQ)"""
import os
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SQUEAK_OFF"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication  # noqa: E402

APP = QApplication.instance() or QApplication([])
from chessiq.app import MainWindow  # noqa: E402

PORT = 47891


def pump(until, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        APP.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return False


def click(w, a, b):
    sq = lambda s: (8 - int(s[1])) * 8 + "abcdefgh".index(s[0])
    w.on_square(sq(a))
    w.on_square(sq(b))


class NetTest(unittest.TestCase):
    def setUp(self):
        self.host, self.guest = MainWindow(), MainWindow()
        self.assertTrue(self.host.start_hosting("Ann", PORT, "w"))
        self.guest.start_joining("Bob", "127.0.0.1", PORT)
        self.assertTrue(pump(lambda: self.guest.game.mode == "net" and self.guest.link.peer_name == "Ann"
                             and self.host.link.peer_name == "Bob"))

    def tearDown(self):
        for w in (self.guest, self.host):
            w.close()
        pump(lambda: False, 0.3)

    def test_moves_chat_draw_and_resign(self):
        h, g = self.host, self.guest
        self.assertEqual((h.game.human, g.game.human), ("w", "b"))
        click(g, "e7", "e5")                                   # not the guest's turn: ignored
        self.assertEqual(len(g.game.history), 0)
        click(h, "e2", "e4")
        self.assertTrue(pump(lambda: len(g.game.history) == 1))
        click(g, "e7", "e5")
        self.assertTrue(pump(lambda: len(h.game.history) == 2))
        click(h, "h1", "h2")                                   # rook takes its own pawn: legal in Kramnik chess
        self.assertTrue(pump(lambda: len(g.game.history) == 3))
        self.assertEqual(g.game.history[-1]["san"], "Rxh2")
        self.assertTrue(g.game.history[-1]["self"])
        g.chat_in.setText("nice sac")
        g.send_chat()
        self.assertTrue(pump(lambda: "Bob: nice sac" in h.chat_log.toPlainText()))
        g.offer_draw()
        self.assertTrue(pump(lambda: h.offer_bar.isVisibleTo(h)))
        h.decline_draw()
        self.assertTrue(pump(lambda: "declines" in g.note))
        g.resign(confirm=False)
        self.assertTrue(pump(lambda: h.game.over == {"type": "resign", "winner": "w"}))
        self.assertEqual(g.game.over, {"type": "resign", "winner": "w"})
        h.new_game()                                           # the host starts the next game, colours swapped
        self.assertTrue(pump(lambda: g.game.human == "w" and not g.game.history))
        self.assertEqual(h.game.human, "b")
        g.new_game()                                           # only the host may
        self.assertEqual(h.game.human, "b")

    def test_an_impossible_move_closes_the_connection(self):
        h, g = self.host, self.guest
        g.link.send(t="move", ply=0, san="e5")                 # out of turn, and not a white move
        self.assertTrue(pump(lambda: h.link.sock is None and g.link.sock is None))
        self.assertEqual(len(h.game.history), 0)


if __name__ == "__main__":
    unittest.main()

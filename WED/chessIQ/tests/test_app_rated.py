"""Rated games give no advice, as in Chessmaster's Ranked Play ("no advice tools are available") (EPIC CM, CM-13).
Runs the real window off-screen with a throwaway profile directory."""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FSF = os.path.join(ROOT, "engine", "fairy-stockfish-kramnik")


@unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
class RatedGivesNoAdvice(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from chessiq import app as A, rating as R
        self.qa = QApplication.instance() or QApplication([])
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        R.Profile("Tester", 1400).save()
        self.w = A.MainWindow()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def start(self, rated):
        w = self.w
        w.who.setCurrentIndex(w.who.findData("Tasha"))
        w.mode.setCurrentIndex(w.mode.findData("ai"))
        w.side.setCurrentIndex(w.side.findData("w"))
        w.rated_box.setChecked(rated)
        w.new_game()
        w.render()

    def test_unrated_game_shows_book_advice(self):
        self.start(False)
        self.assertTrue(self.w.boardw.hints)
        self.assertIn("Grandmasters here", self.w.openings.text())

    def test_rated_game_shows_none_from_the_first_position(self):
        self.start(True)
        self.assertIsNotNone(self.w.rated)
        self.assertEqual(self.w.boardw.hints, [])
        self.assertIn("No advice during a rated game", self.w.openings.text())


class EngineFailure(unittest.TestCase):           # a dead engine process must not stall the game silently
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from chessiq import app as A, game as G
        self.A, self.qa = A, QApplication.instance() or QApplication([])
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        self.saved_book = G.Game.book_move
        G.Game.book_move = lambda self: None               # out of book at once, so the engine must answer
        self.G = G

    def tearDown(self):
        self.G.Game.book_move = self.saved_book
        self.w.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def run_until(self, cond, secs=40):
        import time
        t = time.monotonic()
        while not cond() and time.monotonic() - t < secs:
            self.qa.processEvents()
            time.sleep(0.05)

    def play_with_kills(self, kills):
        A = self.A
        orig, count = A.MainWindow._start_engine, [0]

        def start_and_kill(win):
            orig(win)
            if win.engine is not None and count[0] < kills:
                count[0] += 1
                win.engine.proc.kill(); win.engine.proc.wait()
        A.MainWindow._start_engine = start_and_kill
        try:
            self.w = w = A.MainWindow()
            w.who.setCurrentIndex(w.who.findData("Tasha"))
            w.mode.setCurrentIndex(w.mode.findData("ai"))
            w.side.setCurrentIndex(w.side.findData("b"))       # the computer (White) moves first
            count[0] = 0
            w.new_game()
            self.run_until(lambda: w.game.history or "failed again" in (w.note or ""))
        finally:
            A.MainWindow._start_engine = orig
        return w

    @unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
    def test_one_failure_restarts_and_plays(self):
        w = self.play_with_kills(1)
        self.assertEqual(len(w.game.history), 1)                # it restarted and played (the move clears the note)
        self.assertEqual(w._restarts, 1)

    @unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
    def test_repeated_failure_says_so(self):
        w = self.play_with_kills(5)
        self.assertEqual(len(w.game.history), 0)
        self.assertIn("failed again", w.note)


class PostGame(unittest.TestCase):                # CM-20: Chessmaster's Post-Game Analysis after a computer game
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from chessiq import app as A
        self.A, self.qa = A, QApplication.instance() or QApplication([])
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def run_until(self, cond, secs=60):
        import time
        t = time.monotonic()
        while not cond() and time.monotonic() - t < secs:
            self.qa.processEvents()
            time.sleep(0.05)

    @unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
    def test_window_after_a_game(self):
        self.w = w = self.A.MainWindow()
        w.who.setCurrentIndex(w.who.findData("Tasha"))
        w.mode.setCurrentIndex(w.mode.findData("ai"))
        w.side.setCurrentIndex(w.side.findData("w"))
        w.new_game()
        w.do_move(w.game.move_from_san("e4"))
        self.run_until(lambda: len(w.game.history) >= 2)
        w.resign(confirm=False)
        self.run_until(lambda: w.postgame is not None and w.postgame.evals is not None)
        d = w.postgame
        self.assertFalse(d.isModal())
        self.assertEqual(len(d.evals), len(w.game.history) + 1)
        self.assertIn(d.kind, ("Blunder", "Dominated", "Disputed", "Balanced"))
        self.assertIn("Game type", d.head.text())
        self.assertTrue(d.suggest_btn.isEnabled())                          # a loss: someone a little weaker
        self.assertLess(d.suggested.rating, w._opponent().rating + 1)


class TournamentFlow(unittest.TestCase):          # CM-22: a whole round robin through the windows
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        os.environ["CHESSIQ_POSTGAME"] = "0"
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from chessiq import app as A, rating as R
        self.A, self.qa = A, QApplication.instance() or QApplication([])
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        R.Profile("Tester", 1300).save()

    def tearDown(self):
        os.environ.pop("CHESSIQ_POSTGAME", None)
        self.w.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def run_until(self, cond, secs=180):
        import time
        t = time.monotonic()
        while not cond() and time.monotonic() - t < secs:
            self.qa.processEvents()
            time.sleep(0.05)

    @unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
    def test_round_robin_through_the_windows(self):
        from chessiq import tourney_ui
        self.w = w = self.A.MainWindow()
        w.people = [p for p in w.people if p.engine == "fsf"]          # engine opponents only, for speed
        tw = tourney_ui.start(w, "rr", 3, 0, 1100, 1500, 0, False, seed=3)
        w.tourney = tw
        t = tw.t
        while True:
            if tw.my_game() is not None:
                tw.play_mine()
                self.assertIsNotNone(w.tourney_game)
                self.run_until(lambda: w.game.local_to_move())
                w.resign(confirm=False)
                self.run_until(lambda: tw.my_game() is None)
            tw.quick_results()
            self.run_until(lambda: not t.pending())
            self.assertEqual(t.pending(), [])
            if len(t.rounds) == t.n_rounds:
                break
            tw.next_round()
        self.assertTrue(t.finished())
        self.assertEqual(t.points(t.human), 0.0)                          # every game resigned
        self.assertEqual(len(t.standings()), 4)
        again = tourney_ui.resume(w)
        self.assertEqual(again.t.standings(), t.standings())
        again.close()


class RatingHistory(unittest.TestCase):            # CM-23
    def test_history_window(self):
        home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = home
        try:
            from PyQt6.QtWidgets import QApplication
            from chessiq import app as A, rating as R
            self.qa = QApplication.instance() or QApplication([])     # keep a reference, or it is collected
            p = R.Profile("Tester", 1300)
            for opp, r, s in (("A", 1250, 1.0), ("B", 1400, 0.5), ("C", 1350, 0.0)):
                p.record(opp, r, s, "w", 40)
            w = A.MainWindow()
            w.rating_history()
            d = w.history_dlg
            self.assertEqual(d.points[0], 1300)
            self.assertEqual(len(d.points), 4)
            self.assertEqual(d.points[-1], p.rating)
            self.assertEqual(d.table.rowCount(), 3)
            self.assertIn("C (1350)", d.table.item(0, 1).text())            # newest first
            d.close(); w.close()
        finally:
            shutil.rmtree(home, ignore_errors=True)


class LeelaOnlyWhenRunnable(unittest.TestCase):    # a missing lc0 must not leave "Leela 1370" played by a stand-in
    @unittest.skipUnless(os.access(FSF, os.X_OK), "Kramnik Fairy-Stockfish missing")
    def test_no_leela_without_lc0(self):
        import subprocess
        code = ("import os, sys; sys.path.insert(0, %r); os.environ['QT_QPA_PLATFORM'] = 'offscreen';"
                "from PyQt6.QtWidgets import QApplication; qa = QApplication([]);"
                "from chessiq import app as A; w = A.MainWindow();"
                "print(sum(p.engine == 'leela' for p in w.people), len(w.people))" % ROOT)
        home = tempfile.mkdtemp(prefix="chessiq-test-")
        try:
            env = dict(os.environ, CHESSIQ_HOME=home, CHESSIQ_LC0="/nonexistent/lc0")
            out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        finally:
            shutil.rmtree(home, ignore_errors=True)
        leela, total = map(int, out.stdout.split()[-2:])
        self.assertEqual(leela, 0)
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()

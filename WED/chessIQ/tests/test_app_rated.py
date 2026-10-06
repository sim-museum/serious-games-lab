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


if __name__ == "__main__":
    unittest.main()

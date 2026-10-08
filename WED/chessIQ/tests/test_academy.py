"""KS-4: the Kramnik Academy, driven by clicks on its board as a player would."""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import kansas as K  # noqa: E402
from chessiq.lessons import LESSONS  # noqa: E402
from chessiq.personalities import by_name  # noqa: E402


def sq(name):
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


class Content(unittest.TestCase):
    def test_every_exercise_is_legal_and_every_opponent_exists(self):
        people = by_name()
        for lesson in LESSONS:
            self.assertIn(lesson.opponent, people)
            self.assertGreater(people[lesson.opponent].kansas, 0)
            self.assertTrue(lesson.exercises, lesson.key)
            for ex in lesson.exercises:
                b, turn, ep, _, _ = K.from_fen(ex.fen)
                for u in ex.solutions:
                    self.assertIsNotNone(K.find(b, turn, ep, u), (lesson.key, u))

    def test_levels_run_from_beginner_to_advanced(self):
        order = ["Beginner", "Intermediate", "Advanced"]
        self.assertEqual([lesson.level for lesson in LESSONS], sorted((lesson.level for lesson in LESSONS),
                                                                       key=order.index))


class Window(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        os.environ["CHESSIQ_POSTGAME"] = "0"
        from PyQt6.QtWidgets import QApplication
        from chessiq import academy, app
        self.qa = QApplication.instance() or QApplication([])
        self.academy, self.app = academy, app

    def tearDown(self):
        os.environ.pop("CHESSIQ_POSTGAME", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def click(self, w, move):
        w.on_square(sq(move[:2])); w.on_square(sq(move[2:4]))

    def test_a_quiz_rejects_a_wrong_move_and_accepts_the_solution(self):
        w = self.academy.AcademyWindow()
        w.list.setCurrentRow([lesson.key for lesson in LESSONS].index("threats"))
        self.click(w, "b7c8")                                     # Qc8+?, the ordinary-chess move
        self.assertFalse(w.solved)
        self.assertIn("not it", w.feedback.text())
        self.click(w, "c1e3")
        self.assertTrue(w.solved)
        self.assertIn("yes!", w.feedback.text())
        w.close()

    def test_finishing_a_lesson_is_remembered(self):
        w = self.academy.AcademyWindow()
        w.list.setCurrentRow(0)                                   # Two new rules: one position
        self.click(w, "g1g2")                                     # Kxg2, the king takes its own pawn
        self.assertTrue(w.solved)
        self.assertIn("rules", self.academy.load_progress())
        self.assertTrue(w.list.item(0).text().startswith("✓"))
        w.close()
        w2 = self.academy.AcademyWindow()
        self.assertTrue(w2.list.item(0).text().startswith("✓"))
        w2.close()

    def test_a_demonstration_shows_the_idea_whatever_is_tried(self):
        w = self.academy.AcademyWindow()
        w.list.setCurrentRow([lesson.key for lesson in LESSONS].index("promotion"))
        self.click(w, "g2h3")                                     # a king move: also wins, but not the idea
        self.assertTrue(w.solved)
        self.assertIn("Bc8", w.feedback.text())
        w.close()

    def test_play_the_specialist(self):
        m = self.app.MainWindow()
        m.academy_open()
        m.academy.list.setCurrentRow([lesson.key for lesson in LESSONS].index("escape"))
        m.academy.play_opponent()
        self.assertEqual(m.who.currentData(), "Mirela")
        self.assertFalse(m.rated_box.isChecked())
        m.academy.close()
        m.close()


if __name__ == "__main__":
    unittest.main()

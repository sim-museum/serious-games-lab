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


class Puzzles(unittest.TestCase):                 # KS-5
    PUZZLES = [
        {"id": 1, "fen": "8/3P1p1k/3R4/6R1/p6P/5Pp1/6P1/1r4K1 w - - 1 41", "solution": ["g1g2"], "san": "Kxg2",
         "kind": "self-capture", "motif": "escape", "explain": "Kxg2!", "rating": 1163},
        {"id": 2, "fen": "4kb1r/1Qp2p2/p4nnp/2q1p1p1/4P3/2P2NNP/PP3PK1/R1B4r w - - 0 19", "solution": ["c1e3"],
         "san": "Be3", "kind": "quiet", "off": "Qc8+", "explain": "Be3.", "rating": 2400},
    ]

    def setUp(self):
        import json
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        from PyQt6.QtWidgets import QApplication
        from chessiq import academy
        self.qa = QApplication.instance() or QApplication([])
        self.academy, self.saved = academy, academy.PUZZLES
        academy.PUZZLES = os.path.join(self.home, "puzzles.json")
        with open(academy.PUZZLES, "w") as f:
            json.dump(self.PUZZLES, f)

    def tearDown(self):
        self.academy.PUZZLES = self.saved
        shutil.rmtree(self.home, ignore_errors=True)

    def test_the_nearest_puzzle_comes_first_and_a_solve_raises_the_rating(self):
        w = self.academy.PuzzleWindow(seed=1)
        self.assertEqual(w.rating, 1200)                          # no profile: 1200
        self.assertEqual(w.current["id"], 1)                       # 1163 is nearer than 2400... among the two
        w.view.on_square(sq("g1")); w.view.on_square(sq("g2"))
        self.assertTrue(w.view.solved)
        self.assertGreater(w.rating, 1200)
        self.assertEqual(self.academy.load_state()["puzzles_solved"], [1])
        a = self.academy.load_ratings()["1"]                       # and the puzzle proved easier: its rating falls
        self.assertEqual((a["n"], a["base"]), (1, 1163))
        self.assertLess(a["r"], 1163)
        w.close()
        w2 = self.academy.PuzzleWindow(seed=1)
        self.assertEqual(self.academy.puzzle_rating(w2.puzzles[0], w2.adj), a["r"])
        w2.close()

    def test_a_wrong_first_try_costs_rating_and_counts_once(self):
        w = self.academy.PuzzleWindow(seed=1)
        w.rating = 2400                                            # level with the puzzle: a miss costs about 16
        w.current = self.PUZZLES[1]
        from chessiq.lessons import Exercise
        w.view.load(Exercise(w.current["fen"], "x", w.current["solution"], "Be3."))
        w.view.on_square(sq("b7")); w.view.on_square(sq("c8"))    # Qc8+?, the ordinary-chess move
        self.assertFalse(w.view.solved)
        w.view.reveal()
        r = w.rating
        self.assertEqual(r, 2384)
        self.assertEqual(self.academy.load_ratings()["2"]["r"], 2420)   # a first miss: the puzzle gains 40 x 0.5
        w.on_finished(True)                                        # a second finish of the same puzzle: no change
        self.assertEqual(w.rating, r)
        self.assertEqual(self.academy.load_ratings()["2"]["n"], 1)
        w.close()

    def test_a_record_against_an_older_shipped_rating_is_ignored(self):
        p = self.PUZZLES[0]
        adj = {"1": {"r": 900, "n": 30, "base": 1100, "fen": p["fen"]}}
        self.assertEqual(self.academy.puzzle_rating(p, adj), 1163)
        adj["1"]["base"] = 1163
        self.assertEqual(self.academy.puzzle_rating(p, adj), 900)
        self.assertEqual([self.academy.puzzle_k(n) for n in (0, 10, 40, 1000)], [40, 20, 8, 8])

    def test_the_shipped_puzzles_are_legal(self):
        import json
        path = self.saved
        if not os.path.exists(path):
            self.skipTest("no puzzles shipped")
        with open(path) as f:
            ps = json.load(f)
        self.assertGreater(len(ps), 20)
        for p in ps:
            b, turn, ep, _, _ = K.from_fen(p["fen"])
            self.assertIsNotNone(K.find(b, turn, ep, p["solution"][0]), p["id"])
            self.assertIn(p["kind"], self.academy.PUZZLE_TEXT)
        self.assertEqual(len({p["id"] for p in ps}), len(ps))


class PuzzleFeedback(unittest.TestCase):           # players' first attempts folded back into the shipped ratings
    def test_fold(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        import puzzle_feedback as F
        ps = [{"id": 1, "fen": "a", "rating": 1000}, {"id": 2, "fen": "b", "rating": 1500},
              {"id": 3, "fen": "c", "rating": 2000}]
        m1 = {"1": {"r": 900, "n": 6, "base": 1000, "fen": "a"}, "2": {"r": 1400, "n": 2, "base": 1500, "fen": "b"},
              "3": {"r": 1000, "n": 50, "base": 1900, "fen": "c"}}                 # 3: an older shipped rating
        m2 = {"1": {"r": 1100, "n": 4, "base": 1000, "fen": "a"}}
        # puzzle 1: (6 x -100 + 4 x +100) / (10 + 10) = -10; puzzle 2: too few attempts; puzzle 3: stale record
        self.assertEqual(F.fold(ps, [m1, m2]), {1: 990})


class PracticeFromYourGame(unittest.TestCase):    # KS-3 + KS-4: your own missed moments become exercises
    TRAP = {"kind": "trap", "ply": 36, "side": "w", "san": "Qc8+", "best": "Be3", "best_uci": "c1e3", "loss": 203,
            "why": "Kxf7 (takes its own pawn)", "fen": "4kb1r/1Qp2p2/p4nnp/2q1p1p1/4P3/2P2NNP/PP3PK1/R1B4r w - - 0 19"}
    PLAYED = {"kind": "played", "ply": 5, "side": "w", "san": "Qxe2", "motif": "attack", "piece": "q", "victim": "b",
              "loss": 300, "fen": K.START, "best_uci": "e2e4"}

    def setUp(self):
        from PyQt6.QtWidgets import QApplication
        from chessiq import academy
        self.qa = QApplication.instance() or QApplication([])
        self.academy = academy

    def test_only_your_missed_and_trapped_moments(self):
        black = dict(self.TRAP, side="b")
        exs = self.academy.practice_exercises([self.TRAP, self.PLAYED, black], side="w")
        self.assertEqual(len(exs), 1)
        self.assertEqual(exs[0].solutions, ["c1e3"])
        self.assertIn("19.Qc8+", exs[0].prompt)
        self.assertEqual(len(self.academy.practice_exercises([self.TRAP, black])), 2)     # hotseat: both sides

    def test_solve_it_in_the_dialog(self):
        d = self.academy.PracticeDialog(self.academy.practice_exercises([self.TRAP]))
        d.view.on_square(sq("c1")); d.view.on_square(sq("e3"))
        self.assertTrue(d.view.solved)
        self.assertIn("yes!", d.view.feedback.text())
        d.close()


class Tour(unittest.TestCase):                     # KS-13: a first-time player's five minutes
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        os.environ["CHESSIQ_POSTGAME"] = "0"
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QApplication
        from chessiq import academy, app
        self.qa = QApplication.instance() or QApplication([])
        self.academy, self.app = academy, app
        self.coach = QSettings("sim-museum", "chessIQ").value("coach", "true")     # the tour turns the coach on

    def tearDown(self):
        from PyQt6.QtCore import QSettings
        QSettings("sim-museum", "chessIQ").setValue("coach", self.coach)
        os.environ.pop("CHESSIQ_POSTGAME", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_the_boards_are_self_captures_easiest_first(self):
        steps = self.academy.tour_steps()
        self.assertEqual([k for k, _ in steps], ["text", "ex", "ex", "ex", "ex", "text", "end"])
        for _, ex in steps[1:5]:
            b, turn, ep, _, _ = K.from_fen(ex.fen)
            for u in ex.solutions:
                self.assertTrue(K.is_self_capture(b, turn, u), (ex.fen, u))
        self.assertIn("in check", steps[2][1].prompt)
        self.assertIn("Mate in one", steps[3][1].prompt)

    def walk(self, t, upto):
        while t.step < upto:
            kind, ex = t.steps[t.step]
            if kind == "ex":
                self.assertFalse(t.next_btn.isEnabled())          # solve it (or press Show) first
                m = K.find(*K.from_fen(ex.fen)[:3], ex.solutions[0])
                t.view.on_square(m.frm); t.view.on_square(m.to)
                self.assertTrue(t.view.solved)
            self.assertTrue(t.next_btn.isEnabled())
            t.next_btn.click()

    def test_from_the_rules_to_a_game_against_felix(self):
        m = self.app.MainWindow()
        m.coach_box.setChecked(False)
        m.tour_open()
        t = m.tour
        self.walk(t, 3)
        t.close()
        t2 = self.academy.TourWindow(m)                           # come back later: the tour resumes
        self.assertEqual(t2.step, 3)
        self.walk(t2, len(t2.steps) - 1)
        self.assertFalse(t2.play_btn.isHidden())                   # the last page: play, not next
        self.assertTrue(t2.next_btn.isHidden())
        t2.play()
        self.assertEqual(m.who.currentData(), "Felix")
        self.assertFalse(m.rated_box.isChecked())
        self.assertTrue(m.coach_box.isChecked())
        self.assertTrue(self.academy.load_state()["tour_done"])
        m.close()

    def test_a_new_player_is_offered_the_tour_once(self):
        os.environ["CHESSIQ_TOUR"] = "1"
        try:
            m = self.app.MainWindow()
            m.welcome()
            self.assertIsNotNone(m.tour)
            self.assertIn("Getting started", m.note)
            m.close()
            m2 = self.app.MainWindow()                            # the tour has saved its place: no second offer
            m2.welcome()
            self.assertIsNone(m2.tour)
            m2.close()
        finally:
            os.environ.pop("CHESSIQ_TOUR", None)


class CoachInTheWindow(unittest.TestCase):         # KS-6: advice only in unrated games
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="chessiq-test-")
        os.environ["CHESSIQ_HOME"] = self.home
        from PyQt6.QtWidgets import QApplication
        from chessiq import app
        self.qa = QApplication.instance() or QApplication([])
        self.w = app.MainWindow()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_shown_in_an_unrated_game(self):
        w = self.w
        w.rated = None
        w._coached(len(w.game.history), ("warning", "Careful: Qc8+ ..."))
        self.assertIn("Coach", w.coach_label.text())

    def test_silent_in_a_rated_game(self):
        w = self.w
        w.rated = {"opponent": "x"}
        w._coached(len(w.game.history), ("warning", "Careful"))
        self.assertEqual(w.coach_label.text(), "")
        n = len(w.threads)
        w.maybe_coach()
        self.assertEqual(len(w.threads), n)                       # no search started either

    def test_a_self_capture_is_named_as_it_happens(self):
        w = self.w
        w.mode.setCurrentIndex(w.mode.findData("human")); w.rated_box.setChecked(False); w.new_game()
        for san in ("e4", "e5", "Be2", "d6", "Qxe2"):
            w.do_move(w.game.move_from_san(san))
        self.assertEqual(w.note, "Qxe2 by White: the queen takes its own bishop and gets into play.")
        w.rated = {"opponent": "x", "recorded": False}             # no commentary during a rated game
        w.do_move(w.game.move_from_san("Nf6")); w.do_move(w.game.move_from_san("Qxe4"))
        self.assertEqual(w.note, "")
        w.rated = None

    def test_stale_advice_is_dropped(self):
        w = self.w
        w.rated = None
        w._coached(len(w.game.history) + 1, ("chance", "old position"))
        self.assertEqual(w.coach_label.text(), "")


if __name__ == "__main__":
    unittest.main()

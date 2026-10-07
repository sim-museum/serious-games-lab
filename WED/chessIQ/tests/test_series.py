"""The tournament series (EPIC CM, CM-25): events open in order, by a top-half finish in the one before."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import personalities, tourney_ui as U  # noqa: E402
from chessiq.tournament import Tournament  # noqa: E402


def finished_rr(my_place):
    """A 4-player round robin where 'You' finish in the given place (players ranked A > B > C otherwise)."""
    t = Tournament([("You", 1300), ("A", 1500), ("B", 1400), ("C", 1350)], "rr", human="You")
    beats = {"A": 3, "B": 2, "C": 1, "You": 4 - my_place + 0.5}   # strength order; You placed by a half step
    while not t.finished():
        r = len(t.rounds)
        t.pair_next()
        for w, b in t.rounds[r]:
            t.record(r, w, b, 1.0 if beats[w] > beats[b] else 0.0)
    return t


class SeriesTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.d.name, "series.json")

    def tearDown(self):
        self.d.cleanup()

    def test_only_the_first_is_open_at_start(self):
        self.assertEqual(U.series_open(U.series_passed(self.path)), ["club"])

    def test_places(self):
        for place in (1, 2, 3, 4):
            self.assertEqual(U.series_place(finished_rr(place)), (place, place <= 2))

    def test_top_half_opens_the_next(self):
        self.assertEqual(U.series_record(finished_rr(2), "club", self.path), (2, True, "County Championship"))
        self.assertEqual(U.series_open(U.series_passed(self.path)), ["club", "county"])

    def test_bottom_half_opens_nothing(self):
        self.assertEqual(U.series_record(finished_rr(3), "club", self.path), (3, False, None))
        self.assertEqual(U.series_open(U.series_passed(self.path)), ["club"])

    def test_last_event_opens_nothing_further(self):
        self.assertEqual(U.series_record(finished_rr(1), "elite", self.path)[2], None)

    def test_window_says_it_once(self):
        from types import SimpleNamespace
        saves = []
        w = SimpleNamespace(t=finished_rr(1), extra={}, save=lambda: saves.append(1))
        old, U.series_path = U.series_path, lambda: self.path
        try:
            first = U.TournamentWindow.series_result(w, "club")
            again = U.TournamentWindow.series_result(w, "club")
        finally:
            U.series_path = old
        self.assertEqual(first, ", you placed 1 of 4. The County Championship is now open.")
        self.assertEqual((again, len(saves)), (first, 1))         # recorded and saved once, not on every refresh

    def test_each_event_has_a_field_in_its_range(self):
        people = personalities.roster()
        for key, name, kind, n, rounds, lo, hi, tc in U.SERIES:
            pool = [p for p in people if lo <= p.rating <= hi]
            self.assertGreaterEqual(len(pool), n, "%s: %d opponents in %d-%d" % (name, len(pool), lo, hi))

    def test_dialog_fills_and_fixes_the_fields(self):
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])     # keep a reference, or Qt loses it
        d = U.NewTournamentDialog(None, 1300, passed={"club"})
        names = [d.event.itemText(i) for i in range(d.event.count())]
        self.assertEqual(names[:3], ["Your own event", "Club Swiss", "County Championship"])
        self.assertFalse(d.event.model().item(3).isEnabled())      # Regional Open: county not passed
        d.event.setCurrentIndex(2)
        self.assertEqual((d.kind.currentData(), d.size.value(), d.lo.value(), d.hi.value()), ("rr", 5, 1300, 1800))
        self.assertTrue(d.rated.isChecked())
        self.assertFalse(d.lo.isEnabled())
        d.event.setCurrentIndex(0)
        self.assertTrue(d.lo.isEnabled())


if __name__ == "__main__":
    unittest.main()

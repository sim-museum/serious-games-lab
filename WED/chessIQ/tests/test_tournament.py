"""Tournaments (EPIC CM, CM-21): pairings, colours, byes, standings."""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq.tournament import BYE, Tournament  # noqa: E402

FIELD = [("You", 1300), ("A", 1500), ("B", 1450), ("C", 1400), ("D", 1350), ("E", 1250), ("F", 1200), ("G", 1150)]


def finish_round(t, rnd):
    for w, b in t.pending():
        t.record(len(t.rounds) - 1, w, b, rnd.choice((1.0, 0.5, 0.0)))


class RoundRobin(unittest.TestCase):
    def check(self, field, double=False):
        t, rnd = Tournament(field, "rr", double=double, seed=1), random.Random(2)
        meetings, whites = Counter(), Counter()
        while t.pair_next() is not None:
            seen = [p for w, b in t.rounds[-1] for p in (w, b) if p is not BYE]
            self.assertEqual(len(seen), len(set(seen)))                     # nobody twice in a round
            for w, b in t.rounds[-1]:
                if b is not BYE:
                    meetings[frozenset((w, b))] += 1; whites[w] += 1
            finish_round(t, rnd)
        n = len(field)
        self.assertEqual(len(meetings), n * (n - 1) // 2)                  # everyone meets everyone
        self.assertEqual(set(meetings.values()), {2 if double else 1})
        games = (n - 1) * (2 if double else 1)
        for p, _ in field:
            self.assertLessEqual(abs(whites[p] - (games - whites[p])), 1 if not double else 0)
        self.assertTrue(t.finished())
        return t

    def test_even_field(self):
        self.check(FIELD)

    def test_odd_field_has_one_bye_each(self):
        t = self.check(FIELD[:7])
        byes = Counter(w for rp in t.rounds for w, b in rp if b is BYE)
        self.assertEqual(set(byes.values()), {1})
        self.assertEqual(len(byes), 7)

    def test_double(self):
        self.check(FIELD[:6], double=True)

    def test_standings_and_sonneborn_berger(self):
        t = Tournament(FIELD[:4], "rr", seed=3)
        res = {("You", "A"): 1.0, ("You", "B"): 1.0, ("You", "C"): 0.0, ("A", "B"): 0.5, ("A", "C"): 1.0,
               ("B", "C"): 1.0}
        while t.pair_next() is not None:
            for w, b in t.pending():
                s = res.get((w, b))
                t.record(len(t.rounds) - 1, w, b, s if s is not None else 1 - res[(b, w)])
        st = t.standings()
        self.assertEqual([p for p, _, _ in st][:1], ["You"])              # You 2, A 1.5, B 1.5, C 1
        self.assertEqual(st[0][1], 2.0)
        self.assertEqual({p: t.tiebreak(p) for p, _ in FIELD[:4]},        # Sonneborn-Berger, by hand
                         {"You": 3.0, "A": 1.75, "B": 1.75, "C": 2.0})
        self.assertEqual([p for p, _, _ in st], ["You", "A", "B", "C"])  # A and B equal on SB: rating decides
        self.assertEqual(t.crosstable()["You"]["C"], [0.0])


class Swiss(unittest.TestCase):
    def test_no_rematches_and_one_bye_each(self):
        for seed in range(20):
            field = FIELD[:7]
            t, rnd = Tournament(field, "swiss", rounds=5, seed=seed), random.Random(seed)
            met, byes = set(), Counter()
            while t.pair_next() is not None:
                for w, b in t.rounds[-1]:
                    if b is BYE:
                        byes[w] += 1
                    else:
                        self.assertNotIn(frozenset((w, b)), met, "seed %d rematch %s-%s" % (seed, w, b))
                        met.add(frozenset((w, b)))
                finish_round(t, rnd)
            self.assertEqual(max(byes.values()), 1)
            self.assertTrue(t.finished())

    def test_you_are_not_given_the_bye(self):
        for seed in range(10):
            t, rnd = Tournament(FIELD[:5], "swiss", rounds=4, seed=seed, human="You"), random.Random(seed)
            while t.pair_next() is not None:
                self.assertNotIn(("You", BYE), t.rounds[-1])
                finish_round(t, rnd)

    def test_leaders_meet(self):
        t = Tournament(FIELD, "swiss", rounds=3, seed=1)
        t.pair_next()
        for w, b in t.pending():                       # higher rating wins round 1
            t.record(0, w, b, 1.0 if t.rating[w] > t.rating[b] else 0.0)
        pairs = t.pair_next()
        leaders = {p for p in t.rating if t.points(p) == 1.0}
        for w, b in pairs:
            self.assertEqual(w in leaders, b in leaders)                  # 1-pointers play 1-pointers

    def test_colours_balance(self):
        t, rnd = Tournament(FIELD, "swiss", rounds=6, seed=4), random.Random(4)
        while t.pair_next() is not None:
            finish_round(t, rnd)
        for p, _ in FIELD:
            w = sum(1 for rp in t.rounds for a, b in rp if a == p and b is not BYE)
            bl = sum(1 for rp in t.rounds for a, b in rp if b == p)
            self.assertLessEqual(abs(w - bl), 2)


class QuickResult(unittest.TestCase):
    def test_engines_play_it_out(self):
        from chessiq import uci_engine
        from chessiq.personalities import Personality
        from chessiq.tournament import play_out
        if not uci_engine.available():
            self.skipTest("Kramnik Fairy-Stockfish missing")
        a, b = uci_engine.PersonalityEngine(Personality("A", 1600), seed=1), \
            uci_engine.PersonalityEngine(Personality("B", 1200), seed=2)
        try:
            self.assertIn(play_out(a, b), (0.0, 0.5, 1.0))
        finally:
            a.close(); b.close()


if __name__ == "__main__":
    unittest.main()

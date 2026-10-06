"""Personalities (EPIC CM, sprint CM-2): the .CMP reader on a synthetic file, the engine-option mapping, the roster.
No Chessmaster data is needed or read here."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import personalities as P  # noqa: E402


def synthetic_cmp(path, rating=1850, contempt=120, attack_raw=-30, knight_own=40):
    v = [0] * 38
    v[6], v[9], v[10], v[12], v[13], v[14], v[8] = rating, 60, 5, 99, 9, contempt, attack_raw
    for i in range(5):
        v[16 + 2 * i] = v[17 + 2 * i] = 100 + 10 * i
    for i, val in enumerate((90, 50, 30, 30, 10)):
        v[26 + 2 * i] = v[27 + 2 * i] = val
    v[32] = knight_own                                  # knight, own
    b = bytearray(3104)
    b[0:24] = b"Chessmaster 10th Edition"
    struct.pack_into("<38i", b, 0x20, *v)
    b[0xC0:0xC0 + 9] = b"Test.OBK\0"
    b[0x1C4:0x1C4 + 9] = b"Test.BMP\0"
    style = b"Loves knights, attacker"
    b[0x1E2:0x1E2 + len(style)] = style
    bio = b"A synthetic personality written by the test suite, long enough to count as a biography."
    b[0x2C0:0x2C0 + len(bio)] = bio
    open(path, "wb").write(b)


class Reader(unittest.TestCase):
    def test_fields(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "Synth.CMP")
            synthetic_cmp(f)
            p = P.read_cmp(f)
        self.assertEqual((p.name, p.rating, p.contempt, p.attack, p.book), ("Synth", 1850, 120, 30, "Test.OBK"))
        self.assertEqual(p.style, "Loves knights, attacker")
        self.assertTrue(p.bio.startswith("A synthetic personality"))
        self.assertEqual(p.positional["Centre"], (100, 100))
        self.assertEqual(p.positional["PawnWeakness"], (140, 140))
        self.assertEqual(p.material["Knight"], (40, 30))
        self.assertEqual(p.material["Queen"], (90, 90))

    def test_rejects_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "x.CMP")
            open(f, "wb").write(b"\0" * 3104)
            self.assertRaises(ValueError, P.read_cmp, f)


class Options(unittest.TestCase):
    def test_neutral_personality_is_neutral(self):
        o = P.Personality("N", 2850).engine_options()
        self.assertTrue(all(v == 100 for k, v in o.items() if k.endswith(" Own") or k.endswith(" Opp")))
        self.assertEqual((o["CM Contempt"], o["CM Attack"], o["UCI_LimitStrength"]), (0, 0, "false"))

    def test_rating_sets_nodes_on_the_ladder(self):
        self.assertEqual(P.Personality("W", 300).engine_options()["UCI_LimitStrength"], "false")
        self.assertEqual(P.level_for(1163), (16, 0))                               # the floor
        n, extra = P.level_for(300)
        self.assertEqual(n, 16); self.assertGreater(extra, 0)                       # below it: randomness
        self.assertLess(P.level_for(1600)[0], P.level_for(2000)[0])                 # stronger = more nodes
        self.assertEqual(P.Personality("E", 2850).search_nodes(), 0)                # full strength on the clock

    def test_below_the_floor_a_measured_continuous_blunder_rate(self):           # CM-14
        rates = [P.blunder_for(r) for r in range(1300, -600, -25)]
        self.assertEqual(rates[0], 0.0)
        self.assertEqual(rates[-1], 1.0)                                            # a random mover at the bottom
        self.assertTrue(all(a <= b for a, b in zip(rates, rates[1:])))             # monotone
        self.assertLess(max(b - a for a, b in zip(rates, rates[1:])), 0.05)         # no cliff
        self.assertAlmostEqual(P.Personality("S", 1).blunder_rate(), 0.68, places=2)
        self.assertEqual(P.Personality("S", 1, blunder=0.2).blunder_rate(), 0.2)

    def test_material_as_percent(self):
        p = P.Personality("K", 2000, material={**{x: (P.BASE[x], P.BASE[x]) for x in P.PIECES}, "Knight": (45, 30)})
        o = p.engine_options()
        self.assertEqual((o["CM Knight Own"], o["CM Knight Opp"]), (150, 100))


class Roster(unittest.TestCase):
    def test_own_roster_without_chessmaster(self):
        saved = P.chessmaster_dir
        P.chessmaster_dir = lambda: None
        try:
            r = P.roster()
        finally:
            P.chessmaster_dir = saved
        own = [p for p in r if p.engine == "fsf"]
        self.assertEqual([p.source for p in own], ["chessIQ"] * len(P.ROSTER))      # then any Leela opponents
        self.assertEqual(sorted(p.rating for p in own), [p.rating for p in own])
        self.assertTrue(all(p.engine == "leela" and p.net for p in r[len(own):]))


if __name__ == "__main__":
    unittest.main()

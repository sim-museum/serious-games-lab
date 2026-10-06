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

    def test_rating_limits_strength(self):
        o = P.Personality("W", 300).engine_options()
        self.assertEqual((o["UCI_LimitStrength"], o["UCI_Elo"]), ("true", 500))   # the engine's floor
        self.assertEqual(P.Personality("M", 1900).engine_options()["UCI_Elo"], 1900)

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
        self.assertEqual([p.source for p in r], ["chessIQ"] * len(P.ROSTER))
        self.assertEqual(sorted(p.rating for p in r), [p.rating for p in r])


if __name__ == "__main__":
    unittest.main()

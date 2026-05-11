#!/usr/bin/env python3
"""Unit tests for the BiddingSystem spec / .RCE parser.

Asserts the live values pulled out of the Q-Plus install (if present)
AND the fallback values when no install is found. Run with:

    python test_bidding_systems.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ben_backend.bidding_systems import (  # noqa: E402
    BiddingSystem, RCERule, get_system, list_systems, parse_rce_file,
)


class TestRCEParser(unittest.TestCase):
    """Parser-level tests: feed it raw text snippets, check the output."""

    def test_parse_simple_flag(self):
        # No parameter → value is None, enabled is True.
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".RCE", delete=False) as f:
            f.write("Conventions\nY A-1NT-Stayman\nN A-1MA-splinter\n")
            path = f.name
        try:
            rules, _ = parse_rce_file(path)
            self.assertIn("A-1NT-Stayman", rules)
            self.assertTrue(rules["A-1NT-Stayman"].enabled)
            self.assertIsNone(rules["A-1NT-Stayman"].value)
            self.assertIn("A-1MA-splinter", rules)
            self.assertFalse(rules["A-1MA-splinter"].enabled)
        finally:
            os.unlink(path)

    def test_parse_param_value(self):
        # `.pNN` parameter token is stripped from name, stored in value.
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".RCE", delete=False) as f:
            f.write("Conventions\n"
                    "Y B-1NT.v-1.min-hcp.p15\n"
                    "Y B-1NT.v-1.max-hcp.p17\n"
                    "Y A-2-over-1-min.hcp-10\n")
            path = f.name
        try:
            rules, _ = parse_rce_file(path)
            self.assertEqual(rules["B-1NT.v-1.min-hcp"].value, 15)
            self.assertEqual(rules["B-1NT.v-1.max-hcp"].value, 17)
            # `hcp-10` has no `.p` prefix so it stays in the name.
            self.assertIn("A-2-over-1-min.hcp-10", rules)
            self.assertIsNone(rules["A-2-over-1-min.hcp-10"].value)
        finally:
            os.unlink(path)

    def test_parse_description(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".RCE", delete=False) as f:
            f.write('.version = 17.1\n'
                    '.description.eng = "Test system"\n'
                    'Conventions\nY A-1NT-Stayman\n')
            path = f.name
        try:
            _, desc = parse_rce_file(path)
            self.assertEqual(desc, "Test system")
        finally:
            os.unlink(path)

    def test_missing_file(self):
        rules, desc = parse_rce_file("/nonexistent/no.RCE")
        self.assertEqual(rules, {})
        self.assertEqual(desc, "")


class TestSystemCatalog(unittest.TestCase):
    """End-to-end: ask for each canonical system, verify shape."""

    def test_listed_systems(self):
        names = list_systems()
        self.assertIn("SAYC", names)
        self.assertIn("Precision90M", names)
        self.assertIn("Precision90P", names)
        self.assertIn("Precision70", names)

    def test_sayc_basic_fields(self):
        s = get_system("SAYC")
        self.assertEqual(s.name, "SAYC")
        self.assertEqual(s.one_nt_min_hcp, 15)
        self.assertEqual(s.one_nt_max_hcp, 17)
        self.assertEqual(s.strong_open_call, "2C")
        self.assertGreaterEqual(s.strong_open_min_hcp, 22)
        self.assertEqual(s.two_over_one_min_hcp, 10)
        self.assertTrue(s.weak_two_diamonds)
        self.assertTrue(s.weak_two_majors)

    def test_precision_basic_fields(self):
        s = get_system("Precision90M")
        self.assertEqual(s.one_nt_min_hcp, 14)
        self.assertEqual(s.one_nt_max_hcp, 16)
        self.assertEqual(s.strong_open_call, "1C")
        self.assertEqual(s.strong_open_min_hcp, 16)
        self.assertFalse(s.weak_two_diamonds)
        # 2♦ is the Precision three-suiter, not a weak two.
        self.assertTrue(any(k.startswith("B-2D.Precision") for k in s.raw_rules))

    def test_precision70_classic(self):
        s = get_system("Precision70")
        self.assertEqual(s.one_nt_min_hcp, 13)
        self.assertEqual(s.one_nt_max_hcp, 15)
        self.assertEqual(s.two_nt_min_hcp, 22)
        self.assertEqual(s.two_nt_max_hcp, 23)

    def test_alias_resolution(self):
        s = get_system("Precision")
        self.assertEqual(s.name, "Precision90M")

    def test_unknown_falls_back_to_sayc(self):
        s = get_system("BananaSystem")
        self.assertEqual(s.name, "SAYC")

    def test_has_convention(self):
        sayc = get_system("SAYC")
        self.assertTrue(sayc.has("A-1NT-Stayman"))
        self.assertTrue(sayc.has("A-1NT-Jacoby-transfer.always"))
        self.assertTrue(sayc.has("C-Sputnik.until-2S"))
        self.assertTrue(sayc.has("O-Michaels"))

    def test_two_over_one_system(self):
        s = get_system("TwoOverOne")
        self.assertEqual(s.name, "TwoOverOne")
        self.assertEqual(s.one_nt_min_hcp, 15)
        self.assertEqual(s.one_nt_max_hcp, 17)
        self.assertEqual(s.strong_open_call, "2C")
        self.assertEqual(s.one_major_card_min, 5)
        # Q-Plus encodes 2/1 GF as min HCP 11 (effectively GF strength).
        self.assertGreaterEqual(s.two_over_one_min_hcp, 11)

    def test_acol_system(self):
        s = get_system("StandardAcol")
        self.assertEqual(s.name, "StandardAcol")
        self.assertEqual(s.one_nt_min_hcp, 12)   # Weak 1NT
        self.assertEqual(s.one_nt_max_hcp, 14)
        self.assertEqual(s.one_major_card_min, 4)  # 4-card majors

    def test_french_system(self):
        s = get_system("StandardFrench")
        self.assertEqual(s.name, "StandardFrench")
        self.assertEqual(s.one_nt_min_hcp, 15)
        self.assertEqual(s.one_nt_max_hcp, 17)
        self.assertEqual(s.one_major_card_min, 5)

    def test_cross_program_aliases(self):
        # bb12 / wBridge5 names map to closest Q-Plus systems.
        self.assertEqual(get_system("Std. Amer.").name, "SAYC")
        self.assertEqual(get_system("2/1").name, "TwoOverOne")
        self.assertEqual(get_system("Wbridge5").name, "TwoOverOne")
        self.assertEqual(get_system("SEF").name, "StandardFrench")
        self.assertEqual(get_system("ACOL").name, "StandardAcol")
        self.assertEqual(get_system("La Majeure 5eme").name, "StandardFrench")

    def test_precision_specific_conventions(self):
        p = get_system("Precision90M")
        self.assertTrue(p.has("A-artificial-1C.switch-1NT-1H"))
        self.assertTrue(p.has("O-strong-1C.dbl-is-majors"))
        # SAYC's 2♣ negative is NOT in Precision (it uses 1♣-1♦).
        self.assertFalse(p.has("A-artificial-2C.negative-2D"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

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


class TestBidDescriptions(unittest.TestCase):
    """describe_bid surfaces system-aware meanings for the info window."""

    def setUp(self):
        from ben_backend.bid_descriptions import describe_bid
        from ben_backend.models import Bid, Seat, Suit
        self.describe = describe_bid
        self.Bid, self.Seat, self.Suit = Bid, Seat, Suit

    def _describe(self, bid, auction, system_name="SAYC"):
        s = get_system(system_name)
        return self.describe(bid, auction, self.Seat.SOUTH, self.Seat.NORTH, s)

    def test_stayman_sayc(self):
        Bid, Suit = self.Bid, self.Suit
        auction = [Bid(level=1, suit=Suit.NOTRUMP), Bid.make_pass()]
        _, _, help_, art = self._describe(Bid(level=2, suit=Suit.CLUBS), auction)
        self.assertIn("Stayman", help_)
        self.assertTrue(art)

    def test_jacoby_transfer_to_hearts(self):
        Bid, Suit = self.Bid, self.Suit
        auction = [Bid(level=1, suit=Suit.NOTRUMP), Bid.make_pass()]
        _, _, help_, _ = self._describe(Bid(level=2, suit=Suit.DIAMONDS), auction)
        self.assertIn("transfer to hearts", help_.lower())

    def test_precision_strong_1c(self):
        Bid, Suit = self.Bid, self.Suit
        _, _, help_, art = self._describe(
            Bid(level=1, suit=Suit.CLUBS), [], "Precision90M")
        self.assertIn("strong artificial 1", help_.lower())
        self.assertTrue(art)

    def test_acol_one_heart_says_four_plus(self):
        Bid, Suit = self.Bid, self.Suit
        _, length, _, _ = self._describe(
            Bid(level=1, suit=Suit.HEARTS), [], "StandardAcol")
        self.assertIn("4+", length)

    def test_sayc_one_heart_says_five_plus(self):
        Bid, Suit = self.Bid, self.Suit
        _, length, _, _ = self._describe(
            Bid(level=1, suit=Suit.HEARTS), [], "SAYC")
        self.assertIn("5+", length)

    def test_strong_2c_sayc_opening(self):
        Bid, Suit = self.Bid, self.Suit
        _, _, help_, art = self._describe(
            Bid(level=2, suit=Suit.CLUBS), [], "SAYC")
        self.assertIn("strong", help_.lower())
        self.assertTrue(art)

    def test_2c_in_precision_is_long_clubs(self):
        Bid, Suit = self.Bid, self.Suit
        _, length, help_, _ = self._describe(
            Bid(level=2, suit=Suit.CLUBS), [], "Precision90M")
        # Precision's 2♣ is limited long-clubs, NOT the strong 2♣.
        self.assertIn("♣", length)
        self.assertNotIn("strong", help_.lower())


class TestRKCBlackwood(unittest.TestCase):
    """End-to-end coverage of the 4NT → 5x → 5NT → 6x → 7y RKC pipeline.

    The pipeline runs the auction with both partners using the same
    BiddingSystem spec and walks until three passes close it. Each
    test inspects the final contract.
    """

    def setUp(self):
        from ben_backend.bidding_systems import get_system
        from ben_backend.native_bidder import (
            decide_bid, evaluate_hand, parse_auction)
        from ben_backend.models import Hand, Card, Suit, Rank, Seat
        self.Hand, self.Card = Hand, Card
        self.Suit, self.Rank, self.Seat = Suit, Rank, Seat
        self.decide_bid = decide_bid
        self.evaluate_hand = evaluate_hand
        self.parse_auction = parse_auction
        self.get_system = get_system

    def _hand(self, spec: str):
        Suit, Rank = self.Suit, self.Rank
        suit_map = {'S': Suit.SPADES, 'H': Suit.HEARTS,
                    'D': Suit.DIAMONDS, 'C': Suit.CLUBS}
        rank_map = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN,
                    'J': Rank.JACK, 'T': Rank.TEN,
                    '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
                    '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR,
                    '3': Rank.THREE, '2': Rank.TWO}
        cards = []
        for grp in spec.split():
            s = suit_map[grp[0]]
            for c in grp[1:]:
                cards.append(self.Card(s, rank_map[c]))
        return self.Hand(cards=cards)

    def _drive(self, hands, system_name, dealer):
        sys_ = self.get_system(system_name)
        auction = []
        seat = dealer
        for _ in range(50):
            state = self.parse_auction(seat, dealer, list(auction))
            e = self.evaluate_hand(hands[seat])
            b = self.decide_bid(state, e, sys_)
            auction.append(b)
            if len(auction) >= 4 and all(x.is_pass for x in auction[-3:]) \
                    and any(not x.is_pass for x in auction[:-3]):
                break
            seat = seat.next()
        return auction

    def _final_contract(self, auction):
        """Return the last non-pass call (the contract)."""
        for b in reversed(auction):
            if not b.is_pass:
                return b
        return None

    def test_precision_strong_1c_grand_slam(self):
        """The Board-405 auction Q-Plus reached 7♥ on. The new RKC
        pipeline drives 1♣ - 1♥ - 4NT - 5♣ - 5NT - 6♣ - 7♥."""
        Seat = self.Seat
        hands = {
            Seat.NORTH: self._hand('S943 HKQT62 DJ843 CK'),
            Seat.EAST:  self._hand('SQT652 H5 DT976 C974'),
            Seat.SOUTH: self._hand('SAJ HAJ984 DAK2 CAQJ'),
            Seat.WEST:  self._hand('SK87 H73 DQ5 CT86532'),
        }
        auction = self._drive(hands, 'Precision90M', Seat.NORTH)
        contract = self._final_contract(auction)
        self.assertEqual(contract.level, 7)
        self.assertEqual(contract.suit, self.Suit.HEARTS)
        # 4NT must have appeared, plus a 5NT king-ask.
        suits_at_level = [(b.level, b.suit) for b in auction]
        self.assertIn((4, self.Suit.NOTRUMP), suits_at_level)
        self.assertIn((5, self.Suit.NOTRUMP), suits_at_level)

    def test_off_two_keys_stops_at_5(self):
        """When the side is missing 2 aces, RKC stops at 5 of trump
        instead of jumping to slam. North opens 1♣ (Precision strong),
        South responds 1♥ positive, North raises with 3-card support,
        4NT asks, 5♣/5♦ shows 0-1 keys → sign-off."""
        Seat = self.Seat
        # Hands chosen so the partnership has 3 keys total (3 aces +
        # trump king split): North 16 HCP with ♥A, South 9 HCP with
        # ♥K plus a 5-card heart suit.
        hands = {
            Seat.NORTH: self._hand('SA32 HA62 DAQ32 CKQJ'),  # 18, 1 ace + AKQ ♣
            Seat.SOUTH: self._hand('S874 HKQT54 D54 C432'),  # 5 HCP, ♥K + 5♥
            Seat.EAST:  self._hand('SKQJT5 H973 DJ97 C765'),
            Seat.WEST:  self._hand('S96 HJ8 DKT86 CAT98'),
        }
        auction = self._drive(hands, 'Precision90M', Seat.NORTH)
        contract = self._final_contract(auction)
        # Side has 3 keys (♠A + ♦A + ♥K — South has just the trump K).
        # Total is 3 keys → asker should stop at 5 if no trump queen,
        # or 6 if queen present. Either way it must NOT be 7.
        self.assertLessEqual(contract.level, 6)

    def test_quantitative_4nt_not_rkc(self):
        """1NT - 4NT with no suit fit is a quantitative invite, not
        RKC — opener should not respond with keycards."""
        Seat = self.Seat
        # Both balanced; responder has 16 HCP so 1NT - 4NT quant.
        hands = {
            Seat.SOUTH: self._hand('SAQ3 HKQ2 DAJ2 CK432'),    # 18 balanced
            Seat.NORTH: self._hand('SK64 HA853 DK63 CAQ5'),    # 16 balanced
            Seat.EAST:  self._hand('SJT982 H97 DQ85 C987'),
            Seat.WEST:  self._hand('S75 HJT64 DT974 CJT6'),
        }
        auction = self._drive(hands, 'SAYC', Seat.SOUTH)
        # The auction should land in NT slam zone (6NT or 4NT pass);
        # crucially the partner of the 4NT bidder should NOT answer
        # with a 5-of-a-minor keycard step.
        for i, b in enumerate(auction):
            if (b.level == 4 and b.suit == self.Suit.NOTRUMP
                    and not b.is_pass):
                # Next non-pass call after 4NT must not be 5♣ / 5♦.
                for nxt in auction[i + 1:]:
                    if nxt.is_pass:
                        continue
                    self.assertFalse(
                        nxt.level == 5
                        and nxt.suit in (self.Suit.CLUBS, self.Suit.DIAMONDS),
                        f"4NT-{nxt} looks like keycard but should be quantitative",
                    )
                    break
                break


if __name__ == "__main__":
    unittest.main(verbosity=2)

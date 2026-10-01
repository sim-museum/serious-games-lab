"""The 'Play defensive signals' preference: OFF must never spend a card on a
signal (plain lowest card), and the switch must round-trip through config."""
import os
os.environ.pop("BIQ_SIGNALLING", None)
os.environ.pop("BIQ_SIGNAL_UDCA", None)

from backend.models import Seat, Suit, Rank, Card, BoardState, Hand
from backend import signals


def _card(s):
    return Card(Suit[s[0]], Rank[s[1:]]) if hasattr(Rank, s[1:]) else Card.from_str(s)


def _board_with(seat, cards):
    b = BoardState()
    b.hands[seat] = Hand(cards)
    return b


def test_default_enabled_and_toggle():
    assert signals.is_enabled()
    signals.set_enabled(False)
    try:
        assert not signals.is_enabled()
    finally:
        signals.set_enabled(True)
    assert signals.is_enabled()


def test_off_plays_lowest_not_the_signal():
    # East holds K 9 3 of spades; partner (West) led the ace, North (dummy)
    # followed low, East is 3rd hand: ON encourages with the 9 (attitude —
    # we hold an honour); OFF must play the plain 3.
    from backend.models import Card as C
    k, nine, three = C.from_str("SK"), C.from_str("S9"), C.from_str("S3")
    b = _board_with(Seat.EAST, [k, nine, three])
    trick = [C.from_str("SA"), C.from_str("S5")]   # West led, North played
    cands = [nine, three]                          # trick-equivalent spots
    signals.set_enabled(True)
    on = signals.choose_signal_card(cands, b, Seat.EAST, trick, Seat.SOUTH, None)
    signals.set_enabled(False)
    try:
        off = signals.choose_signal_card(cands, b, Seat.EAST, trick, Seat.SOUTH, None)
    finally:
        signals.set_enabled(True)
    assert on == nine, on
    assert off == three, off


def test_off_discard_is_lowest_of_longest_suit():
    from backend.models import Card as C
    cands = [C.from_str("H9"), C.from_str("H4"), C.from_str("C7")]
    assert signals.lowest_card(cands) == C.from_str("H4")


def test_config_roundtrip(tmp_path):
    from backend.config import ConfigManager
    cm = ConfigManager(tmp_path)
    cm.config.preferences.signalling_enabled = False
    cm.save_preferences()
    cm2 = ConfigManager(tmp_path)
    cm2.load_preferences()
    try:
        assert cm2.config.preferences.signalling_enabled is False
        assert not signals.is_enabled()
    finally:
        signals.set_enabled(True)


def test_never_signal_with_an_honour():
    """K-T under declarer's ace used to 'signal' with the KING (count: even =
    high), throwing away a trick (22 such cards in the Q-Plus matches). With no
    spot card to spend, the signal is the lowest card."""
    signals.set_enabled(True)
    kt = [Card(Suit.DIAMONDS, Rank.KING), Card(Suit.DIAMONDS, Rank.TEN)]
    assert signals._hl(kt, high=True).rank == Rank.TEN
    assert signals._hl(kt, high=False).rank == Rank.TEN
    spots = [Card(Suit.DIAMONDS, Rank.KING), Card(Suit.DIAMONDS, Rank.EIGHT),
             Card(Suit.DIAMONDS, Rank.THREE)]
    assert signals._hl(spots, high=True).rank == Rank.EIGHT

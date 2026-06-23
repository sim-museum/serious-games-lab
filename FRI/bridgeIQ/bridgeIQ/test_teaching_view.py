#!/usr/bin/env python3
"""Tests for the instrumented teaching view's pure inference layer:
known-card placement, master/winner detection, defensive signal reads,
the per-pair carding config, and suit-preference discard reads."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("BIQ_SIGNAL_UDCA", None)

from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                            Contract, Trick, Vulnerability)
import ui.teaching_view as tv


def _c(s, r):
    return Card(Suit.from_char(s), Rank.from_char(r))


def _full_board(declarer=Seat.SOUTH, level=3, strain=Suit.NOTRUMP):
    deck = [Card(s, r) for s in
            [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS] for r in Rank]
    hands = {Seat.NORTH: Hand(cards=deck[0:13]),   # all spades
             Seat.EAST:  Hand(cards=deck[13:26]),  # all hearts
             Seat.SOUTH: Hand(cards=deck[26:39]),  # all diamonds
             Seat.WEST:  Hand(cards=deck[39:52])}  # all clubs
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE,
                   hands={s: Hand(cards=list(h.cards)) for s, h in hands.items()})
    b.contract = Contract(level=level, suit=strain, declarer=declarer)
    return b


def test_known_layout_forced_placement_and_voids():
    b = _full_board()
    # West (all clubs) leads CA; N/E/S all show out of clubs.
    t = Trick(cards=[_c('C', 'A'), _c('S', '2'), _c('H', '2'), _c('D', '2')],
              leader=Seat.WEST, winner=Seat.WEST)
    b.tricks = [t]
    for seat, c in zip([Seat.WEST, Seat.NORTH, Seat.EAST, Seat.SOUTH], t.cards):
        b.hands[seat].cards.remove(c)

    _, voids, _ = tv.collect_play(b)
    assert Suit.CLUBS in voids[Seat.NORTH]
    layout = tv.known_layout(b, {Seat.SOUTH, Seat.NORTH})
    # Remaining clubs are forced to West (every other seat is void).
    assert len(layout["known"][Seat.WEST][Suit.CLUBS]) == 12
    rem = layout["rem_ranks"]
    assert tv.boss_rank(rem, Suit.CLUBS) == Rank.KING   # CA played
    assert tv.boss_rank(rem, Suit.SPADES) == Rank.ACE


def test_attitude_and_count_reads_and_udca_flip():
    b = _full_board()           # 3NT, no trump
    # West leads HK (our side), N HA wins, E H9 (spot), S H3.
    b.tricks = [Trick(cards=[_c('H', 'K'), _c('H', 'A'), _c('H', '9'), _c('H', '3')],
                      leader=Seat.WEST, winner=Seat.NORTH)]
    std = lambda s: tv.CARDING_PRESETS["Standard"]
    reads = tv.signal_reads(b, Seat.SOUTH, None, std)
    e9 = [r for r in reads if r["card"] == _c('H', '9')][0]
    assert e9["seat"] == Seat.EAST and e9["kind"] == "att" and e9["tag"] == "enc"
    # Upside-down flips the same card to discouraging.
    udca = lambda s: tv.CARDING_PRESETS["Upside-down"]
    e9u = [r for r in tv.signal_reads(b, Seat.SOUTH, None, udca)
           if r["card"] == _c('H', '9')][0]
    assert e9u["tag"] == "disc"


def test_suit_preference_discard():
    b = _full_board(level=4, strain=Suit.SPADES)   # trump = spades
    # West leads HA; East has no hearts → discards D9 (high).
    b.tricks = [Trick(cards=[_c('H', 'A'), _c('H', '3'), _c('D', '9'), _c('S', '2')],
                      leader=Seat.WEST, winner=Seat.WEST)]
    # Standard discard = attitude about the thrown suit.
    std = lambda s: tv.CARDING_PRESETS["Standard"]
    d_std = [r for r in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, std)
             if r["kind"] == "dsc"][0]
    assert d_std["tag"] == "enc" and "likes" in d_std["meaning"]
    # Lavinthal = suit-preference: high spot → higher of {hearts, clubs} = hearts.
    lav = lambda s: tv.CARDING_PRESETS["Std + Lavinthal"]
    d_lav = [r for r in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, lav)
             if r["kind"] == "dsc"][0]
    assert d_lav["tag"] == "sp" and d_lav["meaning"].endswith(Suit.HEARTS.symbol())


def test_per_pair_resolver_picks_by_signaller_side():
    b = _full_board(level=4, strain=Suit.SPADES)
    b.tricks = [Trick(cards=[_c('H', 'A'), _c('H', '3'), _c('D', '9'), _c('S', '2')],
                      leader=Seat.WEST, winner=Seat.WEST)]
    # N/S standard, E/W Lavinthal — the East discard must read as suit-pref.
    def mixed(seat):
        return (tv.CARDING_PRESETS["Std + Lavinthal"] if not seat.is_ns()
                else tv.CARDING_PRESETS["Standard"])
    d = [r for r in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, mixed)
         if r["kind"] == "dsc"][0]
    assert d["seat"] == Seat.EAST and d["tag"] == "sp"


def test_honest_signal_flag():
    """A face-up signaller's follow card is checked against its real holding."""
    std = lambda s: tv.CARDING_PRESETS["Standard"]

    def board_with(east_card):
        b = BoardState(board_number=1, dealer=Seat.SOUTH,
                       vulnerability=Vulnerability.NONE, hands={})
        b.contract = Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
        # West leads HK, North wins HA, East follows a heart spot, South H3.
        b.tricks = [Trick(cards=[_c('H', 'K'), _c('H', 'A'), east_card, _c('H', '3')],
                          leader=Seat.WEST, winner=Seat.NORTH)]
        # East's remaining hearts after the play (no honour → honest = discourage/low).
        others = [c for c in [_c('H', '9'), _c('H', '8'), _c('H', '2')]
                  if c != east_card]
        b.hands = {Seat.EAST: Hand(cards=others + [_c('S', '7'), _c('C', '7')])}
        return b

    # Played high (encourage) with no honour → a false-card; honest card is low.
    bf = board_with(_c('H', '9'))
    rf = [r for r in tv.signal_reads(bf, Seat.SOUTH, None, std, {Seat.EAST})
          if r["card"] == _c('H', '9')][0]
    assert rf["honest"] is False and rf["expected"] is not None
    # Played low (discourage) with no honour → honest.
    bh = board_with(_c('H', '2'))
    rh = [r for r in tv.signal_reads(bh, Seat.SOUTH, None, std, {Seat.EAST})
          if r["card"] == _c('H', '2')][0]
    assert rh["honest"] is True
    # Signaller hidden → not checkable.
    rn = [r for r in tv.signal_reads(bf, Seat.SOUTH, None, std, set())
          if r["card"] == _c('H', '9')][0]
    assert rn["honest"] is None


def test_trump_echo():
    """High-low in the trump suit reads as an odd count (ruff signal)."""
    b = _full_board(level=4, strain=Suit.SPADES)   # trump = spades
    # Declarer South draws trumps: leads SA; West follows S9 (high spot).
    b.tricks = [Trick(cards=[_c('S', 'A'), _c('S', '9'), _c('S', '3'), _c('S', '2')],
                      leader=Seat.SOUTH, winner=Seat.SOUTH)]
    std = lambda s: tv.CARDING_PRESETS["Standard"]
    r = [x for x in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, std)
         if x["card"] == _c('S', '9')][0]
    assert r["seat"] == Seat.WEST and r["tag"] == "ruff" and "trump" in r["meaning"]
    # A LOW trump spot would show even.
    b2 = _full_board(level=4, strain=Suit.SPADES)
    b2.tricks = [Trick(cards=[_c('S', 'A'), _c('S', '2'), _c('S', '9'), _c('S', '3')],
                       leader=Seat.SOUTH, winner=Seat.SOUTH)]
    r2 = [x for x in tv.signal_reads(b2, Seat.SOUTH, Suit.SPADES, std)
          if x["card"] == _c('S', '2')][0]
    assert r2["tag"] == "te"


def test_smith_echo():
    """First card in declarer's suit (NT) reads as attitude about the lead."""
    from dataclasses import replace
    b = _full_board(level=3, strain=Suit.NOTRUMP)
    # T0: West leads H5 (opening lead, hearts). T1: declarer South leads C2,
    # West follows C9 (high) → Smith echo "likes hearts".
    b.tricks = [
        Trick(cards=[_c('H', '5'), _c('H', '2'), _c('H', '3'), _c('H', '4')],
              leader=Seat.WEST, winner=Seat.SOUTH),
        Trick(cards=[_c('C', '2'), _c('C', '9'), _c('C', 'K'), _c('C', 'A')],
              leader=Seat.SOUTH, winner=Seat.EAST),
    ]
    smith_on = lambda s: replace(tv.CARDING_PRESETS["Standard"], smith="standard")
    reads = tv.signal_reads(b, Seat.SOUTH, None, smith_on)
    sm = [r for r in reads if r["kind"] == "smith" and r["card"] == _c('C', '9')]
    assert sm and sm[0]["seat"] == Seat.WEST and sm[0]["tag"] == "enc"
    assert Suit.HEARTS.symbol() in sm[0]["meaning"] and "continue" in sm[0]["meaning"]
    # The ordinary count read on that same C9 must be suppressed.
    assert not [r for r in reads
                if r["kind"] == "cnt" and r["card"] == _c('C', '9')]
    # With Smith off, it is read as a plain count instead.
    off = lambda s: tv.CARDING_PRESETS["Standard"]
    reads_off = tv.signal_reads(b, Seat.SOUTH, None, off)
    assert not [r for r in reads_off if r["kind"] == "smith"]
    assert [r for r in reads_off
            if r["kind"] == "cnt" and r["card"] == _c('C', '9')]


def test_stopper_and_entry_highlights():
    # Stopper length-guard rule.
    assert tv.stopper_rank([Rank.ACE, Rank.FIVE]) == Rank.ACE
    assert tv.stopper_rank([Rank.KING, Rank.THREE]) == Rank.KING
    assert tv.stopper_rank([Rank.KING]) is None          # bare king
    assert tv.stopper_rank([Rank.QUEEN, Rank.FOUR, Rank.TWO]) == Rank.QUEEN
    assert tv.stopper_rank([Rank.QUEEN, Rank.TWO]) is None
    assert tv.stopper_rank([Rank.JACK, Rank.FIVE, Rank.FOUR, Rank.THREE]) == Rank.JACK
    # Entry = the highest sure winner.
    assert tv.top_entry_rank({Rank.KING, Rank.QUEEN}) == Rank.KING
    assert tv.top_entry_rank(set()) is None
    # Badges appear in the rendered Known cell.
    html = tv._render_known([Rank.KING, Rank.THREE], Suit.SPADES,
                            winners=set(), boss=None,
                            entries={Rank.KING}, stoppers={Rank.KING})
    # Vivid inverse-video chips (no superscripts): E = entry, S = stopper.
    assert ">E</span>" in html and ">S</span>" in html


def test_danger_hand_and_knockout_entry():
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE, hands={})
    b.contract = Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
    # West leads a spade (opening lead) → threat = spades, leader = West.
    b.tricks = [Trick(cards=[_c('S', '5'), _c('S', '2'), _c('S', '3'), _c('S', 'A')],
                      leader=Seat.WEST, winner=Seat.SOUTH)]
    # West is long in spades and holds a side Ace (clubs) = the entry to attack.
    b.hands = {
        Seat.WEST: Hand(cards=[_c('S', 'K'), _c('S', 'Q'), _c('S', 'J'), _c('S', '9'),
                               _c('S', '8'), _c('H', '4'), _c('H', '3'), _c('D', '7'),
                               _c('D', '6'), _c('C', 'A'), _c('C', '5'), _c('C', '4'),
                               _c('C', '2')]),
        Seat.EAST: Hand(cards=[_c('S', 'T'), _c('H', 'A'), _c('H', 'K'), _c('H', '9'),
                               _c('D', 'K'), _c('D', 'Q'), _c('D', 'J'), _c('D', 'T'),
                               _c('C', 'K'), _c('C', 'Q'), _c('C', 'J'), _c('C', '9'),
                               _c('C', '8')])}
    vis = {Seat.WEST, Seat.EAST}
    layout = tv.known_layout(b, vis)
    d = tv.danger_info(b, b.contract, Seat.SOUTH, vis, layout, {})
    assert d["seat"] == Seat.WEST and d["threat"] == Suit.SPADES
    assert d["knockout"] == (Suit.CLUBS, Rank.ACE)
    # A knock-out badge is rendered on that card.
    html = tv._render_known([Rank.ACE, Rank.FIVE], Suit.CLUBS, set(), None,
                            knockout={Rank.ACE})
    assert ">KO</span>" in html
    # Suit contracts have no danger-hand read (you ruff).
    b.contract = Contract(level=4, suit=Suit.SPADES, declarer=Seat.SOUTH)
    assert tv.danger_info(b, b.contract, Seat.SOUTH, vis, layout, {}) is None


def test_ruff_lead_suit_preference():
    b = _full_board(level=4, strain=Suit.SPADES)
    # T0: West leads HA, East shows out (discards C2) → East void in hearts.
    # T1: West leads HK giving East a ruff; high heart → higher of {D,C} = D.
    b.tricks = [
        Trick(cards=[_c('H', 'A'), _c('H', '3'), _c('C', '2'), _c('H', '2')],
              leader=Seat.WEST, winner=Seat.WEST),
        Trick(cards=[_c('H', 'K'), _c('H', '5'), _c('S', '3'), _c('H', '4')],
              leader=Seat.WEST, winner=Seat.WEST)]
    std = lambda s: tv.CARDING_PRESETS["Standard"]
    rl = [r for r in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, std)
          if r["kind"] == "ruflead"]
    assert len(rl) == 1 and rl[0]["trick"] == 1        # only after void shown
    assert rl[0]["meaning"].endswith(Suit.DIAMONDS.symbol())


def test_discard_and_trump_echo_honesty():
    std = lambda s: tv.CARDING_PRESETS["Standard"]
    # Attitude discard: East throws C2 (low) but holds the CK honour → dishonest.
    b = _full_board(level=4, strain=Suit.SPADES)
    b.tricks = [Trick(cards=[_c('H', 'A'), _c('H', '3'), _c('C', '2'), _c('H', '2')],
                      leader=Seat.WEST, winner=Seat.WEST)]
    b.hands = {Seat.EAST: Hand(cards=[_c('C', 'K'), _c('C', '9'),
                                      _c('S', '5'), _c('S', '4')])}
    d = [r for r in tv.signal_reads(b, Seat.SOUTH, Suit.SPADES, std, {Seat.EAST})
         if r["kind"] == "dsc"][0]
    assert d["honest"] is False and d["expected"] is not None
    # Trump echo honesty: West plays S9 (high) from a 2-card trump holding
    # (even) — standard echo wants low for even → dishonest.
    b2 = _full_board(level=4, strain=Suit.SPADES)
    b2.tricks = [Trick(cards=[_c('S', 'A'), _c('S', '9'), _c('S', '3'), _c('S', '2')],
                       leader=Seat.SOUTH, winner=Seat.SOUTH)]
    b2.hands = {Seat.WEST: Hand(cards=[_c('S', '6'), _c('H', '4'), _c('H', '3')])}  # 1 trump left → orig 2
    r = [x for x in tv.signal_reads(b2, Seat.SOUTH, Suit.SPADES, std, {Seat.WEST})
         if x["card"] == _c('S', '9')][0]
    assert r["tag"] == "ruff" and r["honest"] is False


def test_finesse_and_squeeze_and_vacant_spaces():
    # Finesse: AK + small (8 cards) missing Q → 8-ever finesse.
    b = _full_board(level=4, strain=Suit.SPADES)
    b.hands = {
        Seat.SOUTH: Hand(cards=[_c('S', 'A'), _c('S', 'K'), _c('S', '5'), _c('S', '4'),
                                _c('H', '2'), _c('H', '3'), _c('H', '4'), _c('H', '5'),
                                _c('D', '2'), _c('D', '3'), _c('D', '4'), _c('D', '5'),
                                _c('C', '2')]),
        Seat.NORTH: Hand(cards=[_c('S', '7'), _c('S', '6'), _c('S', '3'), _c('S', '2'),
                                _c('H', '6'), _c('H', '7'), _c('H', '8'), _c('D', '6'),
                                _c('D', '7'), _c('D', '8'), _c('C', '3'), _c('C', '4'),
                                _c('C', '5')])}
    layout = tv.known_layout(b, {Seat.SOUTH, Seat.NORTH})
    fh = tv.finesse_hints(Seat.SOUTH, Seat.NORTH, {Seat.SOUTH, Seat.NORTH}, layout)
    assert any("8 cards missing Q" in h for h in fh)

    # Squeeze: declarer/dummy hold the second-best in two suits both guarded by
    # West (West holds both masters) → West is busy.
    b2 = _full_board(level=3, strain=Suit.NOTRUMP)
    b2.hands = {
        Seat.SOUTH: Hand(cards=[_c('S', 'K'), _c('H', 'K'), _c('D', '2'), _c('D', '3'),
                                _c('D', '4'), _c('D', '5'), _c('D', '6'), _c('C', '2'),
                                _c('C', '3'), _c('C', '4'), _c('C', '5'), _c('C', '6'),
                                _c('C', '7')]),
        Seat.NORTH: Hand(cards=[_c('S', '2'), _c('H', '2'), _c('D', '7'), _c('D', '8'),
                                _c('D', '9'), _c('D', 'T'), _c('D', 'J'), _c('C', '8'),
                                _c('C', '9'), _c('C', 'T'), _c('C', 'J'), _c('C', 'Q'),
                                _c('C', 'K')]),
        Seat.WEST: Hand(cards=[_c('S', 'A'), _c('H', 'A'), _c('S', '5'), _c('S', '4'),
                               _c('S', '3'), _c('H', '5'), _c('H', '4'), _c('H', '3'),
                               _c('D', 'A'), _c('D', 'K'), _c('D', 'Q'), _c('S', '6'),
                               _c('H', '6')]),
        Seat.EAST: Hand(cards=[_c('S', 'Q'), _c('S', 'J'), _c('S', 'T'), _c('S', '9'),
                               _c('S', '8'), _c('S', '7'), _c('H', 'Q'), _c('H', 'J'),
                               _c('H', 'T'), _c('H', '9'), _c('H', '8'), _c('H', '7'),
                               _c('C', 'A')])}
    vis = {Seat.SOUTH, Seat.NORTH, Seat.WEST, Seat.EAST}
    layout2 = tv.known_layout(b2, vis)
    sq = tv.squeeze_threats(b2, Seat.SOUTH, Seat.NORTH, vis, layout2)
    assert sq is not None
    assert Suit.SPADES in sq["threats"] and Suit.HEARTS in sq["threats"]
    assert Seat.WEST in sq["busy"]

    # Honour placement runs and labels every unseen honour; vacant-space %
    # shows once the two hidden hands diverge in known cards (here, symmetric
    # at trick 1 → the clean side label).
    b3 = _full_board(level=3, strain=Suit.NOTRUMP)
    layout3 = tv.known_layout(b3, {Seat.SOUTH, Seat.NORTH})
    hp = tv.honour_placement(b3, {Seat.SOUTH, Seat.NORTH}, layout3)
    assert hp and all(isinstance(label, str) and label for _, _, label in hp)
    assert any(label == "E/W" for _, _, label in hp)


def test_loser_marking():
    allr = set(Rank)
    # KQx with the ace still out → the small card is the loser (LTC = 1).
    assert tv.suit_loser_ranks([Rank.KING, Rank.QUEEN, Rank.THREE], allr) \
        == {Rank.THREE}
    # AKQ → no losers.
    assert tv.suit_loser_ranks([Rank.ACE, Rank.KING, Rank.QUEEN], allr) == set()
    # Axx → missing K and Q → the two low cards are losers.
    assert tv.suit_loser_ranks([Rank.ACE, Rank.SEVEN, Rank.SIX], allr) \
        == {Rank.SEVEN, Rank.SIX}
    # Rendered Known cell draws the red loser box.
    html = tv._render_known([Rank.KING, Rank.QUEEN, Rank.THREE], Suit.SPADES,
                            winners=set(), boss=None, losers={Rank.THREE})
    assert tv.ACC_RED in html


def test_suit_pref_honesty():
    b = _full_board()
    b.hands[Seat.WEST] = Hand(cards=[_c('H', 'A'), _c('H', 'K'),
                                     _c('C', '3'), _c('C', '2')])
    vis = {Seat.WEST}
    # Points to hearts, where West actually holds A K → honest.
    h, exp = tv._suit_pref_honest(b, Seat.WEST, Suit.HEARTS, Suit.CLUBS, 0, vis)
    assert h is True and exp is None
    # Points to clubs (no values there) → false-card.
    h2, _ = tv._suit_pref_honest(b, Seat.WEST, Suit.CLUBS, Suit.HEARTS, 0, vis)
    assert h2 is False
    # Signaller hidden → not checkable.
    h3, _ = tv._suit_pref_honest(b, Seat.WEST, Suit.HEARTS, Suit.CLUBS, 0, set())
    assert h3 is None


def test_squeeze_type_and_rectified():
    b2 = _full_board(level=3, strain=Suit.NOTRUMP)
    b2.hands = {
        Seat.SOUTH: Hand(cards=[_c('S', 'K'), _c('H', 'K'), _c('D', '2'), _c('D', '3'),
                                _c('D', '4'), _c('D', '5'), _c('D', '6'), _c('C', '2'),
                                _c('C', '3'), _c('C', '4'), _c('C', '5'), _c('C', '6'),
                                _c('C', '7')]),
        Seat.NORTH: Hand(cards=[_c('S', '2'), _c('H', '2'), _c('D', '7'), _c('D', '8'),
                                _c('D', '9'), _c('D', 'T'), _c('D', 'J'), _c('C', '8'),
                                _c('C', '9'), _c('C', 'T'), _c('C', 'J'), _c('C', 'Q'),
                                _c('C', 'K')]),
        Seat.WEST: Hand(cards=[_c('S', 'A'), _c('H', 'A'), _c('S', '5'), _c('S', '4'),
                               _c('S', '3'), _c('H', '5'), _c('H', '4'), _c('H', '3'),
                               _c('D', 'A'), _c('D', 'K'), _c('D', 'Q'), _c('S', '6'),
                               _c('H', '6')]),
        Seat.EAST: Hand(cards=[_c('S', 'Q'), _c('S', 'J'), _c('S', 'T'), _c('S', '9'),
                               _c('S', '8'), _c('S', '7'), _c('H', 'Q'), _c('H', 'J'),
                               _c('H', 'T'), _c('H', '9'), _c('H', '8'), _c('H', '7'),
                               _c('C', 'A')])}
    vis = {Seat.SOUTH, Seat.NORTH, Seat.WEST, Seat.EAST}
    layout2 = tv.known_layout(b2, vis)
    sq = tv.squeeze_threats(b2, Seat.SOUTH, Seat.NORTH, vis, layout2, None)
    # Both one-card menaces sit in declarer's hand → a simple squeeze (NT).
    assert sq["type"] == "simple"
    assert isinstance(sq["losers"], int)
    assert sq["rectified"] in (True, False)


def test_bayes_distribution():
    import random as _r
    b = _full_board(level=3, strain=Suit.NOTRUMP)   # N♠ E♥ S♦ W♣
    vis = {Seat.NORTH, Seat.SOUTH}                   # E/W hidden
    layout = tv.known_layout(b, vis)
    post = tv.bayes_distribution(b, vis, layout, {}, samples=80, rng=_r.Random(1))
    assert post is not None and post["samples"] > 0
    # Every unseen honour is placed in exactly one hidden hand each world, so its
    # E/W probabilities sum to ~1, and only E/W are candidates.
    for (su, r), probs in post["honour"].items():
        assert 0.9 <= sum(probs.values()) <= 1.0001
        assert set(probs) <= {Seat.EAST, Seat.WEST}
    assert Seat.EAST in post["length"] and Seat.WEST in post["length"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("ALL TEACHING-VIEW TESTS PASSED")

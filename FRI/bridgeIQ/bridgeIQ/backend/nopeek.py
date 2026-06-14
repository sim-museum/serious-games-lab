"""No-peek cardplay engine for biq.

Plays every card using ONLY what the seat is entitled to see — its own hand,
the dummy once it is exposed, the auction, and the cards already played. It
never solves or samples a layout it cannot legitimately see, so it never peeks
at hidden cards. The guarantee is architectural: `decide()` first REDACTS the
board so the hidden hands are physically empty, then all policy runs on the
redacted board — it is structurally incapable of looking at an opponent's (or,
on defence, partner's) cards.

This is a technique/inference engine (3rd-hand-high, 2nd-hand-low, cover an
honour, draw trumps, cash winners, keep guards, return partner's suit, signal),
not a double-dummy or Monte-Carlo solver. It is the honest player a
sophisticated audience expects; it trades the double-dummy engine's omniscient
ceiling for play that never cheats. Strength grows by adding technique, not by
peeking.

v1 is a competent baseline. Hooks for stronger technique (single-dummy belief
sampling for finesse odds, signalling) are marked TODO.
"""
from __future__ import annotations
from typing import List, Optional, Dict

from .models import Seat, Suit, Rank, Card, Hand, BoardState, Contract
from .cardplay_planner import (is_boss_card, filter_safe_discards,
                               own_side_ranks_in_suit)
from . import cardplay_plan


# ---------------------------------------------------------------- redaction

def _dummy_seat(board: BoardState) -> Optional[Seat]:
    return board.contract.declarer.partner() if board.contract else None


def _dummy_exposed(board: BoardState, current_trick_cards: List[Card]) -> bool:
    """Dummy comes down after the opening lead."""
    return bool(board.tricks) or bool(current_trick_cards)


def redact(board: BoardState, seat: Seat,
           current_trick_cards: List[Card]) -> BoardState:
    """A copy of `board` exposing ONLY the hands `seat` is entitled to see.
    Everything else (auction, contract, completed tricks) is public and kept;
    unseen hands are replaced with empty Hands so no policy can read them."""
    entitled = {seat}
    if board.contract is not None:
        decl = board.contract.declarer
        dummy = decl.partner()
        if _dummy_exposed(board, current_trick_cards):
            entitled.add(dummy)                 # everyone sees exposed dummy
        if seat == decl:
            entitled.add(dummy)                 # declarer always sees dummy
        if seat == dummy:
            entitled.add(decl)                  # declarer controls dummy + sees own
    hands = {s: (Hand(cards=list(board.hands[s].cards))
                 if s in entitled and s in board.hands else Hand(cards=[]))
             for s in Seat}
    return BoardState(board_number=board.board_number, dealer=board.dealer,
                      vulnerability=board.vulnerability, hands=hands,
                      auction=list(board.auction), contract=board.contract,
                      tricks=board.tricks)


# ------------------------------------------------------------ card helpers

def _legal(hand: Hand, lead_suit: Optional[Suit]) -> List[Card]:
    if lead_suit is not None:
        follow = [c for c in hand.cards if c.suit == lead_suit]
        if follow:
            return _hi_lo(follow)
    return _hi_lo(hand.cards)


def _hi_lo(cards: List[Card]) -> List[Card]:
    """Sorted high → low (Ace first). rank.value: A=0..2=12, so ascending."""
    return sorted(cards, key=lambda c: (c.suit.value, c.rank.value))


def _by_suit(cards: List[Card]) -> Dict[Suit, List[Card]]:
    out: Dict[Suit, List[Card]] = {}
    for c in cards:
        out.setdefault(c.suit, []).append(c)
    for s in out:
        out[s] = sorted(out[s], key=lambda c: c.rank.value)   # high first
    return out


def _winning_index(trick: List[Card], trump: Optional[Suit]) -> int:
    """Index into `trick` of the card currently winning."""
    lead = trick[0].suit
    wi, wc = 0, trick[0]
    for i, c in enumerate(trick[1:], 1):
        c_t = trump is not None and c.suit == trump
        w_t = trump is not None and wc.suit == trump
        if c_t and not w_t:
            wi, wc = i, c
        elif c_t and w_t and c.rank.value < wc.rank.value:
            wi, wc = i, c
        elif not c_t and not w_t and c.suit == lead \
                and c.rank.value < wc.rank.value:
            wi, wc = i, c
    return wi


def _beats(card: Card, win_card: Card, lead: Suit, trump: Optional[Suit]) -> bool:
    """Does `card` (legal, in lead suit since we are following) beat the
    currently-winning card?"""
    win_is_trump = trump is not None and win_card.suit == trump
    if win_is_trump and card.suit != trump:
        return False                                   # can't beat a ruff in-suit
    if card.suit == win_card.suit:
        return card.rank.value < win_card.rank.value   # lower value = higher card
    return False


# ----------------------------------------------------------------- policies

def _opening_lead(board: BoardState, seat: Seat) -> Card:
    """Defender's opening lead via biq's rule-based lead engine (native_lead).
    It uses ONLY the leader's own hand + public auction/contract — no peek."""
    from . import native_lead
    try:
        d = native_lead.select_opening_lead(
            hand=board.hands[seat], contract=board.contract,
            auction=board.auction, dealer=board.dealer, leader=seat,
            vulnerability=board.vulnerability)
        if d is not None and d.card is not None:
            return d.card
    except Exception:
        pass
    return _by_suit(board.hands[seat].cards)[
        max(_by_suit(board.hands[seat].cards),
            key=lambda s: len(_by_suit(board.hands[seat].cards)[s]))][-1]


def _safe_defender_lead(board: BoardState, seat: Seat, legal: List[Card],
                        trump: Optional[Suit]) -> Card:
    """Subsequent defensive lead: don't underlead honours into a suit contract.
    Prefer top of a touching-honour sequence, the top of an AK, a singleton
    (ruff), or a low card from an honour-LESS suit; underlead only as a last
    resort. No peek (own hand + public)."""
    by = _by_suit([c for c in legal if c.suit != trump]) or _by_suit(legal)

    def seq_top(cards):
        v = [c.rank.value for c in cards]
        for i in range(len(cards) - 2):
            if v[i] + 1 == v[i + 1] and v[i + 1] + 1 == v[i + 2] \
                    and cards[i].rank.value <= 3:
                return cards[i]
        # AK doubleton+ : cash the K (lead it) vs a suit contract
        if trump is not None and len(cards) >= 2 \
                and cards[0].rank == Rank.ACE and cards[1].rank == Rank.KING:
            return cards[1]
        return None

    # 1) top of a sequence / AK in any suit
    for s in sorted(by, key=lambda s: -len(by[s])):
        top = seq_top(by[s])
        if top is not None:
            return top
    # 2) RETURN PARTNER'S SUIT — continue the suit partner attacked. Lead the
    #    higher from a remaining doubleton, else a low card (original count).
    partner = seat.partner()
    partner_suit = None
    for t in board.tricks:
        if getattr(t, "cards", None) and t.leader == partner:
            partner_suit = t.cards[0].suit
            break
    if partner_suit is not None and partner_suit != trump and partner_suit in by:
        cards = by[partner_suit]                       # high → low
        return cards[0] if len(cards) == 2 else cards[-1]
    # 3) a singleton in a side suit (ruff try) vs a suit contract
    if trump is not None:
        for s in by:
            if len(by[s]) == 1:
                return by[s][0]
    # 3) low from an honour-less suit (no A/K/Q to protect)
    honourless = [s for s in by if all(c.rank.value > 2 for c in by[s])]
    if honourless:
        s = max(honourless, key=lambda s: len(by[s]))
        return by[s][-1]
    # 4) last resort: low from the longest
    s = max(by, key=lambda s: len(by[s]))
    return by[s][-1]


def _played_values(board: BoardState, suit: Suit) -> set:
    return {c.rank.value for t in board.tricks for c in t.cards
            if c.suit == suit}


def _develop_finesse(board: BoardState, seat: Seat, legal: List[Card],
                     trump: Optional[Suit], declarer: Seat) -> Optional[Card]:
    """Declarer on lead: if the OTHER declarer hand holds a split tenace over a
    missing honour (AQ / KJ / QT ...), lead a low card from THIS hand toward it.
    The finesse itself falls out of 3rd-hand-high when the other hand follows.
    Uses only the two declarer hands (both visible to declarer). No peek."""
    dummy = declarer.partner()
    other = declarer if seat == dummy else dummy
    if other not in board.hands:
        return None
    best_card, best_len = None, -1
    for suit in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if suit == trump:
            continue
        mine = [c for c in legal if c.suit == suit]
        if not mine:
            continue
        ov = {c.rank.value for c in board.hands[other].cards if c.suit == suit}
        mv = {c.rank.value for c in board.hands[seat].cards if c.suit == suit}
        played = _played_values(board, suit)
        # split tenace: other has v and v+2, the v+1 honour is missing (could
        # be with opponents). v+1 must be an honour rank (<=4 => A..T).
        finesse = any(v in ov and (v + 2) in ov and (v + 1) <= 4
                      and (v + 1) not in ov and (v + 1) not in mv
                      and (v + 1) not in played
                      for v in range(0, 11))
        if finesse and len(mine) > best_len:
            best_card, best_len = mine[-1], len(mine)   # lead our lowest toward it
    return best_card


def _establish_suit(board: BoardState, seat: Seat, legal: List[Card],
                    trump: Optional[Suit], declarer: Seat) -> Optional[Card]:
    """Attack our longest combined side suit to set up length tricks — what a
    good declarer does after drawing trumps, before cashing scattered winners.
    Pick the longest non-trump suit (5+ combined) where we hold the control to
    establish it (>=2 of the top four ranks between the two hands). Lead a boss
    to cash/run it, the top of a touching-honour sequence to force the missing
    honour out, else a low card to concede a round and set up the length. Uses
    only the two declarer hands (visible to declarer). No peek."""
    dummy = declarer.partner()
    other = declarer if seat == dummy else dummy
    best, blen = None, 4
    for su in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if su == trump:
            continue
        mine = [c for c in board.hands[seat].cards if c.suit == su]
        pard = ([c for c in board.hands[other].cards if c.suit == su]
                if other in board.hands else [])
        comb = len(mine) + len(pard)
        tops = {c.rank.value for c in mine + pard if c.rank.value <= 3}
        if comb >= 5 and len(tops) >= 2 and comb > blen:
            best, blen = su, comb
    if best is None:
        return None
    here = sorted((c for c in legal if c.suit == best), key=lambda c: c.rank.value)
    if not here:
        return None                                    # suit is in partner's hand
    top = here[0]
    if is_boss_card(top, board, seat, [], declarer):
        return top                                     # cash/run a winner
    if (len(here) >= 2 and top.rank.value <= 3
            and here[1].rank.value == top.rank.value + 1):
        return top                                     # top of a sequence: force
    return here[-1]                                    # low: concede to set up length


def _outstanding_trumps(board: BoardState, trump: Optional[Suit],
                        declarer: Seat) -> int:
    """How many trumps the DEFENDERS still hold (no peek: 13 - our visible
    trumps - trumps already played)."""
    if trump is None:
        return 0
    dummy = declarer.partner()
    ours = sum(1 for s in (declarer, dummy) if s in board.hands
               for c in board.hands[s].cards if c.suit == trump)
    played = sum(1 for t in board.tricks for c in t.cards if c.suit == trump)
    return max(0, 13 - ours - played)


def _lead(board: BoardState, seat: Seat, legal: List[Card],
          trump: Optional[Suit], declarer: Seat) -> Card:
    """On lead, not the opening lead."""
    decl_side = seat.is_ns() == declarer.is_ns()
    if decl_side:
        # 1) DRAW TRUMPS until the defenders have none — even at the cost of
        #    conceding a trump trick. Leading our highest trump forces theirs
        #    out and stops them ruffing our side-suit winners. (The old rule
        #    only drew while our trump was boss, so it abandoned the job once a
        #    defender held the master trump, then got ruffed.)
        if trump is not None and _outstanding_trumps(board, trump, declarer) > 0:
            my_trumps = sorted((c for c in legal if c.suit == trump),
                               key=lambda c: c.rank.value)
            if my_trumps:
                return my_trumps[0]                # highest trump from this hand
        planned = cardplay_plan.planned_lead(board, seat, [])
        if planned is not None and any(c.suit == planned.suit
                                       and c.rank == planned.rank
                                       for c in legal):
            return planned
        # 2) ESTABLISH the long suit (the trick source) before cashing scattered
        #    short-suit winners — a good declarer attacks length early.
        est = _establish_suit(board, seat, legal, trump, declarer)
        if est is not None:
            return est
        # 3) cash a guaranteed winner (boss card) — lowest such, to keep
        #    communication; prefer the longest suit so we set up length
        bosses = [c for c in legal
                  if is_boss_card(c, board, seat, [], declarer)]
        if bosses:
            by = _by_suit(bosses)
            longest = max(by, key=lambda s: (len(by[s]), -s.value))
            return by[longest][0]                      # the boss (top) to cash
        # 3) develop a finesse toward the other hand's tenace
        fin = _develop_finesse(board, seat, legal, trump, declarer)
        if fin is not None:
            return fin
        # DECLARER PLANNER (sees both hands): rather than lead a passive low card
        # into nothing, CROSS to the partner hand when it holds the winners.
        from . import declarer_plan
        pc = declarer_plan.plan_lead(board, seat, declarer, trump)
        if pc is not None and any(c.suit == pc.suit and c.rank == pc.rank
                                  for c in legal):
            return pc
        # 4) otherwise lead low from our longest non-trump side suit
        by = _by_suit([c for c in legal if c.suit != trump]) or _by_suit(legal)
        if by:
            longest = max(by, key=lambda s: (len(by[s]), -s.value))
            return by[longest][-1]                     # low card
        return legal[-1]
    # defender on lead (not opening): sound technique, no underleading honours
    return _safe_defender_lead(board, seat, legal, trump)


def _should_holdup(board: BoardState, seat: Seat, trick: List[Card],
                   declarer: Seat, legal: List[Card]) -> bool:
    """Declarer-side hold-up in NT: with a SINGLE stopper in the suit the
    defenders are attacking, duck the early rounds to exhaust the shorter
    defender's cards and cut their communications. Win only once we've ducked
    enough (round > our small-card count). No peek — own + dummy + played."""
    if seat.is_ns() != declarer.is_ns():
        return False
    pos = len(trick)
    leader = Seat((seat.value - pos) % 4)
    if leader.is_ns() == seat.is_ns():
        return False                                   # our side led — no hold-up
    led = trick[0].suit
    my = [c for c in legal if c.suit == led]
    if len(my) < 2:
        return False                                   # need the stopper + a small
    dummy = declarer.partner()
    other = declarer if seat == dummy else dummy
    comb = [c for c in board.hands[seat].cards if c.suit == led]
    if other in board.hands:
        comb += [c for c in board.hands[other].cards if c.suit == led]
    comb.sort(key=lambda c: c.rank.value)
    if not is_boss_card(comb[0], board, seat, trick, declarer):
        return False                                   # we don't hold the master
    if len(comb) >= 2 and is_boss_card(comb[1], board, seat, trick, declarer):
        return False                                   # two stoppers — no need
    small = len(comb) - 1                              # cards besides the stopper
    rounds_already = sum(1 for t in board.tricks
                         if t.cards and t.cards[0].suit == led)
    return small >= 1 and rounds_already < small


def _follow(board: BoardState, seat: Seat, legal: List[Card],
            trick: List[Card], trump: Optional[Suit], declarer: Seat) -> Card:
    """Follow suit. legal = our cards in the led suit, high → low."""
    led = trick[0].suit
    pos = len(trick)                                   # 1=2nd,2=3rd,3=4th hand
    wi = _winning_index(trick, trump)
    win_card = trick[wi]
    win_seat = Seat((Seat((seat.value - pos) % 4).value + wi) % 4)
    our_side_winning = win_seat.is_ns() == seat.is_ns()
    low = legal[-1]
    high = legal[0]

    from . import signals
    if our_side_winning and pos in (2, 3):
        # partner/dummy winning — play a non-winning card, but SIGNAL with it
        # (attitude if partner's suit, count if an opponent's): textbook carding
        # at zero trick cost (every legal card here loses this trick anyway).
        return signals.choose_signal_card(legal, board, seat, trick, declarer,
                                           trump)
    beating = [c for c in legal if _beats(c, win_card, led, trump)]
    if not beating:
        return signals.choose_signal_card(legal, board, seat, trick, declarer,
                                           trump)
    # HOLD-UP (NT): duck a single stopper to cut defenders' communications.
    if trump is None and _should_holdup(board, seat, trick, declarer, legal):
        return low
    cheapest = beating[-1]                              # lowest card that still wins
    if pos == 1:                                       # 2nd hand
        # COVER AN HONOUR with an honour to promote our side's spot cards —
        # but not the top of a sequence the leader is visibly holding (don't
        # cover the Q from a QJ; wait for the last of touching honours).
        led_card = trick[0]
        if led_card.rank.value in (1, 2, 3):           # K/Q/J led
            honours = [c for c in beating if c.rank.value <= 3]
            leader = Seat((seat.value - pos) % 4)
            lh = board.hands.get(leader)
            seq = bool(lh and any(c.suit == led and
                                  c.rank.value == led_card.rank.value + 1
                                  for c in lh.cards))
            if honours and not seq:
                return honours[-1]                     # cheapest sufficient honour
        return low                                     # 2nd hand low otherwise
    if pos == 2:                                       # 3rd hand high (cheaply)
        return cheapest
    return cheapest                                    # 4th hand: win as cheaply


def _discard(board: BoardState, seat: Seat, legal: List[Card],
             trick: List[Card], declarer: Seat) -> Card:
    """Void in the led suit and not ruffing: pitch a safe card that SIGNALS
    (suit-preference / attitude) instead of a bare low spot."""
    from . import signals
    safe = filter_safe_discards(legal, board, seat, trick, declarer)
    trump = (board.contract.suit
             if board.contract and board.contract.suit != Suit.NOTRUMP
             else None)
    return signals.choose_signal_card(safe, board, seat, trick, declarer, trump)


# ------------------------------------------------------------------- entry

import os
_AMU_WORLDS = int(os.environ.get("BIQ_AMU_WORLDS", "6"))   # sampled layouts/decision
_AMU_DEPTH = int(os.environ.get("BIQ_AMU_DEPTH", "2"))     # alpha-mu depth in tricks
_AMU_BUDGET = float(os.environ.get("BIQ_AMU_BUDGET", "5")) # per-decision seconds
_AMU_DEFENSE = os.environ.get("BIQ_AMU_DEFENSE", "1") == "1"  # defence alpha-mu
_DEF_ROLLOUT = os.environ.get("BIQ_DEF_ROLLOUT", "0") == "1"  # defence rollout
# (realistic no-peek partner) INSTEAD of alpha-mu defence's perfect-DD partner
_DEF_ROLLOUT_LEAF = os.environ.get("BIQ_DEF_ROLLOUT_LEAF", "0") == "1"  # alpha-mu
# defence with a realistic-partner ROLLOUT leaf (vs the perfect-DD DDS leaf)
_READ_SIGNALS = os.environ.get("BIQ_READ_SIGNALS", "0") == "1"  # hard-filter the
# defence sampler by PARTNER's signals (convention-inversion); see signal_read
_SIGNAL_MARGIN = float(os.environ.get("BIQ_SIGNAL_MARGIN", "0.15"))  # trick
# budget for RELIABLE signalling: widen the alpha-mu tie set so biq always plays
# the convention card among cards it rates within 0.15 tr of best (alpha-mu's
# near-ties are noise; the signal heuristic is a better arbiter). A/B 3 seeds:
# trick-neutral-to-positive vs margin 0 (0.786 vs 0.797). 0 = exact ties only.
_DDS = None


def _get_dds():
    global _DDS
    if _DDS is None:
        from .dds import DDSolver
        _DDS = DDSolver()
    return _DDS


def _alphamu_card(b: BoardState, seat: Seat, trick: List[Card],
                  declarer: Seat, trump: Optional[Suit]) -> Optional[Card]:
    """Card via alpha-mu: sample the HIDDEN layouts consistent with the play (a
    BELIEF — never the actual cards), DDS-evaluate, commit ONE line across
    indistinguishable layouts. DDS on representative samples is not peeking; the
    consistent strategy avoids PIMC's omniscient tells.

    Declaring: biq sees both its hands, the two defenders are hidden, and biq
    plays a consistent line for {declarer, dummy} to MAX declarer tricks.
    Defending: biq sees its hand + dummy; declarer AND partner are hidden; biq
    plays a consistent line for its ONE seat to MAX defensive tricks. Other
    seats (a hidden partner, the opponents) each play DD-best for their own side
    at the leaves — cooperation and competition fall out automatically."""
    from . import declarer_search, alphamu
    dummy = declarer.partner()
    defending = seat.is_ns() != declarer.is_ns()
    if defending:
        # need dummy faced to sample only declarer + partner as the hidden hands
        if dummy not in b.hands or not b.hands[dummy].cards:
            return None
        known_seats, biq_seats = {seat, dummy}, {seat}
    else:
        known_seats, biq_seats = {declarer, dummy}, {declarer, dummy}
    if defending and _READ_SIGNALS:
        # HARD-FILTER the sampled partner hands by partner's own signals: keep
        # only layouts biq's convention would have produced (legitimate info —
        # partner is telling us). Over-sample, filter, fall back if too few.
        from . import signal_read
        recs = signal_read.read(b, seat, declarer, trump)
        raw, hidden = declarer_search._sample_defenders(
            b, seat, trick, declarer, _AMU_WORLDS * 4, known_seats=known_seats)
        if recs and raw:
            partner = seat.partner()
            kept = [a for a in raw
                    if signal_read.consistent(recs, set(a[partner]))]
            samples = kept[:_AMU_WORLDS] if len(kept) >= 2 \
                else raw[:_AMU_WORLDS]
        else:
            samples = raw[:_AMU_WORLDS]
    else:
        samples, hidden = declarer_search._sample_defenders(
            b, seat, trick, declarer, _AMU_WORLDS, known_seats=known_seats)
    if not samples:
        return None
    worlds = []
    for a in samples:
        w = {}
        for s in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
            if s in hidden:
                w[s] = frozenset(a[s])
            else:
                w[s] = frozenset(c.suit.value * 13 + c.rank.value
                                 for c in b.hands[s].cards)
        worlds.append(w)
    amu = alphamu.AlphaMu(trump, declarer, _get_dds(), depth=_AMU_DEPTH,
                          time_budget=_AMU_BUDGET, biq_seats=biq_seats,
                          defense_rollout_leaf=(defending and _DEF_ROLLOUT_LEAF),
                          vul=b.vulnerability, signal_margin=_SIGNAL_MARGIN)
    # When DEFENDING, break trick-equivalent ties by the standard signal so the
    # carding reads like a real defender (zero trick cost — these tie for best).
    tb = None
    if defending:
        from . import signals
        tb = lambda tied: signals.choose_signal_card(
            tied, b, seat, trick, declarer, trump)
    return amu.choose(b, seat, trick, worlds, tiebreak=tb)


def _defense_rollout_card(b: BoardState, seat: Seat, trick: List[Card],
                          declarer: Seat, trump: Optional[Suit],
                          legal: List[Card]) -> Optional[Card]:
    """Defensive card via MC rollout with a REALISTIC no-peek partner (vs
    alpha-mu defence's perfect-DD partner). See backend.defender_search."""
    from . import defender_search
    return defender_search.best_defense(
        b, seat, trick, declarer, trump, legal, _get_dds(),
        samples=_AMU_WORLDS, time_budget=_AMU_BUDGET)


def _lead_candidates(legal: List[Card]) -> List[Card]:
    """Prune lead candidates to the distinct ones worth searching: the highest
    and lowest card of each suit (leading the 5 vs the 4 of a suit rarely
    differs), cutting rollout cost."""
    by = _by_suit(legal)
    out = []
    for s in by:
        cs = by[s]                                     # high → low
        out.append(cs[0])
        if cs[-1] is not cs[0]:
            out.append(cs[-1])
    return out


def decide(board: BoardState, seat: Seat,
           current_trick_cards: Optional[List[Card]] = None,
           search: bool = True) -> Optional[Card]:
    """Pick `seat`'s card using only entitled information. Redacts first.
    `search=True` lets the DECLARER use a single-dummy lookahead at its leads;
    rollouts call back with search=False (greedy policy, no recursion)."""
    trick = list(current_trick_cards or [])
    b = redact(board, seat, trick)
    hand = b.hands[seat]
    if not hand.cards:
        return None
    lead_suit = trick[0].suit if trick else None
    legal = _legal(hand, lead_suit)
    if len(legal) == 1:
        return legal[0]

    trump = (board.contract.suit
             if board.contract and board.contract.suit != Suit.NOTRUMP
             else None)
    declarer = board.contract.declarer if board.contract else seat
    on_lead = not trick
    opening = on_lead and not board.tricks

    if opening:
        return _opening_lead(b, seat)
    # Alpha-mu search: DDS on belief-sampled hidden layouts + a consistent line.
    # Strong (DDS evaluates vs best play) without peeking or PIMC's omniscient
    # tells. Declarer side always; defenders when BIQ_AMU_DEFENSE (the partner is
    # hidden too, so defence samples declarer + partner).
    if search and board.contract is not None:
        defending = seat.is_ns() != declarer.is_ns()
        # PURE-SIGNAL situation: defending, following the led suit, and unable to
        # win the trick. The choice among our spots is trick-neutral here, so we
        # play the STANDARD signal among ALL legal cards — exactly what
        # signal_read inverts — making biq a perfectly READABLE signaller (so a
        # partner reading these signals never filters out biq's true hand).
        # Bypass alpha-mu for this card only.
        if (defending and lead_suit is not None and legal
                and legal[0].suit == lead_suit):
            wi = _winning_index(trick, trump)
            if not any(_beats(c, trick[wi], lead_suit, trump) for c in legal):
                from . import signals as _sig
                return _sig.choose_signal_card(legal, b, seat, trick,
                                               declarer, trump)
        amc = None
        if defending and _DEF_ROLLOUT:
            amc = _defense_rollout_card(b, seat, trick, declarer, trump, legal)
        elif not defending or _AMU_DEFENSE:
            amc = _alphamu_card(b, seat, trick, declarer, trump)
        if amc is not None and any(c.suit == amc.suit and c.rank == amc.rank
                                   for c in legal):
            return amc
    if on_lead:
        return _lead(b, seat, legal, trump, declarer)
    if any(c.suit == lead_suit for c in legal):
        return _follow(b, seat, legal, trick, trump, declarer)
    return _discard(b, seat, legal, trick, declarer)

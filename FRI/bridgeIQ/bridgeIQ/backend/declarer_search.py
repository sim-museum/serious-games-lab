"""No-peek DECLARER search — single-dummy Monte-Carlo with policy rollout.

When declaring, biq sees both its hands; only the defenders' cards are hidden.
This samples plausible defender layouts (a BELIEF from the play so far — voids
shown, remaining counts, vacant places — never the actual cards), and for each
candidate declarer lead plays the deal to the end with the no-peek POLICY for
all four seats, averaging declarer tricks. It returns the lead with the best
average. No DDS and no peeking: the choice is the expected-best over beliefs and
every rollout decision uses only that seat's entitled view (the rollout calls
nopeek.decide with search=False, so each seat still reasons single-dummy).

This is the non-peeking analogue of PIMC: PIMC double-dummy-solves each sample
(strategy fusion); this rolls out the actual policy, which is a real one-ply
policy improvement over greedy play and cannot fuse strategies.
"""
from __future__ import annotations
import random
from typing import List, Optional

from .models import Seat, Suit, Rank, Card, Hand, BoardState, Trick

_ALL = (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)


def _c52(c: Card) -> int:
    return c.suit.value * 13 + c.rank.value


def _winner(cards: List[Card], leader: Seat, trump: Optional[Suit]) -> Seat:
    wi, wc = 0, cards[0]
    lead = cards[0].suit
    for i, c in enumerate(cards[1:], 1):
        c_t = trump is not None and c.suit == trump
        w_t = trump is not None and wc.suit == trump
        if c_t and not w_t:
            wi, wc = i, c
        elif c_t and w_t and c.rank.value < wc.rank.value:
            wi, wc = i, c
        elif not c_t and not w_t and c.suit == lead \
                and c.rank.value < wc.rank.value:
            wi, wc = i, c
    return Seat((leader.value + wi) % 4)


def _sample_defenders(board: BoardState, seat: Seat, current_trick: List[Card],
                      declarer: Seat, k: int, known_seats=None):
    """k plausible assignments of the unseen cards to the HIDDEN seats, honouring
    remaining counts, shown-out voids, and vacant-places weighting.

    `known_seats` are the seats whose cards we legitimately see; the unseen cards
    are dealt among the rest. Default {declarer, dummy} = declaring (defenders
    hidden). For DEFENCE pass {biq_seat, dummy} so declarer + partner are the
    hidden seats sampled."""
    dummy = declarer.partner()
    decl_side = set(known_seats) if known_seats is not None else {declarer, dummy}
    defenders = [s for s in _ALL if s not in decl_side]
    known = {_c52(c) for s in decl_side for c in board.hands.get(s, Hand()).cards}
    played = {_c52(c) for t in board.tricks for c in t.cards}
    played |= {_c52(c) for c in current_trick}
    unseen = [x for x in range(52) if x not in known and x not in played]

    cur_leader = Seat((seat.value - len(current_trick)) % 4) if current_trick \
        else seat

    def played_by(d):
        n = sum(1 for t in board.tricks
                for i in range(len(t.cards))
                if Seat((t.leader.value + i) % 4) == d)
        n += sum(1 for i in range(len(current_trick))
                 if Seat((cur_leader.value + i) % 4) == d)
        return n
    counts = {d: 13 - played_by(d) for d in defenders}

    shown = {d: set() for d in defenders}
    for t in board.tricks:
        if t.cards:
            led = t.cards[0].suit
            for i, c in enumerate(t.cards):
                p = Seat((t.leader.value + i) % 4)
                if p in defenders and c.suit != led:
                    shown[p].add(led)
    if current_trick:
        led = current_trick[0].suit
        for i, c in enumerate(current_trick):
            p = Seat((cur_leader.value + i) % 4)
            if p in defenders and c.suit != led:
                shown[p].add(led)

    out = []
    for _ in range(k):
        rem = dict(counts)
        assign = {d: [] for d in defenders}
        pool = list(unseen)
        random.shuffle(pool)
        ok = True
        for c52 in pool:
            su = Suit(c52 // 13)
            elig = [d for d in defenders
                    if rem[d] > 0 and su not in shown[d]]
            if not elig:
                ok = False
                break
            ch = random.choices(elig, weights=[rem[d] for d in elig])[0]
            assign[ch].append(c52)
            rem[ch] -= 1
        if ok:
            out.append(assign)
    return out, defenders


def _rollout(board: BoardState, seat: Seat, current_trick: List[Card],
             declarer: Seat, trump: Optional[Suit], assign, defenders,
             candidate: Card) -> int:
    """Play the deal to the end with the no-peek policy after `seat` plays
    `candidate`; return the declarer side's total trick count."""
    from . import nopeek
    decl_ns = declarer.is_ns()
    hands = {}
    for s in _ALL:
        if s in defenders:
            hands[s] = Hand(cards=[Card.from_code52(c) for c in assign[s]])
        else:
            hands[s] = Hand(cards=list(board.hands[s].cards))
    rb = BoardState(board_number=1, dealer=declarer,
                    vulnerability=board.vulnerability, hands=hands,
                    auction=list(board.auction), contract=board.contract,
                    tricks=[Trick(cards=list(t.cards), leader=t.leader,
                                  winner=t.winner) for t in board.tricks])
    dt = sum(1 for t in rb.tricks if t.winner and t.winner.is_ns() == decl_ns)

    leader = Seat((seat.value - len(current_trick)) % 4) if current_trick else seat
    trick = list(current_trick) + [candidate]
    rb.hands[seat].cards = [c for c in rb.hands[seat].cards
                            if not (c.suit == candidate.suit
                                    and c.rank == candidate.rank)]
    cur = seat.next()
    while True:
        rb.current_trick = Trick(cards=list(trick), leader=leader)
        while len(trick) < 4:
            card = nopeek.decide(rb, cur, list(trick), search=False)
            rb.hands[cur].cards = [c for c in rb.hands[cur].cards
                                   if not (c.suit == card.suit
                                           and c.rank == card.rank)]
            trick.append(card)
            cur = cur.next()
        w = _winner(trick, leader, trump)
        rb.tricks.append(Trick(cards=list(trick), leader=leader, winner=w))
        rb.current_trick = None
        dt += (w.is_ns() == decl_ns)
        if not any(rb.hands[s].cards for s in _ALL):
            break
        leader = w
        cur = w
        trick = []
    return dt


def best_lead(board: BoardState, seat: Seat, declarer: Seat,
              trump: Optional[Suit], candidates: List[Card],
              samples: int = 16) -> Optional[Card]:
    """Pick the declarer-side card that yields the most declarer tricks averaged
    over sampled defender layouts (policy rollout). `board` must be REDACTED
    (defender hands empty) so we never peek. Returns None if sampling fails."""
    smp, defenders = _sample_defenders(board, seat, [], declarer, samples)
    if not smp:
        return None
    # de-dup candidates that are equivalent (same suit, touching ranks collapse
    # to the lowest) to cut rollout cost — keep distinct suit/rank choices.
    best_c, best_v = None, None
    for cand in candidates:
        total = 0
        for a in smp:
            total += _rollout(board, seat, [], declarer, trump, a, defenders,
                              cand)
        avg = total / len(smp)
        if best_v is None or avg > best_v:
            best_v, best_c = avg, cand
    return best_c

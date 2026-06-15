#!/usr/bin/env python3
"""Probe/correctness harness for backend.alphamu (single-dummy declarer search).

Builds small, hand-verifiable endings, enumerates ALL consistent defender
layouts as the world set, and checks AlphaMu.choose returns a legal, sensible
card. The real bridge-insight validation (count-gathering, two-way guesses) runs
later via cardplay_eval; this just proves the search machinery is correct.

  python3 tools/alphamu_probe.py
"""
from __future__ import annotations
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import Seat, Suit, Rank, Card             # noqa
from backend.alphamu import AlphaMu, _pbn, _legal             # noqa

_R = "AKQJT98765432"
_S = "SHDC"


def c(txt):
    """'SA' -> c52."""
    s = _S.index(txt[0]); r = _R.index(txt[1])
    return s * 13 + r


def cstr(c52):
    return f"{_S[c52 // 13]}{_R[c52 % 13]}"


def worlds_from(known, defender_pool, e_count, w_count):
    """All ways to split defender_pool into East/West of the given sizes.
    known = {Seat: [c52,...]} for the MAX side (N/S). Returns list of full
    deals dict[Seat]->frozenset."""
    out = []
    for e_cards in itertools.combinations(sorted(defender_pool), e_count):
        w_cards = [x for x in defender_pool if x not in e_cards]
        if len(w_cards) != w_count:
            continue
        d = {s: frozenset(known[s]) for s in known}
        d[Seat.EAST] = frozenset(e_cards)
        d[Seat.WEST] = frozenset(w_cards)
        out.append(d)
    return out


def case(name, trump, declarer, known, defender_pool, on_lead, trick=None,
         expect_in=None, depth=2):
    e_n = w_n = len(defender_pool) // 2
    worlds = worlds_from(known, defender_pool, e_n, w_n)
    amu = AlphaMu(trump, declarer, depth=depth)
    trick_cards = [Card.from_code52(x) for x in (trick or [])]
    chosen = amu.choose(None, on_lead, trick_cards, worlds)
    my = sorted(worlds[0][on_lead])
    legal = _legal(worlds[0][on_lead],
                   trick_cards[0].suit.value if trick_cards else None)
    ok = chosen is not None and chosen.code52() in legal
    tag = "ok " if ok else "FAIL"
    extra = ""
    if expect_in is not None:
        good = chosen is not None and cstr(chosen.code52()) in expect_in
        tag = "ok " if (ok and good) else "FAIL"
        extra = f" expect∈{expect_in}"
    print(f"  [{tag}] {name}: {len(worlds)} worlds, "
          f"{on_lead.name} holds {[cstr(x) for x in my]} -> "
          f"chose {cstr(chosen.code52()) if chosen else None}{extra}")
    return ok


def main():
    n = 0; bad = 0
    print("alpha-mu machinery probe")

    # Case 1 — 2 cards each, NS have the only two winners (SA, HA). Any legal
    # lead makes exactly 2 tricks; just assert a legal card comes back.
    known = {Seat.SOUTH: [c("SA"), c("H2")], Seat.NORTH: [c("S2"), c("HA")]}
    pool = [c("SK"), c("HK"), c("DA"), c("DK")]
    n += 1; bad += not case("2-card cash", None, Seat.SOUTH, known, pool,
                            Seat.SOUTH)

    # Case 2 — sure-winner test: South on lead with SA (boss) + a loser; should
    # be happy to cash SA. 3 cards each.
    known = {Seat.SOUTH: [c("SA"), c("SQ"), c("H2")],
             Seat.NORTH: [c("S2"), c("H3"), c("D2")]}
    pool = [c("SK"), c("HA"), c("HK"), c("DA"), c("DK"), c("CA")]
    n += 1; bad += not case("sure-winner SA", None, Seat.SOUTH, known, pool,
                            Seat.SOUTH)

    # Case 3 — declarer in a suit contract (spades trump), simple draw-trumps
    # shape; assert legal output mid-search with a trump.
    known = {Seat.SOUTH: [c("SA"), c("SK"), c("H2")],
             Seat.NORTH: [c("SQ"), c("S2"), c("HA")]}
    pool = [c("SJ"), c("ST"), c("HK"), c("HQ"), c("DA"), c("DK")]
    n += 1; bad += not case("trump draw", Suit.SPADES, Seat.SOUTH, known, pool,
                            Seat.SOUTH)

    # Case 4 — dummy (North) on lead, biq controls it; finesse position.
    known = {Seat.SOUTH: [c("HA"), c("HQ"), c("S2")],
             Seat.NORTH: [c("H3"), c("H4"), c("D2")]}
    pool = [c("HK"), c("SA"), c("SK"), c("DA"), c("DK"), c("CA")]
    n += 1; bad += not case("dummy-lead finesse", None, Seat.NORTH, known, pool,
                            Seat.NORTH)

    print(f"  {n - bad}/{n} cases returned a legal card")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

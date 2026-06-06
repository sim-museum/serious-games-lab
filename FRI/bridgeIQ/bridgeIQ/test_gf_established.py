#!/usr/bin/env python3
"""Characterization + spec test for AuctionContext.gf_established.

This is T1 of the game-forcing-state rework (see memory plan_biq_gf_established).
It pins what `derive_context().gf_established` returns TODAY for a curated set of
auctions, and documents — per row — what it SHOULD return. The gap between the
two is the rework's to-do list.

`gf_established` is PERSPECTIVE-RELATIVE ("MY side is game-forced"), so every
auction is evaluated from the OPENER's seat (always on the forcing side).

How to use during the rework:
  * `current`  = what the code returns now. The test HARD-ASSERTS this, so it is
    a regression guard: any change to gf_established that touches these auctions
    trips the test and must be reviewed.
  * `desired`  = the correct game-forcing answer. Rows where current != desired
    are printed as TODO. As each is fixed in auction_context.derive_context,
    flip its `current` to match `desired`.

Run: python3 test_gf_established.py     (exit 0 = all current values hold)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.models import Bid, Seat, Suit, Vulnerability      # noqa: E402
from backend.native_bidder import parse_auction                # noqa: E402
from backend.auction_context import derive_context             # noqa: E402

_SEAT = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_SUIT = {"C": Suit.CLUBS, "D": Suit.DIAMONDS, "H": Suit.HEARTS,
         "S": Suit.SPADES, "N": Suit.NOTRUMP}


def _mk(tok):
    """'1H' / '2N!' (alerted) / 'P' / 'X' / 'XX' → Bid."""
    if tok in ("P", "X", "XX"):
        return Bid(is_pass=tok == "P", is_double=tok == "X",
                   is_redouble=tok == "XX")
    alert = tok.endswith("!")
    t = tok[:-1] if alert else tok
    return Bid(level=int(t[0]), suit=_SUIT[t[1]], alert=alert)


def gf_from_opener(dealer, auction):
    """gf_established evaluated from the opener's seat (the forcing side)."""
    bids = [_mk(t) for t in auction.split()]
    dl = _SEAT[dealer]
    opener = derive_context(
        parse_auction(dl, dl, bids, vulnerability=Vulnerability.NONE)
    ).opener_seat
    if opener is None:
        return None
    st = parse_auction(Seat(int(opener)), dl, bids,
                       vulnerability=Vulnerability.NONE)
    return derive_context(st).gf_established


# (label, dealer, auction, current, desired, note)
# dealer N throughout; "!" marks an alerted (artificial) call.
CASES = [
    # ---- correct game-forces (current == desired == True) ----
    ("2/1 over 1-major (1H-2C)",        "N", "1H P 2C",          True,  True,
     "2/1 GF response"),
    ("Jacoby 2NT (1H-2NT!)",            "N", "1H P 2N!",         True,  True,
     "Jacoby 2NT = GF major raise"),
    ("4th-suit forcing (1C-1H-1S-2D)",  "N", "1C P 1H P 1S P 2D", True, True,
     "4SF to game"),
    ("strong 2C + positive (2C!-2H)",   "N", "2C! P 2H",         True,  True,
     "strong 2C, positive response"),
    ("strong 1C + positive (1C!-1H)",   "N", "1C! P 1H",         True,  True,
     "Precision 1C, positive response"),

    # ---- correct non-forces (current == desired == False) ----
    ("strong 2C + negative 2D",         "N", "2C! P 2D",         False, False,
     "negative response, not yet GF"),
    ("1NT-2D-2H TRANSFER",              "N", "1N P 2D! P 2H",    False, False,
     "GUARD: artificial transfer-accept must NOT be GF (the reverted-net bug)"),
    ("1NT-2C-2D Stayman",               "N", "1N P 2C! P 2D",    False, False,
     "GUARD: artificial Stayman must NOT be GF"),
    ("invitational (1D-1S-2D-2NT)",     "N", "1D P 1S P 2D P 2N", False, False,
     "2NT here is invitational, not GF"),
    ("simple rebid (1H-1S-2H)",         "N", "1H P 1S P 2H",     False, False,
     "opener's simple rebid, no force yet"),
    ("weak-two raise (2S-3S)",          "N", "2S P 3S",          False, False,
     "raise of a preempt is invitational"),
    ("1NT opening only",                "N", "1N",               False, False,
     "no force yet"),

    # ---- raises do NOT establish GF (fixed 2026-06-05; was the line-283 bug) ----
    ("simple raise (1S-2S)",            "N", "1S P 2S",          False, False,
     "a single major raise is 6-9, NOT game-forcing"),
    ("jump/limit raise (1S-3S)",        "N", "1S P 3S",          False, False,
     "a limit raise is invitational, NOT game-forcing"),
    ("competitive raise (1S-(2H)-3S)",  "N", "1S 2H 3S",         False, False,
     "a competitive raise over interference is NOT game-forcing"),

    # ---- GAPS: the underbidding target (current False, desired True) ----
    ("3rd-suit-3-level (1D-1S-2D-3C)",  "N", "1D P 1S P 2D P 3C", False, True,
     "GAP A1: responder's 3rd natural suit at the 3-level = GF (deal 3928-79)"),
    ("3rd-suit-3-level (1H-1S-2H-3C)",  "N", "1H P 1S P 2H P 3C", False, True,
     "GAP A1: same pattern over a major opening"),
]


def main():
    fails = []
    todos = []
    for label, dealer, auc, current, desired, note in CASES:
        got = gf_from_opener(dealer, auc)
        if got != current:
            fails.append((label, auc, current, got, note))
        if current != desired:
            todos.append((label, auc, current, desired, note))

    print(f"gf_established characterization — {len(CASES)} auctions\n")
    if fails:
        print("✗ CURRENT-VALUE REGRESSIONS (code changed under the test):")
        for label, auc, exp, got, note in fails:
            print(f"   {label:34} [{auc}]  expected {exp}, got {got}")
            print(f"      {note}")
        print()
    else:
        print(f"✓ all {len(CASES)} current values hold (no regressions)\n")

    print(f"REWORK TO-DO — {len(todos)} rows where current != desired:")
    for label, auc, cur, des, note in todos:
        kind = "GAP " if (not cur and des) else "BUG "
        print(f"   [{kind}] {label:30} now={cur} want={des}  — {note}")
    print("\n(As each is fixed in derive_context, flip its `current` to "
          "`desired`.)")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

"""Probe analyzer — reads the Q-Plus BDL output of a probes.bde
session, finds each probe's documented test position, and reports
what Q-Plus chose vs what bridgeIQ would choose.

Usage:
    python3 probe_analyzer.py --bdl /path/to/log-NNN.bdl

The analyzer assumes the BDL contains 8 deals labelled
PROBE-01-… through PROBE-08-… (the labels the BDE file writes
into each deal block). For each probe we know the position
under test from the README and look up Q-Plus's card there.

This isn't yet wired into anything bigger — it just prints a
short report so a human can decide which conventions to encode
as new overrides in `_position_override_card`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.bdl_reader import load_bdl_file
from backend.models import Card, Seat, Suit


# Test points: for each probe, the (trick_index, player_seat) of
# the card we care about, and a short description.
PROBE_TESTS = {
    "PROBE-01-holdup": (
        (0, "S"),
        "Hold-up: ♠ by S at trick 1. Expected: ♠4 (duck) or ♠A/K (grab).",
    ),
    "PROBE-02-avoidance": (
        # The avoidance decision is mid-hand — by the time declarer
        # leads clubs we are at trick 4-5. Look at the FIRST club
        # declarer leads (from which hand) and which direction.
        (3, "S"),
        "Avoidance: declarer's first club lead. Expected: from dummy "
        "toward S (keeps W off lead) or from S toward dummy (other way).",
    ),
    "PROBE-03-third-hand-high": (
        (0, "E"),
        "3rd-hand-high: E's play under partner's ♠ lead at trick 1. "
        "Expected: ♠Q (3rd hand high) or ♠7 (middle / dummy-aware).",
    ),
    "PROBE-04-cover-honor": (
        # Declarer must lead the ♠T from dummy first; E's cover
        # decision is the trick after.
        (2, "E"),
        "Cover-honor: E's play when declarer leads ♠T from dummy. "
        "Expected: ♠Q (cover) or ♠5/9 (duck).",
    ),
    "PROBE-05-suit-preference": (
        # First forced discard by W on the long heart run — trick 4
        # is usually when W runs out of hearts.
        (3, "W"),
        "Suit-preference discard: W's first forced discard. Expected: "
        "high spade (Lavinthal: 'want spades') or low diamond / "
        "attitude inversion.",
    ),
    "PROBE-06-attitude-lead": (
        (0, "S"),
        "Attitude signal: S's play under partner's ♥A lead at trick 1. "
        "Expected: ♥9 (encouraging) or ♥6 (discouraging).",
    ),
    "PROBE-07-endplay-throw-in": (
        # The end-play happens around trick 10-11. Look at declarer's
        # cards around then.
        (9, "S"),
        "End-play setup: declarer's choice around trick 10. Expected: "
        "finesse spades early (♠J from dummy) or strip-and-end-play "
        "(exit ♠5 to W).",
    ),
    "PROBE-08-discard-choice": (
        # W's first discard on the heart run, similar to PROBE-05.
        (3, "W"),
        "Discard suit choice: W's first discard. Triangulates with "
        "PROBE-05 — does W discard the same suit twice across probes?",
    ),
}


def _seat_idx(name: str) -> int:
    return {"N": 0, "E": 1, "S": 2, "W": 3}[name]


def _card_str(c) -> str:
    if c is None:
        return "?"
    suits = "SHDC"
    ranks = "AKQJT98765432"
    si = c.suit.value if hasattr(c.suit, "value") else c.suit
    ri = c.rank.value if hasattr(c.rank, "value") else c.rank
    return f"{suits[si]}{ranks[ri]}"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--bdl", required=True,
                   help="Path to the BDL log Q-Plus wrote while "
                        "playing probes.bde")
    args = p.parse_args(argv)

    deals = load_bdl_file(args.bdl)
    if not deals:
        print(f"No deals in {args.bdl}", file=sys.stderr)
        return 1

    # Q-Plus labels deals in the log header; the bdl_reader's
    # BDLDeal exposes `label` when present.
    labels = []
    with open(args.bdl, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            if line.startswith("Deal "):
                _, _, lbl = line.partition(":")
                labels.append(lbl.strip())

    print(f"# Probe analysis from {args.bdl}\n")
    for idx, deal in enumerate(deals):
        if idx >= len(labels):
            break
        label = labels[idx]
        if label not in PROBE_TESTS:
            continue
        (trick_idx, seat_name), description = PROBE_TESTS[label]
        print(f"## {label}")
        print(f"  Test: {description}")

        # Find the card played by seat_name at trick trick_idx.
        # bdl_reader stores tricks as dicts: {"cards": [...], "leader": Seat}.
        if trick_idx >= len(deal.tricks):
            print(f"  → only {len(deal.tricks)} tricks recorded; "
                  f"test position not reached.\n")
            continue
        trick = deal.tricks[trick_idx]
        trick_cards = trick.get("cards", []) if isinstance(trick, dict) else trick.cards
        trick_leader = trick.get("leader") if isinstance(trick, dict) else trick.leader
        if trick_leader is None:
            # Fall back to opening-lead seat for trick 0.
            trick_leader = deal.contract.declarer.next() if deal.contract else Seat.NORTH
        leader_idx = (trick_leader.value if hasattr(trick_leader, "value")
                      else int(trick_leader))
        seat_target = _seat_idx(seat_name)
        position = (seat_target - leader_idx) % 4
        if position >= len(trick_cards):
            print(f"  → seat {seat_name} didn't play yet in trick "
                  f"{trick_idx + 1}.\n")
            continue
        played = trick_cards[position]
        # Show the full trick for context.
        played_str = lambda c: c if isinstance(c, str) else _card_str(c)
        all_cards = [played_str(c) for c in trick_cards]
        leader_name = "NESW"[leader_idx]
        print(f"  Trick {trick_idx + 1} (led by {leader_name}): "
              f"{' '.join(all_cards)}")
        print(f"  → {seat_name} played {played_str(played)} "
              f"(position {position + 1} of 4)\n")

    print("# End of probe analysis.")
    print("# Compare each Q-Plus pick against the README's "
          "'expected' values to decide which conventions to encode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

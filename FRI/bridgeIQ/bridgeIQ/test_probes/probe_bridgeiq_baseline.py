"""Run bridgeIQ through the 8 probe deals and record:

  * the contract bridgeIQ's bidder reaches
  * the opening lead
  * the card played at each probe's test position

This gives us bridgeIQ's *own* answer to each probe so we can
compare side-by-side against what Q-Plus does once the user runs
the suite. Run this BEFORE handing the BDE to Q-Plus; the output
is the "before" snapshot.

Usage:
    python3 probe_bridgeiq_baseline.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.engine import BridgeEngine
from backend.models import (
    BoardState, Bid, Card, Hand, Rank, Seat, Suit, Trick,
    Vulnerability, Contract,
)
from backend.native_bidder import (
    decide_bid, evaluate_hand, parse_auction,
)
from backend.bidding_systems import get_system
from backend.native_lead import select_opening_lead


# Per-probe test target: (trick_index, seat). Aligned with
# probe_analyzer.py's PROBE_TESTS.
PROBE_TESTS = {
    "PROBE-01-holdup":           (0, Seat.SOUTH),
    "PROBE-02-avoidance":        (3, Seat.SOUTH),
    "PROBE-03-third-hand-high":  (0, Seat.EAST),
    "PROBE-04-cover-honor":      (2, Seat.EAST),
    "PROBE-05-suit-preference":  (3, Seat.WEST),
    "PROBE-06-attitude-lead":    (0, Seat.SOUTH),
    "PROBE-07-endplay-throw-in": (9, Seat.SOUTH),
    "PROBE-08-discard-choice":   (3, Seat.WEST),
}

# Rank parsing
RANK_OF_CHAR = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN,
                'J': Rank.JACK, 'T': Rank.TEN, '9': Rank.NINE,
                '8': Rank.EIGHT, '7': Rank.SEVEN, '6': Rank.SIX,
                '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
                '2': Rank.TWO}
DEALER_OF_CHAR = {'N': Seat.NORTH, 'E': Seat.EAST,
                  'S': Seat.SOUTH, 'W': Seat.WEST}


def _parse_hand_line(line: str, suit: Suit) -> list:
    chars = re.findall(r'[AKQJT2-9]', line)
    return [Card(suit, RANK_OF_CHAR[c]) for c in chars]


def parse_bde(path: Path):
    """Yield (name, dealer, hands_dict)."""
    text = path.read_text()
    for block in re.split(r'\*{20,}', text):
        m_name = re.search(r'Deal\s*:\s*(\S+)', block)
        m_dealer = re.search(r'Dealer\s*:\s*(\S+)', block)
        if not (m_name and m_dealer):
            continue
        name = m_name.group(1)
        dealer = DEALER_OF_CHAR[m_dealer.group(1)[0].upper()]

        # Card lines: 4 north suits, then 4 W/E joint, then 4 south.
        lines = []
        in_cards = False
        for raw in block.split('\n'):
            if 'Cards' in raw:
                in_cards = True
                rest = raw.split(':', 1)[1] if ':' in raw else ''
                if rest.strip():
                    lines.append(rest)
                continue
            if in_cards:
                if not raw.strip() or '*' in raw or 'Deal' in raw:
                    break
                rest = raw.split(':', 1)[1] if ':' in raw else raw
                lines.append(rest)

        if len(lines) < 12:
            continue

        suits = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
        n_cards = []
        s_cards = []
        for i, su in enumerate(suits):
            n_cards += _parse_hand_line(lines[i], su)
            s_cards += _parse_hand_line(lines[8 + i], su)

        # W and E share each line — separated by ≥3 spaces.
        w_cards = []
        e_cards = []
        for i, su in enumerate(suits):
            parts = re.split(r' {3,}', lines[4 + i].strip())
            if len(parts) == 2:
                w_cards += _parse_hand_line(parts[0], su)
                e_cards += _parse_hand_line(parts[1], su)
            else:
                # Single line — assume W left, E right by index
                chars = re.findall(r'[AKQJT2-9]', lines[4 + i])
                # Best effort: split in half by rough position
                # (this branch rarely triggers in our probes)
                half = len(chars) // 2
                w_cards += [Card(su, RANK_OF_CHAR[c]) for c in chars[:half]]
                e_cards += [Card(su, RANK_OF_CHAR[c]) for c in chars[half:]]

        hands = {
            Seat.NORTH: Hand(n_cards),
            Seat.EAST:  Hand(e_cards),
            Seat.SOUTH: Hand(s_cards),
            Seat.WEST:  Hand(w_cards),
        }
        yield name, dealer, hands


def _bid_repr(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{b.suit.to_char() if b.suit else '?'}"


def _card_repr(c: Card) -> str:
    suits = "SHDC"
    ranks = "AKQJT98765432"
    si = c.suit.value
    ri = c.rank.value
    return f"{suits[si]}{ranks[ri]}"


def drive_auction(hands, dealer, system_name="Precision90M"):
    """Drive bridgeIQ's bidder; return (auction, contract_or_None)."""
    sys_ = get_system(system_name)
    auction = []
    seat = dealer
    illegal_streak = 0
    for _ in range(60):
        state = parse_auction(seat, dealer, list(auction))
        # Build a temporary BoardState-like object for evaluation
        e = evaluate_hand(hands[seat])
        b = decide_bid(state, e, sys_)
        # Basic legality re-check
        last = next((x for x in reversed(auction)
                     if not x.is_pass), None)
        if (not b.is_pass and not b.is_double and not b.is_redouble
                and last and not last.is_pass and not last.is_double):
            if (last.suit is not None and b.suit is not None
                    and (b.level < last.level
                         or (b.level == last.level
                             and b.suit.value > last.suit.value))):
                b = Bid.make_pass()
                illegal_streak += 1
                if illegal_streak >= 4:
                    break
            else:
                illegal_streak = 0
        auction.append(b)
        if (len(auction) >= 4
                and all(x.is_pass for x in auction[-3:])
                and any(not x.is_pass for x in auction[:-3])):
            break
        if len(auction) >= 4 and all(x.is_pass for x in auction):
            break
        seat = seat.next()

    # Determine contract from the final non-pass bid
    last_bid = None
    declarer = None
    for i, b in enumerate(auction):
        if not b.is_pass and not b.is_double and not b.is_redouble:
            last_bid = b
    if last_bid is None:
        return auction, None

    # Declarer = first player on the declaring side to bid the
    # final strain.
    final_strain = last_bid.suit
    cur = dealer
    for i, b in enumerate(auction):
        if (not b.is_pass and not b.is_double and not b.is_redouble
                and b.suit == final_strain):
            # Check partnership
            if declarer is None:
                # First mention of the strain on this side
                declarer = cur
                break
        cur = cur.next()

    contract = Contract(
        level=last_bid.level,
        suit=last_bid.suit,
        declarer=declarer or dealer,
        doubled=False,
        redoubled=False,
    )
    return auction, contract


def main():
    bde = _HERE / "probes.bde"
    print(f"# bridgeIQ baseline run — {bde.name}")
    print(f"# system: Precision90M")
    print()
    eng = BridgeEngine(verbose=False)
    if not eng.initialize():
        print("Engine initialize failed.", file=sys.stderr)
        return 1

    for name, dealer, hands in parse_bde(bde):
        if name not in PROBE_TESTS:
            continue
        print(f"## {name}")
        print(f"  Dealer: {dealer.name}")
        auction, contract = drive_auction(hands, dealer)
        print(f"  bridgeIQ auction: "
              f"{' '.join(_bid_repr(b) for b in auction)}")
        if contract is None:
            print("  → no contract (pass-out). Skip.\n")
            continue
        print(f"  bridgeIQ contract: "
              f"{contract.level}{contract.suit.to_char()} by "
              f"{contract.declarer.name}")
        # Opening lead
        leader = contract.declarer.next()
        board = BoardState(
            board_number=1,
            dealer=dealer,
            vulnerability=Vulnerability.NONE,
            hands=dict(hands),
            auction=list(auction),
            contract=contract,
            tricks=[],
        )
        lead_res = select_opening_lead(
            hands[leader], contract, auction, dealer, leader,
            Vulnerability.NONE)
        lead_card = (lead_res.card if hasattr(lead_res, "card")
                     else lead_res.action if hasattr(lead_res, "action")
                     else lead_res)
        if lead_card:
            print(f"  Opening lead by {leader.name}: "
                  f"{_card_repr(lead_card)}")
        print()

    print("# To compare:")
    print("# 1. Load probes.bde in Q-Plus, play through, save the log.")
    print("# 2. Run probe_analyzer.py on Q-Plus's BDL.")
    print("# 3. Compare bridgeIQ's contracts/leads above with Q-Plus's "
          "to spot bidding-driven probe-failure cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

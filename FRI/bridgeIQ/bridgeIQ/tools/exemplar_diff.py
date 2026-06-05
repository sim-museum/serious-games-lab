"""Analyze Q-Plus runs of the system-exemplar BDEs.

For each system the user has run (one Q-Plus session per BDE
file), point this at the resulting BDL log. We:

  1. Load Q-Plus's deals + auctions from the BDL.
  2. Drive bridgeIQ's bidder through the same hands using the
     matching system.
  3. Tally perfect-auction matches per system.
  4. For boards where Q-Plus and bridgeIQ reach the SAME final
     contract, drive bridgeIQ's card-play engine through the
     deal and tally card-by-card match rate.
  5. Print per-system summary + aggregate.

Usage:
    python3 tools/exemplar_diff.py \\
        --sayc LOG/log-NNN.bdl \\
        --twoone LOG/log-MMM.bdl \\
        --acol LOG/log-PPP.bdl \\
        --french LOG/log-QQQ.bdl \\
        --precision LOG/log-RRR.bdl

Any system without a log given is skipped.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

PKG = Path("/home/h/sgl/FRI/bridgeIQ/bridgeIQ")
sys.path.insert(0, str(PKG))

from backend.bdl_reader import load_bdl_file
from backend.models import Bid, Card, Hand, Seat, Suit, Vulnerability, BoardState
from backend.engine import BridgeEngine
from backend.native_bidder import (
    decide_bid, evaluate_hand, parse_auction,
)
from backend.native_lead import select_opening_lead
from backend.bidding_systems import get_system
from tools.qplus_diff import _diff_auctions, _bid_repr, _drive_bridgeIQ


def _read_deal_labels(bdl_path: Path) -> List[str]:
    labels = []
    try:
        with open(bdl_path, "r", encoding="latin-1",
                  errors="replace") as f:
            for line in f:
                if line.startswith("Deal "):
                    _, _, v = line.partition(":")
                    labels.append(v.strip())
    except OSError:
        pass
    return labels


def _bid_str(b):
    if b is None:
        return "?"
    return _bid_repr(b)


def _card_str(c):
    if c is None:
        return "?"
    if isinstance(c, str):
        return c
    suits = "SHDC"
    ranks = "AKQJT98765432"
    return f"{suits[c.suit.value]}{ranks[c.rank.value]}"


def _final_contract(auction):
    """Return (level, suit, declarer_idx) or None for passed-out."""
    level = 0
    suit = None
    for b in auction:
        if (not b.is_pass and not b.is_double
                and not b.is_redouble and b.suit is not None):
            level = b.level
            suit = b.suit
    if level == 0:
        return None
    return (level, suit)


def diff_one_system(bdl_path: Path, system_name: str) -> dict:
    """Return per-deal results for one system."""
    try:
        deals = load_bdl_file(str(bdl_path))
    except Exception as ex:
        print(f"  [load error: {ex!r}]")
        return {"deals": 0, "auction_matches": 0,
                "contract_matches": 0, "card_matches": 0,
                "card_total": 0}
    labels = _read_deal_labels(bdl_path)
    n_deals = len(deals)
    auction_matches = 0
    contract_matches = 0
    card_matches = 0
    card_total = 0
    per_deal = []
    eng = None  # init lazily for card play

    for i, qdeal in enumerate(deals):
        # Build BoardState from Q-Plus's deal.
        if not qdeal.hands or len(qdeal.hands) < 4:
            continue
        board = qdeal.to_board_state()
        # Drive bridgeIQ's auction on the same hands
        our_auction = _drive_bridgeIQ(board, system_name)
        their_auction = list(qdeal.auction)
        diffs = _diff_auctions(their_auction, our_auction)
        if not diffs:
            auction_matches += 1
        our_contract = _final_contract(our_auction)
        their_contract = _final_contract(their_auction)
        contract_match = (our_contract == their_contract)
        if contract_match and our_contract is not None:
            contract_matches += 1
        per_deal.append({
            "label": labels[i] if i < len(labels) else f"deal-{i+1}",
            "their_auction": their_auction,
            "our_auction": our_auction,
            "diff_count": len(diffs),
            "their_contract": their_contract,
            "our_contract": our_contract,
            "contract_match": contract_match,
        })

    # Card-play diff for contract-matching deals
    contract_match_deals = [(i, deals[i], pd)
                            for i, pd in enumerate(per_deal)
                            if pd["contract_match"]
                            and pd["their_contract"] is not None]
    if contract_match_deals:
        eng = BridgeEngine(verbose=False)
        eng.initialize()
        for idx, qdeal, pd in contract_match_deals:
            try:
                cm, ct = _diff_card_play(qdeal, system_name, eng)
                card_matches += cm
                card_total += ct
                pd["card_matches"] = cm
                pd["card_total"] = ct
            except Exception as ex:
                pd["card_matches"] = 0
                pd["card_total"] = 0

    return {
        "deals": n_deals,
        "auction_matches": auction_matches,
        "contract_matches": contract_matches,
        "card_matches": card_matches,
        "card_total": card_total,
        "per_deal": per_deal,
    }


def _diff_card_play(qdeal, system_name, eng) -> Tuple[int, int]:
    """Replay Q-Plus's tricks card-by-card; at each step ask
    bridgeIQ what card it would play and tally matches. Returns
    (matches, total)."""
    # Need to reconstruct the hand state through the play.
    if not qdeal.tricks:
        return 0, 0
    if not qdeal.contract:
        return 0, 0
    board = qdeal.to_board_state()
    board.contract = qdeal.contract
    declarer = qdeal.contract.declarer
    leader = declarer.next()  # Opening leader

    matches = 0
    total = 0
    for trick_idx, trick in enumerate(qdeal.tricks):
        trick_cards_qp = trick.get("cards", []) if isinstance(trick, dict) else trick.cards
        trick_leader = trick.get("leader") if isinstance(trick, dict) else trick.leader
        if trick_leader is None:
            trick_leader = leader
        seat = trick_leader

        # Lazy reset of current_trick / accumulated state
        from backend.models import Trick as TrickModel
        cur_trick = TrickModel(leader=trick_leader)
        board.current_trick = cur_trick

        for pos, card in enumerate(trick_cards_qp):
            # Parse the card if it's a string ("SK", "H2", etc.)
            if isinstance(card, str):
                if len(card) < 2:
                    continue
                ch_s = card[0].upper()
                ch_r = card[1].upper()
                from backend.models import Rank
                try:
                    qp_card = Card(Suit.from_char(ch_s),
                                   Rank.from_char(ch_r))
                except Exception:
                    continue
            else:
                qp_card = card

            # Ask bridgeIQ what it would play
            try:
                if trick_idx == 0 and pos == 0:
                    resp = eng.get_opening_lead(board)
                else:
                    resp = eng.get_card_play(board, seat,
                                              list(cur_trick.cards))
                our_card = resp.action if resp else None
            except Exception:
                our_card = None
            total += 1
            if our_card is not None and \
                    our_card.suit == qp_card.suit and \
                    our_card.rank == qp_card.rank:
                matches += 1

            # Advance state using Q-Plus's actual card.
            if seat in board.hands and \
                    qp_card in board.hands[seat].cards:
                board.hands[seat].remove_card(qp_card)
            trump = (qdeal.contract.suit
                     if qdeal.contract.suit
                     and qdeal.contract.suit != Suit.NOTRUMP
                     else None)
            cur_trick.add_card(qp_card, trump)
            seat = seat.next()

        # Trick complete — record it
        if cur_trick.is_complete():
            board.tricks.append(cur_trick)
            winner = cur_trick.winner
            if winner is not None:
                seat = winner
        board.current_trick = None
        leader = seat

    return matches, total


SYSTEM_TAG = {
    "sayc":      ("SAYC", "A-SAYC-I"),
    "twoone":    ("TwoOverOne", "A-2-1-A"),
    "acol":      ("StandardAcol", "B-ACL-S"),
    "french":    ("StandardFrench", "F-FRA-M"),
    "precision": ("Precision90M", "P-P90M-A"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sayc", help="BDL log for SAYC session")
    ap.add_argument("--twoone", help="BDL log for TwoOverOne")
    ap.add_argument("--acol", help="BDL log for StandardAcol")
    ap.add_argument("--french", help="BDL log for StandardFrench")
    ap.add_argument("--precision", help="BDL log for Precision90M")
    args = ap.parse_args()

    log_dir_default = Path(
        "/home/h/sgl/FRI/WP/drive_c/games/qbridge17/DATA/LOG")
    print("# System-exemplar diff (20 deals each system)\n")
    aggregate = {
        "deals": 0, "auction_matches": 0,
        "contract_matches": 0,
        "card_matches": 0, "card_total": 0,
    }
    for key, (sys_name, tag) in SYSTEM_TAG.items():
        bdl = getattr(args, key)
        if not bdl:
            print(f"## {sys_name} ({tag}): no log provided — skip\n")
            continue
        p = Path(bdl)
        if not p.is_absolute():
            p = log_dir_default / p
        if not p.exists():
            print(f"## {sys_name} ({tag}): file not found "
                  f"({p}) — skip\n")
            continue
        print(f"## {sys_name} ({tag}) — {p.name}")
        r = diff_one_system(p, sys_name)
        n = r["deals"]
        if n == 0:
            print("  (no deals loaded)\n")
            continue
        am = r["auction_matches"]
        cm = r["contract_matches"]
        ckm = r["card_matches"]
        ckt = r["card_total"]
        print(f"  Deals:              {n}")
        print(f"  Auction matches:    {am}/{n}  "
              f"({am*100//max(1,n)}%)")
        print(f"  Contract matches:   {cm}/{n}  "
              f"({cm*100//max(1,n)}%)")
        if ckt > 0:
            print(f"  Card-play matches:  {ckm}/{ckt}  "
                  f"({ckm*100//max(1,ckt)}%) "
                  f"(across contract-matching deals)")
        else:
            print(f"  Card-play matches:  n/a "
                  f"(no contract-matching deals)")
        print()
        for k in aggregate:
            aggregate[k] += r[k]

    print("## Aggregate")
    n = aggregate["deals"]
    if n == 0:
        print("  no data")
        return 0
    am = aggregate["auction_matches"]
    cm = aggregate["contract_matches"]
    ckm = aggregate["card_matches"]
    ckt = aggregate["card_total"]
    print(f"  Total deals:        {n}")
    print(f"  Auction matches:    {am}/{n}  "
          f"({am*100//max(1,n)}%)")
    print(f"  Contract matches:   {cm}/{n}  "
          f"({cm*100//max(1,n)}%)")
    if ckt > 0:
        print(f"  Card-play matches:  {ckm}/{ckt}  "
              f"({ckm*100//max(1,ckt)}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

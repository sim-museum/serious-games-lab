"""Q-Plus card-play diff: compare bridgeIQ's card choices to Q-Plus's.

Pre-requisite: a BDL file with the same deals bridgeIQ generates
(same seed) — typically the output of `tools/qplus_diff.py`. The
auctions must already match (bidding diff = 0); this script
takes that as a given and focuses on card play.

For each deal:

  1. Build the same BoardState bridgeIQ's bidder used.
  2. Set the contract from Q-Plus's BDL.
  3. For every card Q-Plus played, ask bridgeIQ what it would
     play in that same position and tally matches / divergences.
     We always advance the position by Q-Plus's actual card
     (not bridgeIQ's choice) so the comparison stays in sync.

bridgeIQ's card engine: opening lead goes through BEN's NN
(`get_opening_lead`); follow-on cards go through Monte Carlo +
DDS (`get_mc_card_play`), which is the default `use_monte_carlo_play`
preference in `B-PREFER.CFG`. Both are non-deterministic — repeat
runs will produce different choices on close calls.

Usage:
    python3 tools/qplus_card_diff.py --bdl LOG/log-028.bdl
    # or with a specific subset:
    python3 tools/qplus_card_diff.py --bdl LOG/log-028.bdl --board 1
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.bdl_reader import BDLDeal, load_bdl_file
from backend.engine import BridgeEngine
from backend.models import (
    BoardState, Bid, Card, Contract, Hand, Rank, Seat, Suit, Trick,
    Vulnerability,
)
from qplus_diff import _generate_deals, _read_deal_labels


# ---------------------------------------------------------------------------
# Q-Plus trick parsing (BDL → list of (seat, Card) tuples in play order)
# ---------------------------------------------------------------------------

_RANK_FROM_CHAR = {
    "A": Rank.ACE, "K": Rank.KING, "Q": Rank.QUEEN, "J": Rank.JACK,
    "T": Rank.TEN, "9": Rank.NINE, "8": Rank.EIGHT, "7": Rank.SEVEN,
    "6": Rank.SIX, "5": Rank.FIVE, "4": Rank.FOUR, "3": Rank.THREE,
    "2": Rank.TWO,
}
_SUIT_FROM_CHAR = {
    "S": Suit.SPADES, "H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS,
}


def _card_from_bdl(token: str) -> Card:
    """Parse 'H4' or 'sJ' or 'D9' into a Card. Q-Plus trick lines
    sometimes use lower-case suit letters; we coerce to upper."""
    if len(token) < 2:
        raise ValueError(f"bad card token {token!r}")
    suit_c = token[0].upper()
    rank_c = token[1].upper()
    return Card(suit=_SUIT_FROM_CHAR[suit_c], rank=_RANK_FROM_CHAR[rank_c])


def _qplus_play_sequence(deal: BDLDeal) -> List[Tuple[Seat, Card]]:
    """Flatten the BDL's trick list into a seat-by-seat play sequence."""
    out: List[Tuple[Seat, Card]] = []
    if not deal.tricks:
        return out
    for trick in deal.tricks:
        leader = trick.get("leader")
        cards = trick.get("cards") or []
        if leader is None:
            # Legacy BDLs without an explicit leader: use the
            # winner of the previous trick (or opening leader for
            # trick 0).
            if out:
                # Compute previous winner from `out[-4:]`.
                prev_trick = out[-4:]
                if len(prev_trick) == 4:
                    # Reconstruct via the BoardState semantics —
                    # we just give up here; caller should bail.
                    raise ValueError(
                        "legacy BDL without explicit leader is unsupported")
            else:
                # Trick 0 has no preceding winner — must have leader.
                raise ValueError("trick 0 missing leader")
        leader_seat = leader if isinstance(leader, Seat) else Seat(int(leader))
        # Normalize the "+" / "-" markers Q-Plus tacks onto winners
        # / fail-to-win in the BDL trick cards.
        for i, tok in enumerate(cards):
            tok = tok.replace("+", "").replace("-", "").strip()
            if not tok:
                continue
            seat = Seat((leader_seat.value + i) % 4)
            out.append((seat, _card_from_bdl(tok)))
    return out


# ---------------------------------------------------------------------------
# Contract / declarer parsing
# ---------------------------------------------------------------------------


def _contract_from_bdl(deal: BDLDeal) -> Optional[Contract]:
    return deal.contract


def _opening_leader(contract: Contract) -> Seat:
    return contract.declarer.next()


# ---------------------------------------------------------------------------
# bridgeIQ replay loop
# ---------------------------------------------------------------------------


def _card_repr(c: Card) -> str:
    return f"{c.suit.to_char()}{c.rank.to_char()}"


def _replay_deal(engine: BridgeEngine, board: BoardState,
                 qplus_play: List[Tuple[Seat, Card]],
                 verbose: bool = False) -> Dict:
    """Diff bridgeIQ's card play against Q-Plus's `qplus_play`
    sequence (each element is `(seat, card)` in play order).

    Returns a dict {n_total, n_match, divergences: [(idx, seat,
    qplus, ben, who, role), ...]}.
    """
    contract = board.contract
    assert contract is not None, "board must have contract set"
    declarer = contract.declarer
    dummy = declarer.partner()
    trump = contract.suit if contract.suit != Suit.NOTRUMP else None
    leader = _opening_leader(contract)

    # Work on a copy of the hands — we remove cards as we go so
    # bridgeIQ's engine sees a current legal hand.
    live_hands: Dict[Seat, List[Card]] = {
        s: list(board.hands[s].cards) for s in Seat}

    n_match = 0
    divergences = []
    current_trick = Trick(leader=leader)
    completed_tricks: List[Trick] = []
    trick_no = 0

    for idx, (qplus_seat, qplus_card) in enumerate(qplus_play):
        seat = qplus_seat
        # Sync our local model: set up board for the engine call.
        board.tricks = completed_tricks
        board.current_trick = current_trick if current_trick.cards else None
        for s in Seat:
            board.hands[s] = Hand(cards=list(live_hands[s]))

        is_opening_lead = (len(completed_tricks) == 0
                           and len(current_trick.cards) == 0)
        role = "lead" if is_opening_lead else "play"

        try:
            if is_opening_lead:
                resp = engine.get_opening_lead(board)
            else:
                resp = engine.get_mc_card_play(
                    board, seat,
                    current_trick_cards=list(current_trick.cards),
                    num_samples=20)
        except Exception as ex:
            resp = None
            if verbose:
                print(f"  card {idx + 1}: engine exception {ex!r}")

        ben_card = resp.action if resp is not None else None
        ben_who = (resp.who if resp is not None else "Error") or "Unknown"

        # Compare. Ben may return None or a card that's illegal in
        # rare edge cases — we treat None as a divergence and keep
        # going with Q-Plus's actual choice.
        matched = (ben_card is not None
                   and ben_card.suit == qplus_card.suit
                   and ben_card.rank == qplus_card.rank)
        if matched:
            n_match += 1
        else:
            divergences.append({
                "idx": idx,
                "trick": idx // 4 + 1,
                "seat": seat,
                "qplus": qplus_card,
                "ben": ben_card,
                "who": ben_who,
                "role": role,
            })

        if verbose:
            mark = "  " if matched else "× "
            ben_str = _card_repr(ben_card) if ben_card else "??"
            print(f"  {mark}#{idx + 1:2d} t{idx // 4 + 1:2d} {seat.to_char()}: "
                  f"Q+ {_card_repr(qplus_card):3s}  ben {ben_str:3s}"
                  f"  ({ben_who})")

        # Advance position by Q-Plus's actual card.
        live_hands[seat] = [
            c for c in live_hands[seat]
            if not (c.suit == qplus_card.suit and c.rank == qplus_card.rank)
        ]
        current_trick.add_card(qplus_card, trump=trump)
        if current_trick.is_complete():
            completed_tricks.append(current_trick)
            trick_no += 1
            next_leader = current_trick.winner or current_trick.leader
            current_trick = Trick(leader=next_leader)

    return {
        "n_total": len(qplus_play),
        "n_match": n_match,
        "divergences": divergences,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _build_board_for_deal(template: BoardState, qplus_deal: BDLDeal
                          ) -> BoardState:
    """Return a fresh BoardState matching the template (hands,
    dealer, vul, board#) with Q-Plus's contract attached."""
    contract = _contract_from_bdl(qplus_deal)
    if contract is None:
        return None
    return BoardState(
        board_number=template.board_number,
        dealer=template.dealer,
        vulnerability=template.vulnerability,
        hands={s: Hand(cards=list(template.hands[s].cards)) for s in Seat},
        auction=list(qplus_deal.auction or []),
        contract=contract,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bdl", required=True,
                   help="Q-Plus BDL file with the played deals")
    p.add_argument("--n", type=int, default=5,
                   help="number of bridgeIQ-generated deals to consider")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed (must match what produced the BDE)")
    p.add_argument("--board", type=int, default=None,
                   help="restrict to a single board (1-based)")
    p.add_argument("--occurrence", choices=("first", "last"),
                   default="first",
                   help="if the BDL has multiple sessions with the same "
                        "BB-diff-* labels (Q-Plus appends to the same "
                        "log-NNN.bdl on a second run), pick the FIRST or "
                        "LAST occurrence. Default 'first' matches the "
                        "original seed; use 'last' for a re-run.")
    p.add_argument("--leads-only", action="store_true",
                   help="just compare opening leads — skips the heavier "
                        "per-card MC replay")
    p.add_argument("--verbose", action="store_true",
                   help="print every card decision")
    p.add_argument("--report",
                   default=f"qplus_card_diff_"
                           f"{datetime.datetime.now():%Y%m%d_%H%M%S}.txt",
                   help="output report path")
    args = p.parse_args(argv)

    bdl_path = Path(args.bdl)
    if not bdl_path.is_file():
        print(f"[card-diff] BDL not found: {bdl_path}", file=sys.stderr)
        return 2

    qdeals = load_bdl_file(str(bdl_path))
    labels = _read_deal_labels(bdl_path)
    qplus_by_label = {}
    take_last = (args.occurrence == "last")
    for idx, deal in enumerate(qdeals):
        if idx < len(labels):
            label = labels[idx]
            if take_last or label not in qplus_by_label:
                qplus_by_label[label] = deal

    # Auto-grow --n if the BDL has more labels than the user passed
    # (the harness defaults to N=5; running against a 10-deal BDL
    # would silently truncate). The seed is still the user's
    # responsibility — there's no way to recover that from the BDL.
    if len(qplus_by_label) > args.n:
        print(f"[card-diff] BDL has {len(qplus_by_label)} deal "
              f"labels, --n was {args.n}; growing to "
              f"{len(qplus_by_label)}.")
        args.n = len(qplus_by_label)

    our_boards = _generate_deals(args.n, args.seed)

    print(f"[card-diff] Loaded {len(qdeals)} Q-Plus deal blocks "
          f"({len(qplus_by_label)} unique labels) from {bdl_path.name}.")
    print(f"[card-diff] Generated {len(our_boards)} matching deals "
          f"(seed={args.seed}).")

    # Sanity check: hands MUST match between Q-Plus and bridgeIQ.
    # Mismatch usually means the user passed the wrong --seed (the
    # most common footgun — the bidder harness writes deals from
    # seed X, the user re-runs the card-diff with the default 42).
    # Abort cleanly so we don't waste 5 minutes computing a
    # meaningless 1% match rate.
    mismatches = []
    for i, b in enumerate(our_boards, 1):
        label = f"BB-diff-{i:03d}"
        qd = qplus_by_label.get(label)
        if not qd:
            continue
        for seat in Seat:
            q_hand = set(c.code52() for c in qd.hands.get(seat, Hand()).cards)
            b_hand = set(c.code52() for c in b.hands.get(seat, Hand()).cards)
            if q_hand and q_hand != b_hand:
                mismatches.append((i, seat.to_char()))
    if mismatches:
        print("[card-diff] FATAL: hand mismatches at "
              f"{mismatches[:5]}{'...' if len(mismatches) > 5 else ''} "
              f"— --seed={args.seed} doesn't match the seed used to "
              f"write the BDE. The diff would be meaningless. Aborting.",
              file=sys.stderr)
        return 4

    print("[card-diff] Initializing engine (DDS only — no NN, "
          "no TensorFlow)…", flush=True)
    engine = BridgeEngine(verbose=False)
    if not engine.initialize():
        print("[card-diff] BEN engine failed to initialize; aborting.",
              file=sys.stderr)
        return 3
    print("[card-diff] Engine ready.")

    total_total = 0
    total_match = 0
    per_board = []
    for i, b in enumerate(our_boards, 1):
        if args.board is not None and i != args.board:
            continue
        label = f"BB-diff-{i:03d}"
        qd = qplus_by_label.get(label)
        if qd is None:
            print(f"[card-diff] board {i}: no Q-Plus deal — skipping")
            continue
        if not qd.tricks:
            print(f"[card-diff] board {i}: no trick data — skipping")
            continue
        contract = _contract_from_bdl(qd)
        if contract is None:
            print(f"[card-diff] board {i}: no contract in BDL — skipping")
            continue

        play_seq = _qplus_play_sequence(qd)
        if args.leads_only and play_seq:
            play_seq = play_seq[:1]

        board = _build_board_for_deal(b, qd)
        if board is None:
            print(f"[card-diff] board {i}: couldn't build board state — "
                  "skipping")
            continue

        print(f"[card-diff] board {i}: {contract.to_str()} by "
              f"{contract.declarer.to_char()} — diffing "
              f"{len(play_seq)} card(s)…", flush=True)
        result = _replay_deal(engine, board, play_seq, verbose=args.verbose)
        total_total += result["n_total"]
        total_match += result["n_match"]
        per_board.append((i, contract, result))
        print(f"[card-diff] board {i}: matched {result['n_match']}/"
              f"{result['n_total']} cards "
              f"({100 * result['n_match'] // max(1, result['n_total'])}%)")

    # Write the full report.
    with open(args.report, "w") as f:
        f.write(f"# Q-Plus card-play diff — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"# bdl={bdl_path.name}\n")
        f.write(f"# leads_only={args.leads_only}\n\n")
        if total_total:
            f.write(f"Overall match rate: {total_match}/{total_total} "
                    f"({100 * total_match // total_total}%)\n\n")
        for i, contract, result in per_board:
            f.write(f"## Board {i} — {contract.to_str()} by "
                    f"{contract.declarer.to_char()}\n")
            f.write(f"matched {result['n_match']}/{result['n_total']}\n")
            for d in result["divergences"]:
                ben_str = _card_repr(d["ben"]) if d["ben"] else "—"
                f.write(f"  #{d['idx'] + 1:2d} t{d['trick']:2d} "
                        f"{d['seat'].to_char()} ({d['role']}): "
                        f"Q+={_card_repr(d['qplus'])}  "
                        f"ben={ben_str}  ({d['who']})\n")
            f.write("\n")
    print(f"[card-diff] Report written: {args.report}")
    if total_total:
        print(f"[card-diff] Overall: {total_match}/{total_total} "
              f"({100 * total_match // total_total}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

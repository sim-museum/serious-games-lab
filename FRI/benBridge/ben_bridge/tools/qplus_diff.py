"""Diff harness: ben_bridge vs Q-Plus auctions.

Generates N random deals, writes them as a single multi-deal
`.BDE` file in Q-Plus's `DATA/OWN-DEALS/` directory, asks the
user to load + auto-play through them in Q-Plus, polls
`DATA/LOG/` for the resulting BDL files, parses each, and
produces a per-position divergence report.

Usage:

    cd ben_bridge
    python tools/qplus_diff.py --n 20

Workflow:

  1. Run this script. It writes `OWN-DEALS/BB_DIFF.BDE` with N
     deals and snapshots `LOG/` to know which files are new.
  2. In Q-Plus: `Own deals → Open → BB_DIFF.BDE` → click through
     the N deals (Q-Plus auto-plays each one).
  3. The script polls LOG/ until N new BDLs appear, then diffs
     each auction against ben_bridge's bidder.
  4. Report lands at `qplus_diff_<timestamp>.txt`.

Why Q-Plus instead of wbridge5:
  Q-Plus plays all four seats automatically (wbridge5 in Auto
  mode leaves one seat HUMAN), and Q-Plus's BDL output is a
  documented text file format we already parse. wbridge5's
  Bridge-Table-Manager dialect turned out to be too buggy /
  non-standard to drive reliably.
"""

from __future__ import annotations

import argparse
import datetime
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ben_backend.bidding_systems import get_system            # noqa: E402
from ben_backend.bdl_reader import load_bdl_file              # noqa: E402
from ben_backend.models import (                              # noqa: E402
    BoardState, Hand, Card, Seat, Suit, Rank, Vulnerability, Bid,
)
from ben_backend.native_bidder import (                       # noqa: E402
    decide_bid, evaluate_hand, parse_auction,
)
from ben_backend.qplus_driver import (                        # noqa: E402
    qplus_log_dir, qplus_own_deals_dir, snapshot_log_files,
    wait_for_new_bdls, write_multi_deal_bde,
)


_SUIT_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2,
              Suit.SPADES: 3, Suit.NOTRUMP: 4}


def _generate_deals(n: int, seed: int) -> List[BoardState]:
    """N uniformly-random deals with standard rotation."""
    rng = random.Random(seed)
    deck = [Card(s, r)
            for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
            for r in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                      Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                      Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE, Rank.TWO)]
    out = []
    for i in range(n):
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hands = {
            Seat.NORTH: Hand(cards=shuffled[0:13]),
            Seat.EAST:  Hand(cards=shuffled[13:26]),
            Seat.SOUTH: Hand(cards=shuffled[26:39]),
            Seat.WEST:  Hand(cards=shuffled[39:52]),
        }
        board_num = i + 1
        dealer, vuln = BoardState._board_dealer_vuln(board_num)
        out.append(BoardState(board_number=board_num, dealer=dealer,
                              vulnerability=vuln, hands=hands))
    return out


def _is_legal(b: Bid, auction: List[Bid]) -> bool:
    if b.is_pass:
        return True
    if b.is_double:
        last = next((x for x in reversed(auction) if not x.is_pass), None)
        return last is not None and not last.is_double and not last.is_redouble
    if b.is_redouble:
        last = next((x for x in reversed(auction) if not x.is_pass), None)
        return last is not None and last.is_double
    if b.suit is None:
        return False
    # 7-level is the absolute legal max — without this clamp the
    # bidder's competitive-overcall bug can spit out 1C-2C-3C-4C
    # … 40C indefinitely, each bid technically "higher" than the
    # last, but well past grand slam.
    if b.level < 1 or b.level > 7:
        return False
    last_suit = next((x for x in reversed(auction)
                      if not x.is_pass and not x.is_double
                      and not x.is_redouble), None)
    if last_suit is None:
        return True
    if b.level > last_suit.level:
        return True
    if b.level == last_suit.level:
        return _SUIT_RANK[b.suit] > _SUIT_RANK[last_suit.suit]
    return False


def _drive_ben_bridge(board: BoardState, system_name: str) -> List[Bid]:
    sys_ = get_system(system_name)
    auction: List[Bid] = []
    seat = board.dealer
    illegal_streak = 0
    for _ in range(80):
        state = parse_auction(seat, board.dealer, list(auction))
        e = evaluate_hand(board.hands[seat])
        b = decide_bid(state, e, sys_)
        if not _is_legal(b, auction):
            b = Bid.make_pass()
            illegal_streak += 1
            if illegal_streak >= 4:
                break
        else:
            illegal_streak = 0
        auction.append(b)
        if len(auction) >= 4 and all(x.is_pass for x in auction[-3:]) \
                and any(not x.is_pass for x in auction[:-3]):
            break
        if len(auction) >= 4 and all(x.is_pass for x in auction):
            break
        seat = seat.next()
    return auction


def _bid_repr(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    suit = {Suit.CLUBS: "C", Suit.DIAMONDS: "D",
            Suit.HEARTS: "H", Suit.SPADES: "S",
            Suit.NOTRUMP: "NT"}.get(b.suit, "?")
    return f"{b.level}{suit}"


def _bid_equal(a: Bid, b: Bid) -> bool:
    if a is None or b is None:
        return False
    if a.is_pass and b.is_pass:
        return True
    if a.is_double and b.is_double:
        return True
    if a.is_redouble and b.is_redouble:
        return True
    if a.is_pass or b.is_pass or a.is_double or b.is_double \
            or a.is_redouble or b.is_redouble:
        return False
    return a.level == b.level and a.suit == b.suit


def _diff_auctions(theirs: List[Bid], ours: List[Bid]
                   ) -> List[Tuple[int, str, str]]:
    out = []
    for i in range(max(len(theirs), len(ours))):
        t = theirs[i] if i < len(theirs) else None
        o = ours[i] if i < len(ours) else None
        if not _bid_equal(t, o):
            out.append((i,
                        _bid_repr(t) if t is not None else "—",
                        _bid_repr(o) if o is not None else "—"))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=10,
                   help="number of deals to diff (default 10)")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed for shuffling")
    p.add_argument("--system", default="SAYC-wbridge5",
                   help="ben_bridge system to test against Q-Plus auctions")
    p.add_argument("--report",
                   default=f"qplus_diff_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt",
                   help="output diff report path")
    p.add_argument("--bde-name", default="BB_DIFF.BDE",
                   help="name of the multi-deal file to drop in OWN-DEALS")
    p.add_argument("--timeout", type=float, default=600.0,
                   help="seconds to wait for Q-Plus to produce BDL output")
    p.add_argument("--dry-run", action="store_true",
                   help="write the BDE + dump ben_bridge auctions; skip "
                        "polling for Q-Plus output. Useful for smoke "
                        "testing the file generation.")
    args = p.parse_args(argv)

    own_dir = qplus_own_deals_dir()
    log_dir = qplus_log_dir()
    if own_dir is None or log_dir is None:
        print("[diff] Q-Plus install not found under FRI/WP/. Aborting.",
              file=sys.stderr)
        return 2

    deals = _generate_deals(args.n, args.seed)
    bde_path = own_dir / args.bde_name
    write_multi_deal_bde(deals, bde_path,
                         description=f"ben_bridge diff batch, N={args.n}")
    print(f"[diff] Wrote {args.n} deals to {bde_path}")

    ours = [_drive_ben_bridge(b, args.system) for b in deals]

    if args.dry_run:
        for i, (board, oauc) in enumerate(zip(deals, ours), 1):
            print(f"  ben_bridge board {board.board_number:3d}: "
                  f"{' '.join(_bid_repr(b) for b in oauc)}")
        return 0

    print(f"[diff] Now in Q-Plus: Own deals → Open → {args.bde_name}, "
          f"then auto-play each deal.")
    print(f"[diff] Polling {log_dir} for new BDL files "
          f"(timeout {args.timeout:.0f}s)…")
    pre = snapshot_log_files(log_dir)
    try:
        new_bdls = wait_for_new_bdls(log_dir, pre, args.n,
                                     timeout=args.timeout)
    except TimeoutError as ex:
        print(f"[diff] {ex}", file=sys.stderr)
        return 3
    print(f"[diff] {len(new_bdls)} new BDLs found")

    results = []
    for i, (board, oauc, bdl_path) in enumerate(zip(deals, ours, new_bdls),
                                                start=1):
        try:
            qdeals = load_bdl_file(str(bdl_path))
            qdeal = qdeals[0] if qdeals else None
            theirs = list(qdeal.auction) if qdeal else []
        except Exception as ex:
            print(f"[diff] couldn't parse {bdl_path}: {ex!r}")
            theirs = []
        diffs = _diff_auctions(theirs, oauc)
        results.append((board, bdl_path, theirs, oauc, diffs))
        marker = "✓" if not diffs else f"× {len(diffs)} diff"
        print(f"[diff] board {board.board_number:3d} ({i}/{args.n})  "
              f"{bdl_path.name}  {marker}")

    rpt = Path(args.report)
    with open(rpt, "w") as f:
        f.write(f"# Q-Plus diff report — N={args.n}, seed={args.seed}\n")
        f.write(f"# system={args.system}\n")
        f.write(f"# generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        total = len(results)
        matching = sum(1 for _, _, _, _, d in results if not d)
        f.write(f"Matching auctions: {matching}/{total} "
                f"({matching * 100 // max(1, total)}%)\n\n")
        pos_counts = Counter(d[0] for _, _, _, _, ds in results for d in ds)
        if pos_counts:
            f.write("Divergences by auction position (0 = opening bid):\n")
            for pos, c in sorted(pos_counts.items()):
                f.write(f"  pos {pos:2d}: {c}\n")
            f.write("\n")
        for board, bdl_path, theirs, oauc, diffs in results:
            if not diffs:
                continue
            f.write(f"--- board {board.board_number}  "
                    f"dealer={board.dealer.to_char()}  "
                    f"vul={board.vulnerability.value}  "
                    f"({bdl_path.name})\n")
            f.write(f"  Q-Plus    : "
                    f"{' '.join(_bid_repr(b) for b in theirs)}\n")
            f.write(f"  ben_bridge: "
                    f"{' '.join(_bid_repr(b) for b in oauc)}\n")
            for pos, t, o in diffs:
                f.write(f"  pos {pos:2d}: Q-Plus={t:5s} "
                        f"ben_bridge={o:5s}\n")
            f.write("\n")
    print(f"[diff] report written to {rpt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

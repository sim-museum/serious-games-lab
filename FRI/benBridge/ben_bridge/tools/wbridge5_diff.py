"""Diff harness: ben_bridge SAYC-wbridge5 vs actual wbridge5.

Drives wbridge5 (running under Wine, in Bridge Table Manager
client mode) through N randomly-generated deals via the TM
protocol; in parallel runs ben_bridge's native SAYC-wbridge5
bidder on the same deals; reports per-board divergence and
summary statistics so we can iteratively tune our system to
match wbridge5's actual play.

Usage:

    cd ben_bridge
    python tools/wbridge5_diff.py --n 20

    # advanced — pin a particular seed and route through a
    # specific TM port:
    python tools/wbridge5_diff.py --n 100 --seed 42 --port 9173

Workflow (until we find a wbridge5 CLI flag for TM-auto-connect):

  1. Run this script with --n N. It starts a TMServer on a random
     port and launches wbridge5 under Wine.
  2. In wbridge5: File → Bridge Table Manager → Connect. The host
     /port boxes are already populated (the driver patches
     WBRIDGE5.INI before spawning). Click OK.
  3. wbridge5 connects all four seats to our server. We run N
     deals, capture each auction, run ben_bridge's bidder, and
     produce the diff report.
  4. When done, the report lands at ``wbridge5_diff_<timestamp>.txt``.

Reports are formatted to highlight (a) absolute mismatch rate
per system / seat / auction-position, and (b) the specific
auction sequences where we diverge — these are the inputs you
feed back into ``native_bidder.py`` for the next round of
tuning.
"""

from __future__ import annotations

import argparse
import datetime
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Tuple

# Allow `python tools/wbridge5_diff.py` from the ben_bridge root.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ben_backend.bidding_systems import get_system   # noqa: E402
from ben_backend.models import (                     # noqa: E402
    BoardState, Hand, Card, Seat, Suit, Rank, Vulnerability, Bid,
)
from ben_backend.native_bidder import (              # noqa: E402
    decide_bid, evaluate_hand, parse_auction,
)
from ben_backend.pavlicek import (                    # noqa: E402
    number_to_deal,
)
from ben_backend.wbridge5_driver import (             # noqa: E402
    TMServer, Wbridge5Driver, TMDeal,
)


def _generate_deals(n: int, seed: int) -> List[BoardState]:
    """Generate N uniformly-random deals.

    Previously sampled board numbers from 1..30000 and ran them
    through Pavlicek number_to_deal — but Pavlicek numbers in that
    low range cluster heavily into freak distributions (e.g. board
    20953 = North-with-all-13-spades), and wbridge5 raises a Delphi
    range-check error on numbers above ~32K. Instead we shuffle a
    deck per deal and assign board numbers 1..N for wbridge5.
    Dealer / vulnerability cycle through the standard 16-board
    rotation so the harness exercises all conditions.
    """
    from ben_backend.models import Card, Hand, Rank, Suit
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
        out.append(BoardState(
            board_number=board_num,
            dealer=dealer,
            vulnerability=vuln,
            hands=hands,
        ))
    return out


def _drive_ben_bridge(board: BoardState, system_name: str) -> List[Bid]:
    """Run ben_bridge's native bidder on every seat in dealer order.

    Returns the bid list in chronological order — same shape as
    what the TM auction loop produces, so we can diff per-position.
    Coerces illegal bids (lower-than-current-contract, double-of-
    nothing, etc.) to a Pass so a misfiring `decide_bid` doesn't
    spam infinite loops into the diff report. The bidder bug
    those reveal is a separate fix.
    """
    sys_ = get_system(system_name)
    auction = []
    seat = board.dealer
    illegal_streak = 0
    for _ in range(80):    # safety bound
        state = parse_auction(seat, board.dealer, list(auction))
        e = evaluate_hand(board.hands[seat])
        b = decide_bid(state, e, sys_)
        if not _is_legal(b, auction):
            b = Bid.make_pass()
            illegal_streak += 1
            # If the bidder keeps refusing to pass we're in a real
            # divergence loop — bail out to keep the harness usable.
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


_SUIT_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1,
              Suit.HEARTS: 2, Suit.SPADES: 3, Suit.NOTRUMP: 4}


def _is_legal(b: Bid, auction: List[Bid]) -> bool:
    """True iff `b` is a legal next call given the auction so far."""
    if b.is_pass:
        return True
    if b.is_double:
        # Double is legal iff the most recent non-pass is an
        # opponent's natural suit/NT (not a double already).
        last_non_pass = next((x for x in reversed(auction)
                              if not x.is_pass), None)
        if last_non_pass is None:
            return False
        return not last_non_pass.is_double and not last_non_pass.is_redouble
    if b.is_redouble:
        last_non_pass = next((x for x in reversed(auction)
                              if not x.is_pass), None)
        return last_non_pass is not None and last_non_pass.is_double
    if b.suit is None:
        return False
    # Suit bid must outrank the current contract.
    last_suit_bid = next((x for x in reversed(auction)
                          if not x.is_pass and not x.is_double
                          and not x.is_redouble), None)
    if last_suit_bid is None:
        return True
    if b.level > last_suit_bid.level:
        return True
    if b.level == last_suit_bid.level:
        return _SUIT_RANK[b.suit] > _SUIT_RANK[last_suit_bid.suit]
    return False


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
    if a.is_pass and b.is_pass:
        return True
    if a.is_double and b.is_double:
        return True
    if a.is_redouble and b.is_redouble:
        return True
    if a.is_pass or b.is_pass or a.is_double or b.is_double:
        return False
    if a.is_redouble or b.is_redouble:
        return False
    return a.level == b.level and a.suit == b.suit


def _diff_auctions(theirs: List[Bid], ours: List[Bid]) -> List[Tuple[int, str, str]]:
    """Per-position diff. Returns [(pos, theirs, ours), …]."""
    out = []
    for i in range(max(len(theirs), len(ours))):
        t = theirs[i] if i < len(theirs) else None
        o = ours[i] if i < len(ours) else None
        if t is None or o is None or not _bid_equal(t, o):
            out.append((i,
                        _bid_repr(t) if t is not None else "—",
                        _bid_repr(o) if o is not None else "—"))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=10,
                   help="number of deals to diff (default 10)")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed for board selection")
    p.add_argument("--port", type=int, default=0,
                   help="TCP port for the TM server (0 = random)")
    p.add_argument("--system", default="SAYC-wbridge5",
                   help="ben_bridge system to test (default SAYC-wbridge5)")
    p.add_argument("--report",
                   default=f"wbridge5_diff_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt",
                   help="output diff report path")
    p.add_argument("--single-socket", action="store_true",
                   help="Engine plays all 4 seats over one socket "
                        "(wbridge5 default).")
    p.add_argument("--launch-wbridge5", action="store_true",
                   help="Also spawn wbridge5.exe under Wine. Without "
                        "this flag the script just runs the TM server "
                        "and you start wbridge5 by hand.")
    p.add_argument("--connect-timeout", type=float, default=180.0,
                   help="Seconds to wait for wbridge5 to connect to "
                        "the TM server (default 180).")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip the wbridge5 half — just run ben_bridge's "
                        "bidder on the N deals and dump the auctions. "
                        "Useful for smoke-testing the system spec "
                        "without needing wbridge5 to TM-connect.")
    p.add_argument("--debug", action="store_true",
                   help="Log every TM-protocol line sent to / received "
                        "from wbridge5 — useful for diagnosing dialect "
                        "mismatches.")
    args = p.parse_args(argv)

    # Dry-run path: just dump the ben_bridge auctions to stdout and
    # exit cleanly. No TM server, no wbridge5 launch.
    if args.dry_run:
        deals = _generate_deals(args.n, args.seed)
        print(f"[dry-run] {args.n} deals, system={args.system}")
        for d in deals:
            auc = _drive_ben_bridge(d, args.system)
            print(f"  board {d.board_number:5d}  "
                  f"dealer={d.dealer.to_char()}  "
                  f"vul={d.vulnerability.value:5s}  "
                  + " ".join(_bid_repr(b) for b in auc))
        return 0

    deals = _generate_deals(args.n, args.seed)

    print(f"[diff] N={args.n}, seed={args.seed}, system={args.system}")
    log_fn = (lambda d, ln: print(f"  TM{d} {ln}", flush=True)) \
             if args.debug else None
    server = TMServer(port=args.port, log_fn=log_fn)
    print(f"[diff] TM server listening on {server.host}:{server.port}")

    drv = None
    if args.launch_wbridge5:
        try:
            drv = Wbridge5Driver(server)
        except FileNotFoundError as ex:
            print(f"[diff] {ex}", file=sys.stderr)
            return 2
        drv.start()
        print("[diff] wbridge5 launched under Wine. In its window:")
        print("       Actions → Connection ... → pick a Place → "
              "click 'connection'")
        print(f"       Host/port pre-filled to {server.host}:{server.port}")
        print("       Tick 'Auto' to let wbridge5 cycle through the "
              "other seats automatically.")
    else:
        print("[diff] Now start wbridge5 manually and connect it.")
        print("       (Actions → Connection ... ; host/port should "
              f"already be {server.host}:{server.port}.)")

    # Accept the engine's connection(s).
    try:
        if args.single_socket:
            conn = server.accept_one_client(timeout=args.connect_timeout)
            # Treat the single socket as four-seat capable; key by NORTH.
            seat_conns = {Seat.NORTH: conn}
            # The connect-handshake — read the engine's "Connecting…"
            # line before we hand it any deals.
            server._read_connect(conn)
        else:
            seat_conns = server.accept_four_seats(timeout=args.connect_timeout)
    except (TimeoutError, OSError) as ex:
        print(f"[diff] wbridge5 did not connect within "
              f"{args.connect_timeout}s ({ex.__class__.__name__}). "
              "Open wbridge5 → Actions → Connection ... → click "
              "'connection' (host/port pre-filled).")
        if drv is not None:
            drv.stop()
        return 3
    print(f"[diff] connected: {[s.to_char() for s in seat_conns]}")

    # Ben_bridge bidder used as a fallback whenever wbridge5
    # punts a seat to "human" (which it does in Auto mode for at
    # least South). The auction we capture is HYBRID: some bids
    # come from wbridge5, some from ben_bridge — but every bid is
    # made in the same auction context, so per-bid diffing
    # remains meaningful as long as we attribute correctly.
    from ben_backend.bidding_systems import get_system as _gs
    _system_cached = _gs(args.system)

    def _fallback_bid(seat, auction_so_far):
        from ben_backend.native_bidder import (
            decide_bid as _decide, evaluate_hand as _eval,
            parse_auction as _parse,
        )
        # Build a state pointing at this seat as the next bidder.
        # The board's dealer is the auction's natural start.
        st = _parse(seat, board_for_callback.dealer,
                    list(auction_so_far))
        return _decide(st, _eval(board_for_callback.hands[seat]),
                       _system_cached)

    results = []
    for i, board in enumerate(deals, 1):
        board_for_callback = board     # closure-captured by _fallback_bid
        deal = TMDeal(
            board_number=board.board_number,
            dealer=board.dealer,
            vulnerability=board.vulnerability,
            hands=board.hands,
        )
        try:
            theirs = server.play_auction(seat_conns, deal,
                                         bid_callback=_fallback_bid)
        except Exception as ex:
            print(f"[diff] board {board.board_number}: wbridge5 failed: {ex!r}")
            theirs = []
        ours = _drive_ben_bridge(board, args.system)
        diffs = _diff_auctions(theirs, ours)
        results.append((board, theirs, ours, diffs))
        n_diff = len(diffs)
        marker = "✓" if n_diff == 0 else f"× {n_diff} diff"
        print(f"[diff] board {board.board_number:5d} ({i}/{args.n})  {marker}")

    # Write the report.
    rpt = Path(args.report)
    with open(rpt, "w") as f:
        f.write(f"# wbridge5 diff report — N={args.n}, seed={args.seed}\n")
        f.write(f"# system={args.system}\n")
        f.write(f"# generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        total = len(results)
        matching = sum(1 for _, _, _, d in results if not d)
        f.write(f"Matching auctions: {matching}/{total} "
                f"({matching * 100 // max(1, total)}%)\n\n")
        # Aggregate divergence positions.
        pos_counts = Counter(d[0] for _, _, _, ds in results for d in ds)
        f.write("Divergences by auction position (0 = opening bid):\n")
        for pos, n in sorted(pos_counts.items()):
            f.write(f"  pos {pos:2d}: {n}\n")
        f.write("\n")
        for board, theirs, ours, diffs in results:
            if not diffs:
                continue
            f.write(f"--- board {board.board_number}  "
                    f"dealer={board.dealer.to_char()}  "
                    f"vul={board.vulnerability.value}\n")
            f.write(f"  wbridge5 : "
                    f"{' '.join(_bid_repr(b) for b in theirs)}\n")
            f.write(f"  ben_bridge: "
                    f"{' '.join(_bid_repr(b) for b in ours)}\n")
            for pos, t, o in diffs:
                f.write(f"  pos {pos:2d}: wbridge5={t:5s} "
                        f"ben_bridge={o:5s}\n")
            f.write("\n")
    print(f"[diff] report written to {rpt}")

    if drv is not None:
        drv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

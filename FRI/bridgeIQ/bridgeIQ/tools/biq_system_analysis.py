"""biq-only analysis: same deals × all 25 NS/EW system-pair combinations.

For each deal in the aggregate corpus (union of 11075, 7371, 38263 seeds),
run bridgeIQ's bidder through all 5×5 NS/EW system combinations and capture:
  * the auction
  * the final contract (level, strain, declarer)
  * the DD trick count and NS score

Output:
  * System-sensitivity ranking per deal (how many distinct contracts across
    the 25 cells).
  * System-pair strength ranking (average NS score across all deals).
  * Per-NS-system score (EW averaged out).
  * Per-EW-system score (NS averaged out).
  * A `teaching_deck.json` of the top-N most system-sensitive deals,
    each with its 5×5 contract matrix and sample auctions.

Run:  python3 tools/biq_system_analysis.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.dds import DDSolver  # noqa: E402
from backend.models import Seat, Suit, Bid  # noqa: E402
from tools.qplus_mixed_corpus import gen_random_deals  # noqa: E402
from tools.mixed_corpus_diff import (  # noqa: E402
    drive_bridgeIQ_mixed, _determine_contract, _dd_tricks, _ns_score,
)

SYSTEMS = ["SAYC", "TwoOverOne", "StandardAcol",
           "StandardFrench", "Precision90M"]
SHORT = {"SAYC": "SAY", "TwoOverOne": "2/1", "StandardAcol": "ACO",
         "StandardFrench": "FRA", "Precision90M": "PR9"}

SEEDS = [11075, 7371, 38263]
DEALS_PER_SEED = 64


def _bid_str(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{b.suit.to_char() if b.suit else '?'}"


def _auction_str(auction: List[Bid]) -> str:
    return " ".join(_bid_str(b) for b in auction)


def _contract_key(c) -> str:
    """Hashable contract id: '4S-N' / 'PASS' / etc."""
    if c is None:
        return "PASS"
    # `Contract` dataclass — render to a stable string.
    decl = c.declarer.name[0] if c.declarer is not None else "?"
    return f"{c.to_str()}-{decl}"


def run_grid(deals, limit: Optional[int] = None) -> Dict:
    """Drive biq through every (deal × NS-sys × EW-sys) combination.
    Returns a structured results dict keyed by deal index.
    """
    if limit:
        deals = deals[:limit]
    dds = DDSolver()
    results: Dict[int, Dict] = {}
    n_total = len(deals) * len(SYSTEMS) * len(SYSTEMS)
    n_done = 0
    t0 = time.time()
    for di, board in enumerate(deals):
        cells = {}  # (ns, ew) → record
        for ns in SYSTEMS:
            for ew in SYSTEMS:
                auction = drive_bridgeIQ_mixed(board, ns, ew)
                contract = _determine_contract(board, auction)
                dd = _dd_tricks(dds, board, contract) if contract else 0
                # DDS returns -2 on errors; clamp.
                if dd is None or dd < 0 or dd > 13:
                    dd = 0
                score = _ns_score(contract, dd, board.vulnerability)
                cells[(ns, ew)] = {
                    "auction": _auction_str(auction),
                    "contract": _contract_key(contract),
                    "dd": dd,
                    "score": score,
                }
                n_done += 1
        results[di] = {
            "board_number": board.board_number,
            "dealer": board.dealer.name[0],
            "vul": board.vulnerability.name,
            "cells": cells,
        }
        elapsed = time.time() - t0
        eta = (elapsed / max(n_done, 1)) * (n_total - n_done)
        sys.stderr.write(
            f"\r[{n_done:5d}/{n_total} cells] deal {di+1}/{len(deals)} "
            f"elapsed {elapsed:5.0f}s  ETA {eta:5.0f}s   ")
        sys.stderr.flush()
    sys.stderr.write("\n")
    return results


def summarize(results: Dict) -> Dict:
    """Compute aggregate stats from the raw grid results."""
    # System-sensitivity per deal = # distinct contracts across 25 cells.
    sensitivity: List[Tuple[int, int, str]] = []
    # Score totals per (ns, ew).
    pair_totals: Dict[Tuple[str, str], int] = defaultdict(int)
    pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    # Per-NS / per-EW (averaged over the other side).
    ns_totals: Dict[str, int] = defaultdict(int)
    ew_totals: Dict[str, int] = defaultdict(int)
    ns_counts: Dict[str, int] = defaultdict(int)
    ew_counts: Dict[str, int] = defaultdict(int)
    contract_freq: Counter = Counter()

    for di, deal in results.items():
        contracts = [c["contract"] for c in deal["cells"].values()]
        distinct = len(set(contracts))
        # most common contract across the 25 cells
        mode_contract = Counter(contracts).most_common(1)[0][0]
        sensitivity.append((di, distinct, mode_contract))
        for c in contracts:
            contract_freq[c] += 1
        for (ns, ew), rec in deal["cells"].items():
            pair_totals[(ns, ew)] += rec["score"]
            pair_counts[(ns, ew)] += 1
            ns_totals[ns] += rec["score"]
            ns_counts[ns] += 1
            ew_totals[ew] += rec["score"]
            ew_counts[ew] += 1
    sensitivity.sort(key=lambda r: -r[1])
    pair_avg = {p: pair_totals[p] / max(1, pair_counts[p])
                for p in pair_totals}
    ns_avg = {s: ns_totals[s] / max(1, ns_counts[s]) for s in ns_totals}
    ew_avg = {s: ew_totals[s] / max(1, ew_counts[s]) for s in ew_totals}
    return {
        "sensitivity": sensitivity,
        "pair_avg": pair_avg,
        "ns_avg": ns_avg,
        "ew_avg": ew_avg,
        "contract_freq": dict(contract_freq.most_common(15)),
    }


def print_report(results: Dict, summary: Dict, top_n: int = 15):
    n_deals = len(results)
    print(f"\n# biq self-consistency report — {n_deals} deals × 25 system pairs")
    print(f"# total auctions simulated: {n_deals * 25}")

    print("\n## Per-NS-system average NS score (EW averaged out)")
    print("  (positive = biq's NS side beats DD-expected; higher = stronger system for biq)")
    for sys_ in sorted(summary["ns_avg"], key=lambda s: -summary["ns_avg"][s]):
        print(f"    {sys_:16s}  {summary['ns_avg'][sys_]:+7.1f}")

    print("\n## Per-EW-system average NS score (NS averaged out)")
    print("  (lower = stronger EW defense / opponent value)")
    for sys_ in sorted(summary["ew_avg"], key=lambda s: summary["ew_avg"][s]):
        print(f"    {sys_:16s}  {summary['ew_avg'][sys_]:+7.1f}")

    print("\n## All 25 system pairs ranked by avg NS score")
    print(f"  {'NS':<14s} {'EW':<14s} {'avg score':>10s}")
    ranked = sorted(summary["pair_avg"].items(), key=lambda kv: -kv[1])
    for (ns, ew), avg in ranked:
        print(f"    {ns:14s} {ew:14s} {avg:+10.1f}")

    print(f"\n## Top {top_n} most system-SENSITIVE deals "
          f"(many distinct contracts across the 25 system pairs)")
    print(f"  these are the most teaching-rich deals")
    print(f"  {'deal#':<6s} {'#distinct contracts':<22s} "
          f"{'mode contract':<14s}")
    for di, dist, mode in summary["sensitivity"][:top_n]:
        board = results[di]
        print(f"    deal {di+1:3d} ({board['dealer']}/{board['vul']:4s}) "
              f"  {dist:2d}/25 distinct       "
              f"  most-common: {mode}")

    print(f"\n## Top {top_n} most system-INSENSITIVE deals "
          f"(everyone bids the same contract — good for mechanical practice)")
    bottom = sorted(summary["sensitivity"], key=lambda r: r[1])[:top_n]
    print(f"  {'deal#':<6s} {'#distinct contracts':<22s} "
          f"{'mode contract':<14s}")
    for di, dist, mode in bottom:
        board = results[di]
        print(f"    deal {di+1:3d} ({board['dealer']}/{board['vul']:4s}) "
              f"  {dist:2d}/25 distinct       "
              f"  most-common: {mode}")

    print(f"\n## Most-common biq contracts across all (deal × pair) cells")
    for c, n in summary["contract_freq"].items():
        print(f"    {c:<10s} {n:5d}")


def write_teaching_deck(results: Dict, summary: Dict,
                       out_path: Path, top_n: int = 16):
    """Write a JSON deck of the top-N system-sensitive deals."""
    deck = []
    for di, dist, mode in summary["sensitivity"][:top_n]:
        deal = results[di]
        # Build a 5x5 contract matrix and a sample-auctions matrix.
        matrix = {}
        auctions = {}
        for ns in SYSTEMS:
            for ew in SYSTEMS:
                cell = deal["cells"][(ns, ew)]
                matrix[f"{ns}/{ew}"] = cell["contract"]
                auctions[f"{ns}/{ew}"] = cell["auction"]
        deck.append({
            "deal_index": di,
            "dealer": deal["dealer"],
            "vul": deal["vul"],
            "distinct_contracts": dist,
            "mode_contract": mode,
            "matrix": matrix,
            "auctions": auctions,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deck, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="cap the deal count (for fast smoke tests)")
    p.add_argument("--out", type=str,
                   default="data/biq_system_analysis.json")
    p.add_argument("--deck", type=str,
                   default="data/teaching_deck.json")
    p.add_argument("--top-n", type=int, default=15)
    args = p.parse_args(argv)

    # Build the deal aggregate.
    deals = []
    for seed in SEEDS:
        deals.extend(gen_random_deals(DEALS_PER_SEED, seed))
    print(f"# {len(deals)} unique deals from seeds {SEEDS}")

    results = run_grid(deals, limit=args.limit)
    summary = summarize(results)
    print_report(results, summary, top_n=args.top_n)

    # Save raw + curated outputs.
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Strip non-JSON-safe fields for the raw dump.
    raw = {str(di): {
        "board_number": d["board_number"],
        "dealer": d["dealer"],
        "vul": d["vul"],
        "cells": {f"{ns}/{ew}": {
            "auction": rec["auction"],
            "contract": rec["contract"],
            "dd": rec["dd"],
            "score": rec["score"],
        } for (ns, ew), rec in d["cells"].items()},
    } for di, d in results.items()}
    out.write_text(json.dumps(raw, indent=2))
    print(f"\n# raw grid → {out}")
    write_teaching_deck(results, summary, Path(args.deck),
                       top_n=args.top_n)
    print(f"# teaching deck → {args.deck}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

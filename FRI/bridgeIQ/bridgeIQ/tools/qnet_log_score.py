#!/usr/bin/env python3
"""Score a Q-NET match from the biq client log — independent of Q-Plus's
.qss export, which caps at 64 boards (Q-Plus 17.1's score sheet holds only
64; longer matches silently drop the rest, even though all boards were
dealt and played).

The biq client log (tools/runs/biq_N.log) carries, per deal: the full
4-hand PBN (from `new_deal_pbn`), the auction (`bid` lines), the final
`CONTRACT:`, and one `trick won by <seat>` per trick. That's everything
needed to score every board. We score biq's actual NS table result against
double-dummy PAR (a complete, Q-Plus-independent reference) and, when a
.qss is given, validate the parsed raw scores against its (≤64) deals.

Usage:
    python3 tools/qnet_log_score.py --log tools/runs/biq_N.log \
        [--set 6281] [--qss <path-to-validate>] [--worst 15]
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import Contract, Suit, Seat               # noqa: E402
from backend.scoring import calculate_contract_score, diff_to_imps  # noqa: E402
from backend.dds import DDSolver                              # noqa: E402

_SUIT = {'C': Suit.CLUBS, 'D': Suit.DIAMONDS, 'H': Suit.HEARTS,
         'S': Suit.SPADES, 'N': Suit.NOTRUMP, 'NT': Suit.NOTRUMP}
_SEAT = {'NORTH': Seat.NORTH, 'EAST': Seat.EAST,
         'SOUTH': Seat.SOUTH, 'WEST': Seat.WEST}
_NS = {Seat.NORTH, Seat.SOUTH}
_STRAINS = ['C', 'D', 'H', 'S', 'N']           # rank order; N high
_DD_STRAIN = {'C': 'C', 'D': 'D', 'H': 'H', 'S': 'S', 'N': 'NT'}


def _parse_deals(log_path, want_set):
    """Yield dict(label, dealer, vul, pbn, contract, declarer, doubled,
    redoubled, decl_tricks, passed_out) for each deal of the set."""
    text = Path(log_path).read_text(errors='replace')
    # Split on the new_deal_pbn marker; each chunk is one board.
    ndp = re.compile(
        r'new_deal_pbn"?\s*\[[NESW]\s+(\d+)\s+(\d+)\]\s*\[[^\]]*\]\s*'
        r'\[([^\]]+)\]\s*\[([^\]]+)\]')
    chunks = re.split(r'(?="?new_deal_pbn)', text)
    deals = {}
    for ch in chunks:
        m = ndp.search(ch)
        if not m:
            continue
        board_no, dset, label, pbn = m.groups()
        if str(dset) != str(want_set):
            continue
        # pbn looks like "E EW N:hands…" → dealer, vul, "N:hands…"
        pm = re.match(r'([NESW])\s+(\S+)\s+([NESW]:.+)', pbn.strip())
        if not pm:
            continue
        dealer, vul, hands = pm.groups()
        # auction
        bids = re.findall(r'"bid"\s*\[(\w+)\]\s*\[\s*([^\]]*?)\s*\]', ch)
        # final contract
        cm = re.search(r'CONTRACT:\s*(\d)([CDHSN])\s+by\s+(\w+)', ch)
        # tricks
        won = re.findall(r'trick won by (\w+)', ch)
        passed_out = cm is None and bids and all(
            b[1].strip().lower() == 'p' for b in bids)
        d = {'label': label, 'board': int(board_no), 'dealer': dealer,
             'vul': vul, 'pbn': hands, 'passed_out': passed_out}
        if cm:
            lvl, strain, decl = cm.groups()
            decl_seat = _SEAT[decl]
            # doubling: scan auction after the last natural (suit/NT) bid
            dbl = redbl = False
            for who, val in bids:
                v = val.strip().lower()
                if re.match(r'\d[cdhsn]', v):
                    dbl = redbl = False
                elif v == 'x':
                    dbl = True
                elif v == 'xx':
                    redbl = True
            decl_side = {decl_seat, decl_seat.partner()}
            d.update(level=int(lvl), strain=strain, declarer=decl_seat,
                     doubled=dbl, redoubled=redbl,
                     decl_tricks=sum(1 for w in won
                                     if _SEAT.get(w) in decl_side),
                     n_tricks=len(won))
        deals[label] = d            # dedupe: keep last occurrence
    return deals


def _ns_score(level, strain, declarer, tricks, doubled, redoubled,
              vul_ns, vul_ew):
    c = Contract(level=level, suit=_SUIT[strain], doubled=doubled,
                 redoubled=redoubled, declarer=declarer)
    decl_vul = (declarer in _NS and vul_ns) or (declarer not in _NS and vul_ew)
    sc = calculate_contract_score(c, tricks, decl_vul)
    return sc if declarer in _NS else -sc


def _par_ns(dd, vul_ns, vul_ew):
    """Double-dummy par (NS perspective) via greedy-by-rank equilibrium:
    walk contracts low→high; each side bids higher whenever doing so
    improves its own result (a make, or a cheaper sacrifice)."""
    par = 0
    for level in range(1, 8):
        for strain in _STRAINS:
            for side in ('NS', 'EW'):
                seats = ((Seat.NORTH, Seat.SOUTH) if side == 'NS'
                         else (Seat.EAST, Seat.WEST))
                decl = max(seats, key=lambda s: dd[s.name[0]][_DD_STRAIN[strain]])
                tricks = dd[decl.name[0]][_DD_STRAIN[strain]]
                made = tricks >= 6 + level
                doubled = not made          # par doubles sacrifices/penalties
                ns = _ns_score(level, strain, decl, tricks, doubled, False,
                               vul_ns, vul_ew)
                if side == 'NS' and ns > par:
                    par = ns
                elif side == 'EW' and ns < par:
                    par = ns
    return par


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log', default='tools/runs/biq_N.log')
    ap.add_argument('--set', default='6281')
    ap.add_argument('--qss', default=None, help='validate raw scores vs this .qss')
    ap.add_argument('--worst', type=int, default=15)
    args = ap.parse_args()

    deals = _parse_deals(args.log, args.set)
    if not deals:
        print(f"No deals for set {args.set} in {args.log}", file=sys.stderr)
        return 1
    solver = DDSolver()
    rows = []
    for label in sorted(deals, key=lambda L: deals[L]['board']):
        d = deals[label]
        vul_ns = d['vul'] in ('NS', 'All', 'Both', 'ALL', 'BOTH')
        vul_ew = d['vul'] in ('EW', 'All', 'Both', 'ALL', 'BOTH')
        dd = solver.solve_dd_table(d['pbn'])
        par = _par_ns(dd, vul_ns, vul_ew)
        if d['passed_out'] or 'level' not in d:
            actual = 0
            cstr = 'PASS' if d['passed_out'] else '??'
            dd_tr = None
        else:
            actual = _ns_score(d['level'], d['strain'], d['declarer'],
                               d['decl_tricks'], d['doubled'], d['redoubled'],
                               vul_ns, vul_ew)
            dd_tr = dd[d['declarer'].name[0]][_DD_STRAIN[d['strain']]]
            cstr = (f"{d['level']}{d['strain']}"
                    f"{'XX' if d['redoubled'] else ('X' if d['doubled'] else '')}"
                    f" {d['declarer'].name[0]}")
        imp = diff_to_imps(actual - par)        # +ve = biq above par
        rows.append({'label': label, 'contract': cstr, 'actual': actual,
                     'par': par, 'imp': imp,
                     'cardplay': (None if dd_tr is None
                                  else d['decl_tricks'] - dd_tr),
                     'decl_ns': ('level' in d and d['declarer'] in _NS)})

    tot = sum(r['imp'] for r in rows)
    n = len(rows)
    ns_decl = [r for r in rows if r['decl_ns']]
    ew_decl = [r for r in rows if 'PASS' not in r['contract'] and not r['decl_ns']]
    print(f"# biq vs double-dummy PAR, from {args.log} (set {args.set})\n")
    print(f"  Deals scored:    {n}")
    print(f"  Total IMP vs par: {tot:+d}   ({tot/n:+.2f}/deal)")
    print(f"  biq NS declared: {len(ns_decl)} deals, {sum(r['imp'] for r in ns_decl):+d} IMP")
    print(f"  EW declared:     {len(ew_decl)} deals, {sum(r['imp'] for r in ew_decl):+d} IMP")
    cp = [r['cardplay'] for r in rows if r['cardplay'] is not None]
    print(f"  Cardplay vs DD:  {sum(cp):+d} tricks over {len(cp)} played "
          f"contracts (–ve = biq/opps under DD)")

    print(f"\n## Worst {args.worst} deals (biq below par)")
    for r in sorted(rows, key=lambda r: r['imp'])[:args.worst]:
        print(f"  {r['label']:10} {r['contract']:8} "
              f"actual={r['actual']:>6}  par={r['par']:>6}  IMP={r['imp']:>4}")

    if args.qss:
        qtext = Path(args.qss).read_text(errors='replace')
        qre = dict(re.findall(r'DI "([^"]+)".*?\nRE (-?\d+) -?\d+', qtext, re.S))
        match = miss = 0
        bad = []
        for r in rows:
            if r['label'] in qre:
                if int(qre[r['label']]) == r['actual']:
                    match += 1
                else:
                    miss += 1
                    bad.append((r['label'], r['actual'], qre[r['label']]))
        print(f"\n## Validation vs {Path(args.qss).name}: "
              f"{match}/{match+miss} raw NS scores match")
        for lab, mine, theirs in bad[:8]:
            print(f"    MISMATCH {lab}: log={mine} qss={theirs}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

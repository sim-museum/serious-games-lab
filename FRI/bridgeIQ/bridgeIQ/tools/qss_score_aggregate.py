"""Aggregate biq-vs-Q-Plus IMP totals from a Q-Plus teams / Closed-Room
score export (.qss in DATA/LOCAL-MATCHES, written by the Score dialog's
"Save and send").

Use this, NOT qnet_score_aggregate.py, for Closed-Room/teams matches:
Q-Plus relays only *some* deals' `report_score` over the network, so the
proxy log is incomplete in teams mode. The .qss has EVERY deal.

Per-deal fields used:
  DI "<id>"                              deal id
  DD "<dealer> <vul> <starter>:<hands>"  deal (for dealer/vul)
  RE <ns_open> <ns_closed>               NS raw score per room (biq=open)
  IM <ns_imp> <ew_imp>                   teams IMP swing (one side is 0)
"""
import argparse
import re


def parse_qss(path):
    deals = []
    cur = None
    for line in open(path, errors="replace"):
        m = re.match(r'\s*DI\s+"([^"]*)"', line)
        if m:
            if cur:
                deals.append(cur)
            cur = {"id": m.group(1), "dealer": "?", "vul": "?",
                   "re": None, "im": None}
            continue
        if cur is None:
            continue
        m = re.match(r'\s*DD\s+"(\S+)\s+(\S+)', line)
        if m:
            cur["dealer"], cur["vul"] = m.group(1), m.group(2)
            continue
        m = re.match(r"\s*RE\s+(-?\d+)\s+(-?\d+)", line)
        if m:
            cur["re"] = (int(m.group(1)), int(m.group(2)))
            continue
        m = re.match(r"\s*IM\s+(-?\d+)\s+(-?\d+)", line)
        if m:
            cur["im"] = (int(m.group(1)), int(m.group(2)))
            continue
    if cur:
        deals.append(cur)
    return [d for d in deals if d["im"] is not None]


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Aggregate biq IMP totals from a Q-Plus .qss teams "
                    "score export (complete; use instead of the proxy "
                    "aggregator for Closed-Room matches)")
    p.add_argument("--qss", required=True, nargs="+",
                   help="path(s) to .qss file(s); pass several segment "
                        "exports to combine them into one result (each "
                        "Q-Plus teams sheet caps at 64 boards)")
    p.add_argument("--our-seat", choices=["N", "E", "S", "W"], default="S",
                   help="which seat biq played")
    a = p.parse_args(argv)
    # Combine one or more segment .qss files, de-duping by deal id so an
    # overlapping board isn't counted twice. Boards keep deal-id order.
    by_id = {}
    for path in a.qss:
        for d in parse_qss(path):
            by_id.setdefault(d["id"], d)
    if len(a.qss) > 1:
        print(f"# combined {len(a.qss)} segment files "
              f"-> {len(by_id)} distinct boards\n")
    deals = sorted(by_id.values(), key=lambda d: d["id"])
    ns = a.our_seat in ("N", "S")
    side = "NS" if ns else "EW"
    biq_tot = opp_tot = ns_raw = 0
    wins = losses = ties = 0
    rows = []
    for d in deals:
        ns_imp, ew_imp = d["im"]
        biq = ns_imp if ns else ew_imp
        opp = ew_imp if ns else ns_imp
        biq_tot += biq
        opp_tot += opp
        if biq > opp:
            wins += 1
        elif opp > biq:
            losses += 1
        else:
            ties += 1
        score = d["re"][0] if d["re"] else 0
        ns_raw += score
        rows.append((d["id"], d["dealer"], d["vul"], score, biq, opp))
    n = len(deals)
    print(f"# biq-vs-Q-Plus aggregate from QSS ({n} deals, biq plays {side})\n")
    print(f"  Total IMPs: biq={biq_tot:+d}  opp={opp_tot:+d}  "
          f"net (biq - opp) = {biq_tot - opp_tot:+d}")
    if n:
        print(f"  Net IMPs/deal: {(biq_tot - opp_tot) / n:+.2f}")
    print(f"  Deal wins:  biq={wins}  opp={losses}  ties={ties}")
    print(f"  Total {side} raw score (biq's table): {ns_raw}\n")
    print(f"  {'#':>3}  {'deal':12}  {'dealer/vul':11}  {'tbl-score':>9}  "
          f"{'biq IMP':>7}  {'opp IMP':>7}")
    for i, (did, dl, vl, sc, bq, op) in enumerate(rows, 1):
        print(f"  {i:>3}  {did:12}  {(dl + ' ' + vl):11}  {sc:>9}  "
              f"{bq:>+7}  {op:>+7}")


if __name__ == "__main__":
    main()

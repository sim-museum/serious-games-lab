"""Parse Q-NET `report_score` messages from a proxy session log
and aggregate per-deal results into a biq-vs-Q-Plus IMP totals
report.

Q-Plus's `report_score` payload format (decoded from captures):

    "report_score" [<status>] [<k=v;k=v;...>]

where the k=v fields include:
    DI "<deal_label>"           — deal ID
    DD "<dealer> <vul> <starter>:<hands>"  — PBN deal
    C1 "<n> <n> <n> <n> <n>"    — DD trick counts (one declarer
                                   side), one per strain (C,D,H,S,NT)
    C2 "<n> <n> <n> <n> <n>"    — DD trick counts (other side)
    RE <actual_NS> <par_EW>     — result (NS actual score, EW par
                                   score reference)
    IM <NS_imp> <EW_imp>        — IMPs from the deal (one is 0)
    CN ... NC ...               — board / session counters

Usage:
    python3 tools/qnet_score_aggregate.py [--log path] [--our-seat E]

`--our-seat` says which seat biq is playing, so the script can
infer whether biq's side won or lost IMPs each deal (East/West =
EW = biq, North/South = NS = biq).
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _payloads_from_proxy_log(path: Path) -> List[Tuple[int, str, str]]:
    """Reconstruct each packet's full ASCII payload from the
    hex+ASCII dump format the proxy writes. Returns
    [(ms, direction, payload), ...]."""
    log = path.read_text()
    hdr_re = re.compile(r'^\[\s*(\d+)\s*ms\]\s+(C2S|S2C)\s+len=(\d+)\s*$')
    hex_re = re.compile(r'^\s+[0-9a-f]{4}\s+((?:[0-9a-f]{2} ){1,16})\s+')
    blocks = re.split(r'\n\n+', log)
    out = []
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue
        m = hdr_re.match(lines[0])
        if not m:
            continue
        ms = int(m.group(1))
        direction = m.group(2)
        length = int(m.group(3))
        payload = bytearray()
        for line in lines[1:]:
            hm = hex_re.match(line)
            if hm:
                for tok in hm.group(1).strip().split():
                    payload.append(int(tok, 16))
        if payload:
            out.append((ms, direction,
                          payload[:length].decode('latin-1', 'replace')
                          .rstrip()))
    return out


def _payloads_from_client_log(path: Path) -> List[Tuple[int, str, str]]:
    """Extract `"report_score" […]` payloads from a plain-text biq CLIENT
    log (no proxy). Same return shape as the proxy reader so aggregate()
    is source-agnostic. The biq log is appended across the run (incl. the
    relaunches at each reset), so the whole file == the current run."""
    out = []
    for line in path.read_text(errors='replace').splitlines():
        i = line.find('"report_score"')
        if i != -1:
            out.append((0, 'S2C', line[i:]))   # payload from the cmd onward
    return out


def _parse_report_score(payload: str) -> Optional[Dict]:
    """Parse one `"report_score" [...] [DI ...]` line into a dict."""
    m = re.match(r'^"report_score"\s+\[([^\]]*)\]\s+\[([^\]]*)\]', payload)
    if not m:
        return None
    status = m.group(1).strip()
    fields_str = m.group(2)
    out = {"status": status}
    # Split on ; outside quotes
    for chunk in fields_str.split(';'):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, _, rest = chunk.partition(' ')
        rest = rest.strip()
        # Strip surrounding quotes if present
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
        out[key] = rest
    return out


def _parse_imp(im_field: str) -> Tuple[int, int]:
    """IM '11 0' → (11, 0). Returns (ns_imp, ew_imp). One is 0."""
    parts = im_field.split()
    if len(parts) < 2:
        return (0, 0)
    return (int(parts[0]), int(parts[1]))


def _parse_re(re_field: str) -> Tuple[int, int]:
    """RE '-50 -620' → (-50, -620). (actual_NS, par_EW)."""
    parts = re_field.split()
    if len(parts) < 2:
        return (0, 0)
    return (int(parts[0]), int(parts[1]))


def _parse_dd_dealer_contract(dd_field: str) -> Optional[str]:
    """DD field starts with `<Dealer> <Vul> <starter>:<hands>`.
    Returns 'E All' style prefix for display."""
    if not dd_field:
        return None
    parts = dd_field.split(None, 2)
    if len(parts) < 2:
        return None
    return f"{parts[0]} {parts[1]}"


def aggregate(log_path: Path, our_seat: str = 'E') -> int:
    if not log_path.exists():
        print(f"[aggregate] log not found: {log_path}", file=sys.stderr)
        return 1
    # Auto-detect: a biq CLIENT log has plain-text `<< "report_score"`
    # lines; the proxy log is a hex dump.
    head = log_path.read_text(errors='replace')[:4000]
    if '[biq_qnet]' in head:        # biq CLIENT log (plain text)
        payloads = _payloads_from_client_log(log_path)
    else:                           # proxy hex dump
        payloads = _payloads_from_proxy_log(log_path)
    deals: List[Dict] = []
    for ms, _d, payload in payloads:
        if payload.startswith('"report_score"'):
            r = _parse_report_score(payload)
            if r:
                r["ms"] = ms
                deals.append(r)
    if not deals:
        print(f"[aggregate] no report_score lines in {log_path}",
              file=sys.stderr)
        return 1
    biq_is_ns = our_seat.upper() in ('N', 'S', 'NS')
    biq_label = "NS" if biq_is_ns else "EW"
    opp_label = "EW" if biq_is_ns else "NS"
    biq_imp_total = 0
    opp_imp_total = 0
    biq_wins = 0
    opp_wins = 0
    ties = 0
    biq_score_total = 0
    rows = []
    for r in deals:
        di = r.get("DI", "?")
        dd_prefix = _parse_dd_dealer_contract(r.get("DD", "")) or "?"
        re_actual_ns, re_par = _parse_re(r.get("RE", "0 0"))
        ns_imp, ew_imp = _parse_imp(r.get("IM", "0 0"))
        biq_imp = ns_imp if biq_is_ns else ew_imp
        opp_imp = ew_imp if biq_is_ns else ns_imp
        biq_imp_total += biq_imp
        opp_imp_total += opp_imp
        if biq_imp > opp_imp:
            biq_wins += 1
        elif opp_imp > biq_imp:
            opp_wins += 1
        else:
            ties += 1
        # NS score is the RE first number; biq's side score:
        biq_score = re_actual_ns if biq_is_ns else -re_actual_ns
        biq_score_total += biq_score
        rows.append({
            "DI": di, "DD": dd_prefix,
            "NS": re_actual_ns,
            "biq_imp": biq_imp, "opp_imp": opp_imp,
        })
    n = len(rows)
    print(f"# biq-vs-Q-Plus aggregate ({n} deals, biq plays {biq_label})")
    print()
    print(f"  Total IMPs: biq={biq_imp_total:+d}  "
          f"opp={opp_imp_total:+d}  "
          f"net (biq - opp) = {biq_imp_total - opp_imp_total:+d}")
    print(f"  Net IMPs/deal: "
          f"{(biq_imp_total - opp_imp_total) / n:+.2f}")
    print(f"  Deal wins:  biq={biq_wins}  opp={opp_wins}  ties={ties}")
    print(f"  Total NS raw score: {biq_score_total if biq_is_ns else -biq_score_total:+d}")
    print()
    print(f"{'#':>3}  {'deal':<12}  {'dealer/vul':<11}  "
          f"{'NS-score':>9}  {'biq IMP':>8}  {'opp IMP':>8}")
    for i, r in enumerate(rows, 1):
        print(f"{i:>3}  {r['DI']:<12}  {r['DD']:<11}  "
              f"{r['NS']:>+9d}  {r['biq_imp']:>+8d}  "
              f"{r['opp_imp']:>+8d}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Aggregate biq-vs-Q-Plus IMP totals from a "
                     "Q-NET proxy session log")
    p.add_argument("--log",
                   default=Path(__file__).parent / "runs"
                            / "qnet_session.log",
                   type=Path,
                   help="proxy log file (default tools/runs/qnet_session.log)")
    p.add_argument("--our-seat", default="E",
                   choices=["N", "E", "S", "W"],
                   help="which seat biq played in the session")
    args = p.parse_args(argv)
    return aggregate(args.log, args.our_seat)


if __name__ == "__main__":
    sys.exit(main())

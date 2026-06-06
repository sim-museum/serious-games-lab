#!/usr/bin/env python3
"""M1 — competitive DECISION probe for the competitive-bidding rework.

Measures competitive-bidding changes WITHOUT a live run, sidestepping two
traps: the corpus/biq-vs-biq probe has no competition (contested auctions
vanish), and full-auction replay is unsound (once biq deviates, the opponents'
recorded later bids don't fit). So this probes the DECISION POINT:

  For every deal in a run log, walk the RECORDED auction; at each turn that was
  biq's (N/S), rebuild the state from the recorded prefix and ask the CURRENT
  bidder what it would call now. Report each point where biq's call CHANGED
  vs the log — split by direction (pass→action = more aggressive; action→pass
  = more passive) — with the deal's DD facts and result.

Use: run it before and after a competitive fix. A U-fix should turn biq's
losing PASSES into actions on the right deals; the guard is that it must NOT
start bidding on deals where passing was correct (the over-compete O-class).

Usage:
  python3 tools/competitive_decision_probe.py [LOG] [--deals 2428-19,2428-54]
  (default LOG = the 2/1 isolation run)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from backend.models import (Bid, Seat, Suit, Hand, Card, Rank,             # noqa: E402
                            Vulnerability)
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid  # noqa: E402
from backend.bidding_systems import get_system                              # noqa: E402
from backend.dds import DDSolver                                            # noqa: E402

_R = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK,
      'T': Rank.TEN, '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
      '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
      '2': Rank.TWO}
_SC = {'c': Suit.CLUBS, 'd': Suit.DIAMONDS, 'h': Suit.HEARTS,
       's': Suit.SPADES, 'n': Suit.NOTRUMP}
_S = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
_SEAT = {"North": Seat.NORTH, "East": Seat.EAST, "South": Seat.SOUTH,
         "West": Seat.WEST, "N": Seat.NORTH, "E": Seat.EAST,
         "S": Seat.SOUTH, "W": Seat.WEST}
_DLR = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_VUL = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
        "EW": Vulnerability.EW, "All": Vulnerability.BOTH,
        "Both": Vulnerability.BOTH}
_SYSMAP = {"2-1": "TwoOverOne", "SAYC": "SAYC", "ACL": "StandardAcol",
           "FRA": "StandardFrench", "P90M": "Precision90M"}


def parse_call(tok):
    t = tok.strip().lower()
    if t in ("p", "pass"):
        return Bid(is_pass=True)
    if t in ("x", "double", "dbl"):
        return Bid(is_double=True)
    if t in ("xx", "redouble", "rdbl"):
        return Bid(is_redouble=True)
    m = re.match(r"(\d)\s*(nt|n|[cdhs])", t)
    if not m:
        return None
    suit = Suit.NOTRUMP if m.group(2) in ("nt", "n") else _SC[m.group(2)]
    return Bid(level=int(m.group(1)), suit=suit)


def hand_from(s):
    cards = []
    for su, part in zip(_S, s.split(".")):
        for c in part:
            if c != '-':
                cards.append(Card(su, _R[c]))
    return Hand(cards=cards)


def sysname(tok):
    for k, v in _SYSMAP.items():
        if k in tok:
            return v
    return "SAYC"


def parse_log(path):
    txt = Path(path).read_text(errors="replace")
    cfgs = [(sysname(a), sysname(b)) for a, b in re.findall(
        r'conv\.bidding\.N/S = ([^;]+);conv\.bidding\.E/W = ([^;]+)', txt)]
    out = []
    idx = 0
    for ch in re.split(r'(?="?new_deal_pbn)', txt):
        m = re.search(r'new_deal_pbn"? \[[^]]*\] \[[^]]*\] \[([^]]+)\]\s*'
                      r'\[([NESW]) (\S+) (N:[^\]]+)\]', ch)
        if not m:
            continue
        di, dealer, vul, pbn = m.group(1), m.group(2), m.group(3), m.group(4)
        calls = [(s, parse_call(c)) for s, c
                 in re.findall(r'"bid" \[(\w+)\] \[([^\]]+)\]', ch)]
        calls = [(s, b) for s, b in calls if b is not None]
        rs = re.search(r'report_score.*?DI "' + re.escape(di)
                       + r'".*?IM (-?\d+) (-?\d+)', txt)
        imp = (int(rs.group(1)) - int(rs.group(2))) if rs else None
        out.append({"di": di, "dealer": dealer, "vul": vul, "pbn": pbn,
                    "sys": cfgs[idx] if idx < len(cfgs) else ("SAYC", "SAYC"),
                    "calls": calls, "imp": imp})
        idx += 1
    return out


def _bidstr(b):
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{b.suit.to_char() if b.suit is not None else '?'}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    log = args[0] if args else "tools/runs/ab/run_260605_224353.log"
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--deals"):
            only = set(a.split("=", 1)[1].split(",")) if "=" in a else None
    deals = parse_log(log)
    if only:
        deals = [d for d in deals if d["di"] in only]
    dds = DDSolver()
    n_more, n_less, changed_deals = 0, 0, 0
    print(f"# competitive decision probe — {log}  ({len(deals)} deals)\n")
    for d in deals:
        hands = {Seat.NORTH: None, Seat.EAST: None,
                 Seat.SOUTH: None, Seat.WEST: None}
        body = d["pbn"].split(":", 1)[1].split()
        for st, h in zip([Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST], body):
            hands[st] = hand_from(h)
        dealer = _DLR[d["dealer"]]
        vv = _VUL.get(d["vul"], Vulnerability.NONE)
        ns, ew = get_system(d["sys"][0]), get_system(d["sys"][1])
        t = dds.solve_dd_table(d["pbn"])
        ns_dd = max(max(t["N"][k], t["S"][k]) for k in
                    ("S", "H", "D", "C", "NT"))
        ew_dd = max(max(t["E"][k], t["W"][k]) for k in
                    ("S", "H", "D", "C", "NT"))
        prefix = []
        devs = []
        for s_name, logged in d["calls"]:
            seat = _SEAT[s_name]
            if seat.is_ns():
                stt = parse_auction(seat, dealer, list(prefix),
                                    vulnerability=vv)
                cur = decide_bid(stt, evaluate_hand(hands[seat]),
                                 ns if seat.is_ns() else ew)
                if _bidstr(cur) != _bidstr(logged):
                    more = logged.is_pass and not cur.is_pass
                    less = (not logged.is_pass) and cur.is_pass
                    devs.append((seat.name[0], _bidstr(logged),
                                 _bidstr(cur), more, less))
                    if more:
                        n_more += 1
                    if less:
                        n_less += 1
            prefix.append(logged)
        if devs:
            changed_deals += 1
            tag = (f"IMP={d['imp']:+d}" if d['imp'] is not None else "")
            print(f"{d['di']} [{d['sys'][0][:4]}] ddNS={ns_dd} ddEW={ew_dd} "
                  f"{tag}")
            for who, was, now, more, less in devs:
                arrow = "→more" if more else ("→less" if less else "→diff")
                print(f"    {who}: log {was:3} ⇒ now {now:3}  {arrow}")
    print(f"\n# summary: {changed_deals} deals changed; "
          f"{n_more} pass→action (more aggressive), "
          f"{n_less} action→pass (more passive)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mine Q-Plus's own auctions for biq bidding errors, ranked by IMP cost.

Q-Plus writes every deal of every match with all four hands: the closed room
(Q-Plus at all four seats) and the open room (Q-Plus E/W against biq N/S).
For every call a Q-Plus player made, this asks what biq's rules would have
called in the same seat with the same hand after the same calls. Where the
two differ, the auction is finished TWICE by biq's rule bidder (once after
Q-Plus's call, once after biq's) and both final contracts are scored
double-dummy on the real deal, so the only difference between the branches
is that one call. Results are summed per biq RULE (the explanation string
the rule returned), which ranks the rule holes by what they cost.

Two judges: "dd" = plain double-dummy score of the final contract;
"robust" = the opponents reply competently to it (double / outbid, ±1 trick
noise; bid_sim.robust_result), so a call that only wins because biq's rule
continuation gets confused earns nothing. Ranking uses the robust judge.

One deal is one layout: a single disagreement proves little, the totals per
rule over hundreds of deals are what count.

Sources: Q-Plus score sheets (*.qss: D1 = open room, D2 = closed room) and
Q-Plus play logs (DATA/LOG/*.bdl open room, *.cdl closed room). Identical
(deal, calls so far, seat) decisions seen in several files count once.

Usage:
  python3 tools/qplus_auction_mine.py [files/dirs ...] [--rooms closed,open]
          [--top 40] [--jsonl out.jsonl] [--profiles out.jsonl]
With no paths: tools/runs/results/*.qss + Q-Plus's LOCAL-MATCHES and LOG.
--profiles writes one line per Q-Plus call with the caller's hand features
(HCP, suit lengths) and auction context, for modelling Q-Plus's bidding.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backend import bid_sim                                          # noqa: E402
from backend import native_bidder as nb                              # noqa: E402
from backend.bidding_systems import get_system                       # noqa: E402
from backend.dds import DDSolver                                     # noqa: E402
from backend.models import Seat, Vulnerability                       # noqa: E402
from competitive_decision_probe import parse_call, hand_from        # noqa: E402

QPLUS_DATA = ROOT.parent.parent / "WP" / "drive_c" / "games" / "qbridge17" / "DATA"
_SEP = "*" * 60
_SEATS = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_VUL = {"---": Vulnerability.NONE, "N/S": Vulnerability.NS,
        "E/W": Vulnerability.EW, "All": Vulnerability.BOTH}


# ------------------------------------------------------------------ parsing

def file_system(path: str):
    """N/S bidding system a Q-Plus file was played with (e.g. 'A-SAYC-I'),
    or None when the file doesn't say."""
    try:
        head = open(path, errors="replace").read(20000)
    except OSError:
        return None
    m = (re.search(r"conv\.bidding\.N/S = ([^;\s]+)", head)
         or re.search(r"Bidding cnv\s*:\s*N/S:\s*(\S+)", head))
    return m.group(1) if m else None


def _blocks(path: str):
    """Yield (room, lines) for every deal block in a .qss / .bdl / .cdl."""
    text = open(path, errors="replace").read().replace("\r", "")
    if path.lower().endswith(".qss"):
        rooms = {"D1": [], "D2": []}
        for l in text.split("\n"):
            if l[:3] in ("D1 ", "D2 ") or l in ("D1", "D2"):
                rooms[l[:2]].append(l[3:])
        streams = (("open", "\n".join(rooms["D1"])),
                   ("closed", "\n".join(rooms["D2"])))
    else:
        streams = (("open" if path.lower().endswith(".bdl") else "closed", text),)
    for room, s in streams:
        for chunk in s.split(_SEP):
            if re.search(r"^Deal\s*:", chunk, re.M) and re.search(r"^Bids", chunk, re.M):
                yield room, chunk.strip("\n").split("\n")


def _field(lines, key):
    for l in lines:
        if l.startswith(key):
            return l.split(":", 1)[1].strip()
    return None


def _hands(lines):
    i = next(k for k, l in enumerate(lines) if l.startswith("Cards"))
    rows = [l.split(":", 1)[1] if ":" in l else "" for l in lines[i:i + 12]]
    north = [r.split() for r in rows[0:4]]
    south = [r.split() for r in rows[8:12]]
    west = [r[:30].split() for r in rows[4:8]]
    east = [r[30:].split() for r in rows[4:8]]
    h = lambda x: ".".join("".join(c for c in suit if c != "-") for suit in x)
    return {"N": h(north), "E": h(east), "S": h(south), "W": h(west)}


def parse_block(lines):
    """Deal dict, or None when the block is incomplete / unreadable."""
    try:
        label = _field(lines, "Deal")
        dealer = _SEATS[_field(lines, "Dealer")[0]]
        vul = _VUL[_field(lines, "Vuln").split()[0] if _field(lines, "Vuln") else "---"]
        hands = _hands(lines)
        if any(len(v.replace(".", "")) != 13 for v in hands.values()):
            return None
        i = next(k for k, l in enumerate(lines) if l.startswith("Bids"))
        calls = []
        for l in lines[i + 2:]:
            body = l.split(":", 1)[1] if ":" in l else ""
            if "===" in body or not l.strip():
                break
            calls += body.split()
        players = {}
        j = next((k for k, l in enumerate(lines) if l.startswith("Players")), None)
        if j is not None:
            for l in lines[j:j + 4]:
                m = re.search(r":\s*([NESW]):\s*(\S+)", l)
                if m:
                    players[m.group(1)] = m.group(2)
        return {"label": label, "dealer": dealer, "vul": vul, "hands": hands,
                "calls": calls, "players": players}
    except (StopIteration, KeyError, TypeError, AttributeError, IndexError):
        return None


def _call(tok):
    alert = tok.endswith("~")
    t = tok.rstrip("~").strip()
    b = parse_call("p" if t == "-" else t)
    return b, alert


# ------------------------------------------------------------------ judging

def _side(ns_score, seat):
    return ns_score if seat.is_ns() else -ns_score


def _pure_ns(contract, tab, vul):
    if contract is None:
        return 0
    level, suit, decl, dbl = contract
    t = tab[decl.name[0]][bid_sim._STRAIN[suit]]
    sc = bid_sim.duplicate_score(level, suit, t, bid_sim._side_vul(vul, decl), dbl)
    return sc if decl.is_ns() else -sc


def _cstr(c, tab):
    if c is None:
        return "passed out"
    level, suit, decl, dbl = c
    t = tab[decl.name[0]][bid_sim._STRAIN[suit]]
    return (f"{level}{bid_sim._STRAIN[suit]}{'x' * dbl} {decl.name[0]} "
            f"{'=' if t == level + 6 else f'{t - level - 6:+d}'}")


def _rule_key(expl: str) -> str:
    """Group key for a rule: its explanation without numbers / suit detail."""
    e = (expl or "no reason given").split("[")[0]
    e = re.sub(r"\d+", "#", e)
    e = re.sub(r"\b[SHDC]\b|♠|♥|♦|♣", "*", e)
    return e.strip()[:70]


def _context(prefix, seat, dealer):
    """Auction from the caller's view: me/LHO/partner/RHO codes of all
    calls so far, e.g. 'P:1S R:X' (P=partner, L=LHO, R=RHO, M=me)."""
    rel = {0: "M", 1: "L", 2: "P", 3: "R"}
    out, s = [], dealer
    for b in prefix:
        out.append(f"{rel[(s.value - seat.value) % 4]}:{bid_sim._key(b)}")
        s = s.next()
    return " ".join(out)


def _features(hand_str):
    suits = hand_str.split(".")
    hcp = sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(c, 0) for s in suits for c in s)
    return hcp, [len(s) for s in suits]


# ------------------------------------------------------------------ live

def live_divergences(paths, system):
    """First call where the open room (biq N/S) and the closed room (Q-Plus
    N/S) auctions of the SAME board part ways. Up to that call both rooms saw
    identical auctions, so the board's real swing (and its double-dummy
    swing) follows from that one call plus each program's own continuation:
    the live, unflattered measure of a biq call."""
    dds = DDSolver()
    out = []
    for path in paths:
        if not path.lower().endswith(".qss"):
            continue
        text = open(path, errors="replace").read().replace("\r", "")
        for rec in text.split('\nDI "')[1:]:
            m = re.search(r"^RE (-?\d+) (-?\d+)", rec, re.M)
            if not m:
                continue
            re_open, re_closed = int(m.group(1)), int(m.group(2))
            blocks = {}
            for pre, room in (("D1", "open"), ("D2", "closed")):
                lines = [l[3:] for l in rec.split("\n") if l.startswith(pre + " ")]
                blocks[room] = parse_block(lines)
            o, c = blocks["open"], blocks["closed"]
            if o is None or c is None:
                continue
            biq = {s for s, n in o["players"].items() if "biq" in n.lower()} or {"N", "S"}
            ko = [t.rstrip("~") for t in o["calls"]]
            kc = [t.rstrip("~") for t in c["calls"]]
            i = next((k for k in range(min(len(ko), len(kc))) if ko[k] != kc[k]), None)
            if i is None:
                continue
            seat = o["dealer"]
            for _ in range(i):
                seat = seat.next()
            if seat.name[0] not in biq:
                continue                    # Q-Plus E/W diverged (rare)
            prefix = [_call(t)[0] for t in o["calls"][:i]]
            live_b, q_b = _call(o["calls"][i])[0], _call(c["calls"][i])[0]
            if None in prefix or live_b is None or q_b is None:
                continue
            pbn = "N:" + " ".join(o["hands"][s] for s in "NESW")
            tab = dds.solve_dd_table(pbn)
            hands = {_SEATS[s]: hand_from(o["hands"][s]) for s in "NESW"}
            state = nb.parse_auction(seat, o["dealer"], list(prefix),
                                     vulnerability=o["vul"])
            try:
                rb = nb._legalize_bid(nb.decide_bid(state, nb.evaluate_hand(hands[seat]),
                                                    system), state)
            except Exception as e:                               # noqa: BLE001
                rb = nb.passb(f"CRASH {type(e).__name__}")

            def fin(calls):
                bl = [_call(t)[0] for t in calls]
                return None if None in bl else bid_sim.final_contract(bl, o["dealer"])
            fo, fc = fin(o["calls"]), fin(c["calls"])
            dd_sw = bid_sim._imp(_pure_ns(fo, tab, o["vul"]) - _pure_ns(fc, tab, o["vul"]))
            sign = 1 if seat.is_ns() else -1
            same_now = bid_sim._key(rb) == bid_sim._key(live_b)
            out.append({"file": os.path.basename(path), "label": o["label"],
                        "seat": seat.name[0], "hand": o["hands"][seat.name[0]],
                        "vul": o["vul"].name, "dealer": o["dealer"].name[0],
                        "auction": " ".join(bid_sim._key(x) for x in prefix),
                        "biq_live": bid_sim._key(live_b), "qplus": bid_sim._key(q_b),
                        "biq_now": bid_sim._key(rb),
                        "rule": _rule_key(rb.explanation) if same_now
                        else "(rules changed since this run)",
                        "why": (rb.explanation or "")[:100],
                        "open": _cstr(fo, tab), "closed": _cstr(fc, tab),
                        "swing": sign * bid_sim._imp(re_open - re_closed),
                        "dd": sign * dd_sw})
    return out


def report_live(rows, top):
    n = len(rows)
    print(f"{n} live boards where biq's call was the first difference between "
          f"the rooms; real swing {sum(r['swing'] for r in rows):+d} IMP, "
          f"double-dummy swing {sum(r['dd'] for r in rows):+d}")
    same = [r for r in rows if r["rule"] != "(rules changed since this run)"]
    print(f"  current rules still make biq's live call on {len(same)}: real "
          f"{sum(r['swing'] for r in same):+d}, DD {sum(r['dd'] for r in same):+d}")
    kinds = defaultdict(lambda: [0, 0, 0])
    def t(c):
        return "P" if c == "P" else "X" if c in ("X", "XX") else "bid"
    for r in same:
        k = kinds[f"biq {t(r['biq_live'])} / Q-Plus {t(r['qplus'])}"]
        k[0] += 1
        k[1] += r["swing"]
        k[2] += r["dd"]
    for k, v in sorted(kinds.items(), key=lambda kv: kv[1][2]):
        print(f"    {k:22s} {v[0]:4d} boards  real {v[1]:+5d}  DD {v[2]:+5d}")
    per = defaultdict(lambda: [0, 0, 0])
    for r in same:
        per[r["rule"]][0] += 1
        per[r["rule"]][1] += r["swing"]
        per[r["rule"]][2] += r["dd"]
    print(f"\n  rules ranked by DD swing (current rules = live call):")
    print(f"  {'DD':>5} {'real':>5} {'n':>4}  rule")
    for k, v in sorted(per.items(), key=lambda kv: (kv[1][2], kv[1][1]))[:40]:
        print(f"  {v[2]:+5d} {v[1]:+5d} {v[0]:4d}  {k}")
    print(f"\n  worst boards (DD):")
    for r in sorted(same, key=lambda r: (r["dd"], r["swing"]))[:top]:
        print(f"  dd {r['dd']:+3d} real {r['swing']:+3d} {r['file'][:22]:22s} {r['label']} "
              f"{r['seat']} {r['hand']:17s} {r['vul']:4s} d{r['dealer']} "
              f"[{r['auction']}] biq {r['biq_live']} -> {r['open']} | "
              f"Q-Plus {r['qplus']} -> {r['closed']}  ({r['why'][:55]})")


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--rooms", default="closed,open")
    ap.add_argument("--system", default="A-SAYC-I",
                    help="only files Q-Plus played with this N/S system")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--rules", type=int, default=40)
    ap.add_argument("--jsonl", help="write every disagreement here")
    ap.add_argument("--profiles", help="write every Q-Plus call + hand here")
    ap.add_argument("--live", action="store_true",
                    help="judge biq's LIVE calls: first divergence between the "
                         "open and closed room of each board in .qss files")
    a = ap.parse_args()

    paths = []
    for p in a.paths or [str(ROOT / "tools/runs/results"),
                         str(QPLUS_DATA / "LOCAL-MATCHES"), str(QPLUS_DATA / "LOG")]:
        if os.path.isdir(p):
            for ext in ("qss", "bdl", "cdl"):
                paths += sorted(glob.glob(os.path.join(p, f"*.{ext}")))
        else:
            paths.append(p)
    rooms = set(a.rooms.split(","))
    kept = [p for p in paths if file_system(p) == a.system]
    if len(kept) < len(paths):
        print(f"{len(paths) - len(kept)} files skipped (not {a.system} or system "
              f"unknown)")
    paths = kept
    # Q-Plus file system code -> biq's system of the same name.
    biq_system = get_system("Precision90M" if a.system.startswith("P-") else "SAYC")
    if a.live:
        rows = live_divergences(paths, biq_system)
        report_live(rows, a.top)
        if a.jsonl:
            with open(a.jsonl, "w") as fh:
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
        return 0

    # Gather Q-Plus decisions, de-duplicated.
    deals, decisions, seen = {}, [], set()
    profiles = []
    for path in paths:
        for room, lines in _blocks(path):
            if room not in rooms:
                continue
            d = parse_block(lines)
            if d is None:
                continue
            pbn = "N:" + " ".join(d["hands"][s] for s in "NESW")
            deals[pbn] = d
            biq_seats = {s for s, name in d["players"].items() if "biq" in name.lower()}
            seat, prefix, side_keys = d["dealer"], [], {True: [], False: []}
            for tok in d["calls"]:
                b, alert = _call(tok)
                if b is None:
                    break
                sc = seat.name[0]
                key = (pbn, tuple(bid_sim._key(x) for x in prefix), sc)
                if sc not in biq_seats:
                    if key not in seen:
                        seen.add(key)
                        decisions.append((pbn, seat, list(prefix), b, alert, room,
                                          list(side_keys[seat.is_ns()])))
                    side_keys[seat.is_ns()].append(key)
                prefix.append(b)
                seat = seat.next()
    print(f"{len(paths)} files, {len(deals)} distinct deals, "
          f"{len(decisions)} distinct Q-Plus calls", flush=True)

    # Double-dummy tables, batched.
    dds = DDSolver()
    pbns = list(deals)
    tabs = {}
    for i in range(0, len(pbns), 32):
        for p, t in zip(pbns[i:i + 32], dds.solve_dd_tables(pbns[i:i + 32])):
            tabs[p] = t
    print(f"double-dummy tables done ({len(tabs)})", flush=True)

    system = biq_system
    agree = 0
    rows = []
    per_rule = defaultdict(lambda: {"n": 0, "lost": 0, "won": 0, "net": 0,
                                    "dd": 0, "ex": []})
    agrees = {}                 # decision key -> biq's rules made Q-Plus's call
    for k, (pbn, seat, prefix, qb, alert, room, prior) in enumerate(decisions):
        d = deals[pbn]
        tab = tabs[pbn]
        hands = {_SEATS[s]: hand_from(d["hands"][s]) for s in "NESW"}
        evals = {s: nb.evaluate_hand(h) for s, h in hands.items()}
        state = nb.parse_auction(seat, d["dealer"], list(prefix), vulnerability=d["vul"])
        try:
            rb = nb._legalize_bid(nb.decide_bid(state, evals[seat], system), state)
        except Exception as e:                                   # noqa: BLE001
            rb = nb.passb(f"CRASH {type(e).__name__}")
        hcp, lens = _features(d["hands"][seat.name[0]])
        if a.profiles:
            profiles.append({"ctx": _context(prefix, seat, d["dealer"]),
                             "call": bid_sim._key(qb), "alert": alert,
                             "hcp": hcp, "len": lens, "vul": d["vul"].name,
                             "seat": seat.name[0], "dealer": d["dealer"].name[0],
                             "room": room})
        agrees[(pbn, tuple(bid_sim._key(x) for x in prefix), seat.name[0])] = \
            bid_sim._key(rb) == bid_sim._key(qb)
        # On-path: every earlier call by this side is one biq's rules make
        # too, so biq's own partnership could reach this spot live.
        on_path = all(agrees.get(pk, False) for pk in prior)
        if bid_sim._key(rb) == bid_sim._key(qb):
            agree += 1
            continue
        if not nb._is_legal_bid(qb, state):
            continue
        cq = bid_sim._rollout(nb, state, system, hands, evals, qb)
        cb = bid_sim._rollout(nb, state, system, hands, evals, rb)
        opp_ns = not seat.is_ns()
        rq = _side(bid_sim.robust_result(cq, tab, d["vul"], True, opp_ns), seat)
        rbq = _side(bid_sim.robust_result(cb, tab, d["vul"], True, opp_ns), seat)
        dq = _side(_pure_ns(cq, tab, d["vul"]), seat)
        dbq = _side(_pure_ns(cb, tab, d["vul"]), seat)
        imp_r = bid_sim._imp(rbq - rq)        # + = biq's call better
        imp_d = bid_sim._imp(dbq - dq)
        rk = _rule_key(rb.explanation)
        row = {"deal": pbn, "label": d["label"], "room": room,
               "dealer": d["dealer"].name[0], "vul": d["vul"].name,
               "seat": seat.name[0], "hand": d["hands"][seat.name[0]],
               "auction": " ".join(bid_sim._key(x) for x in prefix),
               "qplus": bid_sim._key(qb) + ("~" if alert else ""),
               "biq": bid_sim._key(rb), "rule": rk,
               "why": (rb.explanation or "")[:120],
               "after_qplus": _cstr(cq, tab), "after_biq": _cstr(cb, tab),
               "imp": imp_r, "imp_dd": imp_d, "hcp": hcp, "on_path": on_path}
        rows.append(row)
        pr = per_rule[rk]
        pr["n"] += 1
        pr["net"] += imp_r
        pr["dd"] += imp_d
        if imp_r < 0:
            pr["lost"] += imp_r
        elif imp_r > 0:
            pr["won"] += imp_r
        if (k + 1) % 500 == 0:
            print(f"  {k + 1}/{len(decisions)} calls checked", flush=True)

    n = len(decisions)
    print(f"\nbiq's rules agree with Q-Plus on {agree}/{n} calls "
          f"({100 * agree / max(n, 1):.1f}%); {len(rows)} disagreements judged")
    tot_r = sum(r["imp"] for r in rows)
    tot_d = sum(r["imp_dd"] for r in rows)
    print(f"sum over disagreements, biq's call minus Q-Plus's: robust {tot_r:+d} IMP, "
          f"plain DD {tot_d:+d} IMP  (negative = Q-Plus's call better)")
    alerted = [r for r in rows if r["qplus"].endswith("~")]
    print(f"  of which Q-Plus's call was alerted (conventional, biq may misread "
          f"it in the rollout): {len(alerted)} calls, {sum(r['imp'] for r in alerted):+d} IMP")

    live = [r for r in rows if r["on_path"] and not r["qplus"].endswith("~")]
    print(f"  on-path (biq's partnership could reach the spot), not alerted: "
          f"{len(live)} calls, {sum(r['imp'] for r in live):+d} IMP robust, "
          f"{sum(r['imp_dd'] for r in live):+d} plain DD")
    per_rule = defaultdict(lambda: {"n": 0, "lost": 0, "won": 0, "net": 0, "dd": 0})
    for r in live:
        pr = per_rule[r["rule"]]
        pr["n"] += 1
        pr["net"] += r["imp"]
        pr["dd"] += r["imp_dd"]
        pr["lost" if r["imp"] < 0 else "won"] += r["imp"]
    all_rows, rows = rows, live
    print(f"\nbiq RULES ranked by IMP net (robust judge, on-path, not alerted), worst first:")
    print(f"  {'net':>5} {'lost':>5} {'won':>4} {'dd':>5} {'n':>4}  rule")
    for rk, pr in sorted(per_rule.items(), key=lambda kv: kv[1]["net"])[:a.rules]:
        print(f"  {pr['net']:+5d} {pr['lost']:+5d} {pr['won']:+4d} {pr['dd']:+5d} "
              f"{pr['n']:4d}  {rk}")

    print(f"\nworst single disagreements:")
    for r in sorted(rows, key=lambda r: (r["imp"], r["imp_dd"]))[:a.top]:
        print(f"  {r['imp']:+3d} (dd {r['imp_dd']:+3d}) {r['label']} {r['room'][0]} "
              f"{r['seat']} {r['hand']:18s} vul {r['vul']:4s} "
              f"dlr {r['dealer']} [{r['auction']}] "
              f"Q-Plus {r['qplus']} -> {r['after_qplus']} | biq {r['biq']} -> "
              f"{r['after_biq']}  ({r['why'][:60]})")
    if a.jsonl:
        with open(a.jsonl, "w") as fh:
            for r in all_rows:
                fh.write(json.dumps(r) + "\n")
        print(f"\n{len(all_rows)} disagreements written to {a.jsonl}")
    if a.profiles:
        with open(a.profiles, "w") as fh:
            for p in profiles:
                fh.write(json.dumps(p) + "\n")
        print(f"{len(profiles)} Q-Plus calls written to {a.profiles}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

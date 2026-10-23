#!/usr/bin/env python3
"""How often does biq look wacky (or weak)? Audit of the biq vs Q-Plus matches.

A human partner or opponent judges biq by calls and cards that no good player
would choose. This lists every biq call and card that
  1. differs from Q-Plus (the same spot in the closed room, or for later
     calls, Q-Plus's recorded profile for that call),
  2. breaks a textbook rule (checks below), and
  3. costs: 5+ IMPs on the board for a call, a double-dummy trick that
     changes the contract's result for a card,
and counts them per match and per 100 deals, split into bidding and play.

Bidding checks (each names itself in the report):
  pass-forcing      passed partner's forcing call (2/1, new suit, GF, ...)
  no-length         natural new suit at the 3+ level with 3 or fewer cards
  raise-no-support  raised partner's suit with fewer than 3 cards
                    (partner had bid it once only)
  nt-no-stopper     3NT+ with a void/singleton in a suit the opponents bid
  off-meaning       opening / first response / simple overcall whose HCP is
                    2+ outside what the call shows (system description)
  qplus-never       Q-Plus never makes this call in this spot with a hand
                    like it (profile, HCP +-2 or suit length outside)
Weak (hindsight, whole deal known; only at the first divergence and only
when Q-Plus did better):
  missed-game       biq's side stopped in a partscore with 25+ HCP combined
                    and a double-dummy game that Q-Plus bid
  missed-slam       33+ HCP combined, slam makes, Q-Plus bid it
  sold-out          passed with a fit (8+ cards) at the 2-level when Q-Plus
                    competed and gained

Card checks:
  2nd-hand-high     defender second hand played an honour on a low lead
                    while holding a lower card
  3rd-hand-low      defender third hand did not beat the opponent's winning
                    card when it could
  ruffed-partner    ruffed partner's winning trick
  overtook-partner  played over partner's winning card with a lower card
                    available
  ruff-sluff        defender led a suit both opponents are void in (trumps out)
  discard-winner    discarded a master card while holding a non-master
  unguard-honour    discarded down to a bare honour (Kx->K, Qxx->Qx)
  underlead-ace     opening lead low from an ace against a suit contract

  python3 tools/wacky_audit.py tools/runs/results/*.qss [--top 25]
          [--jsonl out.jsonl]
"""
from __future__ import annotations

import argparse
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
from backend import qplus_model                                      # noqa: E402
from backend.bid_descriptions import describe_bid                    # noqa: E402
from backend.bidding_systems import get_system                       # noqa: E402
from backend.dds import DDSolver                                     # noqa: E402
from backend.models import Suit                                      # noqa: E402
from competitive_decision_probe import hand_from                    # noqa: E402
from qplus_auction_mine import (_call, _context, _features, _pure_ns,  # noqa: E402
                                file_system, parse_block)

_SUITS = "SHDC"
_RK = "AKQJT98765432"
_SU = {"s": 0, "h": 1, "d": 2, "c": 3}
_STRAIN = {"s": 1, "h": 2, "d": 3, "c": 4, "nt": 5}
_SUIT_IDX = {Suit.SPADES: 0, Suit.HEARTS: 1, Suit.DIAMONDS: 2, Suit.CLUBS: 3}


def _hcp_range(s):
    m = re.match(r"(\d+)\s*-\s*(\d+)", s or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(\d+)\+", s or "")
    if m:
        return int(m.group(1)), 40
    return None


# ------------------------------------------------------------------ bidding

def bidding_flags(d, i, system, tab):
    """Textbook flags for the call at index i of the open-room auction."""
    calls = [_call(t)[0] for t in d["calls"]]
    prefix, b = calls[:i], calls[i]
    seat = d["dealer"]
    for _ in range(i):
        seat = seat.next()
    hs = d["hands"][seat.name[0]]
    hcp, lens = _features(hs)
    hand = hand_from(hs)
    st = nb.parse_auction(seat, d["dealer"], list(prefix), vulnerability=d["vul"])
    st = nb._mark_system_alerts(st, system)
    flags = []
    if b.is_pass:
        if nb._partner_was_forcing(st):
            flags.append("pass-forcing")
        return flags, hcp, lens
    if b.is_double or b.is_redouble:
        return flags, hcp, lens
    # Is it natural? Ask biq's own rules what they'd mean by it.
    alert = nb._rules_alert(seat, d["dealer"], list(prefix), b, d["vul"], system)
    natural = not alert
    if b.suit != Suit.NOTRUMP and natural:
        n = lens[_SUIT_IDX[b.suit]]
        partner_suits = st.suit_bid_by_partner
        if b.suit in partner_suits:
            times = partner_suits.count(b.suit)
            if n <= 2 and times == 1 and b.suit not in st.suit_bid_by_me:
                flags.append("raise-no-support")
        elif b.suit not in st.suit_bid_by_me and b.suit not in st.suit_bid_by_opps:
            if b.level >= 3 and n <= 3:
                flags.append("no-length")
    if b.suit == Suit.NOTRUMP and b.level >= 3 and natural:
        for s in set(st.suit_bid_by_opps):
            k = _SUIT_IDX[s]
            if lens[k] <= 1:
                flags.append("nt-no-stopper")
                break
    # Off-meaning: only where the system description is reliable.
    ours = [x for x in st.my_bids + st.partner_bids]
    first_call_of_side = not ours
    simple = (st.opening_bid is None
              or (not st.opp_overcalled and len(st.partner_bids) == 1
                  and not st.my_bids and st.opener_seat == seat.partner())
              or (first_call_of_side and st.opener_seat not in (seat, seat.partner())
                  and b.level <= 2 and len(st.rho_bids + st.lho_bids) == 1))
    if simple:
        try:
            pts, _ln, _h, _art = describe_bid(b, list(prefix), seat, d["dealer"], system)
            r = _hcp_range(pts)
            if r and (hcp < r[0] - 2 or hcp > r[1] + 2):
                flags.append(f"off-meaning({pts} HCP shown, {hcp} held)")
        except Exception:                                        # noqa: BLE001
            pass
    return flags, hcp, lens


def qplus_never(d, i, hcp, lens):
    """Q-Plus's profile for this call here exists and the hand is outside it."""
    calls = [_call(t)[0] for t in d["calls"]]
    seat = d["dealer"]
    for _ in range(i):
        seat = seat.next()
    ctx = qplus_model.context([bid_sim._key(x) for x in calls[:i]],
                              d["dealer"].value, seat.value)
    p = qplus_model.profile(ctx, bid_sim._key(calls[i]))
    if p is None:
        return None
    return not qplus_model.fits(p, hcp, lens, slack=2)


def weak_flags(o, c, i, tab, swing):
    """Hindsight 'weak' checks at the first divergence (Q-Plus did better)."""
    if swing >= 0:
        return []
    calls = [_call(t)[0] for t in o["calls"]]
    seat = o["dealer"]
    for _ in range(i):
        seat = seat.next()
    side = "NS" if seat.is_ns() else "EW"
    hcp = sum(_features(o["hands"][s])[0] for s in side)
    fo = bid_sim.final_contract(calls, o["dealer"])
    fc = bid_sim.final_contract([_call(t)[0] for t in c["calls"]], o["dealer"])
    out = []

    def ours(f):
        return f is not None and (f[2].name[0] in side)

    def lvl(f):
        return f[0] if f is not None else 0

    def is_game(f):
        if f is None:
            return False
        if f[1] == Suit.NOTRUMP:
            return f[0] >= 3
        if f[1] in (Suit.HEARTS, Suit.SPADES):
            return f[0] >= 4
        return f[0] >= 5
    if hcp >= 25 and ours(fc) and is_game(fc) and not (ours(fo) and is_game(fo)):
        out.append(f"missed-game({hcp} HCP)")
    if hcp >= 33 and ours(fc) and lvl(fc) >= 6 and not (ours(fo) and lvl(fo) >= 6):
        out.append(f"missed-slam({hcp} HCP)")
    b = calls[i]
    if (b.is_pass and fo is not None and not ours(fo) and lvl(fo) <= 2
            and ours(fc)):
        fit = max(_features(o["hands"][side[0]])[1][k] + _features(o["hands"][side[1]])[1][k]
                  for k in range(4))
        if fit >= 8:
            out.append("sold-out")
    return out


def audit_bidding(path, system, dds, rows):
    text = open(path, errors="replace").read().replace("\r", "")
    for rec in text.split('\nDI "')[1:]:
        m = re.search(r"^RE (-?\d+) (-?\d+)", rec, re.M)
        if not m:
            continue
        re_open, re_closed = int(m.group(1)), int(m.group(2))
        bl = {}
        for pre, room in (("D1", "open"), ("D2", "closed")):
            lines = [l[3:] for l in rec.split("\n") if l.startswith(pre + " ")]
            bl[room] = parse_block(lines)
        o, c = bl["open"], bl["closed"]
        if o is None or c is None:
            continue
        biq = {s for s, n in o["players"].items() if "biq" in n.lower()} or {"N", "S"}
        swing = bid_sim._imp(re_open - re_closed) * (1 if "N" in biq else -1)
        ko = [t.rstrip("~") for t in o["calls"]]
        kc = [t.rstrip("~") for t in c["calls"]]
        div = next((k for k in range(min(len(ko), len(kc))) if ko[k] != kc[k]), None)
        if div is None:
            continue                     # same auction: nothing to say on bidding
        pbn = "N:" + " ".join(o["hands"][s] for s in "NESW")
        tab = dds.solve_dd_table(pbn)
        seat = o["dealer"]
        auction_str = " ".join(ko)
        for i, tok in enumerate(o["calls"]):
            if i < div:
                seat = seat.next()
                continue
            if seat.name[0] not in biq:
                seat = seat.next()
                continue
            if _call(tok)[0] is None:
                break
            flags, hcp, lens = bidding_flags(o, i, system, tab)
            same_spot = i == div
            qcall = kc[i] if same_spot and i < len(kc) else None
            differs = (qcall is not None and qcall != ko[i])
            qn = qplus_never(o, i, hcp, lens)
            if qn:
                flags.append("qplus-never")
            weak = weak_flags(o, c, i, tab, swing) if same_spot else []
            # What do the CURRENT rules call here (rules only, wire auction)?
            pre = [_call(t)[0] for t in o["calls"][:i]]
            st = nb.parse_auction(seat, o["dealer"], pre, vulnerability=o["vul"])
            try:
                now = bid_sim._key(nb.decide_bid(
                    st, nb.evaluate_hand(hand_from(o["hands"][seat.name[0]])), system))
            except Exception as e:                               # noqa: BLE001
                now = f"CRASH {type(e).__name__}"
            live = bid_sim._key(_call(tok)[0])
            rows.append({"file": os.path.basename(path), "label": o["label"],
                         "seat": seat.name[0], "hand": o["hands"][seat.name[0]],
                         "vul": o["vul"].name, "dealer": o["dealer"].name[0],
                         "i": i, "call": ko[i], "qplus_same_spot": qcall,
                         "first_divergence": same_spot,
                         "differs": bool(differs or qn),
                         "flags": flags, "weak": weak, "swing": swing,
                         "now": now, "still": now == live,
                         "open_auction": auction_str, "closed_auction": " ".join(kc),
                         "hands": {s: o["hands"][s] for s in "NESW"}})
            seat = seat.next()


# ------------------------------------------------------------------ play

def _code(tok):
    return _SU[tok[0]] * 13 + _RK.index(tok[1])


def _name(c):
    return "SHDC"[c // 13] + _RK[c % 13]


def _pbn(hands):
    out = []
    for s in "NESW":
        suits = [[] for _ in range(4)]
        for c in sorted(hands[s]):
            suits[c // 13].append(_RK[c % 13])
        out.append(".".join("".join(x) for x in suits))
    return "N:" + " ".join(out)


def _cards(hand_str):
    return [_SU[su] * 13 + _RK.index(r)
            for su, part in zip("shdc", hand_str.split(".")) for r in part]


def _play(lines):
    d = parse_block(lines)
    if d is None:
        return None
    cl = next((l for l in lines if l.startswith("Contract")), None)
    if cl is None or "passed" in cl:
        return None
    w = cl.split(":", 1)[1].split()
    strain = w[0][1:].lower()
    level = int(w[0][0])
    decl = next(x for x in w if x in ("North", "South", "East", "West"))[0]
    i = next((k for k, l in enumerate(lines) if l.startswith("Tricks")), None)
    if i is None:
        return None
    tricks = []
    for l in lines[i:i + 13]:
        body = l.split(":", 1)[1].split()
        if len(body) < 6:
            break
        tricks.append((body[1], [_code(x.rstrip("+-").lower()[0] + x.rstrip("+-")[1])
                                 for x in body[2:6]]))
    return {"d": d, "strain": strain, "level": level, "decl": decl,
            "contract": " ".join(w[:3]), "tricks": tricks}


def _beats(a, b, led_suit, trump):
    """Does card a beat card b (b currently winning) in a trick?"""
    sa, sb = a // 13, b // 13
    if sa == sb:
        return a < b                       # lower code = higher rank
    if trump is not None and sa == trump:
        return True
    return False


def card_flags(hands, played, seat, card, leader, strain, trump, decl, t, gone):
    """Textbook flags for `card` played by `seat` (hands before the card)."""
    flags = []
    order = "NESW"
    pos = len(played)
    mine = hands[seat]
    su = card // 13
    decl_side = (seat in "NS") == (decl in "NS")
    partner = order[(order.index(seat) + 2) % 4]

    def master(c):
        s = c // 13
        return all(x in gone or x in mine or x // 13 != s or x > c
                   for x in range(s * 13, s * 13 + 13))
    if pos == 0:
        if t == 0 and trump is not None:
            if (card % 13) != 0 and (su * 13) in mine and card // 13 == su:
                flags.append("underlead-ace")
        if not decl_side and trump is not None:
            dh, du = hands[decl], hands[order[(order.index(decl) + 2) % 4]]
            if (not any(x // 13 == su for x in dh) and not any(x // 13 == su for x in du)
                    and any(x // 13 == trump for x in dh)
                    and any(x // 13 == trump for x in du) and su != trump):
                flags.append("ruff-sluff")
        return flags
    led = played[0] // 13
    win_i = 0
    for k in range(1, pos):
        if _beats(played[k], played[win_i], led, trump):
            win_i = k
    win_seat = order[(order.index(leader) + win_i) % 4]
    winning = played[win_i]
    has_led = any(x // 13 == led for x in mine)
    follow = [x for x in mine if x // 13 == led]
    if has_led:
        lower = [x for x in follow if x > card]
        if (not decl_side and pos == 1 and (played[0] % 13) >= 4
                and (card % 13) <= 3 and lower
                and win_seat not in (seat, partner)):
            # 2nd hand played an honour on a low lead, holding a lower card.
            flags.append("2nd-hand-high")
        if (not decl_side and pos == 2 and win_seat != partner
                and not _beats(card, winning, led, trump)
                and any(_beats(x, winning, led, trump) for x in follow)):
            flags.append("3rd-hand-low")
        if (win_seat == partner and pos >= 2 and _beats(card, winning, led, trump)
                and lower and (pos == 3 or master(winning))):
            flags.append("overtook-partner")
    else:
        if trump is not None and su == trump:
            if win_seat == partner and (pos == 3 or master(winning)):
                flags.append("ruffed-partner")
        else:
            # discard
            if master(card) and any(not master(x) for x in mine if x != card):
                flags.append("discard-winner")
            same = [x for x in mine if x // 13 == su]
            for h, n in ((1, 2), (2, 3)):            # Kx -> K, Qxx -> Qx
                hc = su * 13 + h
                if (hc in same and card != hc and len(same) == n
                        and not master(hc)):
                    flags.append("unguard-honour")
    return flags


def audit_play(path, dds, rows):
    text = open(path, errors="replace").read().replace("\r", "")
    order = "NESW"
    for rec in text.split('\nDI "')[1:]:
        rooms = {}
        for pre, room in (("D1", "open"), ("D2", "closed")):
            lines = [l[3:] for l in rec.split("\n") if l.startswith(pre + " ")]
            rooms[room] = _play(lines)
        o, c = rooms["open"], rooms["closed"]
        if o is None:
            continue
        biq = {s for s, n in o["d"]["players"].items() if "biq" in n.lower()} or {"N", "S"}
        strain, decl, level = o["strain"], o["decl"], o["level"]
        trump = None if strain == "nt" else _SU[strain]
        hands = {s: set(_cards(o["d"]["hands"][s])) for s in "NESW"}
        need = level + 6
        # Closed-room play, for "same spot" comparisons.
        same_contract = c is not None and c["contract"] == o["contract"]
        cseq = [x for _, cs in c["tricks"] for x in cs] if same_contract else []
        oseq = []
        gone = set()
        decl_tricks = 0
        for t, (leader, cards) in enumerate(o["tricks"]):
            seat = leader
            played = []
            for pos, card in enumerate(cards):
                res = dds.solve(_STRAIN[strain], order.index(leader), played,
                                [_pbn(hands)], solutions=3)
                if seat in biq and res and card in res:
                    best = max(v[0] for v in res.values())
                    loss = best - res[card][0]
                    decl_side = (seat in "NS") == (decl in "NS")
                    if loss > 0:
                        # Tricks for the side to play, from here, best vs played.
                        mine_so_far = decl_tricks if decl_side else t - decl_tricks
                        fin_best = mine_so_far + best
                        fin_got = mine_so_far + res[card][0]
                        target = need if decl_side else 14 - need
                        result_changed = (fin_best >= target) != (fin_got >= target)
                        flags = card_flags(hands, played, seat, card, leader, strain,
                                           trump, decl, t, gone)
                        k = len(oseq)
                        q_same = (same_contract and cseq[:k] == oseq and k < len(cseq))
                        qcard = _name(cseq[k]) if q_same else None
                        rows.append({"file": os.path.basename(path),
                                     "label": o["d"]["label"], "contract": o["contract"],
                                     "seat": seat, "role": "declarer" if decl_side else "defender",
                                     "trick": t + 1, "pos": pos + 1, "card": _name(card),
                                     "loss": loss, "result_changed": result_changed,
                                     "flags": flags, "qplus_same_spot": qcard,
                                     "differs": qcard is not None and qcard != _name(card),
                                     "trick_so_far": [_name(x) for x in played],
                                     "hand": ".".join(
                                         "".join(_RK[x % 13] for x in sorted(hands[seat])
                                                 if x // 13 == k2) for k2 in range(4))})
                hands[seat].discard(card)
                played.append(card)
                oseq.append(card)
                seat = order[(order.index(seat) + 1) % 4]
            gone.update(cards)
            led = cards[0] // 13
            wi = 0
            for k in range(1, 4):
                if _beats(cards[k], cards[wi], led, trump):
                    wi = k
            ws = order[(order.index(leader) + wi) % 4]
            if (ws in "NS") == (decl in "NS"):
                decl_tricks += 1


# ------------------------------------------------------------------ report

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("qss", nargs="+")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--jsonl")
    ap.add_argument("--min-imp", type=int, default=5)
    ap.add_argument("--no-play", action="store_true", help="bidding only (fast)")
    a = ap.parse_args()
    dds = DDSolver()
    brows, prows = [], []
    deals = defaultdict(int)
    for p in a.qss:
        fs = file_system(p) or ""
        system = get_system("Precision90M" if fs.startswith("P-") else "SAYC")
        n = open(p, errors="replace").read().count('\nDI "')
        deals[os.path.basename(p)] = n
        audit_bidding(p, system, dds, brows)
        if not a.no_play:
            audit_play(p, dds, prows)
        print(f"  {os.path.basename(p)}: {n} deals", file=sys.stderr, flush=True)

    def tb(r):                         # textbook flags excluding the Q-Plus one
        return [f for f in r["flags"] if f != "qplus-never"]
    wacky_b = [r for r in brows if r["differs"] and tb(r) and r["swing"] <= -a.min_imp]
    weak_b = [r for r in brows if r["weak"] and r["swing"] <= -a.min_imp]
    wacky_p = [r for r in prows if r["flags"] and r["result_changed"]
               and r["qplus_same_spot"] != r["card"]]
    costly_p = [r for r in prows if r["result_changed"]]
    tot = sum(deals.values())
    print(f"{len(deals)} matches, {tot} deals\n")
    print(f"{'match':34s} {'deals':>5} {'wacky bid':>9} {'weak bid':>8} "
          f"{'wacky card':>10} {'costly card':>11}")
    for f in sorted(deals):
        print(f"{f[:34]:34s} {deals[f]:5d} "
              f"{sum(1 for r in wacky_b if r['file'] == f):9d} "
              f"{sum(1 for r in weak_b if r['file'] == f):8d} "
              f"{sum(1 for r in wacky_p if r['file'] == f):10d} "
              f"{sum(1 for r in costly_p if r['file'] == f):11d}")
    per = 100 / max(tot, 1)
    print(f"\nstill made by the current rules: wacky calls "
          f"{sum(r['still'] for r in wacky_b)}/{len(wacky_b)}, weak calls "
          f"{sum(r['still'] for r in weak_b)}/{len(weak_b)}")
    print(f"\nper 100 deals: wacky calls {len(wacky_b) * per:.1f} "
          f"(IMPs {sum(r['swing'] for r in wacky_b)}), weak calls "
          f"{len(weak_b) * per:.1f} (IMPs {sum(r['swing'] for r in weak_b)}), "
          f"wacky cards {len(wacky_p) * per:.1f}, result-changing cards "
          f"{len(costly_p) * per:.1f}")

    def count(rows, key):
        c = defaultdict(lambda: [0, 0])
        for r in rows:
            for f in key(r):
                f = f.split("(")[0]
                c[f][0] += 1
                c[f][1] += r.get("swing", r.get("loss", 0))
        return c
    print("\nwacky calls by check:")
    for f, (n, imp) in sorted(count(wacky_b, tb).items(), key=lambda x: x[1][1]):
        print(f"  {f:18s} {n:4d}  IMPs {imp:+d}")
    print("weak calls by check:")
    for f, (n, imp) in sorted(count(weak_b, lambda r: r["weak"]).items(),
                              key=lambda x: x[1][1]):
        print(f"  {f:18s} {n:4d}  IMPs {imp:+d}")
    print("wacky cards by check (DD tricks):")
    for f, (n, tr) in sorted(count(wacky_p, lambda r: r["flags"]).items(),
                             key=lambda x: -x[1][0]):
        print(f"  {f:18s} {n:4d}  tricks {tr}")
    roles = defaultdict(int)
    for r in costly_p:
        roles[r["role"]] += 1
    print("result-changing cards by role:", dict(roles))

    print(f"\nworst wacky calls:")
    for r in sorted(wacky_b, key=lambda r: r["swing"])[:a.top]:
        print(f"  {r['swing']:+3d} {r['file'][:24]:24s} {r['label']} {r['seat']} "
              f"{r['hand']:17s} {r['vul']:4s} d{r['dealer']} call#{r['i']} {r['call']} "
              f"(Q-Plus here: {r['qplus_same_spot'] or '-'}) {', '.join(r['flags'])}"
              f"  [now: {r['now']}{'' if r['still'] else ' FIXED'}]")
        print(f"        biq room:    {r['open_auction']}")
        print(f"        Q-Plus room: {r['closed_auction']}")
    print(f"\nworst weak calls:")
    for r in sorted(weak_b, key=lambda r: r["swing"])[:a.top]:
        print(f"  {r['swing']:+3d} {r['file'][:24]:24s} {r['label']} {r['seat']} "
              f"{r['hand']:17s} call#{r['i']} {r['call']} (Q-Plus {r['qplus_same_spot']}) "
              f"{', '.join(r['weak'])}  [now: {r['now']}{'' if r['still'] else ' FIXED'}]")
        print(f"        biq room:    {r['open_auction']}")
        print(f"        Q-Plus room: {r['closed_auction']}")
    print(f"\nwacky cards:")
    for r in sorted(wacky_p, key=lambda r: -r["loss"])[:a.top]:
        print(f"  -{r['loss']} {r['file'][:24]:24s} {r['label']} {r['contract']:16s} "
              f"{r['seat']} {r['role']:8s} t{r['trick']:2d}/{r['pos']} {r['card']} "
              f"hand {r['hand']} after [{' '.join(r['trick_so_far'])}] "
              f"{', '.join(r['flags'])}"
              + (f" (Q-Plus same spot: {r['qplus_same_spot']})" if r['qplus_same_spot'] else ""))
    if a.jsonl:
        with open(a.jsonl, "w") as fh:
            for r in brows:
                fh.write(json.dumps({"kind": "call", **r}) + "\n")
            for r in prows:
                fh.write(json.dumps({"kind": "card", **r}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

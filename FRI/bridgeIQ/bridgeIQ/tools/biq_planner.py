#!/usr/bin/env python3
"""Adaptive test plan for a continuous biq vs Q-Plus match (biq South, Q-Plus
North/East/West, two rooms; see biq_bluechip_tm.py --continuous).

The planner runs beside the table manager. Every few seconds it reads the
match's results.jsonl and keeps <out>/queue.jsonl a few boards ahead:

  * a fixed share of the boards (plan.json "random_share", default 0.5) are
    queued as random slots, dealt by the TM's seeded random generator: the
    unbiased measure of strength, reported per code version;
  * the rest are TARGETED deals, real deals played normally in both rooms
    and built so that a situation where biq and Q-Plus are known to differ
    (or where biq code just changed) comes up for biq's South hand. The
    closed room gives Q-Plus the same South hand, so every targeted board is
    a direct, end-to-end comparison on that situation.

Which family gets the next targeted board: Thompson sampling on each
family's IMP result for biq (normal posterior), picking the family whose
sampled mean is LOWEST, i.e. where biq looks weakest so far (that is where
fixes pay); families named in plan.json "verify" (code just changed there)
get double weight until they have "verify_boards" new boards on the current
code. A family whose situation rarely comes up at the table ("hit" rate) is
damped.

Explainability: report.md / report.json are rewritten after every board:
strength on random boards per code version, each family's IMPs, hit rate and
its worst boards with both rooms' auctions and biq's reason for each call.

  python3 tools/biq_planner.py --out tools/runs/bluechip/<run> [--once] [--seed N]
plan.json (optional, re-read every cycle) in the same folder:
  {"random_share": 0.5, "ahead": 3, "families": ["ml_adv", ...],
   "families_by_segment": {"SAYC": [...], "Acol": [...]},  (segments.json label)
   "verify": ["wk2_resp"], "verify_boards": 12}
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

from qplus_probe import _deal, _shapes, _band, _lens, _balanced, hcp, pbn_hand, SEATS  # noqa: E402

T = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750, 900, 1100, 1300,
     1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imp(d):
    return sum(abs(d) >= t for t in T) * (1 if d > 0 else -1)


def _suit_hcp(h, s):
    return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(r, 0) for su, r in h if su == s)


def _top2(h, s):
    rs = {r for su, r in h if su == s}
    return ("A" in rs and "K" in rs) or ("K" in rs and "Q" in rs)


_NT = {"ok": lambda h: 15 <= hcp(h) <= 17 and _balanced(h) and max(_lens(h)["S"], _lens(h)["H"]) <= 4}
_WEAK = {"ok": lambda h: hcp(h) <= 9 and max(_lens(h).values()) <= 5}
_WNT = {"ok": lambda h: 12 <= hcp(h) <= 14 and _balanced(h) and max(_lens(h)["S"], _lens(h)["H"]) <= 4}


def _ml_hand(lo=8, hi=14):
    def ok(x):
        sp, hr, mn = x["S"], x["H"], max(x["D"], x["C"])
        return ((sp >= 5 and hr >= 4) or (hr >= 5 and sp >= 4) or (max(sp, hr) == 6 and min(sp, hr) <= 3)
                or (max(sp, hr) == 5 and min(sp, hr) <= 2 and mn >= 5))
    return {"shapes": _shapes(ok), "ok": _band(lo, hi)}


def _weak_two(suits="DHS"):
    def ok(x):
        return any(x[s] == 6 and all(x[o] <= 3 for o in "SH" if o != s) for s in suits)
    return {"shapes": _shapes(ok), "ok": _band(6, 10)}


def _strong_two(suits="DHS"):
    """An Acol strong two (Q-Plus B-2MA.strong / B-2D.strong): a 6-7 card
    diamond or major suit, 18-22 HCP."""
    def ok(x):
        return any(6 <= x[s] <= 7 and all(x[o] <= 4 for o in "SHDC" if o != s) for s in suits)
    return {"shapes": _shapes(ok), "ok": _band(18, 22)}


# Each family: (focus text, dealer, vul choices, specs, deal order, hit test on
# the OPEN room record). South is biq; the closed room seats Q-Plus with it.
FAMILIES = {
    "ml_adv": ("S answers partner's Multi-Landy call over West's 1NT", "W",
               {"W": _NT, "N": _ml_hand()}, "WNSE",
               lambda a: len(a) > 1 and a[0] == "1NT" and a[1] in ("2C", "2D", "2H", "2S", "2NT")),
    "ml_ovc": ("S holds a Multi-Landy hand over East's 1NT", "E",
               {"E": _NT, "S": _ml_hand()}, "ESNW",
               lambda a: len(a) > 1 and a[0] == "1NT"),
    "wk2_resp": ("S has slam values opposite partner's weak two", "N",
                 {"N": _weak_two(), "S": {"ok": _band(15, 21)}}, "NSEW",
                 lambda a: a and a[0] in ("2D", "2H", "2S")),
    "wk2_open": ("S opens a weak two, partner has a strong hand", "S",
                 {"S": _weak_two(), "N": {"ok": _band(15, 21)}}, "SNEW",
                 lambda a: a and a[0] in ("2D", "2H", "2S")),
    "preempt_save": ("partner preempts in spades, S has support, East/West hold hearts", "N",
                     {"N": {"shapes": _shapes(lambda x: x["S"] == 7 and x["H"] <= 2), "ok": _band(5, 9)},
                      "E": {"shapes": _shapes(lambda x: x["H"] >= 6 and x["S"] <= 1), "ok": _band(13, 17)},
                      "S": {"shapes": _shapes(lambda x: x["S"] >= 3 and x["H"] <= 2), "ok": _band(5, 12)}},
                     "NESW", lambda a: a and a[0] in ("2S", "3S", "4S")),
    "unusual_adv": ("S answers partner's Unusual 2NT over East's major", "E",
                    {"E": {"shapes": _shapes(lambda x: max(x["S"], x["H"]) >= 5), "ok": _band(12, 16)},
                     "N": {"shapes": _shapes(lambda x: x["D"] >= 5 and x["C"] >= 5), "ok": _band(7, 12)},
                     "S": {"shapes": _shapes(lambda x: max(x["D"], x["C"]) >= 4)}},
                    "ENSW", lambda a: len(a) > 1 and a[1] == "2NT"),
    "strong2c": ("partner opens a strong 2C, S holds a four-card major", "N",
                 {"N": {"ok": _band(22, 26)},
                  "S": {"shapes": _shapes(lambda x: max(x["S"], x["H"]) == 4), "ok": _band(4, 9)}},
                 "NSEW", lambda a: a and a[0] == "2C"),
    "nt_5spade": ("S has 15-17 balanced with five spades", "S",
                  {"S": {"shapes": [(5, 3, 3, 2), (5, 3, 2, 3), (5, 2, 3, 3)], "ok": _band(15, 17)}},
                  "SNEW", lambda a: bool(a)),
    "third_major": ("S in third seat with a strong four-card major", "N",
                    {"N": _WEAK, "E": _WEAK,
                     "S": {"shapes": _shapes(lambda x: max(x.values()) == 4 and max(x["S"], x["H"]) == 4),
                           "ok": _band(11, 14, lambda h: any(_lens(h)[s] == 4 and _top2(h, s) for s in "SH"))}},
                    "NESW", lambda a: len(a) > 2 and a[0] == "P" and a[1] == "P"),
    # Weak notrump (Acol 12-14) and Acol strong twos.
    "wnt_ovc": ("S holds a two-suiter or long suit over East's weak 1NT", "E",
                {"E": _WNT, "S": _ml_hand()}, "ESNW",
                lambda a: len(a) > 1 and a[0] == "1NT"),
    "wnt_x": ("S opens a weak 1NT, West holds a strong notrump (penalty double, runouts)", "S",
              {"S": _WNT, "W": {"ok": _band(15, 18, _balanced)}, "N": {"ok": _band(0, 7)}}, "SWNE",
              lambda a: len(a) > 1 and a[0] == "1NT" and a[1] == "X"),
    "wnt_5spade": ("S has 12-14 balanced with five spades", "S",
                   {"S": {"shapes": [(5, 3, 3, 2), (5, 3, 2, 3), (5, 2, 3, 3)], "ok": _band(12, 14)}},
                   "SNEW", lambda a: bool(a)),
    "s2_open": ("S opens an Acol strong two (6-7 card suit, 18-22)", "S",
                {"S": _strong_two(), "N": {"ok": _band(0, 12)}}, "SNEW",
                lambda a: a and a[0] in ("2D", "2H", "2S")),
    "s2_resp": ("partner opens an Acol strong two, S answers", "N",
                {"N": _strong_two(), "S": {"ok": _band(0, 12)}}, "NSEW",
                lambda a: a and a[0] in ("2D", "2H", "2S")),
}
VULS = ["None", "NS", "EW", "Both"]


def _shape_weight(sh):
    """How often a hand has this exact (S, H, D, C) shape at the table."""
    return math.prod(math.comb(13, n) for n in sh)


def make_deal(rng, fam):
    """A deal for `fam`. Each constrained hand's shape is drawn with its
    natural frequency, not uniformly over the allowed shapes (uniform made
    preempt_save deal 10- to 13-card suits: boards 790-816)."""
    focus, dealer, specs, order, _ = FAMILIES[fam]
    for _ in range(200):
        sp = {s: (dict(v, shapes=rng.choices(v["shapes"], [_shape_weight(x) for x in v["shapes"]]))
                  if v.get("shapes") else v) for s, v in specs.items()}
        try:
            hands = _deal(rng, sp, order, tries=30)
            break
        except RuntimeError:
            continue
    else:
        hands = _deal(rng, specs, order)
    return {"deal": "N:" + " ".join(pbn_hand(hands[s]) for s in SEATS), "dealer": dealer,
            "vul": rng.choice(VULS), "tags": {"family": fam, "focus": focus}}


# ------------------------------------------------------------------ stats
def load(out: Path):
    rows = []
    try:
        for line in open(out / "results.jsonl"):
            if line.strip():
                rows.append(json.loads(line))
    except OSError:
        pass
    return rows


def boards(rows, start=0):
    """Paired boards: {board: {"open": rec, "closed": rec}} from `start` on."""
    by = defaultdict(dict)
    for r in rows:
        if r["board"] >= start and "room" in r:
            by[r["board"]][r["room"]] = r
    return {n: b for n, b in by.items() if "open" in b and "closed" in b}


def biq_imp(b):
    return imp(b["open"]["ns_score"] + b["closed"]["ns_score"])


def family_of(b):
    o = b["open"]
    if o.get("source") == "queue":
        return (o.get("tags") or {}).get("family", "?")
    return "random"


def stats(bs):
    fam = defaultdict(list)
    for n, b in bs.items():
        fam[family_of(b)].append((n, biq_imp(b), b))
    out = {}
    for f, xs in fam.items():
        v = [x[1] for x in xs]
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) if len(v) > 1 else 7.0
        hit = None
        if f in FAMILIES:
            hit = sum(1 for x in xs if FAMILIES[f][4](x[2]["open"]["auction"].split())) / len(xs)
        out[f] = {"n": len(v), "mean": m, "se": sd / math.sqrt(len(v)), "sum": sum(v),
                  "hit": hit, "boards": xs}
    return out


# ------------------------------------------------------------------ choice
def choose(rng, st, plan, code_now, seg=None):
    fams = (plan.get("families_by_segment") or {}).get(seg) or plan.get("families") or list(FAMILIES)
    fams = [f for f in fams if f in FAMILIES]
    verify = set(plan.get("verify", []))
    vb = int(plan.get("verify_boards", 12))
    best, pick = None, None
    for f in fams:
        s = st.get(f)
        n = s["n"] if s else 0
        mean = s["mean"] if s else 0.0
        se = s["se"] if s and n > 1 else 7.0 / math.sqrt(n + 1)
        draw = rng.gauss(mean, se)                    # lower = biq weaker here
        if f in verify:
            fresh = sum(1 for x in (s["boards"] if s else []) if x[2]["open"].get("code") == code_now)
            if fresh < vb:
                draw -= 4.0                           # check the new code here first
        if s and s["hit"] is not None and n >= 6 and s["hit"] < 0.4:
            draw += 3.0                               # situation rarely arises: damp
        if best is None or draw < best:
            best, pick = draw, f
    return pick


def active_segment(out: Path):
    """Label of the segment the TM is playing now (segments.json + one line
    per handover in handovers.jsonl), or None without segments."""
    try:
        segs = json.loads((out / "segments.json").read_text()).get("segments") or []
    except (OSError, ValueError):
        return None
    try:
        k = sum(1 for line in open(out / "handovers.jsonl") if line.strip())
    except OSError:
        k = 0
    return segs[min(k, len(segs) - 1)].get("label") if segs else None


def unplayed_queue(out: Path, played):
    q = []
    try:
        for line in open(out / "queue.jsonl"):
            if line.strip():
                e = json.loads(line)
                if e["qid"] not in played:
                    q.append(e)
    except OSError:
        pass
    return q


# ------------------------------------------------------------------ report
def _auction_txt(r):
    calls = r["auction"].split()
    d = SEATS.index(r["dealer"])
    out = []
    for k, c in enumerate(calls):
        s = SEATS[(d + k) % 4]
        why = (r.get("explain") or {}).get(str(k))
        out.append(f"{s}:{c}" + (f" [{why[:110]}]" if why and s == "S" else ""))
    return " ".join(out)


def report(out: Path, rows, st, plan, seg=None):
    bs = boards(rows)
    by_code = defaultdict(list)
    for n, b in bs.items():
        if family_of(b) == "random":
            seg = b["open"].get("segment")
            key = (f"segment {seg}, " if seg else "") + f"code {b['open'].get('code', '?')}"
            by_code[key].append(biq_imp(b))
    lines = [f"# Continuous match report ({time.strftime('%Y-%m-%d %H:%M')})", "",
             f"{len(bs)} paired boards. IMPs are biq's (South + Q-Plus partner) vs Q-Plus "
             "holding the same cards at the other table.", "",
             "## Strength on random boards, by segment and code version", ""]
    for c, v in by_code.items():
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) if len(v) > 1 else 0
        lines.append(f"- {c}: {len(v)} boards, {m:+.2f} IMP/board (SE {sd / math.sqrt(len(v)):.2f})")
    lines += ["", "## Targeted families" + (f" (segment {seg}, the one playing now)" if seg else ""), "",
              "| family | focus | boards | IMP/board | SE | situation arose |", "|---|---|---|---|---|---|"]
    for f in sorted(st, key=lambda f: st[f]["mean"]):
        if f == "random":
            continue
        s = st[f]
        hit = f"{100 * s['hit']:.0f}%" if s["hit"] is not None else "-"
        lines.append(f"| {f} | {FAMILIES.get(f, ('?',))[0]} | {s['n']} | {s['mean']:+.2f} | {s['se']:.2f} | {hit} |")
    verify = plan.get("verify", [])
    if verify:
        lines += ["", "## Verification of recent deploys (old code vs new code, per family)", ""]
        code_now = (rows[-1].get("code") if rows else None)
        for f in verify:
            xs = st.get(f, {}).get("boards", [])
            new = [v for _, v, b in xs if b["open"].get("code") == code_now]
            old = [v for _, v, b in xs if b["open"].get("code") != code_now]

            def ms(v):
                if not v:
                    return 0.0, 7.0
                m = sum(v) / len(v)
                sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) if len(v) > 1 else 7.0
                return m, sd / math.sqrt(len(v))
            (mn, sn), (mo, so) = ms(new), ms(old)
            flag = ""
            if len(new) >= 6 and mn < mo - 2 * math.sqrt(sn ** 2 + so ** 2):
                flag = " **WORSE on new code: consider reverting (deploy the previous snapshot)**"
            elif len(new) >= 6 and mn > mo + 2 * math.sqrt(sn ** 2 + so ** 2):
                flag = " (clearly better on new code)"
            lines.append(f"- {f}: new code {len(new)} boards {mn:+.2f} (SE {sn:.2f}); "
                         f"earlier code {len(old)} boards {mo:+.2f} (SE {so:.2f}){flag}")
    lines += ["", "## Worst boards per family (biq's reasons in brackets)", ""]
    for f in sorted(st, key=lambda f: st[f]["mean"]):
        worst = sorted(st[f]["boards"], key=lambda x: x[1])[:3]
        if not worst or worst[0][1] >= 0:
            continue
        lines.append(f"### {f}")
        for n, v, b in worst:
            if v >= 0:
                break
            o, c = b["open"], b["closed"]
            lines.append(f"- board {n}: biq {v:+d} IMP (code {o.get('code', '?')})")
            lines.append(f"  - open (biq S): {_auction_txt(o)} -> {o['contract']} {o['tricks']} tricks, NS {o['ns_score']:+d}")
            lines.append(f"  - closed (Q-Plus holds biq's cards as W): {_auction_txt(c)} -> {c['contract']} {c['tricks']} tricks")
        lines.append("")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    js = {f: {k: v for k, v in s.items() if k != "boards"} for f, s in st.items()}
    js["_by_code_random"] = {c: {"n": len(v), "mean": sum(v) / len(v)} for c, v in by_code.items()}
    (out / "report.json").write_text(json.dumps(js, indent=1))


# ------------------------------------------------------------------ main
def cycle(out: Path, rng, plan, log):
    rows = load(out)
    played = {r.get("qid") for r in rows if r.get("qid")}
    seg = active_segment(out)
    bs = boards(rows, int(plan.get("since_board", 0)))
    if seg is not None:                              # each system has its own weak spots
        bs = {n: b for n, b in bs.items() if b["open"].get("segment") == seg}
    st = stats(bs)
    code_now = rows[-1].get("code") if rows else None
    queue = unplayed_queue(out, played)
    ahead = int(plan.get("ahead", 3))
    share = float(plan.get("random_share", 0.5))
    added = 0
    while len(queue) < ahead:
        if rng.random() < share:
            e = {"random": True}
            what = "random board"
        else:
            fam = choose(rng, st, plan, code_now, seg)
            if fam is None:
                break
            e = make_deal(rng, fam)
            what = FAMILIES[fam][0] + (f" [{seg}]" if seg else "")
        tag = "random" if e.get("random") else e["tags"]["family"]
        e["qid"] = f"{tag}-{int(time.time() * 1000) % 10**10}-{rng.randrange(10**6)}"
        with open(out / "queue.jsonl", "a") as fh:
            fh.write(json.dumps(e) + "\n")
        queue.append(e)
        added += 1
        log(f"queued {e['qid']} ({what})")
    report(out, rows, st, plan, seg)
    return added


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--every", type=float, default=20.0)
    a = ap.parse_args(argv)
    out = Path(a.out)
    rng = random.Random(a.seed)
    logf = open(out / "planner.log", "a")

    def log(msg):
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    while True:
        try:
            plan = json.loads((out / "plan.json").read_text())
        except (OSError, ValueError):
            plan = {}
        try:
            cycle(out, rng, plan, log)
        except Exception as ex:                      # never stop the match's planner
            log(f"cycle failed: {ex!r}")
        if a.once:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()

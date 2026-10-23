#!/usr/bin/env python3
"""Read a probe session: the first trick declarer's side leads in the probe
suit, each Q-Plus defender's card there, set against the design.
  python3 tools/qplus_probe_read.py tools/runs/probes/count1 tools/runs/bluechip/probe_count1"""
import json
import sys

RK = "AKQJT98765432"
O = "NESW"


def first_suit_trick(rec, suit="C"):
    c, d = rec["contract"].split()
    st = c.rstrip("X")[1:]
    tr = None if st == "NT" else st
    leader = O[(O.index(d) + 1) % 4]
    p = rec["play"]
    for t in range(0, len(p) - len(p) % 4, 4):
        tk = p[t:t + 4]
        seats = [O[(O.index(leader) + i) % 4] for i in range(4)]
        if tk[0][1] == suit and seats[0] in "NS":
            return t // 4 + 1, dict(zip(seats, tk)), seats
        def val(x):
            return (2 if tr and x[1] == tr else 1 if x[1] == tk[0][1] else 0, -RK.index(x[0]))
        leader = seats[max(range(4), key=lambda i: val(tk[i]))]
    return None, None, None


AUCTIONS = {"3NT": "1NT P 3NT P P P", "5C": "1C P 5C P P P", "4S": "1S P 4S P P P", "4H": "1H P 4H P P P",
            "6NT": "1NT P 6NT P P P", "1C-1H-1NT-3NT": "1C P 1H P 1NT P 3NT P P P"}


def trick_one(rec, d):
    """att / attS / leads: East's opening lead and West's card to it."""
    au = d.get("contract") or d.get("auction")
    row = {"board": rec["board"], "design": d["design"], "family": d["family"],
           "auction_ok": rec["auction"].replace("PASS", "P") == AUCTIONS[au]}
    row.update({k: d[k] for k in ("contract", "auction", "seq", "dummy", "dv", "W", "N", "E") if k in d})
    p = rec.get("play") or []
    if row["auction_ok"] and len(p) >= 4:
        row.update({"lead": p[0], "dummy_card": p[1], "w_card": p[2], "n_card": p[3]})
    return row


def main():
    pdir, rdir = sys.argv[1], sys.argv[2]
    design = {d["board"]: d for d in map(json.loads, open(f"{pdir}/design.jsonl"))}
    out = []
    for rec in map(json.loads, open(f"{rdir}/results.jsonl")):
        d = design[rec["board"]]
        if d.get("family") in ("att", "attS", "leads"):
            out.append(trick_one(rec, d))
            continue
        ok = rec["auction"].replace("PASS", "P") == AUCTIONS["3NT"]
        t, cards, seats = first_suit_trick(rec) if rec["contract"] != "PASS" else (None, None, None)
        row = {"board": rec["board"], "design": d["design"], "auction_ok": ok, "trick": t,
               "lead_from": seats[0] if seats else None}
        for s in "EW":
            hold = d[s]
            if cards and s in cards and cards[s][1] == "C":
                c = cards[s][0]
                spots = [r for r in hold if RK.index(r) > 4]
                kind = ("honour" if c in "AKQJT" else "high" if spots and c == spots[0] else
                        "low" if spots and c == spots[-1] else "mid")
                row[s] = {"hold": hold, "card": c, "kind": kind, "pos": seats.index(s) + 1,
                          "even": len(hold) % 2 == 0, "nspots": len(spots)}
        row.update({k: d[k] for k in ("ace", "dummy", "N", "dummy_entry", "family") if k in d})
        out.append(row)
    json.dump(out, open(f"{rdir}/probe_read.json", "w"))
    return out


if __name__ == "__main__":
    rows = main()
    fams = {}
    for r in rows:
        f = fams.setdefault(r.get("family", "count"), [0, 0])
        f[0] += 1
        f[1] += r["auction_ok"]
    print(len(rows), "boards;", {k: f"{v[1]}/{v[0]} auctions as scripted" for k, v in fams.items()})

#!/usr/bin/env python3
"""Mid-hand lead study: biq's leads after trick 1 vs Q-Plus's, by kind.

Each lead (declarer side and defence, not the opening lead) is classified
by the suit's history (partner's suit / own earlier suit / suit the other
side led / new suit / trump), whether the double-dummy best card was in
the same suit ("right suit wrong card") or another ("wrong suit"), and
whether the best card was a cash (a master card). Open room = biq N/S,
closed room = Q-Plus N/S on the same deals.

  python3 tools/lead_choice_study.py tools/runs/results/run*.qss
"""
import sys, glob, collections
sys.path.insert(0,'.'); sys.path.insert(0,'tools')
from backend.dds import DDSolver
from wacky_audit import _play, _pbn, _name, _beats, _STRAIN, _SU
order="NESW"
dds=DDSolver()
stats=collections.Counter(); costs=collections.Counter(); ex=collections.defaultdict(list)
qstats=collections.Counter(); qcosts=collections.Counter()
for path in sys.argv[1:]:
    text=open(path,errors='replace').read().replace('\r','')
    for rec in text.split('\nDI "')[1:]:
        for pre, room in (("D1","open"),("D2","closed")):
            lines=[l[3:] for l in rec.split("\n") if l.startswith(pre+" ")]
            o=_play(lines)
            if o is None: continue
            biq={s for s,n in o["d"]["players"].items() if "biq" in n.lower()}
            if room=="open" and not biq: biq={"N","S"}
            who_set = biq if room=="open" else {"N","S"}   # closed room: Q-Plus N/S
            strain,decl=o["strain"],o["decl"]; trump=None if strain=="nt" else _SU[strain]
            from wacky_audit import _cards
            hands={s:set(_cards(o["d"]["hands"][s])) for s in "NESW"}
            led_by=collections.defaultdict(list)   # suit -> seats that led it
            for t,(leader,cards) in enumerate(o["tricks"]):
                if leader in who_set and t>0:
                    res=dds.solve(_STRAIN[strain], order.index(leader), [], [_pbn(hands)], solutions=3)
                    c=cards[0]
                    if res and c in res:
                        best=max(v[0] for v in res.values()); loss=best-res[c][0]
                        decl_side=(leader in "NS")==(decl in "NS")
                        role="decl" if decl_side else "def"
                        su=c//13
                        bests=[k for k,v in res.items() if v[0]==best]
                        same_suit=any(b//13==su for b in bests)
                        partner=order[(order.index(leader)+2)%4]
                        hist=("partner's suit" if partner in led_by[su] else
                              "own earlier suit" if leader in led_by[su] else
                              "opp-led suit" if led_by[su] else "new suit")
                        if trump is not None and su==trump: hist="trump"
                        # master?
                        gone=set().union(*[set(cs) for _,cs in o["tricks"][:t]]) if t else set()
                        mine=hands[leader]
                        def master(x):
                            s=x//13
                            return all(y in gone or y in mine or y//13!=s or y>x for y in range(s*13,s*13+13))
                        cash_avail=any(master(b) for b in bests)
                        kind=f"{role} {strain=='nt' and 'NT' or 'suit'} | {hist} | {'right suit wrong card' if same_suit else 'wrong suit'}{' | best was a cash' if cash_avail and not master(c) else ''}"
                        tgt = (stats,costs) if room=="open" else (qstats,qcosts)
                        tgt[0][kind]+=1; tgt[1][kind]+=loss
                        if room=="open" and loss>0 and len(ex[kind])<4:
                            ex[kind].append(f"{path.split('/')[-1][:14]} {o['d']['label']} {o['contract']} t{t+1} {leader} led {_name(c)} best {' '.join(_name(b) for b in bests[:4])}")
                for k,c in enumerate(cards):
                    s=order[(order.index(leader)+k)%4]; hands[s].discard(c)
                led_by[cards[0]//13].append(leader)
print(f"{'kind':75s} {'biq n':>6} {'lost':>5} {'/100':>5} | {'QP n':>5} {'lost':>5} {'/100':>5}")
for k in sorted(set(stats)|set(qstats), key=lambda k: -(costs[k]-qcosts[k]*stats[k]/max(qstats[k],1))):
    print(f"{k:75s} {stats[k]:6d} {costs[k]:5d} {100*costs[k]/max(stats[k],1):5.1f} | {qstats[k]:5d} {qcosts[k]:5d} {100*qcosts[k]/max(qstats[k],1):5.1f}")
print()
for k in sorted(ex, key=lambda k:-costs[k])[:8]:
    print(k); [print("   ",e) for e in ex[k]]

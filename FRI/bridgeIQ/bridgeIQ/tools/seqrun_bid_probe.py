#!/usr/bin/env python3
"""Reproduce biq's bidding on the flagged seq-run deals to measure bidding
fixes (buckets 1-3) WITHOUT a live run. biq bids all four seats with the
deal's N/S system; for constructive (uncontested) underbids this reproduces
the stop. Reports the contract reached vs the double-dummy makeable, flagging
underbids (stopped below a makeable game/slam)."""
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from backend.models import Bid, Seat
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid
from backend.bidding_systems import get_system
from backend.dds import DDSolver
from backend.models import Hand, Card, Rank, Suit

_R={'A':Rank.ACE,'K':Rank.KING,'Q':Rank.QUEEN,'J':Rank.JACK,'T':Rank.TEN,'9':Rank.NINE,
    '8':Rank.EIGHT,'7':Rank.SEVEN,'6':Rank.SIX,'5':Rank.FIVE,'4':Rank.FOUR,'3':Rank.THREE,'2':Rank.TWO}
_S=[Suit.SPADES,Suit.HEARTS,Suit.DIAMONDS,Suit.CLUBS]
def hand_from(s):
    cards=[]
    for su,part in zip(_S, s.split(".")):
        for c in part:
            if c!='-': cards.append(Card(su,_R[c]))
    return Hand(cards=cards)
def deal_hands(pbn):
    body=pbn.split(":",1)[1].strip()
    hs=body.split()
    order=[Seat.NORTH,Seat.EAST,Seat.SOUTH,Seat.WEST]
    return {order[i]:hand_from(hs[i]) for i in range(4)}
_STR={0:"S",1:"H",2:"D",3:"C",4:"NT"}
def biq_auction(hands, dealer, vul, nssys, ewsys):
    ns,ew=get_system(nssys),get_system(ewsys)
    from backend.models import Vulnerability
    vmap={"None":Vulnerability.NONE,"NS":Vulnerability.NS,"EW":Vulnerability.EW,"All":Vulnerability.BOTH,"Both":Vulnerability.BOTH}
    vv=vmap.get(vul,Vulnerability.NONE)
    auc=[]; seat=dealer
    for _ in range(60):
        st=parse_auction(seat,dealer,list(auc),vulnerability=vv)
        e=evaluate_hand(hands[seat])
        b=decide_bid(st,e, ns if seat.is_ns() else ew)
        auc.append(b)
        if len(auc)>=4 and all(x.is_pass for x in auc[-3:]) and any(not x.is_pass for x in auc[:-3]): break
        if len(auc)>=4 and all(x.is_pass for x in auc): break
        seat=seat.next()
    return auc
def contract(auc, dealer):
    seat=dealer; last=None; decl={}
    for b in auc:
        if not b.is_pass and not b.is_double and not b.is_redouble:
            last=b
            side=seat.is_ns()
            strain=b.suit
            if (side,strain) not in decl: decl[(side,strain)]=seat
        seat=seat.next()
    if last is None: return None
    side=None; sseat=dealer
    # find first to bid the final strain on the winning side
    seat=dealer; declarer=None
    for b in auc:
        if not b.is_pass and not b.is_double and not b.is_redouble and b.suit==last.suit and (seat.is_ns()==_winowner(auc,dealer)):
            declarer=seat; break
        seat=seat.next()
    return last, declarer
def _winowner(auc,dealer):
    seat=dealer; last=None
    for b in auc:
        if not b.is_pass and not b.is_double and not b.is_redouble: last=seat.is_ns()
        seat=seat.next()
    return last

deals=json.loads(Path("tools/runs/seqrun_deals.json").read_text())
dds=DDSolver()
ids=sys.argv[1:] or ["3928-122","3928-101","3928-73","3928-79","3928-94","3928-120"]
from backend.models import Vulnerability
for di in ids:
    d=deals[di]
    hands=deal_hands(d["pbn"])
    dealer={"N":Seat.NORTH,"E":Seat.EAST,"S":Seat.SOUTH,"W":Seat.WEST}[d["dealer"]]
    auc=biq_auction(hands,dealer,d["vul"],d["sys"][0],d["sys"][1])
    res=contract(auc,dealer)
    t=dds.solve_dd_table(d["pbn"])
    ns_dd=max(max(t["N"][k],t["S"][k]) for k in("S","H","D","C","NT"))
    # render auction
    seat=dealer; toks=[]
    for b in auc:
        tok="P" if b.is_pass else ("X" if b.is_double else ("XX" if b.is_redouble else f"{b.level}{b.suit.to_char() if b.suit else '?'}"))
        toks.append(f"{seat.name[0]}:{tok}"); seat=seat.next()
    c=res[0] if res else None
    cs=f"{c.level}{c.suit.to_char() if c.suit else 'N'}" if c else "PASS"
    flag=""
    if c and ns_dd>=12 and c.level<6 and _winowner(auc,dealer): flag=" <<< MISSED SLAM"
    elif c and ns_dd>=10 and c.level<4 and _winowner(auc,dealer): flag=" <<< MISSED GAME"
    print(f"{di} [{d['sys'][0][:4]}] ddNS={ns_dd}  biq→ {cs}{flag}")
    print(f"   probe: {' '.join(toks)}")
    print(f"   live : {d['auc']}")

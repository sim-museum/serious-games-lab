#!/usr/bin/env python3
"""partner_model (learned partner ranges) and the learned game check in
native_bidder. Run: python3 test_partner_model.py"""
import sys

sys.path.insert(0, ".")
import test_qplus_match_fixes as t                       # noqa: E402
from backend import partner_model as PM                 # noqa: E402
from backend import native_bidder as NB                 # noqa: E402
from backend.bidding_systems import get_system          # noqa: E402

fails = 0


def check(name, ok, info=""):
    global fails
    print(f"[{'ok ' if ok else 'BAD'}] {name} {info}")
    fails += not ok


# context / keys / pack
ctx = PM.context(["1H", "P", "2H", "P"], 0, 0)        # N dealer, N to call
check("context", ctx == ["M:1H", "L:P", "P:2H", "R:P"], ctx)
k = PM.keys(ctx)
check("keys", k == {"K1": "M:1H L:P P:2H R:P", "K2": "M:1H P:2H",
                    "K3": "M:1H P:2H | opp 0"}, k)
v = PM.pack(17, [5, 3, 3, 2])
check("pack/unpack", PM.unpack(v) == (17, [5, 3, 3, 2]))
s = PM.summarize([PM.pack(h, [4, 4, 3, 2]) for h in range(6, 16)])
check("summarize", s["n"] == 10 and s["hcp_mean"] == 10.5
      and s["len"][0] == [4, 4, 4], s)

# lookup backs off K1 -> K2 -> K3 and respects MIN_N
prof = {"n": 50, "hcp": [7, 8, 9, 10, 11], "hcp_mean": 9.0,
        "len": [[1, 2, 4], [3, 4, 5], [2, 3, 5], [2, 3, 5]],
        "len_mean": [2.5, 4.0, 3.5, 3.0]}
PM.set_table({"bidder": "x", "profiles": {"K2 M:1H P:2H": prof,
                                          "K1 M:1H L:P P:2H R:P": dict(prof, n=3)}})
got = PM.lookup(ctx)
check("backoff past a thin K1", got is not None and got["level"] == "K2", got)

# The game check: 1H-(P)-2H-(P) opener with 16 HCP + a singleton bids 4H when
# partner's learned range (mean 9) makes 26+; the rules alone invite or pass.
sy = get_system("SAYC")


def call(auction, seat, hand):
    st = NB.parse_auction(t._SEAT[seat], t._SEAT["N"], [t._mk(x) for x in auction.split()])
    return t._str(NB.decide_bid(st, NB.evaluate_hand(t._hand(hand)), sy))


NB.GNET = True
b = call("1h p 2h p", "N", "A4.AKJ65.KQ4.T32")
check("game net leaves a rule bid alone", b != "P", b)
# A pass the rules make below game with values: synthetic context.
PM.set_table({"bidder": "x", "profiles": {
    "K1 M:1S L:P P:2C R:P M:2S L:P P:3S R:P":
        dict(prof, hcp_mean=11.0, len_mean=[3.5, 2.5, 3.0, 5.0])}})
st = NB.parse_auction(t._SEAT["N"], t._SEAT["N"],
                      [t._mk(x) for x in "1s p 2c p 2s p 3s p".split()])
e = NB.evaluate_hand(t._hand("KQJ65.A4.KJ2.J32"))
net = NB._learned_game_net(st, e, sy, NB.passb())
check("net bids 4S: 15+1 TP with partner ~11 and a fit",
      net is not None and t._str(net) == "4S", net and net.explanation)
NB.GNET = False
check("BIQ_GAME_NET off", NB._learned_game_net(st, e, sy, NB.passb()) is None)
NB.GNET = True
PM.set_table({"bidder": "x", "profiles": {}})
check("no profile -> rules stand", NB._learned_game_net(st, e, sy, NB.passb()) is None)

# The shipped table should match the bidder it ships with (warning only:
# a stale table still works, it just describes slightly older rules).
PM._TABLE = None
built = PM.built_with()
if built and built != PM.bidder_fingerprint():
    print(f"[warn] partner profiles built with bidder {built}, current "
          f"{PM.bidder_fingerprint()}: rebuild with tools/biq_profile_build.py")
check("shipped table loads", bool(PM._table().get("profiles")),
      f"{len(PM._table().get('profiles', {}))} profiles")

print(f"\n{fails} failing")
sys.exit(1 if fails else 0)

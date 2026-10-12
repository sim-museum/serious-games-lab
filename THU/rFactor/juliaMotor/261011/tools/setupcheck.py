import glob, os, re
from ibt import header
G = os.path.expanduser("~/gold standard/julia racer")
def setup(f):
    _, _, y, *_ = header(f)
    i = y.find("CarSetup:"); blk = y[i:].split("\n")
    out = {}; path = []
    for ln in blk[1:]:
        if not ln.strip() or not ln.startswith(" "): break
        ind = (len(ln) - len(ln.lstrip()))
        k, _, v = ln.strip().partition(":")
        path = path[:ind-1] + [k]
        if v.strip(): out["/".join(path)] = v.strip()
    return out
IGN = ("LastHotPressure", "LastTemps", "TreadRemaining", "UpdateCount", "CornerWeight", "RideHeight", "ShockDeflection", "CrossWeight")
def clean(s): return {k: v for k, v in s.items() if not any(x in k for x in IGN)}
REF_D = clean(setup(G + "/lotus49_nurburgring nordschleife 2026-06-24 15-53-11.ibt"))
REF_W = clean(setup(glob.glob(G + "/261005/*00-01-05.ibt")[0]))
PLAN = {"17-46-09": "T1 default", "19-18-36": "T1 default", "19-30-13": "T2 default", "19-33-54": "T2 default", "19-34-35": "T2 default",
        "14-52-47": "T3 default bias50", "14-55-22": "T3 default bias50", "14-58-38": "T3 default bias50", "15-03-24": "T3 default bias54", "15-07-27": "T3 default bias58", "15-09-41": "T3 default bias58",
        "15-20-13": "T4 default arms soft", "15-24-06": "T4 default arms mid", "15-28-20": "T4 default arms firm",
        "15-34-40": "T6 default", "15-35-50": "T6 default", "15-45-00": "T6 default",
        "15-54-13": "T7 default fuel20", "16-07-12": "T7 default fuel179.5", "16-12-38": "T7 default fuel(145)",
        "16-19-11": "WW T1", "16-43-06": "WW T1", "16-53-12": "WW T6", "17-03-15": "WW T2"}
print("reference default:", "lotus49_nurburgring nordschleife 2026-06-24 15-53-11 (the game's default template)")
print("reference WW103  : 261005 00-01-05 (the game's WW103 template)\n")
for f in sorted(glob.glob(G + "/261010/*.ibt"), key=lambda p: p.split(" 2026-")[1]):
    st = re.search(r"(\d\d-\d\d-\d\d)\.ibt$", f).group(1); s = clean(setup(f))
    dd = {k: (REF_D.get(k), v) for k, v in s.items() if REF_D.get(k) != v}
    dw = {k: (REF_W.get(k), v) for k, v in s.items() if REF_W.get(k) != v}
    kind = "default" if len(dd) <= len(dw) else "WW103"
    diffs = dd if kind == "default" else dw
    print(f"{st} {os.path.basename(f)[8:-25]:28s} plan: {PLAN.get(st,'?'):22s} | closest {kind:7s} ({len(diffs)} fields differ)")
    for k, (r, v) in sorted(diffs.items()):
        print(f"      {k:45s} ref {r!s:14s} -> {v}")

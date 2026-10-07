#!/usr/bin/env python3
"""Anchored gold <-> ours alignment (GPLVIS-1 lesson, 2026-10-06): a lap-time line is good to +-30 s (+-1 km at the Ring),
so align on LANDMARKS seen in both, then refine each station by image similarity.

usage: anchor_align.py <ours_dir> <gold_dir> <out_json> <anchors "t1:s1,t2:s2,..."> [window_s=10] [gold_viewport=619,140,1898,860]

ours_dir : chase captures named s<NNNNN>.ppm|jpg (our lap distance in metres)
gold_dir : the gold video at 1 fps, g<NNNN>.jpg (NNNN = second, from 1), any size; the viewport is cropped and rescaled to 1920x1080
anchors  : >= 2 (gold second : our metres) pairs seen by eye; between/beyond them t(s) is piecewise linear
Each station s gets the gold second within +-window of the anchor line whose edge map (car masked) matches best.
Writes [{s, t_line, t, cost, cost_line}] -- cost = 1 - cosine similarity of edge maps (0 = identical layout).
"""
import sys, glob, os, json
import numpy as np
from PIL import Image, ImageFilter

ours_dir, gold_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
anc = sorted((float(a.split(':')[1]), float(a.split(':')[0])) for a in sys.argv[4].split(','))   # (s, t)
win = int(sys.argv[5]) if len(sys.argv) > 5 else 10
vp = tuple(map(int, (sys.argv[6] if len(sys.argv) > 6 else '619,140,1898,860').split(',')))
FW, FH = 64, 36

def feat(im):
    im = im.convert('L').resize((256, 144)).filter(ImageFilter.GaussianBlur(1.5))
    a = np.asarray(im, dtype=float)
    e = np.hypot(np.abs(np.diff(a, axis=1))[:-1, :], np.abs(np.diff(a, axis=0))[:, :-1])
    h, w = e.shape
    e[int(h * 0.45):, int(w * 0.28):int(w * 0.72)] = 0      # the car (lower centre)
    e[:int(h * 0.06), :] = 0                                 # HUD / title strip
    e = np.asarray(Image.fromarray(e.astype(np.float32)).resize((FW, FH), Image.BILINEAR))
    e = e - e.mean(); n = np.linalg.norm(e)
    return (e / n).ravel() if n > 0 else e.ravel()

def t_line(s):
    if s <= anc[0][0]:  (s0, t0), (s1, t1) = anc[0], anc[1]
    elif s >= anc[-1][0]: (s0, t0), (s1, t1) = anc[-2], anc[-1]
    else:
        k = max(i for i in range(len(anc)) if anc[i][0] <= s); (s0, t0), (s1, t1) = anc[k], anc[min(k + 1, len(anc) - 1)]
    return t0 + (t1 - t0) * (s - s0) / (s1 - s0) if s1 != s0 else t0

ours = sorted(glob.glob(os.path.join(ours_dir, 's*.ppm')) + glob.glob(os.path.join(ours_dir, 's*.jpg')))
gcache = {}
def gfeat(t):
    if t not in gcache:
        p = os.path.join(gold_dir, f'g{t:04d}.jpg')
        if not os.path.exists(p): gcache[t] = None
        else:
            im = Image.open(p); sx, sy = im.width / 1920, im.height / 1080
            gcache[t] = feat(im.crop((int(vp[0]*sx), int(vp[1]*sy), int(vp[2]*sx), int(vp[3]*sy))))
    return gcache[t]

# candidates per station, then a MONOTONE path (gold time never runs backwards as s grows) by dynamic programming
rows = []
for p in ours:
    s = float(os.path.basename(p)[1:6]); im = Image.open(p)
    f = feat(im.crop((0, int(im.height * 0.05), im.width, im.height)))
    tl = t_line(s); cand = []
    for t in range(int(round(tl)) - win, int(round(tl)) + win + 1):
        g = gfeat(t)
        if g is not None: cand.append((t, 1.0 - float(f @ g)))
    gl = gfeat(int(round(tl)))
    rows.append((s, tl, cand, (1.0 - float(f @ gl)) if gl is not None else None))
INF = 1e9; prev = []                       # DP over (station, candidate): cost, back-pointer
for i, (s, tl, cand, _) in enumerate(rows):
    cur = []
    for (t, c) in cand:
        if i == 0 or not prev: cur.append((c, -1)); continue
        bc, bj = INF, -1
        for j, (pt, _) in enumerate(rows[i - 1][2]):
            if pt <= t and prev[j][0] < bc: bc, bj = prev[j][0], j
        cur.append((bc + c, bj) if bj >= 0 else (INF, -1))
    rows[i] = rows[i] + (cur,); prev = cur
res = [None] * len(rows); j = min(range(len(rows[-1][4])), key=lambda k: rows[-1][4][k][0]) if rows[-1][4] else -1
for i in range(len(rows) - 1, -1, -1):
    s, tl, cand, cl, dp = rows[i]
    if j < 0 or not cand: res[i] = dict(s=s, t_line=round(tl, 1), t=None, cost=None, cost_line=None); j = -1; continue
    t, c = cand[j]
    res[i] = dict(s=s, t_line=round(tl, 1), t=t, cost=round(c, 3), cost_line=round(cl, 3) if cl is not None else None)
    j = dp[j][1]
json.dump(res, open(out, 'w'), indent=0)
c = [r['cost'] for r in res if r['cost'] is not None]
print(f"{len(res)} stations; refined cost median {np.median(c):.3f}; worst 10 %: {np.percentile(c, 90):.3f}")

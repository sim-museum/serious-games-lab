#!/usr/bin/env python3
"""Align a gold chase-cam lap (1 fps frames) to our chase captures (every STEP m) by a circular
monotonic DP over edge-map features; write pair montages for review.

usage: align.py <track> <gold_viewport x0,y0,x1,y1 in 1920x1080> <step_m> [maxadv]
"""
import sys, glob, os, json
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

track = sys.argv[1]
vx0, vy0, vx1, vy1 = map(int, sys.argv[2].split(','))
step = float(sys.argv[3])
maxadv = int(sys.argv[4]) if len(sys.argv) > 4 else 5
B = '/home/admin/jr-parity/p2'
gold = sorted(glob.glob(f'{B}/gold/{track}/g*.jpg'))
OD = os.environ.get('OURS', 'ours'); ours = sorted(glob.glob(f'{B}/{OD}/{track}/s*.jpg'))
FW, FH = 64, 36

def feat(im):
    im = im.convert('L').resize((256, 144)).filter(ImageFilter.GaussianBlur(1.5))
    a = np.asarray(im, dtype=float)
    gx = np.abs(np.diff(a, axis=1))[:-1, :]; gy = np.abs(np.diff(a, axis=0))[:, :-1]
    e = np.hypot(gx, gy)
    h, w = e.shape
    e[int(h*0.48):, int(w*0.30):int(w*0.70)] = 0          # the car (lower centre)
    e = np.asarray(Image.fromarray(e.astype(np.float32)).resize((FW, FH), Image.BILINEAR))
    e = e - e.mean(); n = np.linalg.norm(e)
    return (e / n).ravel() if n > 0 else e.ravel()

def gold_view(p):
    return Image.open(p).crop((vx0, vy0, vx1, vy1))
def ours_view(p):
    im = Image.open(p)                                    # 720x405, HUD band = top 39 rows
    return im.crop((0, 39, im.width, im.height))

G = np.array([feat(gold_view(p)) for p in gold])
O = np.array([feat(ours_view(p)) for p in ours])
C = 1.0 - G @ O.T                                         # (m, n) cost
m, n = C.shape
# speed prior from the PO's own telemetry lap(s) on this track: expected advance per gold second
import csv
def _moving(f):
    k = set()
    for l in open(f):
        p = l.split('\t')
        try:
            if float(p[3]) > 30: k.add(int(float(p[2]) // step))
        except: pass
    return len(k)
tel = max(glob.glob(f'/home/admin/.local/share/julia-racer/THU/rFactor/juliaMotor/demo/native/{track}_racer_*.txt') +
          glob.glob(f'/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/{track}_racer_*.txt'), key=_moving)
bins = [[] for _ in range(n)]
for l in open(tel):
    if l.startswith('#'): continue
    f = l.split('\t')
    try: ld, kmh = float(f[2]), float(f[3])
    except: continue
    if kmh > 30: bins[int(ld // step) % n].append(kmh / 3.6)
allv = [v for b_ in bins for v in b_]; vbar = float(np.median(allv)) if allv else 40.0
v = np.array([np.median(b_) if b_ else vbar for b_ in bins])
v = np.convolve(np.concatenate([v[-3:], v, v[:3]]), np.ones(7)/7, 'valid')
# Anchored alignment: the gold lap runs t_a..t_b (seen by eye); map time -> distance through the
# telemetry's own time-per-bin profile scaled to that lap time, solve the one unknown (the phase j0)
# globally by total image cost, then let each frame refine +-2 steps.
ta, tb = map(int, os.environ['TWIN'].split(','))
dt_bin = step / np.maximum(v, 5.0)                       # seconds per bin at the PO's speed
Tp = dt_bin.sum(); scale = Tp / (tb - ta)                # gold lap time -> telemetry lap time
cum = np.concatenate([[0], np.cumsum(dt_bin)])          # time at the START of each bin, one lap
def prior(j0):
    # bin index at each gold second t (for t in ta..tb), starting at bin j0 at t=ta
    base = cum[j0]; out = []
    for t in range(ta, tb + 1):
        tau = (base + (t - ta) * scale) % Tp
        out.append((j0 + 0) * 0 + int(np.searchsorted(cum, tau, side='right') - 1) % n)
    return out
rng = range(ta, tb + 1)
best = None
for j0 in range(n):
    pj = prior(j0); c = float(np.mean([C[t][pj[k]] for k, t in enumerate(rng)]))
    if best is None or c < best[0]: best = (c, j0, pj)
c0, j0, pj = best
if 'PHASE' in os.environ:
    j0 = int(round(float(os.environ['PHASE']) / step)) % n; pj = prior(j0); c0 = float('nan')
REF = int(os.environ.get('REFINE', '0'))
path = []
for k, t in enumerate(rng):
    js = [(pj[k] + d) % n for d in range(-REF, REF + 1)]
    path.append(min(js, key=lambda jj: C[t][jj]))
gold = gold[ta:tb + 1]; C = C[ta:tb + 1]; m = len(gold)
print('telemetry', os.path.basename(tel), 'lap', round(Tp,1), 's -> gold', tb - ta, 's; phase s0 =', j0*step, 'm; prior cost', round(c0, 3))
cost = [float(C[i][path[i]]) for i in range(m)]
res = [dict(gold=os.path.basename(gold[i]), t=i, ours=os.path.basename(ours[path[i]]),
            s=path[i]*step, cost=round(cost[i], 3)) for i in range(m)]
json.dump(res, open(f'{B}/align_{track}' + ('' if OD == 'ours' else '_' + OD) + '.json', 'w'), indent=0)
print(track, 'frames', m, 'ours', n, 'mean cost', round(float(np.mean(cost)), 3),
      'lap covered', round(len(set(path))/n*100), '%')
# montages: every Kth pair, 6 rows x 2 cols per image
K = max(1, int(sys.argv[5]) if len(sys.argv) > 5 else 4)
sel = list(range(0, m, K)); W, H = 480, 270
for part in range(0, len(sel), 8):
    chunk = sel[part:part+8]
    M = Image.new('RGB', (W*4, H*len(range(0, len(chunk), 2)) + 0), 'white')
    M = Image.new('RGB', (W*4, H*((len(chunk)+1)//2)), 'white'); d = ImageDraw.Draw(M)
    for q, i in enumerate(chunk):
        r, c = q // 2, (q % 2) * 2
        M.paste(gold_view(gold[i]).resize((W, H)), (c*W, r*H))
        M.paste(ours_view(ours[path[i]]).resize((W, H)), ((c+1)*W, r*H))
        d.rectangle([c*W, r*H, c*W+230, r*H+16], fill='black')
        d.text((c*W+3, r*H+2), f'GOLD t={i+ta}s   ours s={path[i]*step:.0f} c={cost[i]:.2f}', fill='yellow')
    M.save(f'{B}/pairs_{track}_' + ('' if OD == 'ours' else OD + '_') + f'{part//8:02d}.jpg', quality=82)

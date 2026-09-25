import sys, json, numpy as np
from PIL import Image
t = sys.argv[1]; import os; OD = os.environ.get('OURS','ours'); r = json.load(open(f'align_{t}.json'))
def patch(im, box):
    a = np.asarray(im.convert('RGB').resize((320, 180)), dtype=float)
    x0, y0, x1, y1 = box; return a[y0:y1, x0:x1].reshape(-1, 3)
G = []; O = []
for x in r:
    g = Image.open(f'gold/{t}/{x["gold"]}').crop((0, 144, 1280, 952))
    o = Image.open(f'{OD}/{t}/{x["ours"]}'); o = o.crop((0, 39, o.width, o.height))
    # road: just behind/beside the car's rear wheels, lower frame (both views place the car there)
    for box in ((40, 150, 90, 175), (230, 150, 280, 175)):
        G.append(np.median(patch(g, box), axis=0)); O.append(np.median(patch(o, box), axis=0))
G = np.array(G); O = np.array(O)
# keep grey samples only (road), drop grass/kerb patches: low saturation
def grey(a): return (a.max(1) - a.min(1)) < 25
kg, ko = grey(G), grey(O)
print(t, 'road median RGB gold', np.median(G[kg], 0).round(), 'ours', np.median(O[ko], 0).round(),
      ' ratio', (np.median(O[ko], 0).mean() / np.median(G[kg], 0).mean()).round(2), f' n={kg.sum()}/{ko.sum()}')

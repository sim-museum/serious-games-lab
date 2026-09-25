import sys, json, numpy as np
from PIL import Image
t = sys.argv[1]; import os; OD = os.environ.get('OURS','ours'); r = json.load(open(f'align_{t}.json'))
def grasspix(im):
    a = np.asarray(im.convert('RGB').resize((320, 180)), dtype=float)[80:180]   # lower frame, ground
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    m = (G > B + 12) & (G >= R - 25) & (R > B) & ((a.max(-1) - a.min(-1)) > 30)                                  # vegetation-ish
    return a[m]
g = np.concatenate([grasspix(Image.open(f'gold/{t}/{x["gold"]}').crop((0, 144, 1280, 952))) for x in r])
o = np.concatenate([grasspix((lambda im: im.crop((0, 39, im.width, im.height)))(Image.open(f'{OD}/{t}/{x["ours"]}'))) for x in r])
print(t, 'grass median RGB gold', np.median(g, 0).round(), 'ours', np.median(o, 0).round(),
      'luma ratio', round(float(np.median(o @ [.3,.59,.11]) / np.median(g @ [.3,.59,.11])), 2))

#!/usr/bin/env python3
"""Render the Julia-simulated lap to an MP4: track geometry + moving car + HUD.

Reads /tmp/demo_track.csv (collision triangles) and /tmp/vid_lap.csv (dense
trajectory with heading), draws frames with Pillow, encodes with ffmpeg.
"""
import csv, math, os, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FPS = 30
VIDEO_SECONDS = 40            # compress the ~254 s lap into ~40 s
OUT = os.path.join(os.path.dirname(__file__), "zandvoort_lap.mp4")
FRAMEDIR = "/tmp/vidframes"

def readcsv(p):
    with open(p) as f: return list(csv.DictReader(f))

trows = readcsv('/tmp/demo_track.csv')
tris = [[float(r[k]) for k in ('x1','z1','x2','z2','x3','z3')] for r in trows]
ttype = [r.get('type','road') for r in trows]
SURF = {'grass':(26,46,30), 'sand':(70,62,42), 'road':(44,50,60)}
lap  = readcsv('/tmp/vid_lap.csv')
xs = [float(s['x']) for s in lap]; zs = [float(s['z']) for s in lap]
spd = [float(s['speed']) for s in lap]
vmin, vmax = min(spd), max(spd)

# world->screen transform (fit track triangles, with margin), z grows "into" screen
allx = [t[i] for t in tris for i in (0,2,4)] + xs
allz = [t[i] for t in tris for i in (1,3,5)] + zs
xmin,xmax,zmin,zmax = min(allx),max(allx),min(allz),max(allz)
pad = 70
sx = (W-2*pad)/(xmax-xmin); sz = (H-2*pad-80)/(zmax-zmin); sc = min(sx,sz)
ox = (W - sc*(xmax-xmin))/2; oz = pad
def X(x): return ox + (x-xmin)*sc
def Y(z): return oz + (z-zmin)*sc      # screen-down = +z

def speed_color(v):
    t = max(0,min(1,(v-vmin)/(vmax-vmin)))
    r = int(255*min(1,t*2)); g = int(255*min(1,2-t*2)); b = int(120*(1-t))
    return (r,g,b)

# fonts
def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()
F1, F2, F3 = font(34), font(20), font(15)

# precompute static track layer once
base = Image.new("RGB",(W,H),(10,13,18))
bd = ImageDraw.Draw(base)
# draw grass and sand first, road on top, so the racing surface reads clearly
for layer in ('grass','sand','road'):
    col = SURF[layer]
    for t,ty in zip(tris,ttype):
        if ty!=layer: continue
        bd.polygon([(X(t[0]),Y(t[1])),(X(t[2]),Y(t[3])),(X(t[4]),Y(t[5]))], fill=col)
# faint full racing line
pts=[(X(xs[i]),Y(zs[i])) for i in range(len(xs))]
bd.line(pts, fill=(90,98,110), width=1)

if os.path.exists(FRAMEDIR): shutil.rmtree(FRAMEDIR)
os.makedirs(FRAMEDIR)

nframes = FPS*VIDEO_SECONDS
N = len(lap)
trail = 90  # samples of speed-coloured trail behind the car
for f in range(nframes):
    idx = int(f/(nframes-1)*(N-1))
    im = base.copy(); d = ImageDraw.Draw(im)
    # speed-coloured trail
    a = max(0, idx-trail)
    for i in range(a+1, idx+1):
        d.line([(X(xs[i-1]),Y(zs[i-1])),(X(xs[i]),Y(zs[i]))],
               fill=speed_color(spd[i]), width=4)
    # car as an oriented triangle
    cx,cy = X(xs[idx]),Y(zs[idx]); yaw=float(lap[idx]['yaw'])
    # screen heading: world (cos yaw, sin yaw) in (x,z) -> screen (+x right, +z down)
    hx,hy = math.cos(yaw), math.sin(yaw); L=11
    px,py = -hy, hx
    d.polygon([(cx+hx*L, cy+hy*L),(cx-hx*7+px*6, cy-hy*7+py*6),
               (cx-hx*7-px*6, cy-hy*7-py*6)], fill=(255,255,255), outline=(0,0,0))
    # HUD
    s = lap[idx]; v=float(s['speed']); g=int(float(s['gear']))
    thr=float(s['throttle']); brk=float(s['brake']); t=float(s['t']); dist=float(s['lapdist'])
    d.text((24,18), "juliaMotor — Julia engine driving rFactor's Vanwall @ Zandvoort", font=F2, fill=(200,210,220))
    d.text((24, H-66), f"{v:5.0f} km/h", font=F1, fill=(255,255,255))
    d.text((240,H-58), f"gear {g}", font=F2, fill=(180,190,200))
    d.text((240,H-34), f"lap {t:5.1f} s   ·   {dist:4.0f} m", font=F3, fill=(140,150,160))
    # throttle/brake bars
    bx=420
    d.rectangle([bx,H-58,bx+140*thr,H-46], fill=(90,224,138))
    d.rectangle([bx,H-42,bx+140*brk,H-30], fill=(240,120,90))
    d.text((bx,H-78), "throttle / brake", font=F3, fill=(120,130,140))
    im.save(f"{FRAMEDIR}/f{f:05d}.png")

print(f"rendered {nframes} frames")
cmd = ["ffmpeg","-y","-r",str(FPS),"-i",f"{FRAMEDIR}/f%05d.png",
       "-c:v","libx264","-pix_fmt","yuv420p","-crf","20", OUT]
subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
print("wrote", OUT, os.path.getsize(OUT), "bytes")

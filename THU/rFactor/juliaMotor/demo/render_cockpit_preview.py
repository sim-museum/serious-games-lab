#!/usr/bin/env python3
"""Render a still preview of the cockpit view from /scene.json + a /step pose,
by perspective-projecting the track triangles from the driver's eye (painter's
algorithm, flat-shaded by normal·sun).  This verifies the 3D geometry is
world-placed and the cockpit camera frames the track sensibly — independent of
the browser's WebGL path (which we can't headless-screenshot here).

  python3 render_cockpit_preview.py scene.json pose.json out.png
"""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont

scene = json.load(open(sys.argv[1]))
pose  = json.load(open(sys.argv[2]))
out   = sys.argv[3] if len(sys.argv) > 3 else "cockpit_preview.png"

W, H = 1280, 800
FOV = math.radians(72)
f = (W/2) / math.tan(FOV/2)              # focal length in px
cx0, cy0 = W/2, H/2

px, py, pz, h = pose["x"], pose["y"], pose["z"], pose["h"]
eye = (px + math.cos(h)*0.05, py + 1.12, pz + math.sin(h)*0.05)
# camera basis: forward, right, up (look down, matching the client's lookAt)
pitch = math.atan2(2.2+1.12, 9.0)
fwd = (math.cos(h)*math.cos(pitch), -math.sin(pitch), math.sin(h)*math.cos(pitch))
# right = forward × worldup, then up = right × forward
wu = (0,1,0)
def cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    n=math.sqrt(sum(c*c for c in a)) or 1; return (a[0]/n,a[1]/n,a[2]/n)
right = norm(cross(fwd, wu))
up = norm(cross(right, fwd))
sun = norm((0.4,1.0,0.25))

COL = {"road":(55,55,59),"curb":(177,70,58),"grass":(63,122,54),"sand":(205,187,134),
       "foliage":(46,91,40),"dark":(25,25,25),"structure":(155,149,139)}

def to_cam(p):
    d=(p[0]-eye[0], p[1]-eye[1], p[2]-eye[2])
    return (d[0]*right[0]+d[1]*right[1]+d[2]*right[2],
            d[0]*up[0]+d[1]*up[1]+d[2]*up[2],
            d[0]*fwd[0]+d[1]*fwd[1]+d[2]*fwd[2])     # (x_r, y_u, z_fwd)

img = Image.new("RGB",(W,H),(156,195,232))
d = ImageDraw.Draw(img)
# ground band below horizon
d.rectangle([0,H//2,W,H], fill=(58,110,48))

polys = []   # (depth, screen_pts, shaded_color)
for cat, g in scene["cats"].items():
    P, N = g["pos"], g["nrm"]
    base = COL.get(cat,(140,140,140))
    for i in range(0, len(P), 9):
        v = [(P[i],P[i+1],P[i+2]),(P[i+3],P[i+4],P[i+5]),(P[i+6],P[i+7],P[i+8])]
        c = [to_cam(p) for p in v]
        if max(p[2] for p in c) < 0.3: continue          # fully behind
        if min(p[2] for p in c) < 0.05: continue         # clip near plane (skip)
        scr=[]; ok=True; depth=0
        for xr,yu,zf in c:
            sx = cx0 + f*xr/zf; sy = cy0 - f*yu/zf; depth += zf
            if abs(sx)>4*W or abs(sy)>4*H: ok=False; break
            scr.append((sx,sy))
        if not ok: continue
        nrm=(N[i],N[i+1],N[i+2])
        lit = max(0.25, abs(nrm[0]*sun[0]+nrm[1]*sun[1]+nrm[2]*sun[2]))*0.85+0.25
        col=tuple(min(255,int(b*lit)) for b in base)
        polys.append((depth/3, scr, col))

polys.sort(key=lambda t:-t[0])      # far first (painter's)
for _,scr,col in polys:
    d.polygon(scr, fill=col)

# simple cockpit hint: dark cowl + steering wheel at bottom centre
d.rectangle([0,H-150,W,H], fill=(14,40,28))
d.ellipse([W/2-110,H-120,W/2+110,H+90], outline=(25,25,28), width=22)
# HUD
try:
    fb=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",34)
    fs=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",18)
except Exception: fb=fs=ImageFont.load_default()
d.rectangle([12,H-92,400,H-12],fill=(0,0,0))
d.text((22,H-86),f'{round(pose["kmh"])} km/h   gear {pose["gear"]}',font=fb,fill=(235,235,235))
ont="on track" if pose["ontrack"] else "OFF TRACK"
d.text((22,H-42),f'rpm {round(pose["rpm"])}   {ont}   lap {pose["laps"]}  {round(pose["lapdist"])} m',
       font=fs,fill=(107,208,107) if pose["ontrack"] else (255,107,107))
d.text((14,14),"juliaMotor cockpit — 1958 Vanwall @ Zandvoort — motion governed by the Julia physics engine",
       font=fs,fill=(255,216,107))
img.save(out); print("wrote",out,img.size,"tris drawn",len(polys))

#!/usr/bin/env python3
"""Render a still of the *driving view* — the same geometry the browser client
draws (/track.json) under the same car-up chase camera as drive.html — given a
car pose from the server's /step.  Used to verify the drivable sim visually
without a browser.

  python3 render_drive_view.py track.json pose.json out.png
"""
import json, math, sys
from PIL import Image, ImageDraw, ImageFont

track = json.load(open(sys.argv[1]))
pose  = json.load(open(sys.argv[2]))
out   = sys.argv[3] if len(sys.argv) > 3 else "drive_view.png"

W, H = 1280, 800
ZOOM = 6.5                       # screen px per metre (matches drive.html)
AX, AY = W/2, H*0.62             # car anchor on screen
cx, cz, h = pose["x"], pose["z"], pose["h"]
a = -math.pi/2 - h               # heading → up
ca, sa = math.cos(a), math.sin(a)

def to_screen(X, Z):
    dx, dz = (X - cx)*ZOOM, (Z - cz)*ZOOM
    return (AX + ca*dx - sa*dz, AY + sa*dx + ca*dz)

img = Image.new("RGB", (W, H), (22, 36, 15))
d = ImageDraw.Draw(img)

VIEW_R = 1.4 * max(W, H) / ZOOM   # cull triangles beyond this (m) from the car
def draw_tris(arr, color):
    for i in range(0, len(arr), 6):
        x1,z1,x2,z2,x3,z3 = arr[i:i+6]
        mxx = (x1+x2+x3)/3; mzz = (z1+z2+z3)/3
        if abs(mxx-cx) > VIEW_R or abs(mzz-cz) > VIEW_R:
            continue
        d.polygon([to_screen(x1,z1), to_screen(x2,z2), to_screen(x3,z3)], fill=color)

draw_tris(track["grass"], (47, 82, 38))
draw_tris(track["sand"],  (185,164,104))
draw_tris(track["road"],  (59, 59, 64))

# racing line (faint), near the car
line = track["line"]
pts = []
for i in range(0, len(line), 2):
    if abs(line[i]-cx) < VIEW_R and abs(line[i+1]-cz) < VIEW_R:
        pts.append(to_screen(line[i], line[i+1]))
if len(pts) > 1:
    d.line(pts, fill=(90, 90, 102), width=2)

# the car (4.0 m × 1.7 m) at screen anchor, pointing up
def carpt(lx, ly):
    # local car frame (lx forward, ly left) → world offset → screen
    fwd = (math.cos(h), math.sin(h)); lft = (-math.sin(h), math.cos(h))
    return to_screen(cx + lx*fwd[0] + ly*lft[0], cz + lx*fwd[1] + ly*lft[1])
L, Wd = 4.0, 1.7
body = [carpt(L*0.5,0), carpt(L*0.18,Wd*0.5), carpt(-L*0.5,Wd*0.42),
        carpt(-L*0.5,-Wd*0.42), carpt(L*0.18,-Wd*0.5)]
d.polygon(body, fill=(226, 59, 59))
for px,py in [(1.2,0.85),(1.2,-0.85),(-1.3,0.9),(-1.3,-0.9)]:
    wheel = [carpt(px-0.33,py-0.18), carpt(px+0.33,py-0.18),
             carpt(px+0.33,py+0.18), carpt(px-0.33,py+0.18)]
    d.polygon(wheel, fill=(17,17,17))

# HUD text
try:
    fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except Exception:
    fb = fs = ImageFont.load_default()
d.rectangle([12, H-92, 360, H-12], fill=(0,0,0))
d.text((22, H-86), f'{round(pose["kmh"])} km/h   gear {pose["gear"]}', font=fb, fill=(235,235,235))
ontrack = "on track" if pose["ontrack"] else "OFF TRACK"
oc = (107,208,107) if pose["ontrack"] else (255,107,107)
d.text((22, H-42), f'rpm {round(pose["rpm"])}   {ontrack}   lap {pose["laps"]}  {round(pose["lapdist"])} m',
       font=fs, fill=oc)
d.text((14, 14), "juliaMotor — 1958 Vanwall @ Zandvoort — motion governed by the Julia physics engine",
       font=fs, fill=(255,216,107))

img.save(out)
print("wrote", out, img.size)

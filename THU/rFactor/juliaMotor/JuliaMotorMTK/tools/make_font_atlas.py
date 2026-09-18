#!/usr/bin/env python3
"""TEXTHUD-1 (GOLDMATCH-JR-1 S1, 2026-09-17): bake a font atlas for julia's text HUD.

The gold (260915_gpl_wg_race_gold.mp4) carries a proportional-text timing overlay on every
cockpit frame -- lap times, Player/Leader Relative, Track Position with driver names -- and our
HUD had "no font, only 7-seg digits and quads". julia has no TTF rasteriser, so the atlas is
baked here with PIL and shipped as two small files the sim reads with plain `read`:
  font<px>.a8   raw 8-bit coverage, W*H bytes, row-major, top row first
  font<px>.txt  "W H lineheight ascent" then one line per glyph: "code x y w h xoff yoff adv"
Usage: make_font_atlas.py [px=18] [ttf]
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont
px = int(sys.argv[1]) if len(sys.argv) > 1 else 18
ttf = sys.argv[2] if len(sys.argv) > 2 else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
out = os.path.join(os.path.dirname(__file__), "..", "..", "demo", "native", "assets")
font = ImageFont.truetype(ttf, px)
asc, desc = font.getmetrics(); lineh = asc + desc
W = 512; x = y = 0; rowh = 0; glyphs = []
img = Image.new("L", (W, 512), 0); draw = ImageDraw.Draw(img)
for code in range(32, 127):
    ch = chr(code)
    l, t, r, b = font.getbbox(ch)            # ink box relative to the origin (top-left, ascent line at y=asc? no: PIL origin is top)
    w, h = max(1, r - l), max(1, b - t)
    adv = font.getlength(ch)
    if x + w + 1 > W: x = 0; y += rowh + 1; rowh = 0
    draw.text((x - l, y - t), ch, font=font, fill=255)
    glyphs.append((code, x, y, w, h, l, t, adv))
    x += w + 1; rowh = max(rowh, h)
H = y + rowh + 1
img = img.crop((0, 0, W, H))
with open(os.path.join(out, f"font{px}.a8"), "wb") as f: f.write(img.tobytes())
with open(os.path.join(out, f"font{px}.txt"), "w") as f:
    f.write(f"{W} {H} {lineh} {asc}\n")
    for g in glyphs: f.write("%d %d %d %d %d %d %d %.3f\n" % g)
print(f"font{px}: {W}x{H} atlas, {len(glyphs)} glyphs, line {lineh}px, from {os.path.basename(ttf)}")

"""
Pixel probe + zoomed body crop.

WHY: The cleanup strategy depends on real color values, not assumptions.
If the body is "blue-ish" and the leader lines / label text are neutral grey,
we can build an alpha mask from COLOR SATURATION and throw away the grey ink
without touching the anatomy. This script prints sampled values and writes a
3x zoom of the body region so a human can confirm what survives.

Run:  python build/probe_pixels.py
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
rgba = np.array(Image.open(ROOT / "rs=h_{640}.webp").convert("RGBA"))
rgb = rgba[:, :, :3].copy()
rgb[rgba[:, :, 3] < 250] = (255, 255, 255)

# (label, x, y) -- hand-picked from the gridded preview so each sample lands
# on a meaningfully different kind of pixel.
SAMPLES = [
    ("white background",        700, 100),
    ("white background 2",      300, 620),
    ("body torso light blue",   500, 280),
    ("body torso blue 2",       490, 260),
    ("skeleton linework",       500, 300),
    ("body left arm",           447, 300),
    ("body leg",                500, 470),
    ("shoulder red glow",       459, 240),
    ("shoulder red glow edge",  465, 225),
    ("hip red glow",            516, 375),
    ("knee red glow",           532, 490),
    ("grey leader line L",      390, 185),
    ("grey leader line R",      620, 230),
    ("grey label bar",          130, 140),
    ("dark bullet text",        100, 175),
    ("logo black",              470, 45),
]

print(f"{'sample':<28} {'x':>5} {'y':>5}  {'RGB':>16}  {'sat':>6}  {'min':>4}  {'B-R':>6}")
print("-" * 80)
for label, x, y in SAMPLES:
    p = rgb[y, x].astype(int)
    mx, mn = p.max(), p.min()
    sat = 0 if mx == 0 else (mx - mn) / mx
    print(f"{label:<28} {x:>5} {y:>5}  {str(tuple(p)):>16}  {sat:>6.3f}  {mn:>4}  {p[2]-p[0]:>6}")

# ---- Zoomed crop of just the anatomical figure ------------------------------
# x 420..585 and y 140..640 keeps the whole figure plus a small margin, and
# excludes all six label panels entirely.
x0, y0, x1, y1 = 415, 135, 590, 640
crop = Image.fromarray(rgb[y0:y1, x0:x1])
zoom = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
out = ROOT / "build" / "body-zoom.png"
zoom.save(out)
print(f"\nbody zoom written  : {out}  ({zoom.width}x{zoom.height})")
print("DONE")

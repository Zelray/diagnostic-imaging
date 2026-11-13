"""
Source-asset reconnaissance for the interactive anatomy hero.

WHAT THIS DOES (plain English):
Before we can rebuild the infographic as a web page, we need exact numbers,
not eyeballed guesses. This script opens the one source WebP and reports:
  1. whether the image really has a usable alpha channel,
  2. where the six red "pain glows" are, in source-pixel coordinates,
  3. the bounding box of the blue anatomical figure,
  4. how much of the image is near-white background vs. grey text/lines.

It also writes a grid-annotated preview PNG so a human can visually confirm
every coordinate the computer found. Nothing here modifies the original.

Run:  python build/analyze_source.py
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Paths. Everything is relative to the folder that holds this script's parent,
# so the script keeps working if the whole Infographics folder is moved.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "rs=h_{640}.webp"
OUT_DIR = ROOT / "build"

# ---------------------------------------------------------------------------
# 1. Load. WebP can carry alpha; we check it instead of assuming.
#    We build two views: the raw RGBA, and an RGB version flattened onto white
#    (which is what a browser would show if alpha were not actually used).
# ---------------------------------------------------------------------------
rgba = np.array(Image.open(SOURCE).convert("RGBA"))
h, w = rgba.shape[:2]
alpha = rgba[:, :, 3]
print(f"source size        : {w} x {h}")
print(f"alpha min/max/mean : {alpha.min()} / {alpha.max()} / {alpha.mean():.1f}")
print(f"alpha unique vals  : {len(np.unique(alpha))}")

rgb = rgba[:, :, :3].copy()
# Flatten any genuinely transparent pixels onto white for honest color stats.
transparent = alpha < 250
rgb[transparent] = (255, 255, 255)

# ---------------------------------------------------------------------------
# 2. Find the RED pain glows.
#    The glows are coral/pink over blue anatomy. Rather than a fragile single
#    threshold we combine three forgiving tests and then cluster the result.
# ---------------------------------------------------------------------------
r, g, b = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
redness = r - (g + b) // 2
red_mask = ((r > 130) & (redness > 35) & (r > b + 20)).astype(np.uint8) * 255

# Close small gaps so one anatomical glow becomes one blob, then label blobs.
red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
red_mask = cv2.dilate(red_mask, np.ones((5, 5), np.uint8), iterations=1)
count, labels, stats, centroids = cv2.connectedComponentsWithStats(red_mask, 8)

glows = []
for i in range(1, count):
    area = stats[i, cv2.CC_STAT_AREA]
    if area < 120:          # ignore specks / anti-aliased text artefacts
        continue
    x, y, bw, bh = stats[i, :4]
    cx, cy = centroids[i]
    glows.append((area, round(cx, 1), round(cy, 1), (x, y, bw, bh)))

glows.sort(key=lambda t: t[2])   # top-to-bottom, the order a reader scans
print(f"\nred glow candidates : {len(glows)}")
for area, cx, cy, box in glows:
    print(f"   center=({cx:6.1f},{cy:6.1f})  area={area:6d}  box={box}")

# ---------------------------------------------------------------------------
# 3. Find the BLUE anatomical figure (saturated blue/cyan, low red).
# ---------------------------------------------------------------------------
blueness = b - r
blue_mask = ((b > 110) & (blueness > 25) & (b > g - 10)).astype(np.uint8) * 255
ys, xs = np.where(blue_mask > 0)
print(f"\nblue figure bbox   : x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}")
print(f"blue pixel count   : {len(xs)}")

# ---------------------------------------------------------------------------
# 4. Background / ink census. Useful for deciding the alpha-keying strategy.
# ---------------------------------------------------------------------------
near_white = ((r > 240) & (g > 240) & (b > 240)).mean()
grey_ink = ((abs(r - g) < 18) & (abs(g - b) < 18) & (r > 90) & (r < 215)).mean()
print(f"\nnear-white fraction: {near_white:.3f}")
print(f"grey-ink fraction  : {grey_ink:.3f}   (label text, leader lines, grey bars)")

# ---------------------------------------------------------------------------
# 5. Grid-annotated preview so the numbers can be visually verified.
#    Grid every 100px on X and 50px on Y, with the detected glows circled.
# ---------------------------------------------------------------------------
preview = Image.fromarray(rgb).convert("RGB")
d = ImageDraw.Draw(preview)
for x in range(0, w, 100):
    d.line([(x, 0), (x, h)], fill=(0, 190, 0), width=1)
    d.text((x + 2, 2), str(x), fill=(0, 120, 0))
for y in range(0, h, 50):
    d.line([(0, y), (w, y)], fill=(0, 190, 0), width=1)
    d.text((2, y + 2), str(y), fill=(0, 120, 0))
for n, (area, cx, cy, (bx, by, bw, bh)) in enumerate(glows, 1):
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], outline=(255, 0, 255), width=2)
    d.rectangle([bx, by, bx + bw, by + bh], outline=(255, 140, 0), width=1)
    d.text((cx + 24, cy - 8), f"P{n} ({cx:.0f},{cy:.0f})", fill=(180, 0, 180))
d.rectangle([xs.min(), ys.min(), xs.max(), ys.max()], outline=(0, 90, 255), width=2)

preview_path = OUT_DIR / "source-grid.png"
preview.save(preview_path)
print(f"\ngrid preview       : {preview_path}")
print("DONE")

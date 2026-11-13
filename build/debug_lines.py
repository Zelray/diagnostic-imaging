"""
Diagnostic: WHERE are the leader lines, really?

WHY: Three cleanup attempts left visible line stubs. Rather than keep tuning
blindly, draw every detected long straight line on top of the FULL source
image and look at it. Full-image detection is far more reliable than the tight
body crop because the leader lines are 200-400px long there.

Also prints each line's endpoints and angle so we can hard-code the six real
ones if detection is still noisy.

Run:  python build/debug_lines.py
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
rgba = np.array(Image.open(ROOT / "rs=h_{640}.webp").convert("RGBA"))
rgb = rgba[:, :, :3].copy()
rgb[rgba[:, :, 3] < 250] = (255, 255, 255)

f = rgb.astype(np.float32)
mx, mn = f.max(axis=2), f.min(axis=2)
sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
# Neutral, non-white ink: label text, grey bars, leader lines.
ink = ((sat < 0.17) & (mn < 225) & (mx > 40)).astype(np.uint8) * 255

lines = cv2.HoughLinesP(
    ink, 1, np.pi / 360, threshold=45, minLineLength=90, maxLineGap=28
)

vis = rgb.copy()
found = []
if lines is not None:
    for x1, y1, x2, y2 in lines[:, 0, :]:
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        ang = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if 12 < ang < 80:
            found.append((round(length, 1), round(ang, 1), (x1, y1, x2, y2)))
            cv2.line(vis, (x1, y1), (x2, y2), (255, 0, 255), 2)

found.sort(reverse=True)
print(f"detected diagonal lines: {len(found)}")
for i, (length, ang, pts) in enumerate(found[:20], 1):
    print(f"  {i:2d}. len={length:6.1f} angle={ang:5.1f}deg  {pts}")

Image.fromarray(vis).save(ROOT / "build" / "debug-detected-lines.png")
cv2.imwrite(str(ROOT / "build" / "debug-ink-mask.png"), ink)
print("\nwrote build/debug-detected-lines.png + debug-ink-mask.png")

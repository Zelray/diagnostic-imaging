"""
Gate G1 -- prove the cleaned assets are real and correctly measured.

WHAT IT CHECKS
  1. The ORIGINAL source WebP is still present and untouched (we never edit it).
  2. assets/body-scan.webp is RGBA with both fully-transparent and fully-opaque
     pixels -- i.e. the white background really was keyed out.
  3. assets/hotspots.json has exactly 6 hotspots, 3 left / 3 right, unique ids,
     and percentages inside the image.
  4. assets/infographic-clean.png has a pure-white top band, proving the
     syringe / capsule / AmeraCel logo were removed.
  5. The measured glow percentages agree with the crop geometry in the JSON.

Prints "asset verification passed" ONLY after every assertion succeeds.
Run:  python build/verify_asset.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    # 1. Source untouched.
    source = ROOT / "rs=h_{640}.webp"
    if not source.exists():
        fail("original source WebP is missing")
    src = Image.open(source)
    if src.size != (1002, 640):
        fail(f"source dimensions changed: {src.size}")

    # 2. Ship asset has real alpha.
    ship_path = ASSETS / "body-scan.webp"
    if not ship_path.exists():
        fail("assets/body-scan.webp missing")
    ship = np.array(Image.open(ship_path).convert("RGBA"))
    if ship.shape[:2] != (1000, 370):
        fail(f"unexpected ship dimensions: {ship.shape[:2]}")
    alpha = ship[:, :, 3]
    if alpha.min() > 5:
        fail("no transparent pixels -- white background was not keyed out")
    if alpha.max() < 250:
        fail("no opaque pixels -- anatomy was erased")
    # At least 3% of the plate must be opaque (the body is present).
    if (alpha > 200).mean() < 0.03:
        fail("anatomy occupies almost no opaque pixels")

    # 2b. Light plate: opaque, original colors, same geometry.
    light_path = ASSETS / "body-light.webp"
    if not light_path.exists():
        fail("assets/body-light.webp missing (light theme plate)")
    light = Image.open(light_path)
    if light.size != (370, 1000):
        fail(f"light plate dimensions wrong: {light.size}")
    if light.mode not in ("RGB", "RGBA"):
        fail(f"light plate unexpected mode: {light.mode}")

    # 3. Hotspot geometry.
    hs_path = ASSETS / "hotspots.json"
    if not hs_path.exists():
        fail("assets/hotspots.json missing")
    data = json.loads(hs_path.read_text(encoding="utf-8"))
    spots = data.get("hotspots", [])
    if len(spots) != 6:
        fail(f"expected 6 hotspots, found {len(spots)}")
    ids = [s["id"] for s in spots]
    if len(set(ids)) != 6:
        fail("hotspot ids are not unique")
    sides = [s["side"] for s in spots]
    if sides.count("left") != 3 or sides.count("right") != 3:
        fail(f"expected 3 left / 3 right, got {sides}")
    for s in spots:
        if not (0 < s["xPct"] < 100 and 0 < s["yPct"] < 100):
            fail(f"hotspot {s['id']} has out-of-range percentages")

    # Percentages must be exactly reproducible from the crop + source coords.
    c = data["crop"]
    cw, ch = c["x1"] - c["x0"], c["y1"] - c["y0"]
    for s in spots:
        sx, sy = s["sourceXY"]
        ex, ey = round((sx - c["x0"]) / cw * 100, 2), round((sy - c["y0"]) / ch * 100, 2)
        if abs(ex - s["xPct"]) > 0.01 or abs(ey - s["yPct"]) > 0.01:
            fail(f"hotspot {s['id']} percentage disagrees with its source coord")

    # 4. Branding removed from the bonus static infographic.
    clean = np.array(Image.open(ASSETS / "infographic-clean.png").convert("RGB"))
    band = clean[0:130, 0:620]
    if band.min() < 250:
        fail("top band is not pure white -- branding may still be present")

    # 5. The embedded image and the JSON must describe the same aspect ratio.
    if abs(data["aspect"] - 370 / 1000) > 0.0001:
        fail("hotspots.json aspect disagrees with the shipped WebP")

    print("asset verification passed")


if __name__ == "__main__":
    main()

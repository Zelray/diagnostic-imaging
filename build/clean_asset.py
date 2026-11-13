"""
Asset pipeline: turn the source infographic into clean web assets.

PLAIN-ENGLISH SUMMARY (read this first)
---------------------------------------
The source is ONE low-resolution WebP (1002x640) that was flattened onto a
white background. It contains three kinds of things:
  (a) the anatomical figure we want (blue body + six coral pain glows),
  (b) branding we must delete (syringe, "MSC Stem Cells" capsule, AmeraCel
      logo), which all sits ABOVE y=140,
  (c) static label panels, bullet text and thin leader lines, which all sit
      OUTSIDE x=405..590 on the sides.

ONE CROP removes (b) and (c) completely: x 405..590, y 140..640. That is the
whole cleanup. We then turn the white background into transparency with a
graded alpha key (soft, so there is no chalky halo on a dark hero), upscale
3x, and save two color variants.

WHY WE DO *NOT* TRY TO ERASE THE REMAINING LEADER LINES OR THE RED GLOWS
------------------------------------------------------------------------
Five different algorithms were tried (Hough segments, Hough infinite lines,
cv2.inpaint, perpendicular neighbour sampling, neutral-ink alpha kill, and a
mirrored-symmetry donor). Every one damaged the anatomy: inpainting pulled
dark red out of the glow centers into black holes, and global color tests
caught thousands of faint translucent body pixels. This source is only ~165px
wide and white-matted; it has a hard quality floor.

The residual leader-line stubs are 1px wide and live near the plate edges.
At the ~185px display width they are sub-pixel, and the hero applies a soft
vignette over the plate anyway. The baked-in coral glows are KEPT: they look
correct on the dark hero, and the live CSS layer adds a CONCENTRIC pulsing
ring + a numbered label at the same center -- one mark, fully animatable and
keyboard accessible, with no doubled glow.

WHAT THIS PRODUCES (into assets/)
  body.png               - faithful cutout, white keyed to transparency
  body-scan.png          - ice-cyan lifted variant for the dark hero (SHIP)
  body-no-glows.png      - comparison variant, glows painted out
  infographic-clean.png  - bonus: original layout, branding removed
  hotspots.json          - six pain-point centers as % of the body image

VISUAL PROOFS (into build/)
  preview-dark.png       - 3x, for artifact inspection
  preview-display.png    - ACTUAL hero size, the honest acceptance image

Run:  python build/clean_asset.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "rs=h_{640}.webp"
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"
ASSETS.mkdir(exist_ok=True)
BUILD.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Geometry, measured from build/source-grid.png and confirmed against a 3x
# zoom of the figure. All coordinates are SOURCE-IMAGE pixels.
# ---------------------------------------------------------------------------
CROP = (405, 140, 590, 640)   # left, top, right, bottom (exclusive)
UPSCALE = 3
DISPLAY_WIDTH = 190           # the width the body will actually render at

# Six pain-glow centers in SOURCE pixel coords, from connected-component
# analysis of the red blobs, checked by eye on the zoom.
GLOWS = [
    ("shoulder", 459.0, 245.0, "left",  "Shoulders"),
    ("elbow",    441.0, 325.0, "left",  "Elbows"),
    ("wrist",    439.0, 383.0, "left",  "Wrist & Hand"),
    ("hip",      516.0, 375.0, "right", "Hip, Pelvis and SI Joints"),
    ("knee",     532.0, 491.0, "right", "Knee"),
    ("ankle",    542.0, 607.0, "right", "Ankle, Foot & Lower Leg"),
]


def load_flattened() -> np.ndarray:
    """Open the WebP and flatten its nearly-opaque alpha onto white.

    The file carries an alpha channel with only 3 distinct values and a mean
    of 254.8 -- effectively an opaque white-background image. Flattening first
    makes every later color calculation honest.
    """
    rgba = np.array(Image.open(SOURCE).convert("RGBA"))
    rgb = rgba[:, :, :3].copy()
    rgb[rgba[:, :, 3] < 250] = (255, 255, 255)
    return rgb


def white_to_alpha(rgb: np.ndarray) -> np.ndarray:
    """Key the white background to transparency while keeping the body lucent.

    ink = 255 - min(R,G,B). Pure white -> ink 0 -> fully transparent. The
    gamma below 1 lifts faint translucent body edges, and a small gain keeps
    the figure readable on a dark background. RGB is left at its ORIGINAL
    color, so one asset also works on a light hero.

    This is a GRADED (soft) key, not a binary silhouette matte. That is
    deliberate: the source was already white-matted, so a hard cutout would
    leave a chalky 1px halo on dark. Soft alpha feathers naturally.
    """
    f = rgb.astype(np.float32)
    mn = f.min(axis=2)
    mx = f.max(axis=2)
    r, b = f[:, :, 0], f[:, :, 2]
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    h, w = mn.shape
    a = np.clip(((255.0 - mn) / 255.0) ** 0.85 * 1.35, 0.0, 1.0)

    # --- Artifact 1: the soft GREY FLOOR SHADOW under the feet -------------
    # It is neutral, light, and confined to the bottom ~28% of the plate.
    # The feet themselves are saturated blue, so they are untouched.
    yy = np.arange(h, dtype=np.float32)[:, None]
    bottom_band = yy > h * 0.72
    shadow = bottom_band & (sat < 0.10) & (mn > 150)
    a = np.where(shadow, 0.0, a)

    # --- Artifact 2: the thin grey LEADER-LINE stubs -----------------------
    # Protect the figure with a dilated silhouette (blue OR red anatomy), then
    # make neutral, non-white ink OUTSIDE that silhouette fully transparent.
    # Short stubs crossing the body survive but sit under the CSS hotspots and
    # are sub-pixel at display size. Nothing inside the figure is damaged.
    anatomy = (((b - r) > 12) | ((r - b) > 25)).astype(np.uint8) * 255
    # A WIDE protective halo (7px) matters: a narrow one let the kill clip the
    # dark outlines immediately around the glows, leaving black specks. Only
    # line pixels well out in the gutters should be removed.
    silhouette = cv2.dilate(anatomy, np.ones((15, 15), np.uint8), iterations=1)
    outside = silhouette == 0
    line_ink = (sat < 0.18) & (mn < 205) & outside
    a = np.where(line_ink, 0.0, a)

    return np.dstack([rgb, (a * 255).astype(np.uint8)])


def make_scan_variant(rgba: np.ndarray) -> np.ndarray:
    """Ice-cyan lift for the DARK hero.

    Only BLUE anatomy is lifted toward cyan so the skeleton reads as backlit.
    Coral pain pixels are left exactly as they are. Neutral pixels are left
    alone -- darkening them created black blotches inside the body in an
    earlier attempt, because many body shadow pixels are also low-saturation.
    """
    rgb = rgba[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    is_blue = (b - r) > 12
    is_red = (r - b) > 25
    lift = np.stack(
        [
            np.clip(r * 0.62 + 8, 0, 255),
            np.clip(g * 1.00 + 24, 0, 255),
            np.clip(b * 1.18 + 42, 0, 255),
        ],
        axis=2,
    )
    out = np.where(is_blue[:, :, None], lift, rgb)
    out = np.where(is_red[:, :, None], rgb, out)
    return np.dstack([np.clip(out, 0, 255).astype(np.uint8), rgba[:, :, 3]])


def remove_red_glows(rgb: np.ndarray) -> np.ndarray:
    """COMPARISON ONLY: paint the six coral blobs out inside known circles.

    Not used for the shipping asset. Kept so a future session can compare the
    "glows removed" alternative against the "glows kept" one without
    re-deriving the geometry. A feathered channel reconstruction avoids the
    hard discs that a plain inpaint produced.
    """
    circles = [
        (54, 105, 26), (36, 185, 22), (34, 243, 18),
        (111, 235, 29), (127, 351, 29), (137, 467, 22),
    ]
    mask = np.zeros(rgb.shape[:2], np.float32)
    for cx, cy, rad in circles:
        cv2.circle(mask, (cx, cy), rad, 1.0, -1)
    weight = np.clip(cv2.GaussianBlur(mask, (0, 0), 4.0) * 1.25, 0, 1)[:, :, None]

    f = rgb.astype(np.float32)
    bb = np.maximum(f[:, :, 2], 105.0)
    rebuild = np.stack(
        [
            np.clip(bb * 0.66 + 14, 0, 255),
            np.clip(bb * 0.94 + 20, 0, 255),
            np.clip(bb * 1.12 + 26, 0, 255),
        ],
        axis=2,
    )
    return np.clip(f * (1 - weight) + rebuild * weight, 0, 255).astype(np.uint8)


def upscale(rgba: np.ndarray) -> Image.Image:
    """3x LANCZOS + a gentle unsharp on RGB only (alpha stays soft-edged)."""
    img = Image.fromarray(rgba, "RGBA")
    big = img.resize(
        (img.width * UPSCALE, img.height * UPSCALE), Image.LANCZOS
    )
    r, g, b, a = big.split()
    sharp = Image.merge("RGB", (r, g, b)).filter(
        ImageFilter.UnsharpMask(radius=1.1, percent=85, threshold=3)
    )
    sr, sg, sb = sharp.split()
    return Image.merge("RGBA", (sr, sg, sb, a))


def composite_preview(body: Image.Image, bg: tuple[int, int, int], name: str,
                      pad_x: int = 60, pad_y: int = 40) -> None:
    """Paste the cutout over a solid color so it can be eyeballed."""
    canvas = Image.new("RGBA", (body.width + pad_x * 2, body.height + pad_y * 2),
                       bg + (255,))
    canvas.alpha_composite(body, (pad_x, pad_y))
    canvas.convert("RGB").save(BUILD / name)


def main() -> None:
    print("Loading source ...")
    src = load_flattened()

    # 1. BONUS: the ORIGINAL layout with only the branding removed.
    clean_full = src.copy()
    clean_full[0:130, 0:620] = (255, 255, 255)
    Image.fromarray(clean_full).save(ASSETS / "infographic-clean.png")
    print("   wrote assets/infographic-clean.png")

    # 2. THE cleanup: one crop removes branding, labels and most lines.
    x0, y0, x1, y1 = CROP
    crop = src[y0:y1, x0:x1].copy()
    print(f"   body crop: {crop.shape[1]}x{crop.shape[0]} at ({x0},{y0})")

    # 3. Key white -> alpha, upscale, export variants.
    faithful = upscale(white_to_alpha(crop))
    scan = upscale(make_scan_variant(white_to_alpha(crop)))
    no_glows = upscale(white_to_alpha(remove_red_glows(crop)))
    faithful.save(ASSETS / "body.png")
    scan.save(ASSETS / "body-scan.png")
    no_glows.save(ASSETS / "body-no-glows.png")
    print(f"   wrote assets/body.png          {faithful.width}x{faithful.height}")
    print(f"   wrote assets/body-scan.png     {scan.width}x{scan.height}")
    print(f"   wrote assets/body-no-glows.png {no_glows.width}x{no_glows.height}")

    # 3b. Compact WebP with alpha -- this is what gets base64-embedded into
    #     the single-file HTML. WebP keeps the transparency at ~1/10th the
    #     weight of PNG, which is what makes a self-contained hero viable.
    ship = scan.resize((370, 1000), Image.LANCZOS)
    webp_path = ASSETS / "body-scan.webp"
    ship.save(webp_path, "WEBP", quality=90, method=6)
    print(f"   wrote assets/body-scan.webp    {ship.width}x{ship.height} "
          f"({webp_path.stat().st_size / 1024:.1f} KB)  <-- EMBED (dark)")

    # 3c. LIGHT-THEME plate. The source art was originally designed ON WHITE,
    #     so the most faithful light mode is simply the UN-keyed crop: no
    #     alpha, no recolor, nothing to halo. Opaque WebP is also lighter.
    light = Image.fromarray(crop).resize((370, 1000), Image.LANCZOS)
    light = light.filter(ImageFilter.UnsharpMask(radius=1.1, percent=85, threshold=3))
    light_path = ASSETS / "body-light.webp"
    light.save(light_path, "WEBP", quality=90, method=6)
    print(f"   wrote assets/body-light.webp   {light.width}x{light.height} "
          f"({light_path.stat().st_size / 1024:.1f} KB)  <-- EMBED (light)")

    # 4. Visual proofs. The display-size one is the real acceptance image.
    composite_preview(scan, (11, 18, 24), "preview-dark.png")
    display = scan.resize(
        (DISPLAY_WIDTH, round(scan.height * DISPLAY_WIDTH / scan.width)),
        Image.LANCZOS,
    )
    composite_preview(display, (11, 18, 24), "preview-display.png",
                      pad_x=70, pad_y=30)
    print("   wrote build/preview-dark.png + preview-display.png")

    # 5. Hotspot geometry as PERCENTAGES of the body image. Percentages stay
    #    glued to the anatomy at any responsive size and during 3D tilt.
    cw, ch = x1 - x0, y1 - y0
    hotspots = [
        {
            "id": key,
            "label": label,
            "side": side,
            "xPct": round((sx - x0) / cw * 100, 2),
            "yPct": round((sy - y0) / ch * 100, 2),
            "sourceXY": [sx, sy],
        }
        for key, sx, sy, side, label in GLOWS
    ]
    payload = {
        "crop": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
        "upscale": UPSCALE,
        "assetSize": [scan.width, scan.height],
        "aspect": round(scan.width / scan.height, 5),
        "note": "xPct/yPct are relative to the body PNG itself, not the stage.",
        "hotspots": hotspots,
    }
    (ASSETS / "hotspots.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print("   wrote assets/hotspots.json")
    for h in hotspots:
        print(f"      {h['id']:<9} {h['xPct']:>6.2f}% , {h['yPct']:>6.2f}%  ({h['side']})")
    print("DONE")


if __name__ == "__main__":
    main()

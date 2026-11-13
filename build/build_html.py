"""
Bake the readable source files into ONE double-clickable index.html.

WHY A BUILD STEP
  Mike is not a coder and should never have to keep a folder of files
  together. The deliverable is a single index.html that works offline from
  file:// with zero network requests. But a single 200KB file with a giant
  base64 blob is miserable to edit. So we keep:
      build/hero-template.html  <- readable HTML/CSS/JS
      build/data.json           <- the 23 conditions
      assets/body-scan.webp     <- the anatomy plate
  and this script merges them into index.html.

  CRITICAL file:// RULES baked in:
    * the image is a base64 data URI (no second request, no canvas tainting),
    * all data is inline (fetch() of a local .json is CORS-blocked),
    * classic <script> only (ES modules are CORS-blocked),
    * system fonts only (no webfont CDN).

Run:  python build/build_html.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "build" / "hero-template.html"
DATA = ROOT / "build" / "data.json"
IMAGE_DARK = ROOT / "assets" / "body-scan.webp"
IMAGE_LIGHT = ROOT / "assets" / "body-light.webp"
OUTPUT = ROOT / "index.html"


def main() -> None:
    for path in (TEMPLATE, DATA, IMAGE_DARK, IMAGE_LIGHT):
        if not path.exists():
            raise SystemExit(f"missing input: {path}")

    template = TEMPLATE.read_text(encoding="utf-8")
    data = json.loads(DATA.read_text(encoding="utf-8"))

    # Compact the JSON into one line. It sits inside a <script type=application/json>
    # block, so no escaping is needed beyond the fact that the copy contains no
    # "</script>" sequence (the verifier asserts the block parses cleanly).
    json_text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "</script" in json_text.lower():
        raise SystemExit("data contains a script-closing sequence; escape it first")

    def to_data_uri(path: Path) -> str:
        return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    placeholders = {
        "__BODY_IMAGE__": to_data_uri(IMAGE_DARK),
        "__BODY_IMAGE_LIGHT__": to_data_uri(IMAGE_LIGHT),
        "__PH_DATA__": json_text,
    }
    for token, value in placeholders.items():
        if template.count(token) != 1:
            raise SystemExit(f"placeholder {token} is missing or duplicated")

    html = template
    for token, value in placeholders.items():
        html = html.replace(token, value)
    OUTPUT.write_text(html, encoding="utf-8")

    print(f"wrote {OUTPUT}")
    print(f"   template : {TEMPLATE.stat().st_size / 1024:.1f} KB")
    print(f"   dark img : {IMAGE_DARK.stat().st_size / 1024:.1f} KB -> "
          f"{len(placeholders['__BODY_IMAGE__']) / 1024:.1f} KB base64")
    print(f"   light img: {IMAGE_LIGHT.stat().st_size / 1024:.1f} KB -> "
          f"{len(placeholders['__BODY_IMAGE_LIGHT__']) / 1024:.1f} KB base64")
    print(f"   data     : {len(json_text) / 1024:.1f} KB ({len(data['regions'])} regions, "
          f"{sum(len(r['ailments']) for r in data['regions'])} ailments)")
    print(f"   TOTAL    : {OUTPUT.stat().st_size / 1024:.1f} KB, single file, zero requests")


if __name__ == "__main__":
    main()

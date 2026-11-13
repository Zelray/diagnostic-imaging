"""
Gate G2 -- prove the hero is offline-safe and content-complete.

WHAT IT CHECKS
  1. Zero network dependencies: no http/https, no CDN, no fetch(), no ES
     modules, no @import, no external font. This is what makes index.html
     work when Mike double-clicks it from disk (file://).
  2. Exactly ONE base64 data:image URI (the anatomy plate is embedded).
  3. lang="en", prefers-reduced-motion present, a viewport meta.
  4. The inline JSON data has 6 regions, 23 ailments, unique ids, the exact
     source counts 5/2/3/5/3/5, and non-empty draft copy for every ailment.
  5. Every region carries measured xPct/yPct inside the plate.

Prints "html verification passed" ONLY after every assertion succeeds.
Run:  python build/verify_html.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    if not HTML.exists():
        fail("index.html missing -- run build/build_html.py first")
    html = HTML.read_text(encoding="utf-8")

    # 1. Offline safety. Strip the JSON data block, HTML comments, and the
    #    base64 payload before scanning. Comments legitimately EXPLAIN that
    #    fetch() and file:// are forbidden -- that prose is not a violation.
    #    Only real markup/scripts should be judged.
    markup = re.sub(
        r'<script type="application/json"[^>]*>.*?</script>',
        "", html, flags=re.S,
    )
    markup = re.sub(r'<!--.*?-->', "", markup, flags=re.S)
    markup = re.sub(r'data:image/[^"\')]+', 'data:image/PAYLOAD', markup)
    forbidden = {
        "http://": "external URL",
        "https://": "external URL",
        "fetch(": "fetch() is blocked on file://",
        'type="module"': "ES modules are blocked on file://",
        "@import": "external CSS import",
        "url(https": "external CSS url",
        "//cdn": "CDN reference",
    }
    for token, why in forbidden.items():
        if token in markup:
            fail(f"offline violation: {token} ({why})")

    # No external src/href (data: URIs are fine).
    for attr in re.findall(r'\b(?:src|href)="([^"]*)"', markup):
        if not (attr.startswith("data:") or attr.startswith("#") or attr == ""):
            fail(f"external resource reference: {attr[:60]}")

    # 2. Exactly two embedded images: the dark (cyan scan) and light
    #    (original art) anatomy plates.
    n_images = html.count("data:image/")
    if n_images != 2:
        fail(f"expected 2 embedded images (dark + light plates), found {n_images}")
    if "data-theme" not in markup:
        fail("theme toggle wiring missing (body[data-theme])")

    # 3. Baseline accessibility / responsiveness.
    if '<html lang="en"' not in html:
        fail("missing lang=en")
    if "prefers-reduced-motion" not in html:
        fail("missing prefers-reduced-motion handling")
    if 'name="viewport"' not in html:
        fail("missing viewport meta")

    # 4. Inline data.
    m = re.search(
        r'<script type="application/json" id="ph-data">(.*?)</script>',
        html, flags=re.S,
    )
    if not m:
        fail("inline #ph-data JSON block missing")
    data = json.loads(m.group(1))
    regions = data.get("regions", [])
    if len(regions) != 6:
        fail(f"expected 6 regions, found {len(regions)}")

    expected_counts = [5, 2, 3, 5, 3, 5]
    counts = []
    all_ids: list[str] = []
    for i, region in enumerate(regions):
        for key in ("id", "label", "side", "xPct", "yPct", "ailments"):
            if key not in region:
                fail(f"region {i} missing key {key}")
        if not (0 < region["xPct"] < 100 and 0 < region["yPct"] < 100):
            fail(f"region {region['id']} has out-of-range hotspot percentages")
        if region["side"] not in ("left", "right"):
            fail(f"region {region['id']} has invalid side")
        ailments = region["ailments"]
        counts.append(len(ailments))
        for a in ailments:
            if not a.get("id") or not a.get("title"):
                fail(f"ailment in {region['id']} missing id/title")
            copy = a.get("copy", "")
            if not (40 <= len(copy) <= 400):
                fail(f"ailment {a['id']} copy length {len(copy)} out of range")
            if "\n" in copy:
                fail(f"ailment {a['id']} copy contains a newline")
            all_ids.append(a["id"])
    if counts != expected_counts:
        fail(f"ailment counts {counts} != source counts {expected_counts}")
    if sum(counts) != 23:
        fail(f"expected 23 ailments total, found {sum(counts)}")
    if len(set(all_ids)) != 23:
        fail("ailment ids are not unique")
    if len({r["id"] for r in regions}) != 6:
        fail("region ids are not unique")

    print("html verification passed")


if __name__ == "__main__":
    main()

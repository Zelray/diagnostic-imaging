"""
Gate G3 -- prove the hero actually WORKS in a real Chrome, headlessly.

WHY THIS EXISTS
  Static file checks cannot prove that the JavaScript built the DOM, or that
  clicking one condition closes another. This gate launches Chrome in headless
  mode against file://index.html?selftest=1. The page's built-in self-test
  (gated behind that query string, invisible in normal use) clicks two
  conditions in different regions, verifies the globally single-open rule,
  toggles the same one closed, exercises hover-to-pulse and keyboard Escape,
  and writes SELFTEST PASS / SELFTEST FAIL into the DOM.

  --dump-dom returns the fully-rendered DOM after JS has run, so parsing it
  gives real browser evidence from a single command. No server, no npm, no
  Selenium, no network.

Prints "dom verification passed" ONLY after every assertion succeeds.
Run:  python build/verify_dom.py
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    if not HTML.exists():
        fail("index.html missing -- run build/build_html.py first")
    chrome = next((p for p in CHROME_CANDIDATES if Path(p).exists()), None)
    if chrome is None:
        fail("Chrome not found at the standard install paths")

    url = HTML.as_uri() + "?selftest=1"
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--virtual-time-budget=4000",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, encoding="utf-8",
        errors="replace",
    )
    raw_dom = proc.stdout or ""
    if not raw_dom:
        fail(f"Chrome returned no DOM (exit {proc.returncode}): {proc.stderr[:400]}")

    # Look for the self-test RESULT element specifically. The inline <script>
    # source contains the literal strings "SELFTEST PASS" / "SELFTEST FAIL", so
    # matching the whole document would be a false positive.
    result = re.search(r'id="selftest-results"[^>]*>([^<]*)<', raw_dom)
    if not result:
        fail("self-test result element was never rendered -- JS did not run")
    verdict = result.group(1).strip()
    if verdict != "SELFTEST PASS":
        fail(f"in-browser self-test failed: {verdict[:400]}")

    # Count only RENDERED markup, not strings inside script/style source.
    # ORDER MATTERS: HTML comments must be stripped FIRST. The template's
    # header comment literally contains the word "<script>", so stripping
    # scripts first would start a match inside that comment and swallow the
    # whole document up to the real closing tag (a 235KB -> 1KB false result).
    dom = re.sub(r'<!--.*?-->', "", raw_dom, flags=re.S)
    dom = re.sub(r'<script\b[^>]*>.*?</script>', "", dom, flags=re.S | re.I)
    dom = re.sub(r'<style\b[^>]*>.*?</style>', "", dom, flags=re.S | re.I)

    # The JS actually built the interactive DOM.
    n_buttons = dom.count('aria-expanded="false"') + dom.count('aria-expanded="true"')
    if n_buttons != 23:
        fail(f"expected 23 accordion buttons with aria-expanded, found {n_buttons}")
    n_panels = dom.count('role="region"')
    if n_panels != 23:
        fail(f"expected 23 role=region panels, found {n_panels}")
    n_hot = len(re.findall(r'class="ph-hot(?:\s|")', dom))
    if n_hot < 6:
        fail(f"expected at least 6 hotspot buttons, found {n_hot}")
    if dom.count('aria-controls="') < 23:
        fail("accordion buttons are missing aria-controls")
    if 'role="img"' not in dom and "Illustrative" not in dom and "illustrative" not in dom:
        fail("body illustration has no accessible description")

    print("dom verification passed")


if __name__ == "__main__":
    main()

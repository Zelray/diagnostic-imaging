"""
Gate: prove there is NO horizontal overflow at phone, tablet and desktop.

WHY: a headless screenshot at 390px showed the eyebrow and deck running off
the right edge. A visual check alone is easy to fool (the clipped words just
look like a narrow crop). This gate launches Chrome --headless --dump-dom at
three widths with ?selftest=1, reads the LAYOUT report the page writes into
the DOM, and asserts scrollWidth <= innerWidth at every size.

Prints "layout verification passed" ONLY after all three widths pass.
Run:  python build/verify_layout.py
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

WIDTHS = [(390, 844, "phone"), (900, 1000, "tablet"), (1440, 900, "desktop")]


def fail(msg: str) -> None:
    raise AssertionError(msg)


def main() -> None:
    if not HTML.exists():
        fail("index.html missing -- run build/build_html.py first")
    chrome = next((p for p in CHROME if Path(p).exists()), None)
    if chrome is None:
        fail("Chrome not found at the standard install paths")

    url = HTML.as_uri() + "?selftest=1"
    for w, h, label in WIDTHS:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--hide-scrollbars", f"--window-size={w},{h}",
            "--force-device-scale-factor=1",
            "--virtual-time-budget=4000", "--dump-dom", url,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        dom = proc.stdout or ""
        m = re.search(
            r'id="layout-report"[^>]*>\s*LAYOUT innerWidth=(\d+) scrollWidth=(\d+)',
            dom,
        )
        if not m:
            fail(f"{label}: layout report missing (JS did not run?)")
        inner, scroll = int(m.group(1)), int(m.group(2))
        # Allow 1px for sub-pixel rounding, no more.
        if scroll > inner + 1:
            fail(f"{label} ({w}x{h}): horizontal overflow "
                 f"scrollWidth={scroll} > innerWidth={inner}")
        print(f"   {label:<8} {w}x{h}  innerWidth={inner}  scrollWidth={scroll}  OK")

    print("layout verification passed")


if __name__ == "__main__":
    main()

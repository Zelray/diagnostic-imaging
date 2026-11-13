"""
Full browser QA gate -- real viewport, real mouse, real keyboard.

WHY THIS EXISTS
  Static checks prove the files are well-formed; headless --dump-dom proves the
  JS builds the DOM. Neither proves a 390px phone has no horizontal overflow,
  that a real hover pulses the right glow, or that Escape closes an accordion.
  This script drives the ACTUAL Chrome binary through Playwright at three
  viewports and writes screenshots into build/qa-*.png as visual evidence.

CHECKS
  1. No horizontal overflow at 390 / 900 / 1440 CSS px.
  2. Zero console errors and zero network (http) requests -> truly offline.
  3. Six hotspots, 23 accordion buttons, 23 role=region panels.
  4. Single-open: click in one region, click in another, first must close.
  5. Hover a region label -> exactly that one hotspot pulses.
  6. Keyboard: Enter opens, Escape closes and restores focus.
  7. Drag tilts the figure and it springs back to flat.
  8. Reduced motion: no tilt transform and no pulse animation.
  9. Dark/light toggle: flips body[data-theme], swaps the visible plate,
     changes the rendered ground color, and a light-OS context STARTS light.

Prints "browser verification passed" ONLY after every assertion succeeds.
Run:  python build/verify_browser.py
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"
SHOTS = ROOT / "build"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def count_true(page) -> int:
    return page.locator('.ph-ailment[aria-expanded="true"]').count()


def main() -> None:
    if not HTML.exists():
        fail("index.html missing -- run build/build_html.py first")
    if not Path(CHROME).exists():
        fail("Chrome binary not found")

    url = HTML.as_uri()
    errors: list[str] = []
    http_requests: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME, headless=True,
            args=["--no-first-run", "--disable-extensions"],
        )
        try:
            # ---------------------------------------------------------------
            # 1. Responsive widths + screenshots + console/network hygiene
            # ---------------------------------------------------------------
            for w, h, label in [(390, 844, "phone"), (900, 1000, "tablet"),
                                (1440, 900, "desktop")]:
                # color_scheme is pinned DARK for determinism: Playwright
                # contexts default to a LIGHT OS scheme, and the hero
                # legitimately boots in whatever the OS prefers.
                ctx = browser.new_context(
                    viewport={"width": w, "height": h},
                    device_scale_factor=2 if label == "phone" else 1,
                    is_mobile=(label == "phone"),
                    has_touch=(label == "phone"),
                    color_scheme="dark",
                )
                page = ctx.new_page()
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("request", lambda r: http_requests.append(r.url)
                        if r.url.startswith("http") else None)
                page.goto(url, wait_until="load")
                page.wait_for_timeout(900)

                metrics = page.evaluate(
                    "() => ({inner: window.innerWidth, "
                    "scroll: document.documentElement.scrollWidth})"
                )
                if metrics["scroll"] > metrics["inner"] + 1:
                    fail(f"{label}: horizontal overflow "
                         f"scrollWidth={metrics['scroll']} > innerWidth={metrics['inner']}")
                page.screenshot(path=str(SHOTS / f"qa-{label}.png"))
                print(f"   {label:<8} innerWidth={metrics['inner']} "
                      f"scrollWidth={metrics['scroll']}  OK")
                if label != "desktop":
                    ctx.close()
                    continue

                # -----------------------------------------------------------
                # 2-7. All interaction checks run on the desktop context.
                # -----------------------------------------------------------
                if page.locator(".ph-hot").count() != 6:
                    fail("expected 6 hotspot buttons")
                if page.locator(".ph-ailment").count() != 23:
                    fail("expected 23 accordion buttons")
                if page.locator('.ph-detail[role="region"]').count() != 23:
                    fail("expected 23 role=region panels")
                print("   DOM       6 hotspots / 23 buttons / 23 panels  OK")

                # Single-open, ACROSS different body regions.
                page.locator("#ph-btn-a01").click()
                if count_true(page) != 1:
                    fail("first click did not open exactly one accordion")
                page.locator("#ph-btn-a16").click()
                if count_true(page) != 1:
                    fail("clicking a different region left more than one open")
                if page.locator("#ph-btn-a01").get_attribute("aria-expanded") != "false":
                    fail("the first accordion did not close")
                if page.locator("#ph-detail-a01").get_attribute("aria-hidden") != "true":
                    fail("closed panel is still exposed to screen readers")

                # The description must be VISIBLE, not merely flagged expanded.
                # The open/close uses a 260ms grid-template-rows transition, so
                # wait for it before measuring. A 0-height open panel would be
                # a silent functional failure that aria attributes cannot show.
                page.wait_for_timeout(400)
                det_h = page.evaluate(
                    "() => document.getElementById('ph-detail-a16')"
                    ".getBoundingClientRect().height"
                )
                if det_h < 20:
                    fail(f"open accordion has no visible height: {det_h}px")
                if page.locator("#ph-detail-a16 p").is_visible() is False:
                    fail("open accordion description is not visible")
                page.screenshot(path=str(SHOTS / "qa-open.png"))
                print(f"   single-open across regions + visible copy ({det_h:.0f}px)  OK")

                # Re-click closes; Escape closes and restores focus.
                page.locator("#ph-btn-a16").click()
                if count_true(page) != 0:
                    fail("clicking the open accordion did not close it")
                page.locator("#ph-btn-a03").focus()
                page.keyboard.press("Enter")
                if count_true(page) != 1:
                    fail("Enter did not open the focused accordion")
                page.keyboard.press("Escape")
                if count_true(page) != 0:
                    fail("Escape did not close the accordion")
                if page.evaluate("() => document.activeElement.id") != "ph-btn-a03":
                    fail("Escape did not restore focus to the header")
                print("   keyboard Enter / Escape + focus restore  OK")

                # Hover a REGION LABEL -> exactly its own hotspot pulses.
                page.locator('.ph-group[data-region="shoulder"] .ph-group__title').hover()
                page.wait_for_timeout(120)
                pulsing = page.locator(".ph-hot.is-pulsing")
                if pulsing.count() != 1:
                    fail(f"hover pulsed {pulsing.count()} hotspots, expected 1")
                if pulsing.first.get_attribute("data-region") != "shoulder":
                    fail("hover pulsed the WRONG hotspot")
                page.screenshot(path=str(SHOTS / "qa-hover.png"))
                print("   hover -> correct single hotspot pulses  OK")

                # Drag tilt: clamped while dragging, flat again on release.
                stage = page.locator("#ph-stage")
                box = stage.bounding_box()
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                page.mouse.move(cx, cy)
                page.mouse.down()
                page.mouse.move(cx + 180, cy, steps=12)
                page.wait_for_timeout(120)
                ry = page.evaluate(
                    "() => parseFloat(document.getElementById('ph-stage')"
                    ".style.getPropertyValue('--ry')) || 0"
                )
                if not (0 < ry <= 16.01):
                    fail(f"drag tilt out of range: --ry={ry}")
                page.screenshot(path=str(SHOTS / "qa-tilt.png"))
                page.mouse.up()
                # Move the pointer completely OUT of the viewport. While the
                # cursor stays inside, passive parallax legitimately holds a
                # small tilt; leaving must settle the figure back to flat.
                page.mouse.move(5, 5)
                page.wait_for_timeout(500)
                ry2 = page.evaluate(
                    "() => parseFloat(document.getElementById('ph-stage')"
                    ".style.getPropertyValue('--ry')) || 0"
                )
                if abs(ry2) > 1:
                    fail(f"body did not settle flat after pointer left: --ry={ry2}")
                print(f"   drag tilt {ry:.1f}deg -> {ry2:.1f}deg (flat on leave)  OK")

                # -----------------------------------------------------------
                # 9. Dark / light toggle.
                # -----------------------------------------------------------
                if page.evaluate(
                    "() => document.body.getAttribute('data-theme')"
                ) != "dark":
                    fail("pinned-dark context did not boot in dark theme")
                ground_dark = page.evaluate(
                    "() => getComputedStyle(document.body).backgroundColor"
                )
                page.locator("#ph-theme").click()
                page.wait_for_timeout(150)
                if page.evaluate(
                    "() => document.body.getAttribute('data-theme')"
                ) != "light":
                    fail("toggle did not switch body to light theme")
                if page.locator("#ph-theme").get_attribute("aria-pressed") != "true":
                    fail("toggle did not report light as active (aria-pressed)")
                if not page.locator("#ph-body-light").is_visible():
                    fail("light anatomy plate is not visible in light theme")
                if page.locator("#ph-body").is_visible():
                    fail("dark anatomy plate still visible in light theme")
                ground_light = page.evaluate(
                    "() => getComputedStyle(document.body).backgroundColor"
                )
                if ground_dark == ground_light:
                    fail(f"theme toggle changed nothing visually: {ground_dark}")
                page.screenshot(path=str(SHOTS / "qa-light.png"))
                # Open an accordion IN LIGHT MODE: the single-open rule and the
                # copy visibility must hold in both themes.
                page.locator("#ph-btn-a05").click()
                page.wait_for_timeout(350)
                if count_true(page) != 1:
                    fail("single-open broken in light theme")
                page.screenshot(path=str(SHOTS / "qa-light-open.png"))
                page.locator("#ph-theme").click()   # back to dark
                page.wait_for_timeout(150)
                if page.evaluate(
                    "() => document.body.getAttribute('data-theme')"
                ) != "dark":
                    fail("toggle did not switch back to dark")
                print(f"   theme toggle dark({ground_dark}) <-> light({ground_light})  OK")
                ctx.close()

            # A context whose OS PREFERS LIGHT must boot in light with no
            # click at all (and storage isolation means the earlier toggle
            # must not leak into it).
            lc = browser.new_context(viewport={"width": 1440, "height": 900},
                                     color_scheme="light")
            lp = lc.new_page()
            lp.goto(url, wait_until="load")
            lp.wait_for_timeout(300)
            if lp.evaluate("() => document.body.getAttribute('data-theme')") != "light":
                fail("OS light preference did not boot the light theme")
            lp.screenshot(path=str(SHOTS / "qa-light-os.png"))
            print("   OS prefers-light boots light (no click needed)  OK")
            lc.close()

            # ---------------------------------------------------------------
            # 8. Reduced motion: flat figure, no infinite pulse animation.
            # ---------------------------------------------------------------
            rm = browser.new_context(viewport={"width": 1440, "height": 900},
                                     reduced_motion="reduce", color_scheme="dark")
            rp = rm.new_page()
            rp.goto(url, wait_until="load")
            rp.wait_for_timeout(300)
            transform = rp.evaluate(
                "() => getComputedStyle(document.getElementById('ph-stage')).transform"
            )
            if transform not in ("none", "matrix(1, 0, 0, 1, 0, 0)"):
                fail(f"reduced motion still tilts the figure: {transform}")
            rp.locator('.ph-group[data-region="shoulder"] .ph-group__title').hover()
            rp.wait_for_timeout(120)
            anim = rp.evaluate(
                "() => getComputedStyle(document.querySelector('.ph-hot.is-pulsing .ph-hot__ring')"
                ").animationDuration"
            )
            # Under reduced motion the duration is forced to ~0.001ms.
            if anim and anim not in ("0s", "0.001ms", "1e-05s"):
                try:
                    if float(anim.replace("ms", "").replace("s", "")) > 0.01:
                        fail(f"reduced motion still animates: {anim}")
                except ValueError:
                    pass
            rp.screenshot(path=str(SHOTS / "qa-reduced-motion.png"))
            print("   reduced motion: flat figure, no pulse  OK")
            rm.close()
        finally:
            browser.close()

    if http_requests:
        fail(f"hero made network requests: {http_requests[:3]}")
    if errors:
        fail(f"console/page errors: {errors[:3]}")
    print("   0 console errors, 0 network requests  OK")
    print("browser verification passed")


if __name__ == "__main__":
    main()

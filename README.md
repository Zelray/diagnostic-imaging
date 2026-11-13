# Diagnostic imaging hero

This started as one static infographic a clinic uses in its marketing: a translucent anatomical figure, six glowing pain points, and 23 conditions listed down both sides. It was a flattened raster -- white background, baked-in text, a syringe and a logo across the top. The brief was to turn it into the hero of a new imaging site: the figure responds, the conditions open, the branding goes away.

Open `index.html`. That's the entire site. One file, about 260 KB, no dependencies, no build step, zero network requests. Double-click it and it works.

## What it does

Hover a body-part label and its pain point pulses on the figure while the other five dim. Click any of the 23 conditions and a sentence or two opens right under it. Click a different one and the first one shuts. One accordion open at a time, across all six panels -- that rule is structural, one variable in the script, so it can't drift.

You can drag the figure to tilt it a few degrees. The art is a flat front-view image with no back, so this is a perspective tilt only. It is never labeled 360 or 3D, because it isn't.

There's a dark/light toggle in the top corner. Dark is the default look: a cyan figure on near-black, like film on a lightbox. Light swaps in the original artwork, which was drawn for white anyway. The toggle follows your OS setting first, then remembers your click.

Keyboard works: Tab, arrows, Home, End, Escape. A screen reader announces each condition and which body region it lives in. Ask your OS for reduced motion and the pulse and tilt stop; the states change color instead.

Tested at 390, 900 and 1440 px wide with no horizontal scroll, zero console errors, and zero network requests. Screenshots are in `docs/`.

## What's in here

```
index.html                  the deliverable -- open this
build/hero-template.html    readable source (HTML/CSS/JS, no image blob)
build/data.json             the six regions and 23 conditions
build/build_html.py         bakes template + data + art into index.html
build/clean_asset.py        how the original art was cleaned (crop, alpha key)
build/verify_*.py           the checks: assets, offline safety, DOM, layout, browser
assets/                     the cleaned anatomy plates
docs/                       browser screenshots
```

## Rebuilding it

1. Edit `build/hero-template.html` and `build/data.json`. Don't edit `index.html` -- it's generated, and it contains a 165 KB base64 image.
2. Run `python build/build_html.py`.

`clean_asset.py` needs the original infographic, which is not in this repo. The artwork belongs to the clinic's brand and isn't ours to redistribute. Everything else runs as-is.

## Limits, stated plainly

- The 23 condition descriptions are draft copy pending the doctor's review. The page says so, on the page.
- The source list has a typo ("Quadraceps") and one near-duplicate pair ("Joint Arthritis" / "Arthritic Joints"). They were left as-is on purpose. Those are the doctor's calls, not a coder's.
- A few hairline callout marks from the original image still cross the figure. Every attempt to erase them damaged the art worse than the marks. The real fix is the layered original, which the clinic may have.
- The body is a perspective tilt, not a rotatable model. A true turn needs new art.

## Verification

Five scripts in `build/` check that the thing actually works. The browser one drives real Chrome through Playwright: it clicks two conditions in different regions and proves the first one closed, hovers a label and proves exactly one hotspot pulses, drags the figure and proves it settles back, and confirms the theme toggle flips both plates. Run them:

```
python build/verify_asset.py
python build/verify_html.py
python build/verify_dom.py
python build/verify_layout.py
python build/verify_browser.py
```

This is spec work for critique, so the page carries a noindex tag. Pull that one line out before it goes on a real site.

Next stop is the doctor's opinion.

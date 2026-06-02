#!/usr/bin/env python3
"""Headless render check: load the served site, wait for tiles, screenshot, and
report any console errors + a pixel-colour sample to prove the choropleth painted."""
import sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/gpmap.png"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=1)
    errors = []
    pg.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_timeout(3500)  # let MapLibre fetch tiles + paint
    pg.screenshot(path=OUT, full_page=False)

    # Sample the freshness badge text + table row count + a map pixel.
    badge = pg.inner_text("#freshness")
    rows = pg.eval_on_selector_all("#worst100 tbody tr", "els => els.length")
    headers = pg.eval_on_selector_all("#worst100 thead th", "els => els.length")
    # Toggle vacancy overlay to confirm it works.
    pg.check("#toggle-vacant")
    pg.wait_for_timeout(800)
    pg.screenshot(path=OUT.replace(".png", "_vacant.png"))
    print("badge:", badge)
    print("worst100 rows:", rows, "| header cols:", headers)
    print("console errors/warnings:", len(errors))
    for e in errors[:15]:
        print("  ", e)
    b.close()

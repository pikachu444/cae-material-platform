"""Capture and measure the UXC-00D static approval proposal."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs/17-evidence/images/uxc-00d-responsive-design"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
SCREENS = ("materials", "modeling", "activity", "administration")
REGIONS = {"materials": ("explorer-filter", "result-datasheet", "context"), "modeling": ("curve-tree", "settings", "graph"), "activity": ("result-datasheet",), "administration": ("explorer-filter", "result-datasheet", "context")}

def rectangle(page, role):
    locator = page.locator(f'[data-region="{role}"]')
    if not locator.count(): return {"role": role, "x": 0, "y": 0, "width": 0, "height": 0, "radius": "0px", "shadow": "none"}
    box = locator.bounding_box()
    style = locator.evaluate("e => { const s = getComputedStyle(e); return {radius:s.borderRadius, shadow:s.boxShadow} }")
    if not box: return {"role": role, "x": 0, "y": 0, "width": 0, "height": 0, **style}
    return {"role": role, **{key: round(box[key]) for key in ("x", "y", "width", "height")}, **style}

def tile(source, title, size=(700, 430)):
    image = Image.open(source).convert("RGB"); canvas = Image.new("RGB", size, "white")
    fitted = ImageOps.contain(image, (size[0] - 16, size[1] - 38)); canvas.paste(fitted, ((size[0] - fitted.width) // 2, 30 + (size[1] - 38 - fitted.height) // 2))
    draw = ImageDraw.Draw(canvas); draw.rectangle((0, 0, size[0], 28), fill="#27343b"); draw.text((9, 8), title, fill="white", font=ImageFont.load_default())
    return canvas

def board(items, name):
    cell = (700, 430); canvas = Image.new("RGB", (1400, 860), "#d8dddf")
    for index, (title, path) in enumerate(items): canvas.paste(tile(path, title, cell), ((index % 2) * 700, (index // 2) * 430))
    canvas.save(OUTPUT / name)

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True); entries = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for screen in SCREENS:
            for width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(f"http://127.0.0.1:8765/{screen}.html", wait_until="networkidle")
                page.screenshot(path=str(OUTPUT / f"{screen}-{width}x{height}.png"))
                entry = {"screen": screen, "viewport": {"width": width, "height": height}, "regions": [rectangle(page, role) for role in REGIONS[screen]], "pageHorizontalOverflow": page.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "nestedCards": page.locator(".card, [class*='card']").count(), "typography": {"body": page.locator("body").evaluate("e => getComputedStyle(e).fontSize"), "utility": page.evaluate("getComputedStyle(document.querySelector('.tree-row, .curve-tree, .admin-pane-title, .queue-table th')).fontSize")}, "primaryCount": page.locator(".button.primary").count() - page.locator(".preview-actions .button.primary").count()}
                if screen == "modeling":
                    svg = page.locator(".engineering-chart").bounding_box(); workspace = page.locator("[data-region='modeling-workspace']").bounding_box()
                    settings = page.locator("[data-region='settings']").bounding_box()
                    controls = {
                        label: page.get_by_role("button", name=label, exact=True).bounding_box()
                        for label in ("Select fit range", "Pick point", "Candidate parameters ▸")
                    }
                    entry["graphSvg"] = {"width": round(svg["width"]), "height": round(svg["height"])}
                    entry["graphWorkspacePercent"] = round(100 * svg["width"] / workspace["width"], 1)
                    entry["graphControlsVisible"] = all(
                        box
                        and box["y"] >= settings["y"]
                        and box["y"] + box["height"] <= settings["y"] + settings["height"]
                        for box in controls.values()
                    )
                if screen == "activity":
                    entry["queueRowHeight"] = round(
                        page.locator(".queue-table tbody tr").first.bounding_box()["height"]
                    )
                    entry["selectedQueueRows"] = page.locator(".queue-table tbody tr.selected").count()
                    entry["roleView"] = page.locator(".role-preview select").input_value()
                    entry["reviewerActions"] = {
                        label: page.get_by_role("button", name=label, exact=True).count()
                        for label in ("Request changes", "Approve", "Publish")
                    }
                    page.locator(".role-preview select").focus()
                    entry["focusOutline"] = page.locator(".role-preview select").evaluate(
                        "e => { const s = getComputedStyle(e); return {style:s.outlineStyle, width:s.outlineWidth} }"
                    )
                if screen == "materials":
                    entry["normalTextHasInternalId"] = "CMP-DEMO" in page.locator("body").inner_text()
                entries.append(entry); page.close()
        browser.close()
    (OUTPUT / "measurements.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    board([(screen.title(), OUTPUT / f"{screen}-1440x900.png") for screen in SCREENS], "four-screen-comparison.png")
    board([("Activity: attention queue", OUTPUT / "activity-1366x768.png"), ("Activity: 1440", OUTPUT / "activity-1440x900.png"), ("Administration: object workspace", OUTPUT / "administration-1366x768.png"), ("Administration: 1440", OUTPUT / "administration-1440x900.png")], "activity-administration-comparison.png")
    (OUTPUT / "manifest.yaml").write_text(
        "version: 1\n"
        "purpose: UXC-00D responsive design proposal approved by product owner on 2026-07-26\n"
        "approval_status: approved\n"
        "approval_date: 2026-07-26\n"
        "generator: docs/00-research/ux-layout-review/capture_uxc00d.py\n"
        "viewports: [1366x768, 1440x900, 1920x1080]\n"
        "screens: [materials, modeling, activity, administration]\n"
        "images: 14\n",
        encoding="utf-8",
    )

if __name__ == "__main__": main()

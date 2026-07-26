"""Capture the local-only Storybook foundation without using product fixtures or APIs."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


STORY_PATH = "/iframe.html?id=foundation-engineeringcurveplot--default&viewMode=story"
FOUNDATION_GROUPS = (
    "ApplicationShell",
    "ResizableSplitPane",
    "ModelingWorkspaceLayout",
    "EngineeringCurvePlot",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture the local Storybook DUI-09C foundation.")
    parser.add_argument("--base-url", default="http://127.0.0.1:6006")
    parser.add_argument(
        "--output",
        default="docs/user-guide/images/current/storybook-foundation-1440x900.png",
        type=Path,
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        index = page.request.get(f"{args.base_url.rstrip('/')}/index.json")
        if not index.ok:
            raise RuntimeError("Storybook index is unavailable")
        titles = {entry.get("title") for entry in index.json().get("entries", {}).values()}
        missing_groups = set(f"Foundation/{group}" for group in FOUNDATION_GROUPS) - titles
        if missing_groups:
            raise RuntimeError(f"Storybook foundation groups are missing: {sorted(missing_groups)}")
        page.goto(f"{args.base_url.rstrip('/')}{STORY_PATH}", wait_until="networkidle")
        page.locator("svg.processing-curve").wait_for()
        if page.locator("[role='alert']:visible, #error-message:visible, .sb-errordisplay:visible").count():
            raise RuntimeError("Storybook canvas reported a rendered error")
        if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
            raise RuntimeError("Storybook canvas has horizontal overflow")
        page.screenshot(path=str(output))
        browser.close()


if __name__ == "__main__":
    main()

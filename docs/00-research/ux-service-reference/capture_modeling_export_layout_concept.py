"""Capture the disposable MOD-EXPORT layout concept."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = ROOT / "docs/00-research/ux-service-reference/modeling-export-layout-concept.html"
DEFAULT_OUTPUT = (
    ROOT
    / "docs/17-evidence/images/issue-167-service-reference"
    / "modeling-export-layout-concept-1440x900.png"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(source.as_uri(), wait_until="networkidle")
        geometry = page.evaluate(
            """() => ({
              documentWidth: document.documentElement.scrollWidth,
              documentHeight: document.documentElement.scrollHeight,
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight
            })"""
        )
        if geometry["documentWidth"] != geometry["viewportWidth"]:
            raise RuntimeError(f"horizontal overflow: {geometry}")
        if geometry["documentHeight"] != geometry["viewportHeight"]:
            raise RuntimeError(f"vertical overflow: {geometry}")
        page.screenshot(path=str(output), full_page=False)
        browser.close()

    print(f"captured {output} at 1440x900")


if __name__ == "__main__":
    main()

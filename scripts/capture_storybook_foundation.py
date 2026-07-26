"""Capture local-only Storybook component baselines without product fixtures or APIs."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


FOUNDATION_STORY_PATH = "/iframe.html?id=foundation-engineeringcurveplot--default&viewMode=story"
GOVERNED_STORY_PATH = "/iframe.html?id=governed-workflowcomponents--target-preview-mixed-mapping-states&viewMode=story"
FOUNDATION_GROUPS = (
    "ApplicationShell",
    "ResizableSplitPane",
    "ModelingWorkspaceLayout",
    "EngineeringCurvePlot",
)
GOVERNED_STORIES = (
    "governed-workflowcomponents--modeling-stage-selected-with-readiness",
    "governed-workflowcomponents--modeling-stage-blocked",
    "governed-workflowcomponents--mapping-exact-transformed-approximated-and-unsupported",
    "governed-workflowcomponents--mapping-empty",
    "governed-workflowcomponents--target-preview-mixed-mapping-states",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture local Storybook component QA evidence.")
    parser.add_argument("--base-url", default="http://127.0.0.1:6006")
    parser.add_argument("--scope", choices=("foundation", "governed"), default="foundation")
    parser.add_argument(
        "--output",
        type=Path,
    )
    args = parser.parse_args()
    default_output = (
        "storybook-foundation-1440x900.png"
        if args.scope == "foundation"
        else "storybook-governed-workflow-1440x900.png"
    )
    output = (
        args.output
        if args.output is not None
        else Path("docs/user-guide/images/current") / default_output
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        index = page.request.get(f"{args.base_url.rstrip('/')}/index.json")
        if not index.ok:
            raise RuntimeError("Storybook index is unavailable")
        entries = index.json().get("entries", {})
        titles = {entry.get("title") for entry in entries.values()}
        missing_groups = set(f"Foundation/{group}" for group in FOUNDATION_GROUPS) - titles
        if missing_groups:
            raise RuntimeError(f"Storybook foundation groups are missing: {sorted(missing_groups)}")
        if args.scope == "foundation":
            story_path = FOUNDATION_STORY_PATH
            page.goto(f"{args.base_url.rstrip('/')}{story_path}", wait_until="networkidle")
            page.locator("svg.processing-curve").wait_for()
        else:
            present_ids = {entry.get("id") for entry in entries.values()}
            missing_stories = set(GOVERNED_STORIES) - present_ids
            if missing_stories:
                raise RuntimeError(
                    f"Storybook governed workflow stories are missing: {sorted(missing_stories)}"
                )
            story_path = GOVERNED_STORY_PATH
            page.goto(f"{args.base_url.rstrip('/')}{story_path}", wait_until="networkidle")
            page.get_by_role("region", name="Target mapping preflight").wait_for()
            for status in ("exact", "transformed", "approximated", "unsupported"):
                page.get_by_text(status, exact=True).wait_for()
        if page.locator("[role='alert']:visible, #error-message:visible, .sb-errordisplay:visible").count():
            raise RuntimeError("Storybook canvas reported a rendered error")
        if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
            raise RuntimeError("Storybook canvas has horizontal overflow")
        page.screenshot(path=str(output))
        browser.close()


if __name__ == "__main__":
    main()

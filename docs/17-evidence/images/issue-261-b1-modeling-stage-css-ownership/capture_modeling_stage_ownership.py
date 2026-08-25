"""Capture the #261 B1 ownership-only Modeling journey in an isolated demo.

The shared capture helper currently treats an optional Data "related" heading as
mandatory.  The live PR #311 DOM legitimately omits that group when the selected
DP780 result set has no related group, so this bounded wrapper accepts only that
known helper timeout and keeps the user-facing and exact-session assertions.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import scripts.capture_current_product as capture  # noqa: E402

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
OUTPUT = Path(__file__).resolve().parent / "after"


def prepare_data(page, base_url: str) -> dict[str, object]:
    try:
        capture._prepare_modeling(
            page,
            base_url,
            verify_reload=False,
            retain_comparisons=True,
        )
    except PlaywrightTimeoutError as exc:
        if ".modeling-data-related .modeling-data-rail-heading" not in str(exc):
            raise
        if page.locator(".modeling-data-related").count() != 0:
            raise RuntimeError("Data related group exists but its heading is unreachable") from exc

    capture._assert_modeling_normal_shell(page)
    page.locator(".modeling-data-browser").wait_for(state="visible", timeout=30_000)
    page.locator(".persistent-modeling-plot").wait_for(state="visible", timeout=30_000)
    page.get_by_role("button", name="Continue to Process", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    session = capture._modeling_session(page)
    focused = session.get("testData")
    mapping = session.get("mappingProfile")
    workspace = session.get("workspace")
    if (
        not isinstance(focused, dict)
        or focused.get("label") != capture.PROCESS_SOURCE_DOCUMENT_KEY
        or focused.get("revisionNo") != 1
        or not focused.get("revisionId")
    ):
        raise RuntimeError(f"Data did not retain exact Test Data r1: {focused!r}")
    if (
        not isinstance(mapping, dict)
        or mapping.get("label") != "CMP demo tensile JSON mapping"
        or mapping.get("revisionNo") != 1
        or not mapping.get("revisionId")
    ):
        raise RuntimeError(f"Data did not retain exact Mapping Profile r1: {mapping!r}")
    refs = workspace.get("selectedTestDataRefs") if isinstance(workspace, dict) else None
    if not isinstance(refs, list) or len(refs) != 3:
        raise RuntimeError(f"Data did not retain the three exact Test Data refs: {workspace!r}")
    close = page.get_by_role("button", name="Close comparison", exact=True)
    if close.count() and close.is_visible():
        close.click()
        capture._wait_for_data_plot(page, lines=1, legends=1)
    return {
        "testData": {
            "id": focused.get("id"),
            "revisionId": focused.get("revisionId"),
            "revisionNo": focused.get("revisionNo"),
        },
        "mappingProfile": {
            "id": mapping.get("id"),
            "revisionId": mapping.get("revisionId"),
            "revisionNo": mapping.get("revisionNo"),
        },
        "selectedTestDataRefs": [
            {
                "id": ref.get("id"),
                "revisionId": ref.get("revisionId"),
                "revisionNo": ref.get("revisionNo"),
            }
            for ref in refs
            if isinstance(ref, dict)
        ],
    }


def assert_viewport(page, stage: str) -> dict[str, object]:
    capture._assert_modeling_normal_shell(page)
    result = page.evaluate(
        """stage => {
          const root = document.documentElement;
          const workspace = document.querySelector(
            stage === 'export'
              ? '.modeling-target-preview, .modeling-export-blocked'
              : `.modeling-workspace-stage-${stage}`
          );
          const active = document.querySelector('.modeling-stage-shell button.active strong');
          if (!workspace) throw new Error(`missing ${stage} workspace`);
          const rect = workspace.getBoundingClientRect();
          const style = getComputedStyle(workspace);
          return {
            activeStage: active?.textContent?.trim() || null,
            pageOverflowX: root.scrollWidth > window.innerWidth + 1,
            pageOverflowY: root.scrollHeight > window.innerHeight + 1,
            workspace: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
            workspaceOverflowX: workspace.scrollWidth > workspace.clientWidth + 1,
            workspaceOverflowY: workspace.scrollHeight > workspace.clientHeight + 1,
            workspaceOverflow: `${style.overflowX}/${style.overflowY}`,
            surface: workspace.classList.contains('modeling-export-blocked')
              ? 'existing-alias-prerequisite-recovery'
              : 'canonical',
          };
        }""",
        stage,
    )
    if result["pageOverflowX"]:
        raise RuntimeError(f"{stage} introduced horizontal page overflow: {result!r}")
    expected = {"data": "Data", "process": "Process", "fit": "Fit", "export": "Export"}[stage]
    if result["activeStage"] != expected:
        raise RuntimeError(f"{stage} active-stage contract drifted: {result!r}")
    return result


def screenshot_crop(page, locator, path: Path) -> None:
    locator.wait_for(state="visible", timeout=30_000)
    path.parent.mkdir(parents=True, exist_ok=True)
    locator.screenshot(path=str(path), animations="disabled")


def capture_stage(page, stage: str, width: int, height: int) -> dict[str, object]:
    original = OUTPUT / "originals" / f"modeling-{stage}-{width}x{height}.png"
    focus_selector = (
        ".modeling-target-preview .export-native-preview-shell" if stage == "export" else None
    )
    capture._capture(
        page,
        original,
        width,
        height,
        focus_selector=focus_selector,
    )
    crops = OUTPUT / "crops"
    screenshot_crop(
        page,
        page.locator(".application-menu-bar"),
        crops / f"modeling-{stage}-{width}x{height}-header-100pct.png",
    )
    navigator = (
        page.get_by_role("complementary", name="Export setup")
        if stage == "export"
        else page.locator(".modeling-workspace-rail")
    )
    screenshot_crop(
        page,
        navigator,
        crops / f"modeling-{stage}-{width}x{height}-navigator-100pct.png",
    )
    controls = {
        "data": page.locator(".modeling-data-results"),
        "process": page.locator(".process-stage-options"),
        "fit": page.locator(".fit-stage-options"),
        "export": page.get_by_role("complementary", name="Export result context"),
    }[stage]
    screenshot_crop(
        page,
        controls,
        crops / f"modeling-{stage}-{width}x{height}-controls-100pct.png",
    )
    graph = (
        page.locator(".export-native-preview-shell")
        if stage == "export"
        else page.locator(".persistent-modeling-plot")
    )
    screenshot_crop(
        page,
        graph,
        crops / f"modeling-{stage}-{width}x{height}-graph-100pct.png",
    )
    return assert_viewport(page, stage)


def open_stage(page, stage: str) -> None:
    capture._open_modeling_stage(page, stage)
    page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
    page.locator(".modeling-work-title h1").get_by_text(
        capture.STAGE_HEADINGS[stage], exact=True
    ).wait_for(timeout=30_000)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: capture_modeling_stage_ownership.py <base-url>")
    base_url = sys.argv[1].rstrip("/")
    measurements: list[dict[str, object]] = []
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in VIEWPORTS:
            page = capture._new_page(browser, base_url, width, height)
            try:
                exact_context = prepare_data(page, base_url)
                measurements.append(
                    {
                        "stage": "data",
                        "viewport": f"{width}x{height}",
                        "exactContext": exact_context,
                        **capture_stage(page, "data", width, height),
                    }
                )

                open_stage(page, "process")
                capture._wait_modeling_process_panel(page)
                capture._assert_modeling_process_preview(page)
                capture._save_process_output_for_fit(
                    page,
                    label=f"B1 exact Process source {width}x{height}",
                    reason="Verify behavior preservation after the Modeling CSS ownership move.",
                )
                measurements.append(
                    {
                        "stage": "process",
                        "viewport": f"{width}x{height}",
                        **capture_stage(page, "process", width, height),
                        **capture._measure_process_fit(page, "process", width, height),
                    }
                )

                open_stage(page, "fit")
                capture._click_modeling_fit_preview_and_wait(page)
                measurements.append(
                    {
                        "stage": "fit",
                        "viewport": f"{width}x{height}",
                        **capture_stage(page, "fit", width, height),
                        **capture._measure_process_fit(
                            page, "fit", width, height, expected_fit_included=1
                        ),
                    }
                )

                capture._save_exact_fit_selection(page)
                open_stage(page, "export")
                capture._prepare_exact_metal_source_if_needed(page)
                capture._prepare_exact_target_preview(page)
                capture._assert_export_exact_source_surface(page)
                measurements.append(
                    {
                        "stage": "export",
                        "viewport": f"{width}x{height}",
                        **capture_stage(page, "export", width, height),
                    }
                )

                if width == 1440:
                    for stage in ("data", "process", "fit", "export"):
                        page.goto(f"{base_url}/datasets/processing?stage={stage}&family=metal")
                        page.locator(".modeling-work-title h1").get_by_text(
                            capture.STAGE_HEADINGS[stage], exact=True
                        ).wait_for(timeout=30_000)
                        capture._assert_modeling_normal_shell(page)
                        capture._capture(
                            page,
                            OUTPUT / "alias" / f"modeling-{stage}-alias-1440x900.png",
                            1440,
                            900,
                        )
                        measurements.append(
                            {
                                "stage": stage,
                                "viewport": "1440x900",
                                "surface": "datasets-processing-alias",
                                "url": page.url,
                                **assert_viewport(page, stage),
                            }
                        )
            finally:
                page.context.close()
        browser.close()

    (OUTPUT / "measurements.json").write_text(
        json.dumps(measurements, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"captures": 20, "aliasCaptures": 4, "measurements": len(measurements)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

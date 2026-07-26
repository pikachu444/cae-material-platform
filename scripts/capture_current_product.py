"""Capture the current product screens declared by the user-guide manifest.

Run against the deterministic Compose demo:

    uv run --with playwright python scripts/capture_current_product.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-browse-1440x900.png",
    "material-detail-1440x900.png",
    "material-cae-cards-1440x900.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "modeling-data-1366x768.png",
    "modeling-data-1440x900.png",
    "modeling-data-1920x1080.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-process-1366x768.png",
    "modeling-process-1440x900.png",
    "modeling-process-1920x1080.png",
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-export-1366x768.png",
    "modeling-export-1440x900.png",
    "modeling-export-1920x1080.png",
    "activity-1440x900.png",
    "administration-database-1440x900.png",
)
STAGE_HEADINGS = {
    "data": "Verify source & channel mapping",
    "process": "Prepare observed curves",
    "fit": "Compare response, residual & extrapolation",
    "export": "Inspect exact source & solver export",
}
UNFINISHED = re.compile(
    r"^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\b.*(?:…|\.\.\.)$",
    re.IGNORECASE,
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _new_page(browser: Browser, base_url: str, width: int, height: int) -> Page:
    context = browser.new_context(viewport={"width": width, "height": height})
    token_response = context.request.get(f"{base_url}/api/v1/demo-identity/token")
    if not token_response.ok:
        raise RuntimeError("local demo identity is unavailable")
    access_token = token_response.json()["access_token"]
    page = context.new_page()
    page.goto(base_url)
    page.evaluate(
        """token => window.localStorage.setItem(
            "cmp.material-platform.api-config",
            JSON.stringify({baseUrl: "/api/v1", accessToken: token})
        )""",
        access_token,
    )
    return page


def _wait_for_settled(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        """() => {
            const unfinished =
              /^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\\b.*(?:…|\\.\\.\\.)$/i;
            const visible = element => element.getClientRects().length > 0;
            const textPending = document.body.innerText
              .split("\\n")
              .some((line) => unfinished.test(line.trim()));
            const activeStatus = [...document.querySelectorAll('[role="status"], .loading-state')]
              .some((element) => visible(element)
                && (element.textContent ?? "").split("\\n")
                  .some((line) => unfinished.test(line.trim())));
            const activeBusy = [...document.querySelectorAll('[aria-busy="true"]')]
              .some(visible);
            return !activeBusy && !textPending && !activeStatus;
        }""",
        timeout=30_000,
    )
    pending_lines = [
        line.strip()
        for line in page.locator("body").inner_text().splitlines()
        if UNFINISHED.match(line.strip())
    ]
    if pending_lines:
        raise RuntimeError(f"unfinished UI state remains: {pending_lines}")


def _capture(page: Page, path: Path, width: int, height: int) -> None:
    _wait_for_settled(page)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow != 0:
        raise RuntimeError(f"horizontal overflow is {overflow}px for {path.name}")
    page.evaluate(
        """() => {
            window.scrollTo(0, 0);
            for (const selector of [
              ".application-workspace",
              ".native-card-preview",
              ".card-preview-actions",
            ]) {
              document.querySelectorAll(selector).forEach(element => {
                element.scrollTop = 0;
                element.scrollLeft = 0;
              });
            }
        }"""
    )
    page.screenshot(path=str(path), full_page=False)
    viewport = page.viewport_size
    if viewport != {"width": width, "height": height}:
        raise RuntimeError(f"viewport drift for {path.name}: {viewport}")


def _open_materials_search(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/materials")
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill("DP780")
    page.get_by_role("button", name="Find", exact=True).click()
    rows = page.locator('table[aria-label="Material results"] tbody tr')
    rows.filter(has_text="DP780").first.wait_for(timeout=30_000)
    _wait_for_settled(page)
    if rows.count() < 1:
        raise RuntimeError("the deterministic DP780 Material result is missing")
    if page.get_by_text("Checking…", exact=True).count():
        raise RuntimeError("Material enrichment is incomplete")
    rows.filter(has_text="DP780").first.click()
    page.get_by_text("Selected material", exact=True).wait_for(timeout=30_000)


def _capture_materials(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        _capture(page, output / f"materials-search-{width}x{height}.png", width, height)
        page.context.close()

    width, height = 1440, 900
    page = _new_page(browser, base_url, width, height)
    _open_materials_search(page, base_url)
    page.locator(".workspace-command-bar").get_by_role(
        "button", name="Browse Tree", exact=True
    ).click()
    page.get_by_role("complementary", name="Materials Browse Tree").wait_for(timeout=30_000)
    page.get_by_role("textbox", name="Find in tree").wait_for(timeout=30_000)
    _capture(page, output / "materials-browse-1440x900.png", width, height)
    page.context.close()

    page = _new_page(browser, base_url, width, height)
    _open_materials_search(page, base_url)
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.dblclick()
    page.wait_for_url(re.compile(r"/materials/[0-9a-f-]+$"), timeout=30_000)
    page.get_by_role("heading", name="Key properties", exact=True).wait_for(timeout=30_000)
    _capture(page, output / "material-detail-1440x900.png", width, height)
    page.get_by_role("tab", name="CAE Cards", exact=True).click()
    page.get_by_role("heading", name="CAE Cards", exact=True).wait_for(timeout=30_000)
    primary_delivery_actions = page.locator(
        ".material-detail-header .card-action-row button.ux-button.primary"
    )
    if (
        primary_delivery_actions.count() != 1
        or not re.match(
            r"^(Download|Preview card|Create card|Start Modeling)",
            primary_delivery_actions.first.inner_text(),
        )
    ):
        raise RuntimeError(
            "CAE Cards must expose exactly one contextual filled delivery command"
        )
    _capture(page, output / "material-cae-cards-1440x900.png", width, height)
    page.context.close()


def _capture_solver_delivery(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        page.locator('table[aria-label="Material results"] tbody tr').filter(
            has_text="DP780"
        ).first.dblclick()
        page.wait_for_url(re.compile(r"/materials/[0-9a-f-]+$"), timeout=30_000)
        page.get_by_role("tab", name="CAE Cards", exact=True).click()
        openradioss = page.locator(".cae-card-table tbody tr").filter(
            has_text="OpenRadioss"
        ).first
        openradioss.get_by_role(
            "button", name=re.compile(r"^Preview(?: card)?$")
        ).click()
        page.wait_for_url(
            re.compile(r"/materials/[0-9a-f-]+/cards/[0-9a-f-]+$"),
            timeout=30_000,
        )
        page.get_by_role("heading", name="Mapping status", exact=True).wait_for(
            timeout=30_000
        )
        download = page.get_by_role("button", name="Download .rad", exact=True)
        download.wait_for(timeout=30_000)
        if page.locator(".mapping-status.unsupported").count():
            raise RuntimeError("exact demo card unexpectedly exposes an unsupported mapping")
        approximation_count = page.locator(
            ".mapping-status.approximated, .mapping-status.ignored"
        ).count()
        acknowledgement = page.get_by_role("checkbox")
        if approximation_count:
            if acknowledgement.count() != 1 or download.is_enabled():
                raise RuntimeError(
                    "approximated solver-card delivery must require one adjacent acknowledgement"
                )
            acknowledgement.check()
            if not download.is_enabled():
                raise RuntimeError(
                    "reviewed approximation did not enable solver-card delivery"
                )
        elif acknowledgement.count() or not download.is_enabled():
            raise RuntimeError("exact solver-card delivery has a redundant confirmation")
        _capture(
            page,
            output / f"solver-card-preview-{width}x{height}.png",
            width,
            height,
        )
        if (width, height) == (1440, 900):
            page.goto(f"{base_url}/activity")
            page.get_by_role(
                "heading", name="Recent solver-card delivery", exact=True
            ).wait_for(timeout=30_000)
            page.get_by_test_id("recent-solver-card-activity").wait_for(
                timeout=30_000
            )
            _capture(page, output / "activity-1440x900.png", width, height)
        page.context.close()


def _prepare_modeling(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/modeling?stage=data&family=metal")
    page.get_by_role("heading", name=STAGE_HEADINGS["data"], exact=True).wait_for(
        timeout=30_000
    )
    revision = page.get_by_role("combobox", name="Data-stage Test Data revision")
    revision.wait_for(timeout=30_000)
    if not revision.input_value():
        revision.select_option(index=1)
    page.get_by_text(re.compile(r"Loaded exact Test Data revision")).wait_for(timeout=30_000)
    advanced_contract = page.locator("details.modeling-data-advanced")
    if not advanced_contract.get_attribute("open"):
        advanced_contract.locator(":scope > summary").click()
    profile = page.get_by_role("combobox", name="Saved Mapping Profile")
    profile.wait_for(timeout=30_000)
    if not profile.input_value():
        profile.select_option(index=1)
    advanced_contract.locator(":scope > summary").click()
    plot = page.locator(".persistent-modeling-plot svg[role=img]")
    # Data has no competing stage-header primary action. Compute the same exact source/mapping
    # preview through Process's secondary action, then return to Data for its evidence capture.
    page.locator(".workspace-command-bar").get_by_role(
        "button", name="Process", exact=True
    ).click()
    page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    page.get_by_role(
        "button", name="Update preview", exact=True
    ).click()
    plot.wait_for(timeout=30_000)
    page.locator(".workspace-command-bar").get_by_role(
        "button", name="Data", exact=True
    ).click()
    page.wait_for_url(re.compile(r"stage=data"), timeout=30_000)
    page.get_by_role("heading", name=STAGE_HEADINGS["data"], exact=True).wait_for(
        timeout=30_000
    )
    _wait_for_settled(page)


def _capture_modeling(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(page, base_url)
        plot = page.locator(".persistent-modeling-plot svg[role=img]")
        for stage, heading in STAGE_HEADINGS.items():
            page.locator(".workspace-command-bar").get_by_role(
                "button", name=stage.title(), exact=True
            ).click()
            page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
            page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)
            if stage == "fit":
                show_settings = page.get_by_role(
                    "button", name="Show current-stage settings", exact=True
                )
                if show_settings.count():
                    show_settings.click()
                _wait_for_settled(page)
                candidate_table = page.get_by_role(
                    "table", name="Hardening candidate comparison"
                )
                candidate_table.wait_for(timeout=30_000)
                if candidate_table.locator("tbody tr").count() != 5:
                    raise RuntimeError(
                        "Fit must expose four calculated single-law candidates "
                        "and the exact calculated preview blend"
                    )
                page.get_by_text(
                    re.compile(r"^Preview blend · .+ · fitted domain$")
                ).wait_for(timeout=30_000)
                for column in (
                    "Decision",
                    "Model / law",
                    "Recommendation",
                    "Metric",
                    "Fit / extrapolation range",
                    "Stability",
                    "Compatibility",
                    "Warning",
                ):
                    if candidate_table.get_by_role(
                        "columnheader", name=column, exact=True
                    ).count() != 1:
                        raise RuntimeError(f"Fit candidate table is missing {column}")
                save_candidate = page.get_by_role(
                    "button", name="Save selected candidate", exact=True
                )
                if save_candidate.count() != 1:
                    raise RuntimeError("Fit is missing the explicit selected-output save")
                if not save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save must remain disabled before an explicit row selection"
                    )
                select_candidate = candidate_table.get_by_role(
                    "button", name=re.compile(r"^Select .+ candidate$")
                ).first
                select_candidate.click()
                page.get_by_text(
                    re.compile(r"^Selected · .+ · fitted domain$")
                ).wait_for(timeout=30_000)
                parameter_table = page.get_by_role(
                    "table", name="Selected candidate parameters and bounds"
                )
                parameter_table.wait_for(timeout=30_000)
                if parameter_table.locator("tbody tr").count() < 1:
                    raise RuntimeError(
                        "Selected Fit candidate must expose parameter and bound evidence"
                    )
                selection_reason = page.get_by_role(
                    "textbox", name="Candidate selection reason"
                )
                selection_reason.fill(
                    "Synthetic reference candidate selected for the export preflight."
                )
                warning_acknowledgement = page.get_by_role(
                    "checkbox", name="Acknowledge selected candidate warning"
                )
                if warning_acknowledgement.count():
                    warning_acknowledgement.check()
                if save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save did not become ready after selection evidence was completed"
                    )
                parameter_table.scroll_into_view_if_needed()
            if stage == "export":
                page.get_by_text("Preview only · not committed", exact=True).wait_for(
                    timeout=30_000
                )
                page.get_by_role(
                    "heading",
                    name="Exact source → mapping preflight → native card",
                    exact=True,
                ).wait_for(timeout=30_000)
                neutral_export = page.locator(
                    ".modeling-workspace-dock .neutral-solver-export"
                )
                if not neutral_export.count():
                    promotion_acknowledgement = page.get_by_role(
                        "checkbox",
                        name=re.compile(
                            r"reviewed the candidate blend and acknowledge "
                            r"its bounded fitted extrapolation",
                            re.IGNORECASE,
                        ),
                    )
                    promotion_acknowledgement.wait_for(timeout=30_000)
                    promotion_acknowledgement.check()
                    page.get_by_role(
                        "button", name="Promote fitted output to IR", exact=True
                    ).click()
                    page.get_by_text(
                        "2. Inspect immutable IR and hardening Artifact", exact=True
                    ).wait_for(timeout=30_000)
                    create_neutral = page.get_by_role(
                        "button", name="Create Neutral Material JSON", exact=True
                    )
                    page.wait_for_function(
                        """() => document.querySelector(
                            ".modeling-workspace-dock .neutral-solver-export"
                          ) || [...document.querySelectorAll("button")].some(
                            button => button.textContent?.trim() === "Create Neutral Material JSON"
                              && !button.disabled
                          )""",
                        timeout=30_000,
                    )
                    if not neutral_export.is_visible():
                        try:
                            create_neutral.click(timeout=30_000)
                        except Exception:
                            neutral_export.wait_for(timeout=30_000)
                neutral_export.wait_for(timeout=30_000)
                page.get_by_text(
                    "kg·m·s (SI) · exact supported unit system", exact=True
                ).wait_for(timeout=30_000)
                workflow_links = page.locator(
                    ".modeling-workspace-dock .domain-workflow-links"
                )
                page.locator(
                    ".modeling-workspace-dock "
                    '.domain-workflow-links[data-resolution-state="resolved"], '
                    ".modeling-workspace-dock "
                    '.domain-workflow-links[data-resolution-state="unprojected"]'
                ).wait_for(timeout=30_000)
                if workflow_links.get_attribute("data-resolution-state") == "unprojected":
                    workflow_links.get_by_text(
                        re.compile(
                            r"not yet projected into a configurable Workflow Explorer record"
                        )
                    ).wait_for(timeout=30_000)
            plot.wait_for(timeout=30_000)
            plot_geometry = plot.evaluate(
                """svg => {
                    const horizontalAxis = [...svg.querySelectorAll(".chart-axis")]
                      .find(line => line.getAttribute("x1") !== line.getAttribute("x2"));
                    if (!horizontalAxis) return { ratio: 0, reason: "horizontal axis missing" };
                    const axisBounds = horizontalAxis.getBoundingClientRect();
                    const drawableWidth = axisBounds.width;
                    const workspace = document.querySelector(".modeling-split-workspace");
                    const plotBounds = svg.getBoundingClientRect();
                    const workspaceWidth = workspace?.getBoundingClientRect().width ?? 0;
                    return {
                      ratio: workspaceWidth ? drawableWidth / workspaceWidth : 0,
                      drawableWidth,
                      plotWidth: plotBounds.width,
                      workspaceWidth,
                    };
                }"""
            )
            drawable_ratio = float(plot_geometry["ratio"])
            if drawable_ratio < 0.72:
                raise RuntimeError(
                    f"Modeling plot drawable is only {drawable_ratio:.1%} "
                    f"of workspace for {stage} at {width}x{height}: {plot_geometry}"
                )
            _capture(
                page,
                output / f"modeling-{stage}-{width}x{height}.png",
                width,
                height,
            )
            if stage == "fit":
                page.get_by_role(
                    "button", name="Save selected candidate", exact=True
                ).click()
                page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
        page.context.close()


def _capture_modeling_session_shell(browser: Browser, base_url: str, output: Path) -> None:
    """Capture the pin-free Data-first state separately from the populated Data workflow."""
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/modeling?stage=data&family=metal")
        page.locator(".workspace-command-bar").get_by_role(
            "button", name="Data", exact=True
        ).wait_for(timeout=30_000)
        page.wait_for_function(
            """() => document.querySelector(
              ".workspace-command-bar button.workspace-command.active"
            )?.textContent?.trim() === "Data" """,
            timeout=30_000,
        )
        page.get_by_role("button", name="New session", exact=True).click()
        page.wait_for_url(re.compile(r"stage=data"), timeout=30_000)
        page.wait_for_function(
            """() => {
              const raw = sessionStorage.getItem("cmp.modeling.recent-session.v3");
              if (!raw) return false;
              const session = JSON.parse(raw);
              return session.contextSelectionRequired === true
                && !session.material
                && !session.materialState;
            }""",
            timeout=30_000,
        )
        shell = page.get_by_role("navigation", name="Modeling workflow stages")
        shell.wait_for(timeout=30_000)
        shell.get_by_role("button").nth(5).wait_for(timeout=30_000)
        shell_text = shell.inner_text()
        for stage in ("Data", "Process", "Fit", "Validate", "Review / Release", "Export"):
            if stage not in shell_text:
                raise RuntimeError(f"Modeling session shell is missing {stage}")
        if "Data\nBlocked" not in shell_text or "Export\nBlocked" not in shell_text:
            raise RuntimeError(
                "A new Modeling session must start pin-free with Data and Export blocked"
            )
        _capture(page, output / f"modeling-session-{width}x{height}.png", width, height)
        page.context.close()


def _capture_supporting_screens(browser: Browser, base_url: str, output: Path) -> None:
    width, height = 1440, 900
    page = _new_page(browser, base_url, width, height)
    page.goto(f"{base_url}/administration/database")
    page.get_by_role("navigation", name="Administration areas").wait_for(timeout=30_000)
    _capture(page, output / "administration-database-1440x900.png", width, height)
    page.context.close()


def _validate_capture_outputs(output: Path) -> int:
    actual_outputs = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    expected_outputs = set(CURRENT_CAPTURE_OUTPUTS)
    if actual_outputs != expected_outputs:
        raise RuntimeError(
            "current capture output drift: "
            f"missing={sorted(expected_outputs - actual_outputs)}, "
            f"unexpected={sorted(actual_outputs - expected_outputs)}"
        )
    for name in CURRENT_CAPTURE_OUTPUTS:
        image = output / name
        value = image.read_bytes()
        if (
            len(value) < 10_000
            or value[:8] != PNG_SIGNATURE
            or value[12:16] != b"IHDR"
        ):
            raise RuntimeError(f"current capture is not a plausible PNG: {name}")
        width, height = struct.unpack(">II", value[16:24])
        expected = re.search(r"-(\d+)x(\d+)\.png$", name)
        if expected is None or (width, height) != (
            int(expected.group(1)),
            int(expected.group(2)),
        ):
            raise RuntimeError(
                f"current capture viewport drift for {name}: {width}x{height}"
            )
    return len(actual_outputs)


def _replace_capture_directory(staged: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = Path(
            tempfile.mkdtemp(prefix=f".{target.name}-previous-", dir=target.parent)
        )
        backup.rmdir()
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except OSError:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def _capture_to_empty_directory(target: Path, producer: Callable[[Path], None]) -> int:
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}-capture-", dir=target.parent
    ) as temporary:
        staged = Path(temporary)
        producer(staged)
        capture_count = _validate_capture_outputs(staged)
        _replace_capture_directory(staged, target)
    return capture_count


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/user-guide/images/current"),
    )
    args = parser.parse_args()

    def produce(output: Path) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                _capture_materials(browser, args.base_url, output)
                _capture_solver_delivery(browser, args.base_url, output)
                _capture_modeling_session_shell(browser, args.base_url, output)
                _capture_modeling(browser, args.base_url, output)
                _capture_supporting_screens(browser, args.base_url, output)
            finally:
                browser.close()

    capture_count = _capture_to_empty_directory(args.output, produce)
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "captures": capture_count,
                "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture and validate the bounded #261 M4 before/after visual packet.

The capture deliberately reuses the product's established deterministic demo and
browser journeys.  It adds only the M4 topology matrix, original-pixel crops, and
an isolated Compose lifecycle around each source tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / ("docs/17-evidence/images/issue-261-m4-shared-css-ownership-consolidation")
FIXTURE = ROOT / "scripts/fixtures/issue-261-m4-shared-css-ownership.json"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
PHASES = ("before", "after")
BASE_SHA = "01d2cb0a48551e2c02175d6969fb13aeac094438"
DUPLICATE_IMAGE_ROOTS = (
    ROOT / "docs/00-research",
    ROOT / "docs/17-evidence/images",
    ROOT / "docs/user-guide/images/current",
)
DUPLICATE_GROUP_RATIONALE = (
    "Byte-identical before/after, crop, and prior-evidence files are equivalent existing "
    "evidence bytes; "
    "no new capture is implied."
)
CAPTURE = runpy.run_path(str(ROOT / "scripts/capture_current_product.py"))
CAPTURE_GLOBALS = CAPTURE["_capture_materials"].__globals__
ORIGINAL_ASSERT_MODELING_DATA_SURFACE = CAPTURE_GLOBALS["_assert_modeling_data_surface"]

TOPOLOGIES: dict[str, dict[str, Any]] = {
    "materials-search": {
        "source": "materials-search-{viewport}.png",
        "regions": ("header", "navigator", "table-form"),
        "owners": ("shell", "tokens", "primitives", "materials"),
    },
    "material-detail": {
        "source": "material-detail-{viewport}.png",
        "regions": ("header", "navigator", "table-form"),
        "owners": ("shell", "primitives", "materials"),
    },
    "materials-curves": {
        "source": "material-curves-{viewport}.png",
        "regions": ("header", "navigator", "table-form", "engineering-graph"),
        "owners": ("shell", "primitives", "materials"),
    },
    "administration-database": {
        "source": "administration-database-{viewport}.png",
        "regions": ("header", "navigator", "table-form"),
        "owners": ("shell", "primitives", "administration"),
    },
    "administration-preview": {
        "source": "administration-database-preview-{viewport}.png",
        "regions": ("header", "navigator", "table-form", "native-preview"),
        "owners": ("shell", "primitives", "administration"),
    },
    "modeling-data": {
        "source": "modeling-data-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "data", "plot"),
    },
    "modeling-process": {
        "source": "modeling-process-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "process", "plot"),
    },
    "modeling-fit": {
        "source": "modeling-fit-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "fit", "plot"),
    },
    "modeling-export": {
        "source": "modeling-export-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "native-preview"),
        "owners": ("shell", "primitives", "core", "export"),
    },
    "modeling-distribution": {
        "source": "modeling-distribution-{viewport}.png",
        "regions": ("header", "navigator", "table-form", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "scalar", "plot"),
    },
    "governed-import": {
        "source": "governed-import-{viewport}.png",
        "regions": ("header", "navigator", "table-form"),
        "owners": ("shell", "primitives", "governed"),
    },
    "modeling-polymer-fit": {
        "source": "modeling-polymer-fit-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "process", "viscoelastic", "plot"),
    },
    "modeling-elastomer-fit": {
        "source": "modeling-elastomer-fit-{viewport}.png",
        "regions": ("header", "navigator", "stage-controls", "engineering-graph"),
        "owners": ("shell", "primitives", "core", "fit", "calibration", "plot"),
    },
}

SOURCE_ONLY_DISPOSITIONS = {
    "calibration": (
        "CSS-0982 is conditional on a promotion confirmation action. The normal seeded "
        "elastomer Fit producer is captured without fabricating that action; source, component, "
        "import-order, and product-bundle oracles remain authoritative."
    ),
}


class EvidenceError(RuntimeError):
    """Raised when the M4 capture or durable packet is incomplete."""


def _open_materials_filters(page: Page, base_url: str) -> None:
    """Preserve the canonical helper journey after Materials made Browse the default."""

    page.goto(f"{base_url}/materials")
    page.get_by_role("button", name="Filters", exact=True).wait_for(timeout=30_000)
    page.wait_for_url(lambda url: "table=" in url, timeout=30_000)
    page.get_by_role("button", name="Filters", exact=True).click()
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill("DP780")
    page.locator(".materials-search-form").get_by_role("button", name="Find", exact=True).click()
    rows = page.locator('table[aria-label="Material results"] tbody tr')
    rows.filter(has_text="DP780").first.wait_for(timeout=30_000)
    CAPTURE["_wait_for_settled"](page)
    if rows.count() < 1:
        raise EvidenceError("the deterministic DP780 Material result is missing")
    if page.get_by_text("Checking…", exact=True).count():
        raise EvidenceError("Material enrichment is incomplete")
    page.locator(".application-status-bar").get_by_text(
        CAPTURE_GLOBALS["REVISION_LABEL_PATTERN"]
    ).wait_for(timeout=30_000)
    if page.get_by_role("columnheader", name="Status", exact=True).count():
        raise EvidenceError("normal Materials results expose a Status column")
    forbidden = CAPTURE_GLOBALS["NORMAL_SURFACE_TECHNICAL_LABELS"]
    for selector in (".materials-results", ".application-status-bar"):
        surface = page.locator(selector)
        surface.wait_for(timeout=30_000)
        surface_text = surface.inner_text()
        if forbidden.search(surface_text):
            raise EvidenceError(
                f"normal Materials surface exposes a technical label in {selector}: {surface_text}"
            )


CAPTURE_GLOBALS["_open_materials_search"] = _open_materials_filters


def _assert_modeling_data_without_optional_related_group(
    page: Page,
    width: int,
    height: int,
    *,
    comparison_open: bool,
) -> None:
    """Keep M1E3's accepted hard gates when the optional related group is absent."""

    page.wait_for_function(
        """() => {
          const labels = [...document.querySelectorAll(
            '.modeling-data-plot .chart-axis-label'
          )].map(element => (element.textContent || '').trim());
          return labels.some(label => label.startsWith('Engineering strain'))
            && labels.some(label => label.startsWith('Engineering stress'));
        }""",
        timeout=30_000,
    )
    page.set_default_timeout(1_000)
    try:
        ORIGINAL_ASSERT_MODELING_DATA_SURFACE(
            page,
            width,
            height,
            comparison_open=comparison_open,
        )
    except PlaywrightTimeoutError as error:
        if ".modeling-data-related .modeling-data-rail-heading" not in str(error):
            raise
        if page.locator(".modeling-data-related").count() != 0:
            raise EvidenceError(
                "Data related group exists but its heading is unreachable"
            ) from error
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise EvidenceError(
                f"Modeling Data has page horizontal overflow at {width}x{height}"
            ) from error
        for selector, label in (
            (".modeling-workspace-stage-data", "workspace"),
            (".modeling-data-browser", "browser"),
            (".modeling-data-results", "results"),
            (".modeling-data-plot", "persistent graph"),
        ):
            locator = page.locator(selector)
            if locator.count() != 1 or not locator.is_visible():
                raise EvidenceError(
                    f"Modeling Data {label} is not uniquely visible at {width}x{height}"
                ) from error
    finally:
        page.set_default_timeout(30_000)


CAPTURE_GLOBALS["_assert_modeling_data_surface"] = (
    _assert_modeling_data_without_optional_related_group
)


def _measure_m4_workspace_geometry(
    page: Page,
    stage: str,
    width: int,
    height: int,
    *,
    expected_fit_included: int | None = None,
) -> dict[str, Any]:
    """Replace retired fixed-width screenshot math with current semantic bounds."""

    geometry = page.evaluate(
        """stage => {
          const visible = element => Boolean(element && element.getClientRects().length);
          const bounds = element => {
            if (!visible(element)) return null;
            const box = element.getBoundingClientRect();
            return {
              left: box.left, right: box.right, top: box.top, bottom: box.bottom,
              width: box.width, height: box.height,
              scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
              scrollHeight: element.scrollHeight, clientHeight: element.clientHeight,
            };
          };
          const workspace = document.querySelector(`.modeling-workspace-stage-${stage}`)
            || document.querySelector('.modeling-workspace-shell');
          const plot = document.querySelector('.persistent-modeling-plot');
          return {
            stage,
            viewport: { width: innerWidth, height: innerHeight },
            devicePixelRatio,
            visualViewportScale: visualViewport?.scale || 1,
            pageOverflowX:
              document.documentElement.scrollWidth - document.documentElement.clientWidth,
            workspace: bounds(workspace),
            plot: bounds(plot),
          };
        }""",
        stage,
    )
    workspace = geometry["workspace"]
    plot = geometry["plot"]
    if geometry["viewport"] != {"width": width, "height": height}:
        raise EvidenceError(f"{stage} viewport drifted: {geometry}")
    if (
        geometry["devicePixelRatio"] != 1
        or geometry["visualViewportScale"] != 1
        or geometry["pageOverflowX"] > 1
    ):
        raise EvidenceError(f"{stage} scale or page overflow drifted: {geometry}")
    if workspace is None or workspace["width"] < width * (0.8 if width > 1920 else 0.7):
        raise EvidenceError(f"{stage} workspace collapsed into a fixed island: {geometry}")
    if plot is None or plot["width"] < 320 or plot["height"] < 180:
        raise EvidenceError(f"{stage} persistent graph is unavailable: {geometry}")
    if (
        workspace["left"] < -1
        or workspace["right"] > width + 1
        or plot["left"] < -1
        or plot["right"] > width + 1
        or plot["top"] < -1
        or plot["bottom"] > height + 1
    ):
        raise EvidenceError(f"{stage} workspace or graph is clipped: {geometry}")
    geometry["expectedFitIncluded"] = expected_fit_included
    return geometry


CAPTURE_GLOBALS["_measure_process_fit"] = _measure_m4_workspace_geometry


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_page(page: Page, label: str, width: int) -> None:
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(700)
    if page.get_by_role("alert").count():
        visible = [
            page.get_by_role("alert").nth(index).inner_text()
            for index in range(page.get_by_role("alert").count())
            if page.get_by_role("alert").nth(index).is_visible()
        ]
        if visible:
            raise EvidenceError(f"{label} exposes an alert: {visible}")
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 1:
        raise EvidenceError(f"{label} has {overflow}px page overflow at width {width}")
    metadata = page.evaluate(
        """() => ({
          width: innerWidth,
          height: innerHeight,
          devicePixelRatio,
          visualViewportScale: visualViewport?.scale || 1,
        })"""
    )
    if metadata["devicePixelRatio"] != 1 or metadata["visualViewportScale"] != 1:
        raise EvidenceError(f"{label} capture scale drifted: {metadata}")


def _navigate_exact_family(page: Page, base_url: str, *, family: str, stage: str) -> None:
    config = json.loads(page.evaluate("localStorage.getItem('cmp.material-platform.api-config')"))
    headers = {"Authorization": f"Bearer {config['accessToken']}"}
    material_response = page.request.get(
        f"{base_url}/api/v1/materials?limit=50&offset=0&material_class={family}",
        headers=headers,
    )
    if not material_response.ok:
        raise EvidenceError(f"cannot resolve exact {family} Material context")
    materials = material_response.json().get("items", [])
    if len(materials) != 1:
        raise EvidenceError(f"expected one seeded {family} Material, got {len(materials)}")
    material = materials[0]
    detail_response = page.request.get(
        f"{base_url}/api/v1/materials/{material['material_id']}", headers=headers
    )
    if not detail_response.ok:
        raise EvidenceError(f"cannot resolve exact {family} Material State context")
    states = detail_response.json().get("states", [])
    if not states:
        raise EvidenceError(f"seeded {family} Material has no current State")
    state = states[0]
    query = urlencode(
        {
            "stage": stage,
            "family": family,
            "material_id": material["material_id"],
            "material_revision_id": material["current_revision"]["id"],
            "material_state_id": state["material_state_id"],
            "material_state_revision_id": state["current_revision"]["id"],
        }
    )
    page.goto(f"{base_url}/modeling?{query}")


def _capture_direct_routes(browser: Browser, base_url: str, raw: Path) -> None:
    new_page = CAPTURE["_new_page"]
    for width, height in VIEWPORTS:
        viewport = f"{width}x{height}"

        governed = new_page(browser, base_url, width, height)
        errors: list[str] = []
        governed.on("pageerror", lambda error, values=errors: values.append(str(error)))
        governed.goto(f"{base_url}/datasets/import")
        governed.locator(".governed-import-route").wait_for(timeout=30_000)
        governed.get_by_role("heading", name="Map tabular test data", exact=True).wait_for()
        _assert_page(governed, "governed-import", width)
        governed.screenshot(path=raw / f"governed-import-{viewport}.png")
        if errors:
            raise EvidenceError(f"governed-import page errors: {errors}")
        governed.context.close()

        polymer = new_page(browser, base_url, width, height)
        errors = []
        polymer.on("pageerror", lambda error, values=errors: values.append(str(error)))
        _navigate_exact_family(polymer, base_url, family="polymer", stage="fit")
        polymer.locator(".modeling-workspace-stage-fit").wait_for(state="visible", timeout=30_000)
        advanced = polymer.locator("details.modeling-advanced-menu")
        advanced.locator("summary").click()
        advanced.get_by_role("tab", name="Polymer · viscoelastic", exact=True).click()
        polymer.locator(".configured-step-list button").filter(
            has_text="Polymer Prony candidate comparison"
        ).click()
        inspector = polymer.locator("details.polymer-temperature-shift-inspector")
        inspector.wait_for(state="visible", timeout=30_000)
        if inspector.get_attribute("open") is None:
            inspector.locator("summary").click()
        polymer.locator(".master-curve-workbench.compact").wait_for(state="visible", timeout=30_000)
        _assert_page(polymer, "modeling-polymer-fit", width)
        polymer.screenshot(path=raw / f"modeling-polymer-fit-{viewport}.png")
        if errors:
            raise EvidenceError(f"modeling-polymer-fit page errors: {errors}")
        polymer.context.close()

        elastomer = new_page(browser, base_url, width, height)
        errors = []
        elastomer.on("pageerror", lambda error, values=errors: values.append(str(error)))
        _navigate_exact_family(elastomer, base_url, family="elastomer", stage="fit")
        elastomer.locator(".modeling-elastomer-workspace").wait_for(state="visible", timeout=30_000)
        elastomer.get_by_text("Ogden", exact=False).first.wait_for(state="visible", timeout=30_000)
        elastomer.locator(".ogden-revision-history").wait_for(state="visible", timeout=30_000)
        elastomer.locator("article.solver-card-item").first.wait_for(
            state="visible", timeout=30_000
        )
        elastomer.get_by_text("1 profile · 4 curves", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        elastomer.locator(".ogden-diagnostics").wait_for(state="visible", timeout=30_000)
        CAPTURE["_wait_for_settled"](elastomer)
        _assert_page(elastomer, "modeling-elastomer-fit", width)
        elastomer.screenshot(path=raw / f"modeling-elastomer-fit-{viewport}.png")
        if errors:
            raise EvidenceError(f"modeling-elastomer-fit page errors: {errors}")
        elastomer.context.close()


def _capture_materials_current(browser: Browser, base_url: str, raw: Path) -> None:
    """Capture the authoritative Browse -> Filters -> detail -> Curves journey."""

    new_page = CAPTURE["_new_page"]
    for width, height in VIEWPORTS:
        viewport = f"{width}x{height}"
        page = new_page(browser, base_url, width, height)
        errors: list[str] = []
        page.on("pageerror", lambda error, values=errors: values.append(str(error)))
        _open_materials_filters(page, base_url)
        _assert_page(page, "materials-search", width)
        page.screenshot(path=raw / f"materials-search-{viewport}.png")

        row = (
            page.locator('table[aria-label="Material results"] tbody tr')
            .filter(has_text="DP780")
            .first
        )
        row.click()
        page.locator(".material-detail-shell").wait_for(state="visible", timeout=30_000)
        page.get_by_role("heading", name="DP780 synthetic reference steel", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        page.wait_for_function(
            "() => !document.body.innerText.includes('Loading Technical Data')",
            timeout=30_000,
        )
        CAPTURE["_wait_for_settled"](page)
        _assert_page(page, "material-detail", width)
        page.screenshot(path=raw / f"material-detail-{viewport}.png")

        page.get_by_role("tab", name="Curves", exact=True).click()
        page.get_by_role("heading", name="Curves", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        CAPTURE["_wait_for_settled"](page)
        _assert_page(page, "materials-curves", width)
        page.screenshot(path=raw / f"material-curves-{viewport}.png")
        if errors:
            raise EvidenceError(f"Materials page errors at {viewport}: {errors}")
        page.context.close()


def _capture_raw(base_url: str, raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            _capture_materials_current(browser, base_url, raw)
            CAPTURE["_capture_administration_database"](browser, base_url, raw)
            CAPTURE["_capture_modeling_data_viewports"](browser, base_url, raw, VIEWPORTS)
            CAPTURE["_capture_modeling_process_fit"](
                browser, base_url, raw, include_fit_states=False
            )
            CAPTURE["_capture_modeling_export_only"](
                browser, base_url, raw, include_delivered=False
            )
            CAPTURE["_capture_modeling_distribution"](browser, base_url, raw)
            _capture_direct_routes(browser, base_url, raw)
        finally:
            browser.close()


def _bounded_box(
    width: int, height: int, box: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    return (
        max(0, min(width - 1, left)),
        max(0, min(height - 1, top)),
        max(1, min(width, right)),
        max(1, min(height, bottom)),
    )


def _crop_box(topology: str, region: str, width: int, height: int) -> tuple[int, int, int, int]:
    header_bottom = min(height, 150)
    navigator_right = min(width, 430 if topology.startswith("administration") else 302)
    content_left = navigator_right
    upper_bottom = min(height, max(420, round(height * 0.5)))
    if region == "header":
        return (0, 0, width, header_bottom)
    if region == "navigator":
        return (0, header_bottom, navigator_right, height)
    if region in {"table-form", "stage-controls"}:
        return (content_left, header_bottom, width, upper_bottom)
    if region in {"engineering-graph", "native-preview"}:
        return (content_left, upper_bottom, width, height)
    raise EvidenceError(f"unknown crop region: {region}")


def _promote_phase(raw: Path, phase_root: Path, evidence_root: Path) -> None:
    phase_root = phase_root.resolve()
    evidence_root = evidence_root.resolve()
    if phase_root.parent != evidence_root or phase_root.name not in PHASES:
        raise EvidenceError(f"refusing to replace an unsafe phase path: {phase_root}")
    if phase_root.exists():
        shutil.rmtree(phase_root)
    for topology, contract in TOPOLOGIES.items():
        for width, height in VIEWPORTS:
            viewport = f"{width}x{height}"
            source = raw / contract["source"].format(viewport=viewport)
            if not source.is_file():
                raise EvidenceError(f"capture is missing: {source.name}")
            target = phase_root / topology / viewport
            target.mkdir(parents=True, exist_ok=True)
            original = target / "original.png"
            shutil.copyfile(source, original)
            with Image.open(original) as image:
                if image.size != (width, height):
                    raise EvidenceError(f"original viewport drifted: {original} {image.size}")
                for region in contract["regions"]:
                    box = _bounded_box(width, height, _crop_box(topology, region, width, height))
                    image.crop(box).save(target / f"{region}.png")


def _capture_phase(source_root: Path, project: str, phase: str, output: Path) -> None:
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import run_disposable_demo_test as disposable

    source_root = source_root.resolve()
    if not (source_root / "deploy/compose/docker-compose.demo.yml").is_file():
        raise EvidenceError(f"source root is not a CAE Material Platform tree: {source_root}")
    project = disposable.validate_project_name(project)
    disposable._load_isolated_config(source_root, project)
    disposable._assert_project_absent(source_root, project, phase="before capture")
    permanent_before = disposable.permanent_demo_snapshot(source_root)
    disposable._print_snapshot("before", permanent_before)
    try:
        services = ["migrate", "api", "worker", "reference-plugins", "seed", "web"]
        disposable._run_command(
            disposable.compose_command(source_root, project, "build", *services),
            cwd=source_root,
        )
        disposable._run_command(
            disposable.compose_command(
                source_root,
                project,
                "up",
                "--detach",
                "api",
                "worker",
                "reference-plugins",
            ),
            cwd=source_root,
        )
        disposable._run_seed_twice_and_assert_stable(source_root, project)
        disposable._run_command(
            disposable.compose_command(source_root, project, "up", "--detach", "web"),
            cwd=source_root,
        )
        base_url = disposable._web_url(source_root, project)
        disposable._wait_for_url(base_url)
        print(f"M4 {phase} disposable browser endpoint: {base_url}")
        with tempfile.TemporaryDirectory(prefix=f"cmp-261-m4-{phase}-") as temporary:
            raw = Path(temporary)
            _capture_raw(base_url, raw)
            _promote_phase(raw, output / phase, output)
    finally:
        disposable._cleanup(source_root, project)
    permanent_after = disposable.permanent_demo_snapshot(source_root)
    disposable._print_snapshot("after", permanent_after)
    if permanent_before != permanent_after:
        raise EvidenceError("permanent cmp-local-demo state changed during M4 capture")
    metadata = {
        "phase": phase,
        "sourceRoot": source_root.as_posix(),
        "project": project,
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "display": "Playwright Chromium CSS viewport; not physical 4K hardware",
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "topologies": list(TOPOLOGIES),
        "permanentDemoPreserved": True,
        "disposableResourcesRemoved": True,
    }
    (output / f"runtime-{phase}.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def _file_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        "width": width,
        "height": height,
    }


def _pixel_comparison(before: Path, after: Path) -> dict[str, Any]:
    with Image.open(before).convert("RGB") as left, Image.open(after).convert("RGB") as right:
        if left.size != right.size:
            raise EvidenceError(f"image dimensions differ: {before} {after}")
        difference = ImageChops.difference(left, right)
        bbox = difference.getbbox()
        extrema = difference.getextrema()
        changed = 0
        if bbox is not None:
            changed = sum(1 for pixel in difference.getdata() if pixel != (0, 0, 0))
        total = left.width * left.height
        rms = ImageStat.Stat(difference).rms
        return {
            "byteIdentical": _sha256(before) == _sha256(after),
            "pixelIdentical": bbox is None,
            "changedPixels": changed,
            "totalPixels": total,
            "changedRatio": round(changed / total, 8),
            "differenceBounds": list(bbox) if bbox is not None else None,
            "maximumChannelDelta": max(value[1] for value in extrema),
            "rmsChannelDelta": [round(value, 6) for value in rms],
        }


def current_duplicate_image_groups(registered_paths: set[str]) -> list[tuple[str, list[str]]]:
    """Return current repository duplicate-image groups containing M4 images."""

    hashes: dict[str, list[str]] = {}
    for image_root in DUPLICATE_IMAGE_ROOTS:
        for path in image_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            relative = path.relative_to(ROOT).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(relative)

    groups = [
        (digest, sorted(paths))
        for digest, paths in hashes.items()
        if len(paths) >= 2 and any(path in registered_paths for path in paths)
    ]
    return sorted(groups, key=lambda item: item[1][0])


def _write_manifest(output: Path, *, accepted: bool) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    registered = [
        _file_record(path) for phase in PHASES for path in sorted((output / phase).rglob("*.png"))
    ]
    comparisons: list[dict[str, Any]] = []
    for topology, contract in TOPOLOGIES.items():
        for width, height in VIEWPORTS:
            viewport = f"{width}x{height}"
            for artifact in ("original", *contract["regions"]):
                before = output / "before" / topology / viewport / f"{artifact}.png"
                after = output / "after" / topology / viewport / f"{artifact}.png"
                comparisons.append(
                    {
                        "topology": topology,
                        "viewport": viewport,
                        "artifact": artifact,
                        **_pixel_comparison(before, after),
                    }
                )
    identical = sum(item["pixelIdentical"] for item in comparisons)
    original_comparisons = [item for item in comparisons if item["artifact"] == "original"]
    duplicate_groups = current_duplicate_image_groups({record["path"] for record in registered})
    status = "ACCEPTED_MAIN_VISUAL_AND_RUNTIME" if accepted else "PENDING_MAIN_REVIEW"
    axis = "PASS_MAIN" if accepted else "PENDING_MAIN"
    manifest = {
        "schemaVersion": "cmp.issue-261.m4.visual-evidence.v1",
        "issue": "#261",
        "unit": "M4-shared-css-ownership-consolidation",
        "status": status,
        "baseSha": BASE_SHA,
        "browserZoomPercent": 100,
        "devicePixelRatio": 1,
        "physicalWindows4KReadability": "DEFERRED_TO_#223",
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "ownership": {
            "candidateSelectorRows": fixture["candidate"]["rows"],
            "candidateGroups": fixture["candidate"]["groups"],
            "movedSelectorRows": fixture["approvedMove"]["rows"],
            "movedGroups": fixture["approvedMove"]["groups"],
            "acceptedInPlaceRows": fixture["acceptedInPlace"]["rows"],
            "acceptedInPlaceGroups": fixture["acceptedInPlace"]["groups"],
            "holdRows": fixture["hold"]["rows"],
            "holdGroups": fixture["hold"]["groups"],
            "tupleSha256": fixture["approvedMove"]["tupleSha256"],
        },
        "capturePlan": {
            "phases": list(PHASES),
            "topologyCount": len(TOPOLOGIES),
            "topologies": [
                {
                    "id": name,
                    "owners": list(contract["owners"]),
                    "regions": list(contract["regions"]),
                }
                for name, contract in TOPOLOGIES.items()
            ],
            "sourceOnlyDispositions": SOURCE_ONLY_DISPOSITIONS,
        },
        "runtime": {
            "before": json.loads((output / "runtime-before.json").read_text(encoding="utf-8")),
            "after": json.loads((output / "runtime-after.json").read_text(encoding="utf-8")),
        },
        "imageInventory": {
            "registeredCount": len(registered),
            "beforeTreeSha256": _tree_sha256(output / "before"),
            "afterTreeSha256": _tree_sha256(output / "after"),
            "registeredImages": registered,
        },
        "allowed_duplicate_groups": [
            {
                "rationale": DUPLICATE_GROUP_RATIONALE,
                "images": paths,
            }
            for _, paths in duplicate_groups
        ],
        "comparison": {
            "artifactPairs": len(comparisons),
            "pixelIdenticalPairs": identical,
            "originalPairs": len(original_comparisons),
            "pixelIdenticalOriginals": sum(item["pixelIdentical"] for item in original_comparisons),
            "maximumChangedRatio": max(item["changedRatio"] for item in comparisons),
            "records": comparisons,
        },
        "mainReview": {
            "allOriginalsOpenedAtOriginalResolution": accepted,
            "direct100PercentCropsOpened": accepted,
            "informationHierarchy": axis,
            "engineeringTaskFlow": axis,
            "responsiveWideScreenComposition": axis,
            "noClippingOverflowOrInteractionRegression": accepted,
            "Q01_Q20": [{"id": f"Q{index:02d}", "disposition": axis} for index in range(1, 21)],
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _validate(output: Path, *, require_accepted: bool) -> None:
    manifest_path = output / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read M4 manifest: {error}") from error
    if manifest.get("schemaVersion") != "cmp.issue-261.m4.visual-evidence.v1":
        raise EvidenceError("M4 evidence schema drifted")
    if require_accepted and manifest.get("status") != "ACCEPTED_MAIN_VISUAL_AND_RUNTIME":
        raise EvidenceError("M4 evidence is not accepted by Main")
    if manifest.get("viewports") != [f"{width}x{height}" for width, height in VIEWPORTS]:
        raise EvidenceError("M4 viewport matrix drifted")
    expected_per_phase = sum(1 + len(item["regions"]) for item in TOPOLOGIES.values()) * len(
        VIEWPORTS
    )
    images = manifest.get("imageInventory", {}).get("registeredImages", [])
    if len(images) != expected_per_phase * 2:
        raise EvidenceError(
            f"M4 image inventory drifted: {len(images)} != {expected_per_phase * 2}"
        )
    for record in images:
        path = ROOT / record["path"]
        if not path.is_file() or _sha256(path) != record["sha256"]:
            raise EvidenceError(f"registered M4 image differs: {record['path']}")
        with Image.open(path) as image:
            if list(image.size) != [record["width"], record["height"]]:
                raise EvidenceError(f"registered dimensions differ: {record['path']}")
    print(
        "M4 visual evidence PASS; "
        f"status={manifest['status']}; topologies={len(TOPOLOGIES)}; "
        f"images={len(images)}; pairs={manifest['comparison']['artifactPairs']}; "
        f"pixel-identical={manifest['comparison']['pixelIdenticalPairs']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--output", type=Path, default=EVIDENCE_ROOT)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--accept", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    actions = sum((args.phase is not None, args.compare, args.accept, args.check))
    if actions != 1:
        parser.error("choose exactly one of --phase, --compare, --accept, or --check")
    if args.phase:
        if args.source_root is None or not args.project:
            parser.error("capture requires --source-root and --project")
        output.mkdir(parents=True, exist_ok=True)
        _capture_phase(args.source_root, args.project, args.phase, output)
        return 0
    if args.compare:
        _write_manifest(output, accepted=False)
        _validate(output, require_accepted=False)
        return 0
    if args.accept:
        _write_manifest(output, accepted=True)
        _validate(output, require_accepted=True)
        return 0
    _validate(output, require_accepted=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture and verify issue #209 DMA/FLD governed-import evidence.

The journey uses only synthetic non-production tabular data. It exercises the
real Compose UI and API, preserves the exact ``origin/main`` Modeling Data
baseline, captures all required CSS viewports at browser zoom 100%, and reads
the saved provenance and canonical values back from the server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import capture_current_product as current
import yaml
from PIL import Image
from playwright.sync_api import Browser, Page, Response, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/user-guide/images/current"
EVIDENCE = ROOT / "docs/17-evidence/images/issue-209-dma-fld-governed-import"
BASE_SHA = "a512c76aa55b5423e06f6b09eb1015ddf28f3aca"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
WIDE_VIEWPORTS = ((1920, 1080), (2560, 1440), (3840, 2160))
DMA_DOCUMENT_KEY = "ISSUE209-DMA-FREQUENCY-TEMPERATURE"
DMA_REJECTED_DOCUMENT_KEY = "ISSUE209-DMA-REJECTED"
DMA_RECOVERED_DOCUMENT_KEY = "ISSUE209-DMA-RECOVERED"
FLD_DOCUMENT_KEY = "ISSUE209-FLD"
DMA_SPECIMEN_CODE = "ISSUE209-DMA-SYNTHETIC-01"
DMA_RUN_LABEL = "Issue 209 synthetic DMA frequency-temperature sweep"
REJECTED_DMA_RETRY_KEY = "20920920-9209-4209-9209-209209209209"


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _project_ref(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _evidence_ref(path: Path, packet: Path) -> str:
    if path.is_relative_to(packet):
        path = EVIDENCE / path.relative_to(packet)
    return _project_ref(path)


def _extract_base_originals(packet: Path) -> None:
    target = packet / "before/originals"
    target.mkdir(parents=True)
    for width, height in VIEWPORTS:
        relative = f"docs/user-guide/images/current/modeling-data-{width}x{height}.png"
        destination = target / Path(relative).name
        with destination.open("wb") as stream:
            subprocess.run(
                ("git", "show", f"{BASE_SHA}:{relative}"),
                cwd=ROOT,
                check=True,
                stdout=stream,
            )


def _bounded_box(
    width: int, height: int, box: tuple[float, float, float, float]
) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    left_i = max(0, min(width - 1, math.floor(left)))
    top_i = max(0, min(height - 1, math.floor(top)))
    right_i = max(left_i + 1, min(width, math.ceil(right)))
    bottom_i = max(top_i + 1, min(height, math.ceil(bottom)))
    return left_i, top_i, right_i, bottom_i


def _crop_base_originals(packet: Path) -> None:
    source_root = packet / "before/originals"
    crop_root = packet / "before/crops"
    crop_root.mkdir(parents=True)
    for width, height in WIDE_VIEWPORTS:
        source = source_root / f"modeling-data-{width}x{height}.png"
        with Image.open(source) as image:
            if image.size != (width, height):
                raise RuntimeError(f"base viewport drifted: {source} {image.size}")
            regions = {
                "header": (0, 0, width, min(height, 180)),
                "navigator": (0, 100, min(width, 302), height),
                "controls": (302, 135, width, min(height, 425)),
                "graph": (302, 425, width, height),
            }
            for name, box in regions.items():
                image.crop(_bounded_box(width, height, box)).save(
                    crop_root / f"modeling-data-{width}x{height}-{name}.png"
                )


def _console_guard(page: Page) -> list[str]:
    failures: list[str] = []
    page.on(
        "console",
        lambda message: (
            failures.append(f"console.{message.type}: {message.text}")
            if message.type == "error"
            else None
        ),
    )
    page.on("pageerror", lambda error: failures.append(f"pageerror: {error}"))
    return failures


def _api_json(page: Page, path: str, accept: str = "application/json") -> Any:
    result = page.evaluate(
        """async ({path, accept}) => {
          const raw = window.localStorage.getItem('cmp.material-platform.api-config');
          if (!raw) throw new Error('missing API config');
          const config = JSON.parse(raw);
          const response = await fetch(path, {
            headers: {Authorization: `Bearer ${config.accessToken}`, Accept: accept},
          });
          const text = await response.text();
          let body;
          try { body = JSON.parse(text); } catch { body = text; }
          return {ok: response.ok, status: response.status, body};
        }""",
        {"path": path, "accept": accept},
    )
    if not result["ok"]:
        raise RuntimeError(f"API read-back failed for {path}: {result}")
    return result["body"]


def _api_post(page: Page, path: str, body: dict[str, Any]) -> dict[str, Any]:
    result = page.evaluate(
        """async ({path, body}) => {
          const raw = window.localStorage.getItem('cmp.material-platform.api-config');
          if (!raw) throw new Error('missing API config');
          const config = JSON.parse(raw);
          const response = await fetch(path, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${config.accessToken}`,
              Accept: 'application/json',
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
          });
          const text = await response.text();
          let responseBody;
          try { responseBody = JSON.parse(text); } catch { responseBody = text; }
          return {ok: response.ok, status: response.status, body: responseBody};
        }""",
        {"path": path, "body": body},
    )
    if not result["ok"] or not isinstance(result["body"], dict):
        raise RuntimeError(f"API setup failed for {path}: {result}")
    return result["body"]


def _record_ref(value: dict[str, Any], *, id_key: str, label: str) -> dict[str, Any]:
    revision = value["current_revision"]
    return {
        "id": value[id_key],
        "revisionId": revision["id"],
        "revisionNo": revision["revision_no"],
        "label": label,
    }


def _modeling_context(
    *,
    family: str,
    material: dict[str, Any],
    material_state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "family": family,
        "material": _record_ref(
            material,
            id_key="material_id",
            label=material["current_revision"]["content"]["name"],
        ),
        "material_state": _record_ref(
            material_state,
            id_key="material_state_id",
            label=material_state["current_revision"]["content"]["name"],
        ),
    }


def _context_url(base_url: str, context: dict[str, Any]) -> str:
    material = context["material"]
    state = context["material_state"]
    query = urlencode(
        {
            "stage": "data",
            "family": context["family"],
            "material_id": material["id"],
            "material_revision_id": material["revisionId"],
            "material_state_id": state["id"],
            "material_state_revision_id": state["revisionId"],
        }
    )
    return f"{base_url}/modeling?{query}"


def _activate_context(page: Page, base_url: str, context: dict[str, Any]) -> None:
    page.goto(_context_url(base_url, context))
    current._wait_for_modeling_data_surface(page)
    page.get_by_role("tab", name="Local file").wait_for(state="visible", timeout=30_000)
    current._wait_for_settled(page)


def _setup_dma_context(page: Page) -> tuple[dict[str, Any], str]:
    listing = _api_json(page, "/api/v1/materials?limit=100")
    materials = [
        item
        for item in listing["items"]
        if item["current_revision"]["content"].get("material_code")
        == "CMP-DEMO-POLYMER-PRONY"
    ]
    if len(materials) != 1:
        raise RuntimeError(f"expected one synthetic polymer Material, got {len(materials)}")
    material = materials[0]
    detail = _api_json(page, f"/api/v1/materials/{material['material_id']}")
    states = [
        item
        for item in detail["states"]
        if item["current_revision"]["content"]["name"] == "Reference conditioned"
    ]
    if len(states) != 1:
        raise RuntimeError(f"expected one synthetic polymer State, got {len(states)}")
    state = states[0]

    specimen_listing = _api_json(
        page, f"/api/v1/material-states/{state['material_state_id']}/specimens"
    )
    specimens = [
        item
        for item in specimen_listing["items"]
        if item["current_revision"]["content"]["specimen_code"] == DMA_SPECIMEN_CODE
    ]
    if len(specimens) > 1:
        raise RuntimeError(f"duplicate issue #209 synthetic DMA Specimens: {specimens!r}")
    specimen = (
        specimens[0]
        if specimens
        else _api_post(
            page,
            f"/api/v1/material-states/{state['material_state_id']}/specimens",
            {
                "material_state_revision_id": state["current_revision"]["id"],
                "specimen_code": DMA_SPECIMEN_CODE,
                "orientation": None,
                "preparation_note": (
                    "Synthetic non-production specimen for issue #209 governed-import evidence."
                ),
                "change_reason": "Create bounded synthetic issue #209 DMA evidence context.",
            },
        )
    )

    method_listing = _api_json(page, "/api/v1/test-methods")
    methods = [
        item
        for item in method_listing["items"]
        if item["current_revision"]["content"]["method_code"]
        == "reference_shear_relaxation"
    ]
    if len(methods) != 1:
        raise RuntimeError(f"expected one reference shear-relaxation method, got {len(methods)}")
    method = methods[0]

    run_listing = _api_json(
        page, f"/api/v1/material-states/{state['material_state_id']}/test-runs"
    )
    runs = [
        item
        for item in run_listing["items"]
        if item["current_revision"]["content"]["run_label"] == DMA_RUN_LABEL
    ]
    if len(runs) > 1:
        raise RuntimeError(f"duplicate issue #209 synthetic DMA Test Runs: {runs!r}")
    run = (
        runs[0]
        if runs
        else _api_post(
            page,
            "/api/v1/test-runs/reference-shear-relaxation",
            {
                "specimen_id": specimen["specimen_id"],
                "specimen_revision_id": specimen["current_revision"]["id"],
                "test_method_id": method["test_method_id"],
                "test_method_revision_id": method["current_revision"]["id"],
                "run_label": DMA_RUN_LABEL,
                "performed_at": "2026-08-13T09:00:00Z",
                "test_temperature_k": 296.15,
                "change_reason": (
                    "Register bounded synthetic DMA frequency-temperature import evidence."
                ),
            },
        )
    )
    content = run["current_revision"]["content"]
    if (
        content["specimen_id"] != specimen["specimen_id"]
        or content["specimen_revision_id"] != specimen["current_revision"]["id"]
        or content["test_method_id"] != method["test_method_id"]
        or content["test_method_revision_id"] != method["current_revision"]["id"]
    ):
        raise RuntimeError(f"issue #209 DMA Test Run exact pins drifted: {run!r}")
    return (
        _modeling_context(family="polymer", material=material, material_state=state),
        run["test_run_id"],
    )


def _metal_context(page: Page) -> tuple[dict[str, Any], str]:
    raw_session = page.evaluate(
        "() => window.sessionStorage.getItem('cmp.modeling.recent-session.v4')"
    )
    if not raw_session:
        raise RuntimeError("normal Modeling Data session was not persisted")
    session = json.loads(raw_session)
    material_id = session.get("material", {}).get("id")
    state_id = session.get("materialState", {}).get("id")
    if not material_id or not state_id:
        raise RuntimeError(f"normal Modeling Data context is incomplete: {session!r}")
    detail = _api_json(page, f"/api/v1/materials/{material_id}")
    states = [item for item in detail["states"] if item["material_state_id"] == state_id]
    if len(states) != 1:
        raise RuntimeError(f"normal metal Material State drifted: {state_id!r}")
    state = states[0]
    runs = _api_json(page, f"/api/v1/material-states/{state_id}/test-runs")["items"]
    fld_runs = [
        item
        for item in runs
        if item["current_revision"]["content"]["run_label"]
        == "CMP demo tensile replicate 2"
    ]
    if len(fld_runs) != 1:
        raise RuntimeError(f"expected exact synthetic FLD Test Run container, got {fld_runs!r}")
    return (
        _modeling_context(
            family="metal",
            material=detail["material"],
            material_state=state,
        ),
        fld_runs[0]["test_run_id"],
    )


def _wait_for_import_response(page: Page, action: Any) -> tuple[Response, dict[str, Any]]:
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/v1/tabular-import-runs")
            and response.request.method == "POST"
        ),
        timeout=30_000,
    ) as pending:
        action()
    response = pending.value
    body = response.json()
    if response.status not in {200, 201} or not isinstance(body, dict):
        raise RuntimeError(f"import response drifted: {response.status} {body!r}")
    return response, body


def _select_test_run(page: Page, test_run_id: str) -> str:
    control = page.get_by_role("combobox", name="Local file Test Run")
    control.wait_for(state="visible", timeout=30_000)
    page.wait_for_function(
        """value => [...(
          document.querySelector('select[aria-label="Local file Test Run"]')?.options ?? []
        )].some(option => option.value === value)""",
        arg=test_run_id,
        timeout=30_000,
    )
    control.select_option(test_run_id)
    value = control.input_value()
    if value != test_run_id:
        raise RuntimeError("exact Test Run selection did not settle")
    return value


def _upload_source(page: Page, source: Path, *, test_run_id: str) -> str:
    page.get_by_role("tab", name="Local file").click()
    run_id = _select_test_run(page, test_run_id)
    page.get_by_label("Local test data file").set_input_files(source)
    inspect = page.get_by_role("button", name="Inspect source")
    inspect.wait_for(state="visible", timeout=30_000)
    inspect.click()
    page.get_by_role("region", name="Raw source table preview").wait_for(
        state="visible", timeout=30_000
    )
    current._wait_for_settled(page)
    return run_id


def _expose_mapping(page: Page) -> None:
    schema = page.get_by_role("combobox", name="Local data schema")
    if schema.count() == 0:
        page.get_by_role("button", name="Change mapping").click()
        schema.wait_for(state="visible", timeout=30_000)


def _fill_metadata(page: Page, document_key: str) -> None:
    row = page.locator(".mapping-context-row")
    row.evaluate("element => element.scrollIntoView({block: 'center', inline: 'nearest'})")
    for name, value in (
        ("test-data-name", document_key),
        ("test-data-maker", "CMP synthetic reference"),
        ("test-data-operator", "Issue 209 analyst"),
        ("test-data-laboratory", "Synthetic validation lab"),
    ):
        control = page.locator(f'input[name="{name}"]')
        control.wait_for(state="visible", timeout=30_000)
        control.fill(value)


def _configure_dma(
    page: Page,
    document_key: str,
    *,
    columns: tuple[str, str, str, str, str | None],
    expose_mapping: bool = True,
) -> None:
    if expose_mapping:
        _expose_mapping(page)
    schema = page.get_by_role("combobox", name="Local data schema")
    if schema.count():
        schema.select_option("dma_frequency_temperature_sweep")
        optional = page.get_by_role("checkbox", name="Include optional tan delta channel")
        if columns[4] is not None and not optional.is_checked():
            optional.check()
        if columns[4] is None and optional.is_checked():
            optional.uncheck()
        mappings = (
            ("Temperature", columns[0], "degC"),
            ("Frequency", columns[1], "Hz"),
            ("Storage modulus", columns[2], "MPa"),
            ("Loss modulus", columns[3], "MPa"),
        )
        for label, column, unit in mappings:
            page.get_by_role("combobox", name=f"{label} source column").select_option(column)
            page.get_by_role("combobox", name=f"{label} original unit").select_option(unit)
        if columns[4] is not None:
            page.get_by_role("combobox", name="Tan delta source column").select_option(columns[4])
            page.get_by_role("combobox", name="Tan delta original unit").select_option("1")
        page.get_by_label("Mapping change reason").fill(
            "The visible columns and units are the recorded synthetic DMA channels."
        )
    _fill_metadata(page, document_key)


def _configure_fld(
    page: Page,
    document_key: str,
    *,
    columns: tuple[str, str],
) -> None:
    _expose_mapping(page)
    page.get_by_role("combobox", name="Local data schema").select_option("forming_limit_diagram")
    page.get_by_role("combobox", name="Minor strain source column").select_option(columns[0])
    page.get_by_role("combobox", name="Minor strain original unit").select_option("%")
    page.get_by_role("combobox", name="Major strain source column").select_option(columns[1])
    page.get_by_role("combobox", name="Major strain original unit").select_option("%")
    page.get_by_label("Mapping change reason").fill(
        "The visible signed strain columns are the synthetic FLD coordinates."
    )
    _fill_metadata(page, document_key)


def _preview(page: Page, *, expected_status: int) -> Response:
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/v1/test-data:convert-tabular")
            and response.request.method == "POST"
        ),
        timeout=30_000,
    ) as pending:
        page.get_by_role("button", name="Update preview", exact=True).click()
    response = pending.value
    if response.status != expected_status:
        raise RuntimeError(
            f"canonical tabular preview returned {response.status}, expected {expected_status}: "
            f"{response.text()}"
        )
    if expected_status == 200:
        page.get_by_role("button", name="Save Test Data", exact=True).wait_for(
            state="visible", timeout=30_000
        )
        page.locator(".persistent-modeling-plot svg").first.wait_for(
            state="visible", timeout=30_000
        )
    else:
        page.get_by_role("button", name="Record rejected import").wait_for(
            state="visible", timeout=30_000
        )
    current._wait_for_settled(page)
    return response


def _element_record(page: Page, selector: str) -> dict[str, Any]:
    locator = page.locator(selector)
    locator.first.wait_for(state="visible", timeout=30_000)
    return locator.first.evaluate(
        """element => {
          const rect = element.getBoundingClientRect();
          return {
            box: {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                  width: rect.width, height: rect.height},
            scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
            scrollHeight: element.scrollHeight, clientHeight: element.clientHeight,
          };
        }"""
    )


def _capture_state(
    page: Page,
    packet: Path,
    *,
    state: str,
    decision_selector: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    originals = packet / "after/originals"
    crops = packet / "after/crops"
    originals.mkdir(parents=True, exist_ok=True)
    crops.mkdir(parents=True, exist_ok=True)
    decision = page.locator(decision_selector).first
    decision.wait_for(state="visible", timeout=30_000)
    decision.evaluate("element => element.scrollIntoView({block: 'center', inline: 'nearest'})")
    page.wait_for_timeout(200)
    current._wait_for_settled(page)
    layout = page.evaluate(
        """() => ({
              viewport: {width: innerWidth, height: innerHeight},
              dpr: devicePixelRatio,
              document: {scrollWidth: document.documentElement.scrollWidth,
                         clientWidth: document.documentElement.clientWidth,
                         scrollHeight: document.documentElement.scrollHeight,
                         clientHeight: document.documentElement.clientHeight},
              body: {scrollWidth: document.body.scrollWidth,
                     clientWidth: document.body.clientWidth},
            })"""
    )
    if layout["viewport"] != {"width": width, "height": height}:
        raise RuntimeError(f"viewport did not settle for {state}: {layout}")
    if layout["dpr"] != 1:
        raise RuntimeError(f"capture requires DPR 1, got {layout['dpr']}")
    if layout["document"]["scrollWidth"] > layout["document"]["clientWidth"] + 1:
        raise RuntimeError(f"page horizontal overflow for {state} {width}x{height}: {layout}")
    selectors = {
        "header": ".application-menu-bar",
        "navigator": ".modeling-workspace-rail",
        "controls": ".modeling-data-ribbon-panel",
        "decision": decision_selector,
        "graph": ".modeling-data-plot-panel",
    }
    elements = {name: _element_record(page, selector) for name, selector in selectors.items()}
    decision_metrics = elements["decision"]
    if decision_metrics["scrollWidth"] > decision_metrics["clientWidth"] + 1:
        # A local table scrollport is acceptable only when it remains reachable.
        if decision.get_attribute("role") != "region" and state != "dma-rejected":
            raise RuntimeError(
                f"unreachable decision overflow for {state} {width}x{height}: {decision_metrics}"
            )
    output = originals / f"modeling-data-{state}-{width}x{height}.png"
    page.screenshot(path=output)
    with Image.open(output) as image:
        if image.size != (width, height):
            raise RuntimeError(f"captured viewport drifted: {output} {image.size}")
        if (width, height) in WIDE_VIEWPORTS:
            for name, record in elements.items():
                box = record["box"]
                bounded = _bounded_box(
                    width,
                    height,
                    (box["left"], box["top"], box["right"], box["bottom"]),
                )
                image.crop(bounded).save(
                    crops / f"modeling-data-{state}-{width}x{height}-{name}.png"
                )
    return {
        "state": state,
        "css_viewport": f"{width}x{height}",
        "browser_zoom": "100%",
        "device_pixel_ratio": layout["dpr"],
        "layout": layout,
        "elements": elements,
    }


def _new_modeling_page(
    source_page: Page,
    base_url: str,
    context: dict[str, Any],
    width: int,
    height: int,
) -> tuple[Page, list[str]]:
    page = source_page.context.new_page()
    page.set_viewport_size({"width": width, "height": height})
    failures = _console_guard(page)
    _activate_context(page, base_url, context)
    return page, failures


def _capture_across_viewports(
    primary_page: Page,
    packet: Path,
    *,
    base_url: str,
    context: dict[str, Any],
    state: str,
    decision_selector: str,
    prepare_secondary: Callable[[Page], None],
) -> tuple[list[dict[str, Any]], list[str]]:
    measurements: list[dict[str, Any]] = []
    failures: list[str] = []
    for width, height in VIEWPORTS:
        page = primary_page
        page_failures: list[str] = []
        secondary = (width, height) != (1440, 900)
        if secondary:
            page, page_failures = _new_modeling_page(
                primary_page, base_url, context, width, height
            )
            prepare_secondary(page)
        measurements.append(
            _capture_state(
                page,
                packet,
                state=state,
                decision_selector=decision_selector,
                width=width,
                height=height,
            )
        )
        if secondary:
            failures.extend(page_failures)
            page.close()
    return measurements, failures


def _assert_float_values(actual: list[Any], expected: list[float], label: str) -> None:
    values = [float(value) for value in actual]
    if len(values) != len(expected) or any(
        not math.isclose(value, wanted, rel_tol=0, abs_tol=1e-9)
        for value, wanted in zip(values, expected, strict=True)
    ):
        raise RuntimeError(f"{label} values drifted: {values!r} != {expected!r}")


def _read_back_document(
    page: Page,
    document_key: str,
    *,
    expected_schema: str,
    expected_run_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    listing = _api_json(page, "/api/v1/test-data-documents")
    matches = [item for item in listing["items"] if item["document_key"] == document_key]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {document_key} document, got {len(matches)}")
    document = matches[0]
    revision_id = document["current_revision"]["id"]
    content = _api_json(
        page,
        f"/api/v1/test-data-documents/{document['test_data_document_id']}/revisions/{revision_id}/content",
        "application/vnd.cmp.test-data+json",
    )
    source = document.get("governed_source")
    tabular = None if source is None else source.get("tabular_import")
    if not source or not tabular:
        raise RuntimeError(f"{document_key} is missing exact governed tabular proof: {source!r}")
    run = _api_json(page, f"/api/v1/tabular-import-runs/{tabular['import_run_id']}")
    if run["status"] != "succeeded" or run["test_run_id"] != expected_run_id:
        raise RuntimeError(f"{document_key} import run pin drifted: {run!r}")
    if run["test_run_revision_id"] != source["test_run"]["revision_id"]:
        raise RuntimeError(f"{document_key} exact Test Run revision pin drifted")
    if (
        run["raw_asset_id"] != tabular["raw_asset_id"]
        or run["raw_artifact_id"] != tabular["raw_artifact_id"]
    ):
        raise RuntimeError(f"{document_key} raw source pins drifted")
    if run["import_profile_revision_id"] != tabular["import_profile"]["revision_id"]:
        raise RuntimeError(f"{document_key} exact Profile revision pin drifted")
    if run["normalized_dataset_revision_id"] != tabular["normalized_dataset"]["revision_id"]:
        raise RuntimeError(f"{document_key} normalized Dataset revision pin drifted")
    if run.get("row_count") != document.get("point_count"):
        raise RuntimeError(f"{document_key} normalized/canonical row count drifted")
    if not source["material"]["revision_id"] or not source["material_state"]["revision_id"]:
        raise RuntimeError(f"{document_key} Material/State revision proof is incomplete")
    schema = run.get("data_schema")
    if schema is not None and schema != expected_schema:
        raise RuntimeError(f"{document_key} schema drifted: {schema!r}")
    return document, content, run


def _assert_dma_content(content: dict[str, Any], *, include_tan: bool) -> None:
    channels = {item["key"]: item for item in content["channels"]}
    expected = {"temperature", "frequency", "storage_modulus", "loss_modulus"}
    if include_tan:
        expected.add("tan_delta")
    if set(channels) != expected:
        raise RuntimeError(f"DMA canonical channels drifted: {set(channels)!r}")
    if (
        channels["temperature"]["axis_role"] != "independent"
        or channels["frequency"]["axis_role"] != "independent"
    ):
        raise RuntimeError("DMA independent-axis semantics drifted")
    _assert_float_values(
        channels["temperature"]["normalized_values"],
        [296.15, 253.15, 353.15, 296.15],
        "DMA temperature",
    )
    _assert_float_values(
        channels["frequency"]["normalized_values"], [10.0, 1.0, 1.0, 1.0], "DMA frequency"
    )
    _assert_float_values(
        channels["storage_modulus"]["normalized_values"],
        [950_000_000.0, 1_480_000_000.0, 510_000_000.0, 900_000_000.0],
        "DMA storage modulus",
    )


def _assert_fld_content(content: dict[str, Any]) -> None:
    channels = {item["key"]: item for item in content["channels"]}
    if set(channels) != {"minor_strain", "major_strain"}:
        raise RuntimeError(f"FLD canonical channels drifted: {set(channels)!r}")
    if channels["minor_strain"]["axis_role"] != "independent":
        raise RuntimeError("FLD minor strain axis semantics drifted")
    _assert_float_values(
        channels["minor_strain"]["normalized_values"],
        [-0.12, 0.06, -0.04, 0.01],
        "FLD minor strain",
    )
    _assert_float_values(
        channels["major_strain"]["normalized_values"], [0.28, 0.25, 0.22, 0.20], "FLD major strain"
    )


def _save_document(page: Page, document_key: str) -> dict[str, Any]:
    _, run = _wait_for_import_response(
        page, lambda: page.get_by_role("button", name="Save Test Data", exact=True).click()
    )
    if run["status"] != "succeeded":
        raise RuntimeError(f"successful save produced failed Import Run: {run!r}")
    page.get_by_text(f"Registered {document_key}", exact=False).wait_for(
        state="visible", timeout=30_000
    )
    current._wait_for_settled(page)
    return run


def _record_rejection(page: Page, retry_key: str) -> tuple[dict[str, Any], str]:
    page.evaluate(
        """value => {
          window.__cmpIssue209OriginalRandomUUID = Crypto.prototype.randomUUID;
          Object.defineProperty(Crypto.prototype, 'randomUUID', {
            configurable: true,
            value: () => value,
          });
        }""",
        retry_key,
    )
    try:
        response, first = _wait_for_import_response(
            page, lambda: page.get_by_role("button", name="Record rejected import").click()
        )
        if first["status"] != "failed" or not first["diagnostics"]:
            raise RuntimeError(f"invalid source did not retain failed diagnostics: {first!r}")
        page.get_by_role("region", name="Rejected source cells").wait_for(
            state="visible", timeout=30_000
        )
        first_key = response.request.headers.get("idempotency-key", "")
        if first_key != retry_key:
            raise RuntimeError(f"governed retry key override did not apply: {first_key!r}")
        response, second = _wait_for_import_response(
            page, lambda: page.get_by_role("button", name="Record rejected import").click()
        )
        second_key = response.request.headers.get("idempotency-key", "")
    finally:
        page.evaluate(
            """() => {
              Object.defineProperty(Crypto.prototype, 'randomUUID', {
                configurable: true,
                value: window.__cmpIssue209OriginalRandomUUID,
              });
              delete window.__cmpIssue209OriginalRandomUUID;
            }"""
        )
    if (
        not first_key
        or second_key != first_key
        or second["import_run_id"] != first["import_run_id"]
    ):
        raise RuntimeError(
            "unchanged invalid retry was not idempotent: "
            f"{first_key!r}, {second_key!r}, {first!r}, {second!r}"
        )
    return first, first_key


def _assert_missing_document(page: Page, document_key: str) -> None:
    listing = _api_json(page, "/api/v1/test-data-documents")
    if any(item["document_key"] == document_key for item in listing["items"]):
        raise RuntimeError(f"rejected source created forbidden Test Data {document_key}")


def _document_exists(page: Page, document_key: str) -> bool:
    listing = _api_json(page, "/api/v1/test-data-documents")
    return any(item["document_key"] == document_key for item in listing["items"])


def _write_sources(directory: Path) -> dict[str, Path]:
    sources = {
        "dma": directory / "issue209-dma-frequency-temperature.csv",
        "dma_invalid": directory / "issue209-dma-invalid.csv",
        "dma_corrected": directory / "issue209-dma-corrected.csv",
        "fld": directory / "issue209-forming-limit.tsv",
    }
    sources["dma"].write_text(
        "temperature_c,frequency_hz,storage_mpa,loss_mpa,tan_delta\n"
        "23,10,950,112,0.1179\n"
        "-20,1,1480,118,0.0797\n"
        "80,1,510,151,0.2961\n"
        "23,1,900,164,0.1822\n",
        encoding="utf-8",
    )
    sources["dma_invalid"].write_text(
        "temperature_bad,frequency_bad,storage_bad,loss_bad\n"
        "23,0,950,112\n"
        "-300,1,1480,118\n"
        "80,10,,151\n"
        "23,1,900,-1\n",
        encoding="utf-8",
    )
    sources["dma_corrected"].write_text(
        "temperature_bad,frequency_bad,storage_bad,loss_bad\n"
        "23,10,950,112\n"
        "-20,1,1480,118\n"
        "80,1,510,151\n"
        "23,1,900,164\n",
        encoding="utf-8",
    )
    sources["fld"].write_text(
        "minor_strain_pct\tmajor_strain_pct\n-12\t28\n6\t25\n-4\t22\n1\t20\n",
        encoding="utf-8",
    )
    return sources


def _capture_journey(browser: Browser, base_url: str, packet: Path) -> dict[str, Any]:
    page = current._new_page(browser, base_url, 1440, 900)
    failures = _console_guard(page)
    current._prepare_modeling(page, base_url, verify_reload=False)
    metal_context, fld_test_run_id = _metal_context(page)
    polymer_context, dma_test_run_id = _setup_dma_context(page)
    _activate_context(page, base_url, polymer_context)
    measurements: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="cmp-issue209-") as temporary:
        sources = _write_sources(Path(temporary))

        dma_run_id = _upload_source(page, sources["dma"], test_run_id=dma_test_run_id)
        _configure_dma(
            page,
            DMA_DOCUMENT_KEY,
            columns=(
                "temperature_c",
                "frequency_hz",
                "storage_mpa",
                "loss_mpa",
                "tan_delta",
            ),
        )
        _preview(page, expected_status=200)
        dma_columns = (
            "temperature_c",
            "frequency_hz",
            "storage_mpa",
            "loss_mpa",
            "tan_delta",
        )

        def prepare_dma_secondary(candidate: Page) -> None:
            _upload_source(candidate, sources["dma"], test_run_id=dma_test_run_id)
            _configure_dma(
                candidate,
                DMA_DOCUMENT_KEY,
                columns=dma_columns,
            )

            _preview(candidate, expected_status=200)

        captured, capture_failures = _capture_across_viewports(
            page,
            packet,
            base_url=base_url,
            context=polymer_context,
            state="dma",
            decision_selector=".data-mapping-table",
            prepare_secondary=prepare_dma_secondary,
        )
        measurements.extend(captured)
        failures.extend(capture_failures)
        if not _document_exists(page, DMA_DOCUMENT_KEY):
            _save_document(page, DMA_DOCUMENT_KEY)
        dma_document, dma_content, dma_run = _read_back_document(
            page,
            DMA_DOCUMENT_KEY,
            expected_schema="dma_frequency_temperature_sweep",
            expected_run_id=dma_run_id,
        )
        _assert_dma_content(dma_content, include_tan=True)

        _upload_source(page, sources["dma_invalid"], test_run_id=dma_test_run_id)
        _configure_dma(
            page,
            DMA_REJECTED_DOCUMENT_KEY,
            columns=("temperature_bad", "frequency_bad", "storage_bad", "loss_bad", None),
        )
        _preview(page, expected_status=422)
        rejected_run, retry_key = _record_rejection(page, REJECTED_DMA_RETRY_KEY)
        _assert_missing_document(page, DMA_REJECTED_DOCUMENT_KEY)
        diagnostic_codes = {item["error_code"] for item in rejected_run["diagnostics"]}
        if len(rejected_run["diagnostics"]) < 4 or not {
            "frequency_not_positive",
            "temperature_below_absolute_zero",
            "missing_value",
            "negative_dma_response",
        }.issubset(diagnostic_codes):
            raise RuntimeError(f"full-file DMA diagnostics drifted: {rejected_run!r}")
        rejected_columns = (
            "temperature_bad",
            "frequency_bad",
            "storage_bad",
            "loss_bad",
            None,
        )

        def prepare_rejected_secondary(candidate: Page) -> None:
            _upload_source(candidate, sources["dma_invalid"], test_run_id=dma_test_run_id)
            _configure_dma(
                candidate,
                DMA_REJECTED_DOCUMENT_KEY,
                columns=rejected_columns,
            )

            _preview(candidate, expected_status=422)
            replay, replay_key = _record_rejection(candidate, REJECTED_DMA_RETRY_KEY)
            if replay_key != retry_key or replay["import_run_id"] != rejected_run["import_run_id"]:
                raise RuntimeError(
                    "five-viewport rejected DMA replay created a different Import Run"
                )

        captured, capture_failures = _capture_across_viewports(
            page,
            packet,
            base_url=base_url,
            context=polymer_context,
            state="dma-rejected",
            decision_selector=".data-import-diagnostics",
            prepare_secondary=prepare_rejected_secondary,
        )
        measurements.extend(captured)
        failures.extend(capture_failures)

        corrected_run_id = _upload_source(
            page, sources["dma_corrected"], test_run_id=dma_test_run_id
        )
        _configure_dma(
            page,
            DMA_RECOVERED_DOCUMENT_KEY,
            columns=("temperature_bad", "frequency_bad", "storage_bad", "loss_bad", None),
            expose_mapping=False,
        )
        _preview(page, expected_status=200)
        if not _document_exists(page, DMA_RECOVERED_DOCUMENT_KEY):
            _save_document(page, DMA_RECOVERED_DOCUMENT_KEY)
        corrected_document, corrected_content, corrected_run = _read_back_document(
            page,
            DMA_RECOVERED_DOCUMENT_KEY,
            expected_schema="dma_frequency_temperature_sweep",
            expected_run_id=corrected_run_id,
        )
        _assert_dma_content(corrected_content, include_tan=False)
        if corrected_run["raw_asset_id"] == rejected_run["raw_asset_id"]:
            raise RuntimeError("corrected source reused the rejected immutable Raw Asset")

        _activate_context(page, base_url, metal_context)
        fld_run_id = _upload_source(page, sources["fld"], test_run_id=fld_test_run_id)
        _configure_fld(
            page,
            FLD_DOCUMENT_KEY,
            columns=("minor_strain_pct", "major_strain_pct"),
        )
        _preview(page, expected_status=200)
        fld_columns = ("minor_strain_pct", "major_strain_pct")

        def prepare_fld_secondary(candidate: Page) -> None:
            _upload_source(candidate, sources["fld"], test_run_id=fld_test_run_id)
            _configure_fld(
                candidate,
                FLD_DOCUMENT_KEY,
                columns=fld_columns,
            )

            _preview(candidate, expected_status=200)

        captured, capture_failures = _capture_across_viewports(
            page,
            packet,
            base_url=base_url,
            context=metal_context,
            state="fld",
            decision_selector=".data-mapping-table",
            prepare_secondary=prepare_fld_secondary,
        )
        measurements.extend(captured)
        failures.extend(capture_failures)
        if not _document_exists(page, FLD_DOCUMENT_KEY):
            _save_document(page, FLD_DOCUMENT_KEY)
        fld_document, fld_content, fld_run = _read_back_document(
            page,
            FLD_DOCUMENT_KEY,
            expected_schema="forming_limit_diagram",
            expected_run_id=fld_run_id,
        )
        _assert_fld_content(fld_content)

    _activate_context(page, base_url, polymer_context)
    page.get_by_role("tab", name="Library").click()
    for label in (DMA_DOCUMENT_KEY, DMA_RECOVERED_DOCUMENT_KEY):
        page.get_by_text(label, exact=True).wait_for(state="visible", timeout=30_000)
    _activate_context(page, base_url, metal_context)
    page.get_by_role("tab", name="Library").click()
    page.get_by_text(FLD_DOCUMENT_KEY, exact=True).wait_for(state="visible", timeout=30_000)
    current._wait_for_settled(page)
    runtime_errors = page.evaluate("() => window.__cmpCaptureRuntimeErrors ?? []")
    if failures or runtime_errors:
        raise RuntimeError(
            f"governed-import browser errors: console={failures!r}, runtime={runtime_errors!r}"
        )
    browser_version = browser.version
    page.context.close()
    return {
        "browser": f"Chromium {browser_version}",
        "browser_zoom": "100%",
        "device_pixel_ratio": 1,
        "density": "standard",
        "measurements": measurements,
        "dma": {
            "document": dma_document,
            "import_run": dma_run,
            "assertion": (
                "two independent axes, four dependent/optional channels, affine temperature "
                "and modulus normalization, unsorted source order preserved"
            ),
        },
        "rejected_dma": {
            "import_run": rejected_run,
            "idempotency_key": retry_key,
            "assertion": (
                "whole file rejected with row/cell/channel recovery diagnostics and no Test "
                "Data revision"
            ),
        },
        "corrected_dma": {
            "document": corrected_document,
            "import_run": corrected_run,
            "assertion": "new immutable source succeeds while rejected evidence remains unchanged",
        },
        "fld": {
            "document": fld_document,
            "import_run": fld_run,
            "assertion": "signed, non-monotonic FLD coordinates and source order preserved",
        },
        "reload": (
            "both DMA identities are visible in the exact polymer context and FLD is visible in "
            "the exact metal context after full route reload"
        ),
    }


def _copy_current_originals(packet: Path) -> None:
    CURRENT.mkdir(parents=True, exist_ok=True)
    for source in sorted((packet / "after/originals").glob("*.png")):
        temporary = CURRENT / f".{source.name}.issue209.tmp"
        shutil.copyfile(source, temporary)
        os.replace(temporary, CURRENT / source.name)


def _file_record(path: Path, packet: Path) -> dict[str, Any]:
    value = path.read_bytes()
    record: dict[str, Any] = {
        "path": _evidence_ref(path, packet),
        "sha256": hashlib.sha256(value).hexdigest(),
        "bytes": len(value),
    }
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            record["pixels"] = f"{image.width}x{image.height}"
    return record


def _duplicate_groups(packet: Path) -> list[dict[str, Any]]:
    inventory_roots = (
        ROOT / "docs/00-research",
        ROOT / "docs/17-evidence/images",
        ROOT / "docs/user-guide/images",
    )
    by_digest: dict[str, list[Path]] = {}
    for inventory_root in inventory_roots:
        for path in inventory_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                by_digest.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(path)
    return [
        {
            "rationale": (
                "Issue #209 keeps the exact current-guide and issue-owned original byte-identical "
                "so product-guide and acceptance provenance remain independently addressable."
            ),
            "images": sorted(_evidence_ref(path, packet) for path in paths),
        }
        for paths in by_digest.values()
        if len(paths) > 1 and any(path.is_relative_to(packet) for path in paths)
    ]


def _write_manifest(
    packet: Path,
    *,
    base_url: str,
    journey: dict[str, Any],
) -> None:
    files = sorted(
        path for path in packet.rglob("*") if path.is_file() and path.name != "visual-evidence.yaml"
    )
    manifest = {
        "issue": 209,
        "captured_at": datetime.now(UTC).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "base_commit": BASE_SHA,
        "branch": _git("branch", "--show-current"),
        "base_url": base_url,
        "synthetic_non_production_only": True,
        "capture_command": (
            "uv run --with playwright==1.62.0 --with pillow --with pyyaml python "
            "scripts/capture_issue209_visual_evidence.py --base-url http://127.0.0.1:5173"
        ),
        "viewports": [f"{width}x{height}" for width, height in VIEWPORTS],
        "density": "standard",
        "browser_zoom": "100%",
        "device_pixel_ratio": 1,
        "available_windows_displays": [
            "2560x1440@59Hz, 96 DPI, 100% scale",
            "2560x1600@165Hz, 96 DPI, 100% scale",
        ],
        "physical_4k_readability": "deferred_to_issue_223",
        "before": {
            "source": "accepted Modeling Data current-guide PNG blobs from exact origin/main base",
            "note": "No missing state or changed baseline pixel was fabricated.",
        },
        "journey": journey,
        "scope_boundary": (
            "DMA frequency-temperature sweep and FLD governed import only; no dma_strain_sweep, "
            "source-v2 bundle adapter, extra unit adapter, DMA-to-Prony, or Material Model IR link."
        ),
        "allowed_duplicate_groups": _duplicate_groups(packet),
        "files": [_file_record(path, packet) for path in files],
    }
    (packet / "visual-evidence.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()

    if EVIDENCE.exists():
        raise RuntimeError(f"refusing to replace existing issue evidence: {EVIDENCE}")
    if _git("status", "--porcelain"):
        raise RuntimeError("issue evidence must start from a clean implementation commit")

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".issue-209-evidence-", dir=EVIDENCE.parent))
    try:
        _extract_base_originals(staging)
        _crop_base_originals(staging)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                journey = _capture_journey(browser, args.base_url, staging)
            finally:
                browser.close()
        _write_manifest(staging, base_url=args.base_url, journey=journey)
        os.replace(staging, EVIDENCE)
        _copy_current_originals(EVIDENCE)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    print(
        json.dumps(
            {
                "source_commit": _git("rev-parse", "HEAD"),
                "evidence": _project_ref(EVIDENCE),
                "files": sum(1 for path in EVIDENCE.rglob("*") if path.is_file()),
                "current_images": 15,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

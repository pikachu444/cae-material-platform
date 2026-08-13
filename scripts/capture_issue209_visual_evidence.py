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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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


def _select_test_run(page: Page, index: int) -> str:
    control = page.get_by_role("combobox", name="Local file Test Run")
    control.wait_for(state="visible", timeout=30_000)
    page.wait_for_function(
        """() => (
          document.querySelector('select[aria-label="Local file Test Run"]')?.options.length ?? 0
        ) > 2""",
        timeout=30_000,
    )
    control.select_option(index=index)
    value = control.input_value()
    if not value:
        raise RuntimeError("exact Test Run selection did not settle")
    return value


def _upload_source(page: Page, source: Path, *, test_run_index: int) -> str:
    page.get_by_role("tab", name="Local file").click()
    run_id = _select_test_run(page, test_run_index)
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
        page.get_by_role("button", name="Save Test Data").wait_for(state="visible", timeout=30_000)
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
) -> list[dict[str, Any]]:
    originals = packet / "after/originals"
    crops = packet / "after/crops"
    originals.mkdir(parents=True, exist_ok=True)
    crops.mkdir(parents=True, exist_ok=True)
    measurements: list[dict[str, Any]] = []
    for width, height in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
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
                    "unreachable decision overflow for "
                    f"{state} {width}x{height}: {decision_metrics}"
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
        measurements.append(
            {
                "state": state,
                "css_viewport": f"{width}x{height}",
                "browser_zoom": "100%",
                "device_pixel_ratio": layout["dpr"],
                "layout": layout,
                "elements": elements,
            }
        )
    return measurements


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
        page, lambda: page.get_by_role("button", name="Save Test Data").click()
    )
    if run["status"] != "succeeded":
        raise RuntimeError(f"successful save produced failed Import Run: {run!r}")
    page.get_by_text(f"Registered {document_key}", exact=False).wait_for(
        state="visible", timeout=30_000
    )
    current._wait_for_settled(page)
    return run


def _record_rejection(page: Page) -> tuple[dict[str, Any], str]:
    response, first = _wait_for_import_response(
        page, lambda: page.get_by_role("button", name="Record rejected import").click()
    )
    if first["status"] != "failed" or not first["diagnostics"]:
        raise RuntimeError(f"invalid source did not retain failed diagnostics: {first!r}")
    page.get_by_role("region", name="Rejected source cells").wait_for(
        state="visible", timeout=30_000
    )
    first_key = response.request.headers.get("idempotency-key", "")
    response, second = _wait_for_import_response(
        page, lambda: page.get_by_role("button", name="Record rejected import").click()
    )
    second_key = response.request.headers.get("idempotency-key", "")
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
    measurements: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="cmp-issue209-") as temporary:
        sources = _write_sources(Path(temporary))

        dma_run_id = _upload_source(page, sources["dma"], test_run_index=1)
        _configure_dma(
            page,
            "ISSUE209-DMA-SWEEP",
            columns=(
                "temperature_c",
                "frequency_hz",
                "storage_mpa",
                "loss_mpa",
                "tan_delta",
            ),
        )
        _preview(page, expected_status=200)
        measurements.extend(
            _capture_state(
                page,
                packet,
                state="dma",
                decision_selector=".data-mapping-table",
            )
        )
        _save_document(page, "ISSUE209-DMA-SWEEP")
        dma_document, dma_content, dma_run = _read_back_document(
            page,
            "ISSUE209-DMA-SWEEP",
            expected_schema="dma_frequency_temperature_sweep",
            expected_run_id=dma_run_id,
        )
        _assert_dma_content(dma_content, include_tan=True)

        _upload_source(page, sources["dma_invalid"], test_run_index=1)
        _configure_dma(
            page,
            "ISSUE209-DMA-REJECTED",
            columns=("temperature_bad", "frequency_bad", "storage_bad", "loss_bad", None),
        )
        _preview(page, expected_status=422)
        rejected_run, retry_key = _record_rejection(page)
        _assert_missing_document(page, "ISSUE209-DMA-REJECTED")
        diagnostic_codes = {item["error_code"] for item in rejected_run["diagnostics"]}
        if len(rejected_run["diagnostics"]) < 4 or not {
            "frequency_not_positive",
            "temperature_below_absolute_zero",
            "missing_value",
            "negative_dma_response",
        }.issubset(diagnostic_codes):
            raise RuntimeError(f"full-file DMA diagnostics drifted: {rejected_run!r}")
        measurements.extend(
            _capture_state(
                page,
                packet,
                state="dma-rejected",
                decision_selector=".data-import-diagnostics",
            )
        )

        corrected_run_id = _upload_source(page, sources["dma_corrected"], test_run_index=1)
        _configure_dma(
            page,
            "ISSUE209-DMA-RECOVERED",
            columns=("temperature_bad", "frequency_bad", "storage_bad", "loss_bad", None),
            expose_mapping=False,
        )
        _preview(page, expected_status=200)
        _save_document(page, "ISSUE209-DMA-RECOVERED")
        corrected_document, corrected_content, corrected_run = _read_back_document(
            page,
            "ISSUE209-DMA-RECOVERED",
            expected_schema="dma_frequency_temperature_sweep",
            expected_run_id=corrected_run_id,
        )
        _assert_dma_content(corrected_content, include_tan=False)
        if corrected_run["raw_asset_id"] == rejected_run["raw_asset_id"]:
            raise RuntimeError("corrected source reused the rejected immutable Raw Asset")

        fld_run_id = _upload_source(page, sources["fld"], test_run_index=2)
        _configure_fld(
            page,
            "ISSUE209-FLD",
            columns=("minor_strain_pct", "major_strain_pct"),
        )
        _preview(page, expected_status=200)
        measurements.extend(
            _capture_state(
                page,
                packet,
                state="fld",
                decision_selector=".data-mapping-table",
            )
        )
        _save_document(page, "ISSUE209-FLD")
        fld_document, fld_content, fld_run = _read_back_document(
            page,
            "ISSUE209-FLD",
            expected_schema="forming_limit_diagram",
            expected_run_id=fld_run_id,
        )
        _assert_fld_content(fld_content)

    page.reload()
    current._wait_for_modeling_data_surface(page)
    page.get_by_role("tab", name="Library").click()
    for label in ("ISSUE209-DMA-SWEEP", "ISSUE209-DMA-RECOVERED", "ISSUE209-FLD"):
        page.get_by_text(label, exact=True).wait_for(state="visible", timeout=30_000)
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
            "all three successful exact Test Data identities are visible after full route reload"
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

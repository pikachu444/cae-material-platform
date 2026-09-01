"""Capture the current product screens declared by the user-guide manifest.

Run against the deterministic Compose demo:

    uv run --with playwright==1.62.0 python scripts/capture_current_product.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import struct
import tempfile
import time
import uuid
from collections.abc import Callable, Sequence
from copy import deepcopy
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, quote, urlencode, urlsplit

# Embedded Playwright snippets and exact UI labels intentionally exceed Ruff's
# line length and preserve typographic punctuation for source-contract checks.
# ruff: noqa: E501, RUF001

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Dialog, FloatRect, Locator, Page, Route

VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
WIDE_VIEWPORTS = ((2560, 1440), (3840, 2160))
DISPLAY_DENSITIES = ("compact", "standard", "large")
CAPTURE_DISPLAY_DENSITY = "standard"
ACTIVITY_HISTORY_VIEWPORTS = (VIEWPORTS[1], VIEWPORTS[2], *WIDE_VIEWPORTS)
REVISION_LABEL_PATTERN = re.compile(r"\br[1-9]\d*\b")
UUID_LIKE_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
MODELING_EXPORT_OUTPUTS = (
    *(f"modeling-export-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    "modeling-export-source-blocked-1440x900.png",
    "modeling-export-approximation-blocked-1440x900.png",
    "modeling-export-delivered-1440x900.png",
)
MODELING_EXPORT_PRE_DELIVERED_OUTPUTS = MODELING_EXPORT_OUTPUTS[:-1]
MODELING_FIT_STATE_OUTPUTS = (
    "modeling-fit-calculation-failed-1920x1080.png",
    "modeling-fit-save-failed-1920x1080.png",
    "modeling-fit-exact-source-blocked-1920x1080.png",
    "modeling-fit-exact-read-failed-1920x1080.png",
    "modeling-fit-restored-1920x1080.png",
)
MODELING_FIT_PRE_RESTORE_OUTPUTS = MODELING_FIT_STATE_OUTPUTS[:-1]
MODELING_FIT_RESTORED_OUTPUTS = MODELING_FIT_STATE_OUTPUTS[-1:]
MODELING_PROCESS_FIT_VIEWPORT_OUTPUTS = (
    *(f"modeling-process-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
)
MODELING_PROCESS_FIT_OUTPUTS = (
    *MODELING_PROCESS_FIT_VIEWPORT_OUTPUTS,
    *MODELING_FIT_STATE_OUTPUTS,
)
MODELING_PROCESS_OUTPUTS = (
    *(f"modeling-process-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    "modeling-process-linear-regression-1366x768.png",
    "modeling-process-manual-1366x768.png",
    "modeling-process-blocked-1440x900.png",
    "modeling-process-exact-read-failed-1440x900.png",
    "modeling-process-siblings-1440x900.png",
)
MODELING_CONSISTENCY_OUTPUTS = tuple(
    f"modeling-{stage}-{width}x{height}.png"
    for stage in ("data", "process", "fit", "export", "session")
    for width, height in VIEWPORTS
)
MODELING_DATA_SESSION_OUTPUTS = (
    *(f"modeling-data-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    *(f"modeling-session-{width}x{height}.png" for width, height in VIEWPORTS),
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-data-invalid-scrolled-1440x900.png",
)
MODELING_PROCESS_MANUAL_OUTPUTS = ("modeling-process-manual-1366x768.png",)
MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS = tuple(
    f"modeling-distribution-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
MODELING_DISTRIBUTION_DETAIL_OUTPUTS = tuple(
    f"modeling-distribution-{region}-from-{width}x{height}-crop.png"
    for width, height in (VIEWPORTS[2], *WIDE_VIEWPORTS)
    for region in ("header", "navigator", "table", "selection-form", "graph")
)
MODELING_DISTRIBUTION_OUTPUTS = (
    *MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS,
    *MODELING_DISTRIBUTION_DETAIL_OUTPUTS,
)
MODELING_DATA_EXCEPTION_OUTPUTS = (
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-data-invalid-scrolled-1440x900.png",
)
PRODUCT_ACCESS_OUTPUTS = (
    *(
        f"administration-access-{width}x{height}.png"
        for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
    ),
)
ADMINISTRATION_DATABASE_OUTPUTS = tuple(
    filename
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
    for filename in (
        f"administration-database-{width}x{height}.png",
        f"administration-database-preview-{width}x{height}.png",
    )
)
ADMINISTRATION_RECORDS_OUTPUTS = tuple(
    f"administration-records-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
ADMINISTRATION_RECORDS_IMPORT_JSON_OUTPUTS = tuple(
    f"administration-records-import-json-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
ACTIVITY_OUTPUTS = (
    *(f"activity-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    *(f"activity-history-{width}x{height}.png" for width, height in ACTIVITY_HISTORY_VIEWPORTS),
    "activity-user-1440x900.png",
    "activity-administrator-1440x900.png",
    "activity-decision-error-1440x900.png",
    "activity-recovery-1440x900.png",
)
REVIEW_SUBMISSION_OUTPUTS = (
    *(
        f"{screen}-{width}x{height}.png"
        for screen in ("solver-card-preview", "activity")
        for width, height in VIEWPORTS
    ),
    "material-detail-1440x900.png",
)
MATERIALS_WORKSPACE_OUTPUTS = (
    *(f"materials-search-{width}x{height}.png" for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)),
    *(f"materials-search-long-{width}x{height}.png" for width, height in VIEWPORTS),
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
)
MATERIAL_DETAIL_OUTPUTS = tuple(
    f"material-detail-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
MATERIAL_CURVE_OUTPUTS = tuple(
    f"material-curves-{width}x{height}.png"
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
)
MATERIAL_DETAIL_EXCEPTION_OUTPUTS = (
    "material-detail-related-long-1440x900.png",
    "material-detail-empty-1440x900.png",
)
SOLVER_CARD_EXCEPTION_OUTPUTS = (
    "solver-card-approximation-blocked-1440x900.png",
    "solver-card-unsupported-blocked-1440x900.png",
)
SOLVER_CARD_WIDE_OUTPUTS = (
    "solver-card-preview-2560x1440.png",
    "solver-card-preview-3840x2160.png",
)
MATERIALS_OUTPUTS = (
    *MATERIALS_WORKSPACE_OUTPUTS,
    *MATERIAL_DETAIL_OUTPUTS,
    *MATERIAL_CURVE_OUTPUTS,
    *MATERIAL_DETAIL_EXCEPTION_OUTPUTS,
    *SOLVER_CARD_EXCEPTION_OUTPUTS,
    *SOLVER_CARD_WIDE_OUTPUTS,
    "material-cae-cards-1440x900.png",
)
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-search-long-1366x768.png",
    "materials-search-long-1440x900.png",
    "materials-search-long-1920x1080.png",
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
    "material-database-categories-1440x900.png",
    "material-database-linked-test-1440x900.png",
    "material-detail-1366x768.png",
    "material-detail-1440x900.png",
    "material-detail-1920x1080.png",
    "material-cae-cards-1440x900.png",
    "materials-search-2560x1440.png",
    "materials-search-3840x2160.png",
    "material-detail-2560x1440.png",
    "material-detail-3840x2160.png",
    "material-curves-1366x768.png",
    "material-curves-1440x900.png",
    "material-curves-1920x1080.png",
    "material-curves-2560x1440.png",
    "material-curves-3840x2160.png",
    "demo-session-recovery-1440x900.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "solver-card-preview-2560x1440.png",
    "solver-card-preview-3840x2160.png",
    "material-detail-related-long-1440x900.png",
    "material-detail-empty-1440x900.png",
    "solver-card-approximation-blocked-1440x900.png",
    "solver-card-unsupported-blocked-1440x900.png",
    "modeling-data-1366x768.png",
    "modeling-data-1440x900.png",
    "modeling-data-1920x1080.png",
    "modeling-data-2560x1440.png",
    "modeling-data-3840x2160.png",
    "modeling-data-dma-1366x768.png",
    "modeling-data-dma-1440x900.png",
    "modeling-data-dma-1920x1080.png",
    "modeling-data-dma-2560x1440.png",
    "modeling-data-dma-3840x2160.png",
    "modeling-data-dma-rejected-1366x768.png",
    "modeling-data-dma-rejected-1440x900.png",
    "modeling-data-dma-rejected-1920x1080.png",
    "modeling-data-dma-rejected-2560x1440.png",
    "modeling-data-dma-rejected-3840x2160.png",
    "modeling-data-fld-1366x768.png",
    "modeling-data-fld-1440x900.png",
    "modeling-data-fld-1920x1080.png",
    "modeling-data-fld-2560x1440.png",
    "modeling-data-fld-3840x2160.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
    "modeling-data-empty-1440x900.png",
    "modeling-data-invalid-1440x900.png",
    "modeling-data-invalid-scrolled-1440x900.png",
    "modeling-process-1366x768.png",
    "modeling-process-linear-regression-1366x768.png",
    "modeling-process-manual-1366x768.png",
    "modeling-process-1440x900.png",
    "modeling-process-1920x1080.png",
    "modeling-process-2560x1440.png",
    "modeling-process-3840x2160.png",
    "modeling-process-blocked-1440x900.png",
    "modeling-process-exact-read-failed-1440x900.png",
    "modeling-process-siblings-1440x900.png",
    "modeling-process-polymer-dma-tts-1366x768.png",
    "modeling-process-polymer-dma-tts-1440x900.png",
    "modeling-process-polymer-dma-tts-1920x1080.png",
    "modeling-process-polymer-dma-tts-2560x1440.png",
    "modeling-process-polymer-dma-tts-3840x2160.png",
    "modeling-process-polymer-dma-tts-saved-1366x768.png",
    "modeling-process-polymer-dma-tts-saved-1440x900.png",
    "modeling-process-polymer-dma-tts-saved-1920x1080.png",
    "modeling-process-polymer-dma-tts-saved-2560x1440.png",
    "modeling-process-polymer-dma-tts-saved-3840x2160.png",
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
    "modeling-fit-calculation-failed-1920x1080.png",
    "modeling-fit-save-failed-1920x1080.png",
    "modeling-fit-exact-source-blocked-1920x1080.png",
    "modeling-fit-exact-read-failed-1920x1080.png",
    "modeling-fit-restored-1920x1080.png",
    "modeling-fit-polymer-source-blocked-1366x768.png",
    "modeling-fit-polymer-source-blocked-1440x900.png",
    "modeling-fit-polymer-source-blocked-1920x1080.png",
    "modeling-fit-polymer-source-blocked-2560x1440.png",
    "modeling-fit-polymer-source-blocked-3840x2160.png",
    "modeling-fit-polymer-saved-1366x768.png",
    "modeling-fit-polymer-saved-1440x900.png",
    "modeling-fit-polymer-saved-1920x1080.png",
    "modeling-fit-polymer-saved-2560x1440.png",
    "modeling-fit-polymer-saved-3840x2160.png",
    "modeling-fit-polymer-input-1920x1080.png",
    "modeling-fit-polymer-residual-1920x1080.png",
    "modeling-fit-polymer-calculation-settings-1920x1080.png",
    "modeling-fit-polymer-stale-1920x1080.png",
    "modeling-fit-polymer-stale-restored-saved-input-1920x1080.png",
    "modeling-fit-polymer-stale-recovered-1920x1080.png",
    "modeling-distribution-1366x768.png",
    "modeling-distribution-1440x900.png",
    "modeling-distribution-1920x1080.png",
    "modeling-distribution-2560x1440.png",
    "modeling-distribution-3840x2160.png",
    "modeling-export-1366x768.png",
    "modeling-export-1440x900.png",
    "modeling-export-1920x1080.png",
    "modeling-export-2560x1440.png",
    "modeling-export-3840x2160.png",
    "modeling-export-source-blocked-1440x900.png",
    "modeling-export-approximation-blocked-1440x900.png",
    "modeling-export-delivered-1440x900.png",
    "activity-1366x768.png",
    "activity-1440x900.png",
    "activity-1920x1080.png",
    "activity-2560x1440.png",
    "activity-3840x2160.png",
    "activity-history-1440x900.png",
    "activity-history-1920x1080.png",
    "activity-history-2560x1440.png",
    "activity-history-3840x2160.png",
    "activity-user-1440x900.png",
    "activity-administrator-1440x900.png",
    "activity-decision-error-1440x900.png",
    "activity-recovery-1440x900.png",
    "administration-format-definitions-1440x900.png",
    "administration-database-1366x768.png",
    "administration-database-1440x900.png",
    "administration-database-1920x1080.png",
    "administration-database-2560x1440.png",
    "administration-database-3840x2160.png",
    "administration-database-preview-1366x768.png",
    "administration-database-preview-1440x900.png",
    "administration-database-preview-1920x1080.png",
    "administration-database-preview-2560x1440.png",
    "administration-database-preview-3840x2160.png",
    "administration-records-1366x768.png",
    "administration-records-1440x900.png",
    "administration-records-1920x1080.png",
    "administration-records-2560x1440.png",
    "administration-records-3840x2160.png",
    "administration-records-import-json-1366x768.png",
    "administration-records-import-json-1440x900.png",
    "administration-records-import-json-1920x1080.png",
    "administration-records-import-json-2560x1440.png",
    "administration-records-import-json-3840x2160.png",
    "administration-access-1366x768.png",
    "administration-access-1440x900.png",
    "administration-access-1920x1080.png",
    "administration-access-2560x1440.png",
    "administration-access-3840x2160.png",
)
STAGE_HEADINGS = {
    "data": "Select Test Data",
    "process": "Process Test Data",
    "fit": "Fit Material Model",
    "export": "Create Solver Card",
}
EXPECTED_EXACT_FIT_RESTORE_ERROR = "Saved Fit result unavailable · Retry exact saved result."
EXPORT_RECOVERY_REASON = "Create a solver card from this model."
PROCESS_SOURCE_DOCUMENT_KEY = "CMP-DEMO-DP780-TEST-JSON"
MODELING_DATA_DOCUMENT_KEYS = (
    PROCESS_SOURCE_DOCUMENT_KEY,
    "CMP-DEMO-DP780-TEST-JSON-02",
    "CMP-DEMO-DP780-TEST-JSON-03",
)
PROCESS_SOURCE_TITLE = "Tensile test 0001"
PROCESS_SOURCE_VISIBLE_IDENTITY = "Tensile test 0001"
PROCESS_NO_PREVIEW_SAVED_INSTRUCTION = (
    "No Process preview is active. Choose Use settings for a saved result, then select "
    "Preview changes to preview the draft."
)
UNFINISHED = re.compile(
    r"^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\b.*(?:…|\.\.\.)$",
    re.IGNORECASE,
)
NORMAL_SURFACE_TECHNICAL_LABELS = re.compile(
    r"\b(?:draft|fixture|uuid|sha(?:256)?|hash|lifecycle[_\s-]?state)\b"
    r"|\bissue\s*#\s*\d+\b|\bimplementation state\b",
    re.IGNORECASE,
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _display_density_scope(access_token: str) -> str:
    claims: dict[str, object] = {}
    try:
        payload = access_token.split(".")[1]
        padding = "=" * ((4 - len(payload) % 4) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
        if isinstance(decoded, dict):
            claims = decoded
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        claims = {}

    def claim(*names: str) -> str | None:
        for name in names:
            value = claims.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    values = (
        "/api/v1",
        claim("organization_id", "org_id") or "local-organization",
        claim("workspace_id", "project_id") or "local-workspace",
        claim("principal_id", "sub", "user_id") or "anonymous",
    )
    return "|".join(quote(value, safe="-_.!~*'()") for value in values)


def _new_page(
    browser: Browser,
    base_url: str,
    width: int,
    height: int,
    persona: str = "administrator",
) -> Page:
    context = browser.new_context(viewport={"width": width, "height": height})
    token_response = context.request.get(
        f"{base_url}/api/v1/demo-identity/token?persona={persona}"
    )
    if not token_response.ok:
        raise RuntimeError("local demo identity is unavailable")
    access_token = token_response.json()["access_token"]
    serialized_config = json.dumps({"baseUrl": "/api/v1", "accessToken": access_token})
    preference_scope = _display_density_scope(access_token)
    serialized_preferences = json.dumps(
        {
            "version": 1,
            "displayDensityByScope": {
                preference_scope: CAPTURE_DISPLAY_DENSITY,
            },
        }
    )
    context.add_init_script(
        script=(
            "window.localStorage.setItem("
            f"'cmp.material-platform.api-config', {json.dumps(serialized_config)}"
            ");"
            "window.localStorage.setItem("
            "'cmp.material-platform.client-preferences.v1', "
            f"{json.dumps(serialized_preferences)}"
            ");"
        )
    )
    page = context.new_page()
    page.goto(base_url)
    return page


def _source_v2_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"source-v2 {label} is not an object")
    return value


def _source_v2_uuid(value: object, label: str) -> str:
    if not isinstance(value, str) or UUID_LIKE_PATTERN.fullmatch(value) is None:
        raise RuntimeError(f"source-v2 {label} is not a UUID")
    return value


def _source_v2_revision(
    value: object,
    *,
    label: str,
    aggregate_id: str,
    lifecycle_state: str,
) -> tuple[dict[str, object], str]:
    revision = _source_v2_object(value, f"{label} revision")
    revision_id = _source_v2_uuid(revision.get("id"), f"{label} revision id")
    if revision.get("aggregate_id") != aggregate_id:
        raise RuntimeError(f"source-v2 {label} revision identity does not match")
    if revision.get("revision_no") != 1:
        raise RuntimeError(f"source-v2 {label} is not revision 1")
    if revision.get("lifecycle_state") != lifecycle_state:
        raise RuntimeError(f"source-v2 {label} has the wrong lifecycle state")
    return revision, revision_id


def _resolve_administration_source_v2(page: Page, base_url: str) -> dict[str, str]:
    raw_config = page.evaluate(
        """() => {
            const raw = window.localStorage.getItem("cmp.material-platform.api-config");
            return raw ? JSON.parse(raw) : null;
        }"""
    )
    config = _source_v2_object(raw_config, "API configuration")
    access_token = config.get("accessToken")
    if not isinstance(access_token, str) or not access_token.strip():
        raise RuntimeError("source-v2 resolver requires an authenticated API token")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    tables_response = page.context.request.get(
        f"{base_url}/api/v1/catalog/tables",
        headers=headers,
    )
    if not tables_response.ok:
        raise RuntimeError(f"source-v2 table resolution failed with HTTP {tables_response.status}")
    tables_payload = _source_v2_object(tables_response.json(), "table response")
    table_items = tables_payload.get("items")
    if not isinstance(table_items, list):
        raise RuntimeError("source-v2 table response has no item list")
    table_matches: list[tuple[dict[str, object], dict[str, object], dict[str, object]]] = []
    for candidate in table_items:
        table = _source_v2_object(candidate, "table item")
        revision = _source_v2_object(table.get("current_revision"), "table current revision")
        content = _source_v2_object(revision.get("content"), "table content")
        if content.get("key") == "technical_data":
            table_matches.append((table, revision, content))
    if len(table_matches) != 1:
        raise RuntimeError("source-v2 Technical Data table key is not unique")
    table, table_revision, table_content = table_matches[0]
    table_id = _source_v2_uuid(table.get("table_id"), "Technical Data table id")
    table_revision_id = _source_v2_uuid(table_revision.get("id"), "Technical Data table revision id")
    _source_v2_revision(
        table_revision,
        label="Technical Data table",
        aggregate_id=table_id,
        lifecycle_state="published",
    )
    if table_content.get("key") != "technical_data":
        raise RuntimeError("source-v2 Technical Data table key changed")
    if table_content.get("name") != "Technical Data":
        raise RuntimeError("source-v2 Technical Data table name changed")
    if table_content.get("data_category") != "technical_data":
        raise RuntimeError("source-v2 Technical Data table category changed")

    layouts_response = page.context.request.get(
        f"{base_url}/api/v1/catalog/tables/{table_id}/layouts",
        headers=headers,
    )
    if not layouts_response.ok:
        raise RuntimeError(f"source-v2 layout resolution failed with HTTP {layouts_response.status}")
    layouts_payload = _source_v2_object(layouts_response.json(), "layout response")
    layout_items = layouts_payload.get("items")
    if not isinstance(layout_items, list):
        raise RuntimeError("source-v2 layout response has no item list")
    layout_matches = [
        _source_v2_object(candidate, "layout item")
        for candidate in layout_items
        if _source_v2_object(candidate, "layout item").get("name")
        == "Technical Data default layout"
    ]
    if len(layout_matches) != 1:
        raise RuntimeError("source-v2 Technical Data default layout is not unique")
    layout = layout_matches[0]
    layout_id = _source_v2_uuid(layout.get("layout_id"), "Technical Data layout id")
    layout_revision_id: str
    if layout.get("table_id") != table_id or layout.get("table_revision_id") != table_revision_id:
        raise RuntimeError("source-v2 Technical Data layout is pinned to the wrong table revision")
    layout_revision, layout_revision_id = _source_v2_revision(
        layout.get("revision"),
        label="Technical Data default layout",
        aggregate_id=layout_id,
        lifecycle_state="published",
    )
    if layout.get("name") != "Technical Data default layout":
        raise RuntimeError("source-v2 Technical Data layout name changed")
    if layout.get("version") not in (None, 1) or layout_revision.get("version") not in (None, 1):
        raise RuntimeError("source-v2 Technical Data layout is not version 1")

    records_response = page.context.request.post(
        f"{base_url}/api/v1/catalog/records:search",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps(
            {
                "table_id": table_id,
                "text": "CMP-246-TECH-DP780",
                "offset": 0,
                "limit": 100,
            }
        ),
    )
    if not records_response.ok:
        raise RuntimeError(f"source-v2 record resolution failed with HTTP {records_response.status}")
    records_payload = _source_v2_object(records_response.json(), "record response")
    record_items = records_payload.get("items")
    if not isinstance(record_items, list):
        raise RuntimeError("source-v2 record response has no item list")
    record_matches: list[tuple[dict[str, object], dict[str, object], dict[str, object]]] = []
    for candidate in record_items:
        record = _source_v2_object(candidate, "record item")
        revision = _source_v2_object(record.get("current_revision"), "record current revision")
        content = _source_v2_object(revision.get("content"), "record content")
        if content.get("external_key") == "CMP-246-TECH-DP780":
            record_matches.append((record, revision, content))
    if len(record_matches) != 1 or records_payload.get("total_count") != 1:
        raise RuntimeError("source-v2 DP780 technical data record is not unique")
    record, record_revision, record_content = record_matches[0]
    record_id = _source_v2_uuid(record.get("record_id"), "DP780 technical data record id")
    record_revision_id = _source_v2_uuid(
        record_revision.get("id"), "DP780 technical data record revision id"
    )
    _source_v2_revision(
        record_revision,
        label="DP780 technical data record",
        aggregate_id=record_id,
        lifecycle_state="draft",
    )
    if record.get("table_id") != table_id:
        raise RuntimeError("source-v2 DP780 technical data record uses the wrong table")
    if record_content.get("table_revision_id") != table_revision_id:
        raise RuntimeError("source-v2 DP780 technical data record uses the wrong table revision")
    if record_content.get("name") != "DP780 technical data":
        raise RuntimeError("source-v2 DP780 technical data record name changed")
    if record_content.get("external_key") != "CMP-246-TECH-DP780":
        raise RuntimeError("source-v2 DP780 technical data record key changed")

    return {
        "table_id": table_id,
        "table_revision_id": table_revision_id,
        "layout_id": layout_id,
        "layout_revision_id": layout_revision_id,
        "record_id": record_id,
        "record_revision_id": record_revision_id,
    }


def _administration_database_url(
    base_url: str,
    pins: dict[str, str],
    *,
    include_record: bool = False,
) -> str:
    entries = [
        ("table_id", pins["table_id"]),
        ("table_revision_id", pins["table_revision_id"]),
        ("object_kind", "layouts"),
        ("object_id", pins["layout_id"]),
        ("object_revision_id", pins["layout_revision_id"]),
    ]
    if include_record:
        entries.extend(
            [
                ("record_id", pins["record_id"]),
                ("record_revision_id", pins["record_revision_id"]),
            ]
        )
    return f"{base_url}/administration/database?{urlencode(entries)}"


def _administration_records_url(base_url: str, pins: dict[str, str], *, include_record: bool = False) -> str:
    entries = [
        ("table_id", pins["table_id"]),
        ("table_revision_id", pins["table_revision_id"]),
    ]
    if include_record:
        entries.extend(
            [
                ("record_id", pins["record_id"]),
                ("record_revision_id", pins["record_revision_id"]),
            ]
        )
    return f"{base_url}/administration/records?{urlencode(entries)}"


def _assert_administration_url(page: Page, expected_url: str) -> None:
    if page.url != expected_url:
        raise RuntimeError(f"Administration exact URL drifted: expected={expected_url} actual={page.url}")


def _wait_for_administration_record_type(page: Page, pins: dict[str, str]) -> Locator:
    record_type = page.get_by_role("combobox", name="Record type", exact=True)
    record_type.wait_for(timeout=30_000)
    deadline = time.monotonic() + 30
    while record_type.input_value() != pins["table_id"]:
        if time.monotonic() >= deadline:
            raise RuntimeError("Administration did not select the resolved source-v2 Record type")
        page.wait_for_timeout(100)
    if record_type.input_value() != pins["table_id"]:
        raise RuntimeError("Administration selected the wrong source-v2 Record type")
    return record_type


def _wait_for_administration_layout(
    page: Page,
    pins: dict[str, str],
    expected_url: str,
    *,
    require_property_form: bool = True,
) -> None:
    page.get_by_role("region", name="Database design", exact=True).wait_for(timeout=30_000)
    page.get_by_role("navigation", name="Database objects", exact=True).wait_for(timeout=30_000)
    _wait_for_administration_record_type(page, pins)
    page.get_by_role(
        "heading", name="Technical Data default layout", exact=True
    ).wait_for(timeout=30_000)
    if require_property_form:
        page.locator(".schema-property-editor .property-sheet").wait_for(timeout=30_000)
    _assert_administration_url(page, expected_url)


def _wait_for_administration_preview(page: Page, pins: dict[str, str], expected_url: str) -> None:
    page.get_by_role("region", name="Datasheet preview", exact=True).wait_for(timeout=30_000)
    page.get_by_role("region", name="Preview fields", exact=True).wait_for(timeout=30_000)
    picker = page.get_by_role("combobox", name="Preview with", exact=True)
    picker.wait_for(timeout=30_000)
    if picker.input_value() != pins["record_id"]:
        raise RuntimeError("Administration preview selected the wrong source-v2 Record")
    selected_option = picker.locator("option:checked")
    if selected_option.count() != 1 or selected_option.inner_text() != "DP780 technical data (Draft, revision 1)":
        raise RuntimeError("Administration preview identity is not DP780 technical data r1 draft")
    _assert_administration_url(page, expected_url)


def _wait_for_administration_record(page: Page, pins: dict[str, str], expected_url: str) -> None:
    page.get_by_role(
        "region", name="Edit DP780 technical data", exact=True
    ).wait_for(timeout=30_000)
    page.get_by_role("heading", name="DP780 technical data", exact=True).wait_for(timeout=30_000)
    page.get_by_text("Draft · Revision 1", exact=True).wait_for(timeout=30_000)
    record_type = page.get_by_role("combobox", name="Record type", exact=True)
    if record_type.input_value() != pins["table_id"]:
        raise RuntimeError("Administration editor selected the wrong source-v2 Record type")
    record_code = page.get_by_role("textbox", name="Record code", exact=True)
    record_code.wait_for(timeout=30_000)
    if record_code.input_value() != "CMP-246-TECH-DP780":
        raise RuntimeError("Administration editor lost the exact DP780 record key")
    _assert_administration_url(page, expected_url)


def _bounding_box_edges(box: FloatRect | None) -> dict[str, float] | None:
    """Add viewport edges to Playwright's x/y/width/height bounding box."""
    if box is None:
        return None
    return {
        "x": box["x"],
        "y": box["y"],
        "width": box["width"],
        "height": box["height"],
        "left": box["x"],
        "right": box["x"] + box["width"],
        "top": box["y"],
        "bottom": box["y"] + box["height"],
    }


def _css_token_px(page: Page, name: str) -> float:
    """Read one resolved shared geometry token from the live root element."""
    value = page.evaluate(
        "name => Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name))",
        name,
    )
    if not isinstance(value, (int, float)):
        raise RuntimeError(f"shared CSS token {name} is not a resolved pixel value: {value!r}")
    return float(value)


def _wait_for_settled(page: Page) -> None:
    # Modeling keeps legitimate background requests alive. DOM readiness plus
    # the observable busy/text contract below is the deterministic screenshot
    # boundary; a global network-idle heuristic can time out on a settled UI.
    page.wait_for_load_state("domcontentloaded")
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


def _wait_for_delivered_solver_card_route(page: Page, expected_path: str) -> None:
    """Wait for the exact Materials card route and its completed native preview."""

    settled_script = """expectedPath => {
      const visible = element => Boolean(
        element
          && element.getClientRects().length > 0
          && getComputedStyle(element).visibility !== "hidden"
          && getComputedStyle(element).display !== "none"
      );
      const heading = [...document.querySelectorAll("h1")].find(visible);
      const headingText = heading?.textContent?.trim() ?? "";
      const nativePreview = document.querySelector(
        '[aria-label="Native solver card preview"]'
      );
      const nativeText = nativePreview?.textContent?.trim() ?? "";
      const unfinished = /^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\\b.*(?:…|\\.\\.\\.)$/i;
      const pendingLines = document.body.innerText
        .split("\\n")
        .map(line => line.trim())
        .filter(line => unfinished.test(line));
      const activeBusy = [...document.querySelectorAll('[aria-busy="true"]')]
        .filter(visible);
      const alerts = [...document.querySelectorAll('[role="alert"]')]
        .filter(visible);
      const deliveryLoading = [...document.querySelectorAll(
        '[data-testid="delivery-loading"], .delivery-loading, .export-delivery-loading'
      )].filter(visible);
      return window.location.pathname === expectedPath
        && Boolean(heading && headingText && headingText !== "Card preview")
        && Boolean(nativePreview && visible(nativePreview) && nativeText
          && nativeText !== "Loading native card preview…"
          && nativeText !== "Loading native card preview...")
        && pendingLines.length === 0
        && activeBusy.length === 0
        && alerts.length === 0
        && deliveryLoading.length === 0;
    }"""

    try:
        page.wait_for_function(settled_script, arg=expected_path, timeout=30_000)
    except Exception as error:
        diagnostics = page.evaluate(
            """() => {
              const visible = element => Boolean(
                element
                  && element.getClientRects().length > 0
                  && getComputedStyle(element).visibility !== "hidden"
                  && getComputedStyle(element).display !== "none"
              );
              const unfinished = /^(Checking|Loading|Calculating|Resolving|Updating|Preparing|Creating)\\b.*(?:…|\\.\\.\\.)$/i;
              const pendingLines = document.body.innerText
                .split("\\n")
                .map(line => line.trim())
                .filter(line => unfinished.test(line));
              const nativePreview = document.querySelector(
                '[aria-label="Native solver card preview"]'
              );
              return {
                pathname: window.location.pathname,
                h1: [...document.querySelectorAll("h1")]
                  .filter(visible)
                  .map(element => element.textContent?.trim() ?? ""),
                nativePreview: nativePreview && visible(nativePreview)
                  ? nativePreview.textContent?.trim() ?? ""
                  : null,
                pendingLines,
                activeBusy: [...document.querySelectorAll('[aria-busy="true"]')]
                  .filter(visible)
                  .map(element => element.textContent?.trim() ?? ""),
                statuses: [...document.querySelectorAll('[role="status"]')]
                  .filter(visible)
                  .map(element => element.textContent?.trim() ?? ""),
                alerts: [...document.querySelectorAll('[role="alert"]')]
                  .filter(visible)
                  .map(element => element.textContent?.trim() ?? ""),
                deliveryLoading: [...document.querySelectorAll(
                  '[data-testid="delivery-loading"], .delivery-loading, .export-delivery-loading'
                )]
                  .filter(visible)
                  .map(element => element.textContent?.trim() ?? ""),
              };
            }"""
        )
        raise RuntimeError(
            "exact delivered solver-card route did not settle: "
            f"expected={expected_path!r}, diagnostics={diagnostics!r}"
        ) from error


def _assert_shared_workspace_geometry(page: Page, width: int, path_name: str) -> None:
    shell_box = _bounding_box_edges(page.locator(".application-workspace").bounding_box())
    if shell_box is None or shell_box["width"] < width * 0.97:
        raise RuntimeError(
            f"application shell does not span the viewport for {path_name}: {shell_box}"
        )

    if width < 1920:
        return

    workspaces = page.evaluate(
        """selectors => selectors.flatMap(selector =>
            [...document.querySelectorAll(selector)]
              .filter(element => element.getClientRects().length > 0)
              .map(element => {
                const box = element.getBoundingClientRect();
                return { selector, width: box.width, left: box.left, right: box.right };
              })
        )""",
        [
            ".materials-page",
            ".materials-workspace",
            ".card-preview-shell",
            ".modeling-workspace-shell",
            ".export-workspace",
            ".activity-shell",
            ".administration-workspace",
            ".administration-record-workbench",
            ".governed-import-route",
        ],
    )
    narrow = [workspace for workspace in workspaces if workspace["width"] < width * 0.8]
    if narrow:
        raise RuntimeError(
            f"wide workspace collapsed into a fixed-width island for {path_name}: {narrow}"
        )


def _assert_semantic_three_pane_geometry(
    page: Page,
    *,
    group_selector: str,
    form_selector: str,
    path_name: str,
) -> None:
    geometry = page.evaluate(
        """selectors => {
            const container = document.querySelector('.administration-content');
            const group = document.querySelector(selectors.group);
            const form = document.querySelector(selectors.form);
            const navigator = group?.children.item(0);
            const primary = group?.children.item(1);
            if (!container || !group || !form || !navigator || !primary) return null;
            const root = getComputedStyle(document.documentElement);
            const token = name => Number.parseFloat(root.getPropertyValue(name));
            const containerBox = container.getBoundingClientRect();
            const groupBox = group.getBoundingClientRect();
            const formBox = form.getBoundingClientRect();
            const navigatorBox = navigator.getBoundingClientRect();
            const primaryBox = primary.getBoundingClientRect();
            return {
              viewportWidth: innerWidth,
              container: {
                left: containerBox.left,
                right: containerBox.right,
                width: containerBox.width,
              },
              group: {
                left: groupBox.left,
                right: groupBox.right,
                width: groupBox.width,
              },
              form: {
                left: formBox.left,
                right: formBox.right,
                width: formBox.width,
              },
              navigator: {
                left: navigatorBox.left,
                right: navigatorBox.right,
                width: navigatorBox.width,
              },
              primary: {
                left: primaryBox.left,
                right: primaryBox.right,
                width: primaryBox.width,
              },
              navigatorMinimum: token('--ux-navigator-min-inline-size'),
              navigatorMaximum: token('--ux-navigator-max-inline-size'),
              readableFormMaximum: token('--ux-readable-form-max-inline-size'),
            };
        }""",
        {"group": group_selector, "form": form_selector},
    )
    if geometry is None:
        raise RuntimeError(f"semantic Administration three-pane workgroup is missing for {path_name}")

    group = geometry["group"]
    container = geometry["container"]
    form = geometry["form"]
    if geometry["viewportWidth"] >= 2560 and group["width"] <= 1920:
        raise RuntimeError(
            f"Administration retained a 1920px-or-narrower work island for {path_name}: {geometry}"
        )
    left_margin = group["left"] - container["left"]
    right_margin = container["right"] - group["right"]
    if abs(left_margin - right_margin) > 2:
        raise RuntimeError(
            f"Administration semantic workgroup is not horizontally balanced for {path_name}: {geometry}"
        )
    if group["width"] < container["width"] * 0.9:
        raise RuntimeError(
            f"Administration semantic workgroup did not use the available content width for {path_name}: {geometry}"
        )
    if geometry["navigator"]["width"] < geometry["navigatorMinimum"] - 1:
        raise RuntimeError(
            f"Administration navigator fell below its shared minimum for {path_name}: {geometry}"
        )
    if geometry["navigator"]["width"] > geometry["navigatorMaximum"] + 1:
        raise RuntimeError(
            f"Administration navigator exceeded its shared maximum for {path_name}: {geometry}"
        )
    if geometry["primary"]["width"] < 288:
        raise RuntimeError(
            f"Administration primary list did not receive a useful elastic allocation for {path_name}: {geometry}"
        )
    if form["width"] > geometry["readableFormMaximum"] + 1:
        raise RuntimeError(
            f"Administration property form exceeded readable width for {path_name}: {geometry}"
        )
    if form["left"] < group["left"] - 1 or form["right"] > group["right"] + 1:
        raise RuntimeError(
            f"Administration property form escaped its semantic workgroup for {path_name}: {geometry}"
        )


def _assert_administration_record_editor_geometry(
    page: Page,
    *,
    group_selector: str,
    form_selector: str,
    path_name: str,
) -> None:
    geometry = page.evaluate(
        """selectors => {
            const container = document.querySelector('.administration-content');
            const group = document.querySelector(selectors.group);
            const form = document.querySelector(selectors.form);
            const facets = group?.querySelector('.catalog-facets');
            const list = group?.querySelector('.catalog-record-list');
            const datasheet = group?.querySelector('.catalog-datasheet');
            if (!container || !group || !form || !facets || !list || !datasheet) return null;
            const root = getComputedStyle(document.documentElement);
            const token = name => Number.parseFloat(root.getPropertyValue(name));
            const box = element => {
              const rect = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {
                left: rect.left,
                right: rect.right,
                top: rect.top,
                bottom: rect.bottom,
                width: rect.width,
                height: rect.height,
                visible: element.getClientRects().length > 0 && style.display !== 'none',
              };
            };
            const containerBox = container.getBoundingClientRect();
            const groupBox = group.getBoundingClientRect();
            const formBox = form.getBoundingClientRect();
            const facetsBox = box(facets);
            const listBox = box(list);
            const datasheetBox = box(datasheet);
            return {
              viewportWidth: innerWidth,
              container: {
                left: containerBox.left,
                right: containerBox.right,
                width: containerBox.width,
              },
              group: {
                left: groupBox.left,
                right: groupBox.right,
                top: groupBox.top,
                bottom: groupBox.bottom,
                width: groupBox.width,
              },
              form: {
                left: formBox.left,
                right: formBox.right,
                width: formBox.width,
              },
              facets: facetsBox,
              list: listBox,
              datasheet: datasheetBox,
              leftAllocation: Math.max(facetsBox.right, listBox.right) -
                Math.min(facetsBox.left, listBox.left),
              readableFormMaximum: token('--ux-readable-form-max-inline-size'),
            };
        }""",
        {"group": group_selector, "form": form_selector},
    )
    if geometry is None:
        raise RuntimeError(f"Administration record editor geometry is missing for {path_name}")

    group = geometry["group"]
    container = geometry["container"]
    form = geometry["form"]
    left_margin = group["left"] - container["left"]
    right_margin = container["right"] - group["right"]
    if abs(left_margin - right_margin) > 2:
        raise RuntimeError(
            f"Administration record editor is not horizontally balanced for {path_name}: {geometry}"
        )
    if group["width"] < container["width"] * 0.9:
        raise RuntimeError(
            f"Administration record editor did not use the available content width for {path_name}: {geometry}"
        )
    if form["width"] > geometry["readableFormMaximum"] + 1:
        raise RuntimeError(
            f"Administration record editor form exceeded readable width for {path_name}: {geometry}"
        )
    if form["left"] < group["left"] - 1 or form["right"] > group["right"] + 1:
        raise RuntimeError(
            f"Administration record editor form escaped its workgroup for {path_name}: {geometry}"
        )
    facets = geometry["facets"]
    record_list = geometry["list"]
    datasheet = geometry["datasheet"]
    if not record_list["visible"] or not datasheet["visible"]:
        raise RuntimeError(
            f"Administration record editor list or datasheet is not visible for {path_name}: {geometry}"
        )
    if geometry["viewportWidth"] < 1600:
        if facets["visible"]:
            raise RuntimeError(
                f"Administration record editor facets should be hidden below 1600px for {path_name}: {geometry}"
            )
        if (
            record_list["top"] >= datasheet["top"]
            or record_list["bottom"] > datasheet["top"] + 1
            or abs(record_list["left"] - datasheet["left"]) > 1
            or abs(record_list["right"] - datasheet["right"]) > 1
        ):
            raise RuntimeError(
                f"Administration record editor list and datasheet are not vertical and non-overlapping below 1600px for {path_name}: {geometry}"
            )
    elif geometry["viewportWidth"] >= 1600:
        if not facets["visible"]:
            raise RuntimeError(
                f"Administration record editor facets should be visible at or above 1600px for {path_name}: {geometry}"
            )
        if geometry["leftAllocation"] < 288:
            raise RuntimeError(
                f"Administration record editor left allocation is too narrow at or above 1600px for {path_name}: {geometry}"
            )
        if (
            datasheet["left"] < facets["right"] - 1
            or datasheet["left"] < record_list["right"] - 1
            or datasheet["top"] > group["bottom"] + 1
            or datasheet["bottom"] < group["top"] - 1
        ):
            raise RuntimeError(
                f"Administration record editor datasheet is not to the right of the left work area at or above 1600px for {path_name}: {geometry}"
            )
        for left_box, right_box in ((facets, datasheet), (record_list, datasheet)):
            if (
                left_box["left"] < right_box["right"] - 1
                and left_box["right"] > right_box["left"] + 1
                and left_box["top"] < right_box["bottom"] - 1
                and left_box["bottom"] > right_box["top"] + 1
            ):
                raise RuntimeError(
                    f"Administration record editor panes overlap at or above 1600px for {path_name}: {geometry}"
                )


def _capture(
    page: Page,
    path: Path,
    width: int,
    height: int,
    *,
    focus_selector: str | None = None,
    before_screenshot: Callable[[], object] | None = None,
    after_animation: Callable[[], object] | None = None,
) -> None:
    _wait_for_settled(page)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow != 0:
        raise RuntimeError(f"horizontal overflow is {overflow}px for {path.name}")
    page.evaluate(
        """() => {
            if (document.activeElement instanceof HTMLElement) {
              document.activeElement.blur();
            }
            window.getSelection()?.removeAllRanges();
            window.scrollTo(0, 0);
            for (const selector of [
              ".application-workspace",
              ".modeling-task-ribbon",
              ".step-option-panel",
              ".native-card-preview",
              ".card-preview-actions",
              ".export-properties",
              ".export-main",
              ".export-result",
              "#modeling-export-native-preview-viewport",
              ".mapping-scroll",
            ]) {
              document.querySelectorAll(selector).forEach(element => {
                element.scrollTop = 0;
                element.scrollLeft = 0;
              });
            }
        }"""
    )
    if focus_selector is not None:
        page.locator(focus_selector).scroll_into_view_if_needed()
    if before_screenshot is not None:
        before_screenshot()
    page.evaluate(
        """async () => {
            if (document.activeElement instanceof HTMLElement) {
              document.activeElement.blur();
            }
            window.getSelection()?.removeAllRanges();
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
        }"""
    )
    if after_animation is not None:
        after_animation()
    _assert_shared_workspace_geometry(page, width, path.name)
    page.mouse.move(1, 1)
    page.screenshot(path=str(path), full_page=False)
    viewport = page.viewport_size
    if viewport != {"width": width, "height": height}:
        raise RuntimeError(f"viewport drift for {path.name}: {viewport}")


def _assert_export_action_visible(page: Page, label: str) -> None:
    """Keep the one Export primary action in the first viewport capture."""
    action = page.get_by_role("button", name=label, exact=True)
    if action.count() != 1 or not action.is_visible():
        raise RuntimeError(f"Export capture must expose one visible {label!r} action")
    box = _bounding_box_edges(action.bounding_box())
    viewport = page.viewport_size
    if box is None or viewport is None or box["top"] < 0 or box["bottom"] > viewport["height"]:
        raise RuntimeError(f"Export {label!r} action is clipped outside the first viewport: {box}")
    if page.evaluate("() => window.scrollY") != 0:
        raise RuntimeError("Export capture must keep application/page scroll at the top")
    advanced = page.locator("details.export-advanced-input")
    if advanced.count() and advanced.get_attribute("open") is not None:
        raise RuntimeError("Export capture must keep native card options Advanced disclosure closed")


def _assert_export_exact_source_surface(
    page: Page,
    *,
    verify_neutral_download: bool = False,
    require_review_action: bool = False,
) -> None:
    """Assert the exact selected model/Neutral controls and optional review action."""
    selected_model = page.get_by_text("Selected model", exact=True)
    if selected_model.count() != 1 or not selected_model.is_visible():
        raise RuntimeError("Export must expose one visible Selected model section")
    model_value = page.locator(".export-properties .export-property-row").filter(
        has_text="Model"
    )
    model_value.wait_for(state="visible", timeout=30_000)
    if model_value.inner_text().strip().endswith("Exact Fit selection unavailable"):
        raise RuntimeError("Export must retain the exact saved Fit model selection")
    neutral_download = page.get_by_role(
        "button", name="Download selected model", exact=True
    )
    neutral_download.wait_for(state="visible", timeout=30_000)
    if neutral_download.count() != 1:
        raise RuntimeError("Export must expose one exact selected Neutral download action")
    exact_source = page.locator("details.export-advanced").filter(
        has_text="Technical details"
    )
    exact_source.wait_for(state="visible", timeout=30_000)
    summary = exact_source.locator(":scope > summary")
    if exact_source.get_attribute("open") is None:
        summary.click()
    exact_source.get_by_text("Material Model IR", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    exact_source.get_by_text("Neutral revision", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    neutral_revision = exact_source.locator("dt").filter(has_text="Neutral revision").locator(
        "xpath=following-sibling::dd[1]"
    )
    if not neutral_revision.inner_text().strip() or "unavailable" in neutral_revision.inner_text():
        raise RuntimeError("Export exact source evidence is missing the selected Neutral revision")
    if exact_source.get_attribute("open") is not None:
        summary.click()
    if verify_neutral_download:
        with page.expect_response(
            lambda response: "/neutral-materials/" in response.url
            and "/revisions/" in response.url
            and response.url.endswith("/download")
        ) as response_info:
            neutral_download.click()
        response = response_info.value
        if not response.ok:
            raise RuntimeError(
                f"exact selected Neutral download failed with HTTP {response.status}"
            )
    if require_review_action:
        review_status = page.get_by_text(
            re.compile(r"^(Request review|Waiting for review|Approved|Changes requested)$")
        ).filter(visible=True)
        review_status.nth(0).wait_for(state="visible", timeout=30_000)
        request_review = page.get_by_role("button", name="Request review", exact=True)
        if request_review.count() == 1:
            request_review.click()
            reason = page.get_by_role("textbox", name="Review request reason", exact=True)
            reason.wait_for(state="visible", timeout=30_000)
            reason.fill(
                "Review this exact solver-card revision, selected model, Neutral identity, and delivery mapping before release."
            )
            page.get_by_role("button", name="Send request", exact=True).click()
            page.get_by_text("Waiting for review", exact=True).wait_for(
                state="visible", timeout=30_000
            )


def _assert_export_capture_shell(page: Page) -> None:
    """Reject a displaced Export capture while leaving local content scrollports alone."""
    metrics = page.evaluate(
        """() => {
          const workspace = document.querySelector('.application-workspace');
          const workbench = document.querySelector('main.processing-workbench-page.stage-export');
          const exportRegion = document.querySelector('section.modeling-target-preview.export-workspace');
          const nativeViewport = document.querySelector('#modeling-export-native-preview-viewport');
          const mappingViewport = document.querySelector('#modeling-export-mapping-viewport');
          const appShell = workspace?.closest('.application-shell');
          const appBar = appShell?.querySelector(':scope > .application-menu-bar');
          const context = workbench?.querySelector(':scope > .modeling-context-strip');
          const stage = workbench?.querySelector(':scope > .modeling-stage-shell');
          if (!(workspace instanceof HTMLElement)
            || !(workbench instanceof HTMLElement)
            || !(exportRegion instanceof HTMLElement)
            || !(nativeViewport instanceof HTMLElement)
            || !(mappingViewport instanceof HTMLElement)
            || !(appBar instanceof HTMLElement)
            || !(context instanceof HTMLElement)
            || !(stage instanceof HTMLElement)) return null;
          const rect = node => {
            const value = node.getBoundingClientRect();
            return {
              top: value.top,
              right: value.right,
              bottom: value.bottom,
              left: value.left,
              width: value.width,
              height: value.height,
            };
          };
          const appBarRect = rect(appBar);
          const workspaceRect = rect(workspace);
          const contextRect = rect(context);
          const stageRect = rect(stage);
          const exportRect = rect(exportRegion);
          const fullyVisible = value => value.width > 0
            && value.height > 0
            && value.top >= -1
            && value.bottom <= window.innerHeight + 1;
          const scrollOrigins = {
            windowY: window.scrollY,
            documentY: document.documentElement.scrollTop,
            bodyY: document.body.scrollTop,
            workspace: workspace.scrollTop,
            workbench: workbench.scrollTop,
            exportRegion: exportRegion.scrollTop,
          };
          const exportLocalScrollOrigins = {
            nativeTop: nativeViewport.scrollTop,
            nativeLeft: nativeViewport.scrollLeft,
            mappingTop: mappingViewport.scrollTop,
            mappingLeft: mappingViewport.scrollLeft,
          };
          const outerScrollZero = Object.values(scrollOrigins).every(value => value === 0);
          const exportLocalScrollZero = Object.values(exportLocalScrollOrigins).every(value => value === 0);
          const shellVisible = [appBarRect, contextRect, stageRect, exportRect].every(fullyVisible);
          const shellStacked = appBarRect.bottom <= workspaceRect.top + 1
            && contextRect.top >= workspaceRect.top - 1
            && contextRect.bottom <= stageRect.top + 1
            && stageRect.bottom <= exportRect.top + 1
            && exportRect.top >= workspaceRect.top - 1
            && exportRect.left >= workspaceRect.left - 1
            && exportRect.right <= workspaceRect.right + 1
            && exportRect.bottom <= workspaceRect.bottom + 1;
          return {
            scrollOrigins,
            exportLocalScrollOrigins,
            outerScrollZero,
            exportLocalScrollZero,
            shellVisible,
            shellStacked,
            appBarRect,
            workspaceRect,
            contextRect,
            stageRect,
            exportRect,
          };
        }"""
    )
    if not metrics:
        raise RuntimeError("Export capture is missing the application shell or Export region")
    if not metrics["outerScrollZero"]:
        raise RuntimeError(f"Export capture has nonzero outer scroll origin: {metrics}")
    if not metrics["exportLocalScrollZero"]:
        raise RuntimeError(f"Export capture has nonzero native or Mapping local scroll origin: {metrics}")
    if not metrics["shellVisible"] or not metrics["shellStacked"]:
        raise RuntimeError(f"Export capture shell or header/ribbon is displaced or clipped: {metrics}")


def _assert_export_recovery_capture(page: Page) -> None:
    """Keep the source recovery visible while prerequisite evidence stays collapsed."""
    metrics = page.evaluate(
        """() => {
          const pane = document.querySelector('.modeling-export-blocked .export-properties');
          const evidence = document.querySelector('.modeling-export-blocked details.export-prerequisite-evidence');
          const recovery = document.querySelector('.modeling-export-recovery');
          if (!(pane instanceof HTMLElement) || !(evidence instanceof HTMLDetailsElement) || !(recovery instanceof HTMLElement)) return null;
          const paneRect = pane.getBoundingClientRect();
          const recoveryRect = recovery.getBoundingClientRect();
          // The recovery is the normal-surface consequence. Align it only
          // when its visible controls would otherwise be clipped by the
          // local setup scrollport; never open or scroll hidden evidence.
          if (recoveryRect.top < paneRect.top + 4 || recoveryRect.bottom > paneRect.bottom - 4) {
            const maxScroll = Math.max(0, pane.scrollHeight - pane.clientHeight);
            const target = recoveryRect.top - paneRect.top + pane.scrollTop - 4;
            pane.scrollTop = Math.min(maxScroll, Math.max(0, target));
          }
          const nextPaneRect = pane.getBoundingClientRect();
          const within = node => {
            if (!(node instanceof HTMLElement)) return false;
            const rect = node.getBoundingClientRect();
            return rect.top >= nextPaneRect.top + 4 && rect.bottom <= nextPaneRect.bottom - 4;
          };
          const visibleRecoveryNodes = [
            recovery,
            recovery.querySelector('h3'),
            recovery.querySelector('label:first-of-type'),
            recovery.querySelector('input[aria-label="Reason for preparing model"]'),
            recovery.querySelector('button.primary'),
          ];
          const visibleRecoveryClipped = visibleRecoveryNodes.some(node => {
            if (!(node instanceof HTMLElement)) return true;
            const rect = node.getBoundingClientRect();
            return rect.top < nextPaneRect.top + 2 || rect.bottom > nextPaneRect.bottom - 2;
          });
          return {
            pageScrollY: window.scrollY,
            paneScrollTop: pane.scrollTop,
            paneClientHeight: pane.clientHeight,
            paneScrollHeight: pane.scrollHeight,
            localOverflow: pane.scrollHeight > pane.clientHeight,
            evidenceClosed: evidence.getAttribute('open') === null && !evidence.open,
            recovery: within(recovery),
            recoveryHeading: within(recovery.querySelector('h3')),
            acknowledgement: within(recovery.querySelector('label:first-of-type')),
            reason: within(recovery.querySelector('input[aria-label="Reason for preparing model"]')),
            prepare: within(recovery.querySelector('button.primary')),
            visibleRecoveryClipped,
          };
        }"""
    )
    if not metrics:
        raise RuntimeError("source-blocked Export capture is missing its local recovery pane")
    if metrics["pageScrollY"] != 0:
        raise RuntimeError("source-blocked Export capture must keep application/page scroll at the top")
    if not metrics["evidenceClosed"]:
        raise RuntimeError(f"source-blocked Export capture must keep prerequisite evidence collapsed: {metrics}")
    if not metrics["recovery"] or not metrics["recoveryHeading"] or not metrics["acknowledgement"] or not metrics["reason"] or not metrics["prepare"]:
        raise RuntimeError(f"source-blocked Export recovery is clipped: {metrics}")
    if metrics["visibleRecoveryClipped"]:
        raise RuntimeError(f"source-blocked Export capture leaves a clipped recovery control: {metrics}")


def _open_materials_search(page: Page, base_url: str) -> None:
    # The current Materials workspace opens in the Browse navigator by
    # default.  Search controls are intentionally available in Filters mode;
    # enter that explicit mode instead of relying on stale route state from a
    # prior capture or session.
    page.goto(f"{base_url}/materials?mode=filters")
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill("DP780")
    page.locator(".materials-search-form").get_by_role("button", name="Find", exact=True).click()
    rows = page.locator('table[aria-label="Material results"] tbody tr')
    rows.filter(has_text="DP780").first.wait_for(timeout=30_000)
    _wait_for_settled(page)
    if rows.count() < 1:
        raise RuntimeError("the deterministic DP780 Material result is missing")
    if page.get_by_text("Checking…", exact=True).count():
        raise RuntimeError("Material enrichment is incomplete")
    # A result row is an exact-revision navigation target in the current
    # workspace, not a separate selection toggle.  The controller selects the
    # first authorized row while the query settles; leave the row untouched so
    # this helper remains on the search surface for viewport captures.
    page.get_by_text("Material selected", exact=True).wait_for(timeout=30_000)
    page.locator(".application-status-bar").get_by_text(REVISION_LABEL_PATTERN).wait_for(
        timeout=30_000
    )
    if page.get_by_role("columnheader", name="Status", exact=True).count():
        raise RuntimeError("normal Materials results must not expose a Status column")
    for selector in (".materials-results", ".application-status-bar"):
        surface = page.locator(selector)
        surface.wait_for(timeout=30_000)
        surface_text = surface.inner_text()
        if NORMAL_SURFACE_TECHNICAL_LABELS.search(surface_text):
            raise RuntimeError(
                f"normal Materials surface exposes technical label in {selector}: {surface_text}"
            )


def _assert_material_pane_reset(page: Page, width: int) -> None:
    expected_navigator = _css_token_px(page, "--ux-navigator-default-inline-size")
    navigator = page.locator(".navigator-panel")
    navigator_separator = page.get_by_role(
        "separator", name=re.compile(r"^Resize (?:navigator|filters)(?: materials)?$")
    )
    before = navigator.bounding_box()
    separator = navigator_separator.bounding_box()
    if before is None or separator is None:
        raise RuntimeError("Materials navigator divider is unavailable for reset verification")
    page.mouse.move(separator["x"] + 2, separator["y"] + 80)
    page.mouse.down()
    page.mouse.move(separator["x"] + 42, separator["y"] + 80)
    page.mouse.up()
    page.wait_for_timeout(100)
    dragged = navigator.bounding_box()
    if dragged is None or abs(dragged["width"] - before["width"]) < 10:
        raise RuntimeError("Materials navigator divider did not resize before reset verification")
    navigator_separator.dblclick()
    page.wait_for_timeout(100)
    reset = navigator.bounding_box()
    if reset is None or abs(reset["width"] - expected_navigator) > 4:
        raise RuntimeError(
            f"Materials navigator reset drift at {width}px: expected {expected_navigator}px, "
            f"got {reset and reset['width']}px"
        )

    if width <= 1390:
        return
    expected_context = _css_token_px(page, "--ux-context-default-inline-size")
    context = page.locator(".context-panel")
    # Source-v2 Materials is a two-pane explorer/results workspace.  The
    # optional detail context pane is not rendered on the search surface; do
    # not require a legacy third-pane divider that has no consumer here.
    if context.count() == 0:
        return
    context_separator = page.get_by_role("separator", name="Resize details")
    context_before = context.bounding_box()
    context_divider = context_separator.bounding_box()
    if context_before is None or context_divider is None:
        raise RuntimeError("Materials context divider is unavailable for reset verification")
    page.mouse.move(context_divider["x"] + 2, context_divider["y"] + 80)
    page.mouse.down()
    page.mouse.move(context_divider["x"] - 42, context_divider["y"] + 80)
    page.mouse.up()
    page.wait_for_timeout(100)
    context_dragged = context.bounding_box()
    if context_dragged is None or abs(context_dragged["width"] - context_before["width"]) < 10:
        raise RuntimeError("Materials context divider did not resize before reset verification")
    context_separator.dblclick()
    page.wait_for_timeout(100)
    context_reset = context.bounding_box()
    if context_reset is None or abs(context_reset["width"] - expected_context) > 4:
        raise RuntimeError(
            f"Materials context reset drift at {width}px: expected {expected_context}px, "
            f"got {context_reset and context_reset['width']}px"
        )


def _assert_response_points_table(page: Page, width: int) -> None:
    table = page.get_by_role("table", name="Representative response points")
    # The source-v2 Technical Data detail can truthfully omit response-point
    # attributes while linked Test Data remains available below.  In that
    # layout there is no response table or rail to validate.
    if table.count() == 0:
        return
    if width < 1800:
        if table.is_visible():
            raise RuntimeError(f"response points table leaked into compact {width}px layout")
        return
    region = page.get_by_role("region", name="Scrollable representative response points")
    region.wait_for(timeout=30_000)
    table.wait_for(timeout=30_000)
    geometry = region.evaluate(
        """region => {
          const shell = region.parentElement;
          const header = region.querySelector('thead th');
          const table = region.querySelector('table');
          const rail = shell?.querySelector('.materials-scroll-rail-y');
          const xRail = shell?.querySelector('.materials-scroll-rail-x');
          const rect = element => {
            if (!element) return null;
            const bounds = element.getBoundingClientRect();
            return {
              left: bounds.left,
              right: bounds.right,
              top: bounds.top,
              bottom: bounds.bottom,
            };
          };
          const style = header ? getComputedStyle(header) : null;
          return {
            region: rect(region),
            table: rect(table),
            rail: rect(rail),
            clientHeight: region.clientHeight,
            scrollHeight: region.scrollHeight,
            clientWidth: region.clientWidth,
            scrollWidth: region.scrollWidth,
            scrollTop: region.scrollTop,
            tabIndex: region.tabIndex,
            role: region.getAttribute('role'),
            headerPosition: style?.position ?? null,
            headerBackground: style?.backgroundColor ?? null,
            scrollY: shell?.getAttribute('data-scroll-y') ?? null,
            scrollX: shell?.getAttribute('data-scroll-x') ?? null,
            hasHorizontalRail: Boolean(xRail),
          };
        }"""
    )
    if geometry["role"] != "region" or geometry["tabIndex"] != 0:
        raise RuntimeError("response points region is not keyboard-focusable")
    if geometry["headerPosition"] != "sticky" or geometry["headerBackground"] in (
        None,
        "rgba(0, 0, 0, 0)",
    ):
        raise RuntimeError("response points header is not visibly sticky")
    if geometry["scrollY"] != "true" or geometry["scrollHeight"] <= geometry["clientHeight"]:
        raise RuntimeError("response points vertical overflow rail is missing")
    if (
        geometry["scrollX"] != "false"
        or geometry["hasHorizontalRail"]
        or geometry["scrollWidth"] > geometry["clientWidth"] + 1
    ):
        raise RuntimeError("response points exposes an unexpected horizontal rail")
    if (
        not geometry["rail"]
        or not geometry["table"]
        or geometry["table"]["right"] > geometry["region"]["right"] + 1
    ):
        raise RuntimeError("response points table and visible rail overlap or are unavailable")
    region.evaluate("element => { element.scrollTop = 0; element.scrollLeft = 0; }")
    if region.evaluate("element => element.scrollTop") != 0:
        raise RuntimeError("response points capture did not restore scroll position")


_SCROLL_TABLE_ID = "materials-reference-table"


def _scroll_metadata(entity_id: str, revision_no: int = 1) -> dict[str, object]:
    return {
        "id": f"{entity_id}-revision",
        "aggregate_id": entity_id,
        "revision_no": revision_no,
        "based_on_revision_id": None,
        "schema_id": "urn:cmp:materials-reference:1",
        "schema_version": "1.0.0",
        "content_hash": "a" * 64,
        "created_at": "2026-08-03T00:00:00Z",
        "created_by": "00000000-0000-0000-0000-000000000001",
        "change_reason": "materials reference archive",
        "organization_id": "00000000-0000-0000-0000-000000000002",
        "project_id": "00000000-0000-0000-0000-000000000003",
        "classification": "internal",
        "lifecycle_state": "published",
    }


def _scroll_table() -> dict[str, object]:
    return {
        "table_id": _SCROLL_TABLE_ID,
        "current_revision": {
            **_scroll_metadata(f"{_SCROLL_TABLE_ID}-current"),
            "content": {
                "key": "demo_material_records",
                "name": "Materials Reference Table",
                "description": "Materials reference table",
            },
        },
    }


def _scroll_folder(folder_id: str, name: str, parent_folder_id: str | None) -> dict[str, object]:
    return {
        "folder_id": folder_id,
        "table_id": _SCROLL_TABLE_ID,
        "current_revision": _scroll_metadata(folder_id),
        "content": {
            "table_revision_id": f"{_SCROLL_TABLE_ID}-current-revision",
            "name": name,
            "description": None,
            "parent_folder_id": parent_folder_id,
            "parent_folder_revision_id": (
                f"{parent_folder_id}-revision" if parent_folder_id else None
            ),
        },
    }


def _scroll_record(
    record_id: str,
    row: int,
    name: str | None = None,
) -> dict[str, object]:
    names = (
        "DP780 dual-phase steel",
        "DP600 dual-phase steel",
        "HSLA structural steel",
        "AISI 304 stainless steel",
        "PA66 glass-filled polymer",
    )
    material_name = name or f"{names[row % len(names)]} · reference {row:03}"
    material_class = "polymer" if "PA66" in material_name else "metal"
    return {
        "record_id": record_id,
        "table_id": _SCROLL_TABLE_ID,
        "domain_binding": {
            "binding_id": f"{record_id}-binding",
            "record_id": record_id,
            "record_revision_id": f"{record_id}-revision",
            "kind": "material",
            "object_id": f"{record_id}-material",
            "revision_id": f"{record_id}-material-revision",
            "workbench_path": f"/materials/{record_id}-material",
        },
        "current_revision": {
            **_scroll_metadata(f"{record_id}-revision"),
            "content": {
                "table_revision_id": f"{_SCROLL_TABLE_ID}-current-revision",
                "name": material_name,
                "external_key": f"MAT-{row + 1:03}",
                "description": "Materials reference record with governed response data",
                "folder_id": None,
                "folder_revision_id": None,
                "values": [
                    {
                        "data_type": "discrete",
                        "attribute_definition_id": "material-class",
                        "attribute_definition_revision_id": "material-class-r1",
                        "value": material_class,
                    },
                    {
                        "data_type": "text",
                        "attribute_definition_id": "provider",
                        "attribute_definition_revision_id": "provider-r1",
                        "value": "Northstar Materials",
                    },
                    {
                        "data_type": "text",
                        "attribute_definition_id": "evidence-source",
                        "attribute_definition_revision_id": "evidence-source-r1",
                        "value": "Governed reference",
                    },
                ],
            },
        },
    }


def _install_material_scroll_fixture(page: Page) -> None:
    folder_names = (
        "Cold-rolled steel reference archive for stamped body panels",
        "Automotive body sheet grades",
        "Structural plate and section data",
        "Heat-treated alloy specifications",
        "Stainless and corrosion-resistant grades",
        "Polymer compound reference data",
        "Supplier certificate imports",
        "Qualification and acceptance records",
        "Legacy design allowables",
        "Temperature-conditioned studies",
        "Welded joint material records",
        "Surface-treated coil references",
    )
    root_folders = [
        _scroll_folder(
            f"folder-{index}",
            f"{folder_names[index % len(folder_names)]} · {index + 1:03}",
            None,
        )
        for index in range(90)
    ]
    short_names = (
        "DP780 dual-phase steel",
        "DP600 dual-phase steel",
        "HSLA structural steel",
        "AISI 304 stainless steel",
        "IF mild steel",
        "TRIP advanced high-strength steel",
    )

    def fulfill(route: Route, value: object) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(value),
        )

    def handle(route: Route) -> None:
        request = route.request
        parsed = urlsplit(request.url)
        request_path = parsed.path
        if request_path.endswith("/catalog/explorer/tables"):
            fulfill(route, {"items": [_scroll_table()]})
            return
        if request_path.endswith(f"/catalog/explorer/tables/{_SCROLL_TABLE_ID}/children"):
            parent = parse_qs(parsed.query).get("parent_folder_id", [None])[0]
            folders = [] if parent else root_folders
            fulfill(route, {"table": _scroll_table(), "folders": folders, "records": []})
            return
        if request_path.endswith(f"/catalog/tables/{_SCROLL_TABLE_ID}/subsets"):
            fulfill(route, {"items": []})
            return
        if request_path.endswith(f"/catalog/tables/{_SCROLL_TABLE_ID}/attributes"):
            fulfill(
                route,
                {
                    "items": [
                        {
                            "attribute_definition_id": "material-class",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "material_class"}},
                        },
                        {
                            "attribute_definition_id": "provider",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "provider"}},
                        },
                        {
                            "attribute_definition_id": "evidence-source",
                            "table_id": _SCROLL_TABLE_ID,
                            "current_revision": {"content": {"key": "evidence_source"}},
                        },
                    ]
                },
            )
            return
        if request_path.endswith("/catalog/records:search"):
            payload = request.post_data_json or {}
            text = payload.get("text") if isinstance(payload, dict) else None
            count = 0 if text == "magnesium" else 6 if text == "steel" else 50
            total_count = 0 if count == 0 else 6 if count == 6 else 120
            facets = (
                []
                if count == 0
                else [
                    {
                        "attribute_definition_id": attribute_id,
                        "value": value,
                        "count": total_count,
                    }
                    for attribute_id, value in (
                        ("material-class", "metal"),
                        ("provider", "Northstar Materials"),
                        ("evidence-source", "Governed reference"),
                    )
                ]
            )
            fulfill(
                route,
                {
                    "items": [
                        _scroll_record(
                            f"record-{index}",
                            index,
                            short_names[index] if text == "steel" else None,
                        )
                        for index in range(count)
                    ],
                    "total_count": total_count,
                    "offset": 0,
                    "limit": 50,
                    "facets": facets,
                },
            )
            return
        route.continue_()

    page.route("**/api/v1/**", handle)


def _open_material_scroll_state(page: Page, base_url: str, search_text: str) -> None:
    page.goto(f"{base_url}/materials?mode=filters")
    search = page.get_by_role("textbox", name="Search materials")
    search.wait_for(timeout=30_000)
    search.fill(search_text)
    page.locator(".materials-search-form").get_by_role("button", name="Find", exact=True).click()
    if search_text == "magnesium":
        page.get_by_text("No materials match this search.", exact=True).wait_for(timeout=30_000)
    else:
        page.locator('table[aria-label="Material results"] tbody tr').first.wait_for(timeout=30_000)
    _wait_for_settled(page)


def _capture_material_scroll_states(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _install_material_scroll_fixture(page)
        _open_material_scroll_state(page, base_url, "reference")
        _capture(
            page,
            output / f"materials-search-long-{width}x{height}.png",
            width,
            height,
        )
        page.context.close()

    for search_text, output_name in (
        ("steel", "materials-search-short-1440x900.png"),
        ("magnesium", "materials-search-empty-1440x900.png"),
    ):
        page = _new_page(browser, base_url, 1440, 900)
        _install_material_scroll_fixture(page)
        _open_material_scroll_state(page, base_url, search_text)
        _capture(page, output / output_name, 1440, 900)
        page.context.close()


def _open_material_detail(page: Page, base_url: str) -> None:
    _open_materials_search(page, base_url)
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.dblclick()
    page.wait_for_url(
        re.compile(
            r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
            r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
        ),
        timeout=30_000,
    )
    page.get_by_role("heading", name="Key properties", exact=True).wait_for(timeout=30_000)
    for tab_name in (
        "Overview",
        "Properties",
        "Curves",
        "CAE Cards",
        "Source & history",
    ):
        page.get_by_role("tab", name=tab_name, exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)
    page.get_by_text(
        re.compile(r"^(Request review|Waiting for review|Approved|Changes requested)$")
    ).first.wait_for(timeout=30_000)
    page.locator(".application-status-bar").get_by_text(REVISION_LABEL_PATTERN).wait_for(
        timeout=30_000
    )
    for selector in (
        ".material-detail-header",
        '[aria-label="Related data"]',
        ".application-status-bar",
    ):
        surface = page.locator(selector)
        surface.wait_for(timeout=30_000)
        surface_text = surface.inner_text()
        if NORMAL_SURFACE_TECHNICAL_LABELS.search(surface_text):
            raise RuntimeError(
                "normal Material detail surface exposes technical label in "
                f"{selector}: {surface_text}"
            )


def _open_material_curves(page: Page) -> None:
    page.get_by_role("tab", name="Curves", exact=True).click()
    browser = page.locator(".material-curve-browser")
    if browser.count() == 0:
        # Source-v2 Technical Data records own the linked Test Data records,
        # while their configured Material layout may legitimately contain no
        # curve attributes.  Keep that truthful empty state instead of
        # inventing a curve preview from a related record.
        page.get_by_text(
            "No curve data is included in this Layout.", exact=True
        ).wait_for(timeout=30_000)
        page.get_by_role("table", name="Modeling inputs", exact=True).wait_for(
            timeout=30_000
        )
        _wait_for_settled(page)
        return
    browser.wait_for(timeout=30_000)
    curve_buttons = browser.locator(".material-curve-list button")
    if curve_buttons.count() < 2:
        raise RuntimeError("Materials Curves must expose observed and statistical curves")
    observed = curve_buttons.filter(has_text="Observed tensile curve").first
    observed.click()
    page.get_by_text("Exact Test Data · Fit input", exact=True).wait_for(timeout=30_000)
    chart = page.locator(".contract-curve-svg")
    chart.wait_for(timeout=30_000)
    page.get_by_role("button", name="Open in Modeling", exact=True).wait_for(timeout=30_000)
    page.get_by_text("No deviation recorded", exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)
    page.locator(".contract-curve-frame").scroll_into_view_if_needed()


def _material_graph_fixture(route: Route, state: str) -> None:
    """Apply one explicit, browser-local graph fixture for Materials state evidence."""
    if route.request.method != "GET":
        route.continue_()
        return
    response = route.fetch()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("links"), list):
        route.fulfill(response=response)
        return
    if state == "empty":
        # Keep the exact selected root and its material binding, while proving
        # the honest no-linked-record surface without a first/latest fallback.
        payload["links"] = []
        payload["nodes"] = [payload["root"]]
    elif state == "related-long":
        links = payload["links"]
        if not links:
            raise RuntimeError("related-long fixture requires one exact source link")
        fixture_links = []
        for index in range(12):
            link = deepcopy(links[index % len(links)])
            link_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"cmp-material-detail-related-long:{index}:{link['record_link_id']}",
                )
            )
            endpoint = link["target"]
            endpoint_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{link_id}:record")
            )
            endpoint_revision_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{link_id}:revision")
            )
            endpoint["record_id"] = endpoint_id
            endpoint["record_revision_id"] = endpoint_revision_id
            endpoint["name"] = f"DP780 related tensile {index + 1:02d}"
            endpoint["external_key"] = f"CMP-371-RELATED-{index + 1:02d}"
            link["record_link_id"] = link_id
            link["current_revision"]["aggregate_id"] = link_id
            link["current_revision"]["id"] = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{link_id}:link-revision")
            )
            content = link["current_revision"].get("content")
            if isinstance(content, dict):
                content["target_record_id"] = endpoint_id
                content["target_record_revision_id"] = endpoint_revision_id
            fixture_links.append(link)
        payload["links"] = [*links, *fixture_links]
    else:
        raise RuntimeError(f"unsupported Material graph fixture state: {state}")
    route.fulfill(response=response, json=payload)


def _material_graph_route_handler(state: str) -> Callable[[Route], None]:
    def handle(route: Route) -> None:
        _material_graph_fixture(route, state)

    return handle


def _capture_material_detail_exceptions(
    browser: Browser, base_url: str, output: Path
) -> None:
    """Capture the approved empty and related-long Materials detail states."""
    for state, filename in (
        ("related-long", "material-detail-related-long-1440x900.png"),
        ("empty", "material-detail-empty-1440x900.png"),
    ):
        page = _new_page(browser, base_url, 1440, 900)
        page.route(
            "**/api/v1/catalog/workflow-explorer/**",
            _material_graph_route_handler(state),
        )
        _open_material_detail(page, base_url)
        page.get_by_role("tab", name="Overview", exact=True).click()
        if state == "related-long":
            group = page.locator(".related-record-group").filter(has_text="Test Data")
            group.wait_for(timeout=30_000)
            if group.locator(".related-record-list li").count() != 12:
                raise RuntimeError(
                    "related-long detail fixture did not expose twelve exact related records"
                )
        else:
            page.get_by_text("No directly linked data.", exact=True).first.wait_for(
                timeout=30_000
            )
            page.get_by_text(
                "No released reference card is available yet.", exact=True
            ).wait_for(timeout=30_000)
            if page.locator(".solver-availability-list").count():
                raise RuntimeError("empty detail fixture exposed a solver-card fallback")
        _capture(page, output / filename, 1440, 900)
        page.context.close()


def _solver_card_mapping_fixture(route: Route, state: str) -> None:
    """Return an explicit mapping-report state for card delivery evidence."""
    if route.request.method != "GET":
        route.continue_()
        return
    response = route.fetch()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("report"), dict):
        route.fulfill(response=response)
        return
    report = payload["report"]
    items = report.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("solver-card state fixture requires a mapping report")
    fixture_items = deepcopy(items)
    if state == "approximation-blocked":
        # Preserve the live card's explicit approximation and leave the
        # acknowledgement unchecked so the download remains blocked.
        if not any(
            isinstance(item, dict)
            and item.get("status") in {"approximated", "ignored"}
            for item in fixture_items
        ):
            fixture_items[0]["status"] = "approximated"
    elif state == "unsupported-blocked":
        fixture_items[0]["status"] = "unsupported"
        payload["exportable"] = False
    else:
        raise RuntimeError(f"unsupported solver-card fixture state: {state}")
    report["items"] = fixture_items
    route.fulfill(response=response, json=payload)


def _solver_card_mapping_route_handler(state: str) -> Callable[[Route], None]:
    def handle(route: Route) -> None:
        _solver_card_mapping_fixture(route, state)

    return handle


def _open_solver_card_for_capture(page: Page, base_url: str) -> None:
    _open_materials_search(page, base_url)
    page.locator('table[aria-label="Material results"] tbody tr').filter(
        has_text="DP780"
    ).first.dblclick()
    page.wait_for_url(
        re.compile(
            r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
            r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
        ),
        timeout=30_000,
    )
    page.get_by_role("tab", name="CAE Cards", exact=True).click()
    openradioss = page.locator(".cae-card-table tbody tr").filter(
        has_text="OpenRadioss"
    ).first
    openradioss.get_by_role("button", name=re.compile(r"^Preview(?: card)?$")).click()
    page.wait_for_url(
        re.compile(
            r"/materials/[0-9a-f-]+/cards/[0-9a-f-]+\?record_id=[0-9a-f-]+"
            r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
        ),
        timeout=30_000,
    )
    page.get_by_role("heading", name="Delivery check", exact=True).wait_for(
        timeout=30_000
    )
    page.get_by_label("Native card and linked response").wait_for(timeout=30_000)


def _capture_solver_card_exceptions(
    browser: Browser, base_url: str, output: Path
) -> None:
    """Capture explicit approximation and unsupported card delivery blockers."""
    for state, filename in (
        ("approximation-blocked", "solver-card-approximation-blocked-1440x900.png"),
        ("unsupported-blocked", "solver-card-unsupported-blocked-1440x900.png"),
    ):
        page = _new_page(browser, base_url, 1440, 900)
        page.route(
            "**/api/v1/neutral-solver-cards/*/mapping-report**",
            _solver_card_mapping_route_handler(state),
        )
        _open_solver_card_for_capture(page, base_url)
        if state == "approximation-blocked":
            page.get_by_text(
                "Review the highlighted delivery note, then acknowledge it to enable this download.",
                exact=True,
            ).wait_for(timeout=30_000)
            checkbox = page.get_by_role(
                "checkbox", name="I reviewed the delivery notes before downloading this card."
            )
            checkbox.wait_for(timeout=30_000)
            if page.get_by_role("button", name="Download blocked", exact=True).count():
                raise RuntimeError("approximation state must use the normal download command")
            if not page.get_by_role("button", name="Download .rad", exact=True).is_disabled():
                raise RuntimeError("approximation state must remain blocked before acknowledgement")
        else:
            page.get_by_text(
                "This card cannot be downloaded because some values are not supported by the selected solver.",
                exact=True,
            ).wait_for(timeout=30_000)
            page.get_by_role("button", name="Download blocked", exact=True).wait_for(
                timeout=30_000
            )
        _capture(page, output / filename, 1440, 900)
        page.context.close()


def _capture_solver_card_wide(
    browser: Browser, base_url: str, output: Path
) -> None:
    """Capture exact solver-card previews at the two wide product viewports."""
    for width, height in WIDE_VIEWPORTS:
        page = _new_page(browser, base_url, width, height, persona="user")
        _open_solver_card_for_capture(page, base_url)
        page.get_by_role("button", name="Download .rad", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_label("Native card and linked response").wait_for(timeout=30_000)
        _capture(page, output / f"solver-card-preview-{width}x{height}.png", width, height)
        page.context.close()


def _capture_materials_workspace(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        _assert_material_pane_reset(page, width)
        _capture(page, output / f"materials-search-{width}x{height}.png", width, height)
        page.context.close()

    for width, height in WIDE_VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_materials_search(page, base_url)
        _capture(page, output / f"materials-search-{width}x{height}.png", width, height)
        page.context.close()

    _capture_material_scroll_states(browser, base_url, output)

    width, height = 1440, 900
    page = _new_page(browser, base_url, width, height)
    _open_materials_search(page, base_url)
    page.get_by_role("button", name="Browse", exact=True).click()
    page.get_by_role("complementary", name="Materials navigator").wait_for(timeout=30_000)
    tree_find = page.get_by_role("textbox", name="Find in tree")
    tree_find.wait_for(timeout=30_000)
    # Source-v2 exposes four peer data categories rather than the retired
    # Material Library bucket.  Capture the same browse surface through the
    # canonical Technical Data category.
    tree_find.fill("Technical Data")
    page.get_by_test_id("navigator").get_by_role("button", name="Find", exact=True).click()
    page.locator('.materials-tree-row.kind-category[title="Technical Data"]').wait_for(
        timeout=30_000
    )
    page.locator("#browse-results-title").wait_for(timeout=30_000)
    page.get_by_text("3 data items", exact=True).wait_for(timeout=30_000)
    _capture(page, output / "materials-browse-1440x900.png", width, height)
    page.context.close()


def _capture_materials(browser: Browser, base_url: str, output: Path) -> None:
    _capture_materials_workspace(browser, base_url, output)

    width, height = 1440, 900
    page = _new_page(browser, base_url, width, height)
    _open_material_detail(page, base_url)
    _assert_response_points_table(page, width)
    _capture(page, output / "material-detail-1440x900.png", width, height)
    _open_material_curves(page)
    _capture(page, output / "material-curves-1440x900.png", width, height)
    page.get_by_role("tab", name="CAE Cards", exact=True).click()
    page.get_by_role("heading", name="CAE Cards", exact=True).wait_for(timeout=30_000)
    _wait_for_settled(page)
    primary_delivery_actions = page.locator(
        ".material-detail-header .card-action-row button.ux-button.primary"
    )
    if primary_delivery_actions.count() != 1 or not re.match(
        r"^(Download|Preview card|Create card|Start Modeling|View solver cards)",
        primary_delivery_actions.first.inner_text(),
    ):
        raise RuntimeError("CAE Cards must expose exactly one contextual filled delivery command")
    _capture(page, output / "material-cae-cards-1440x900.png", width, height)
    page.context.close()

    for width, height in ((1366, 768), (1920, 1080)):
        page = _new_page(browser, base_url, width, height)
        _open_material_detail(page, base_url)
        _assert_response_points_table(page, width)
        _capture(page, output / f"material-detail-{width}x{height}.png", width, height)
        _open_material_curves(page)
        _capture(page, output / f"material-curves-{width}x{height}.png", width, height)
        page.context.close()

    for width, height in WIDE_VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        _open_material_detail(page, base_url)
        _assert_response_points_table(page, width)
        _capture(page, output / f"material-detail-{width}x{height}.png", width, height)
        _open_material_curves(page)
        _capture(page, output / f"material-curves-{width}x{height}.png", width, height)
        page.context.close()

    _capture_material_detail_exceptions(browser, base_url, output)
    _capture_solver_card_exceptions(browser, base_url, output)
    _capture_solver_card_wide(browser, base_url, output)


def _assert_linked_response_labels_visible(page: Page) -> None:
    geometry = page.locator(".response-plot").evaluate(
        """svg => {
          const frame = svg.closest('.response-plot-frame')?.getBoundingClientRect();
          const status = document.querySelector('.application-status-bar')?.getBoundingClientRect();
          const rect = element => {
            if (!element) return null;
            const bounds = element.getBoundingClientRect();
            return {
              left: bounds.left,
              right: bounds.right,
              top: bounds.top,
              bottom: bounds.bottom,
            };
          };
          const xTickLabels = [...svg.querySelectorAll('.linked-response-tick-label')]
            .filter(label => {
              const tick = label.parentElement?.querySelector('.linked-response-tick');
              return tick?.getAttribute('y1') !== tick?.getAttribute('y2');
            });
          return {
            frame: frame
              ? { left: frame.left, right: frame.right, top: frame.top, bottom: frame.bottom }
              : null,
            statusTop: status?.top ?? null,
            xTicks: xTickLabels.map(rect),
            xTitle: rect(svg.querySelector('.linked-response-axis-title:not([transform])')),
          };
        }"""
    )
    if not geometry["frame"] or geometry["statusTop"] is None:
        raise RuntimeError("linked response plot frame or status bar is unavailable")
    if not geometry["xTicks"] or not geometry["xTitle"]:
        raise RuntimeError("linked response plot has no rendered x-axis ticks or title")
    frame = geometry["frame"]
    status_top = float(geometry["statusTop"])
    for label in [*geometry["xTicks"], geometry["xTitle"]]:
        if (
            label["left"] < frame["left"] - 1
            or label["right"] > frame["right"] + 1
            or label["top"] < frame["top"] - 1
            or label["bottom"] > frame["bottom"] + 1
            or label["bottom"] > status_top + 1
        ):
            raise RuntimeError(
                "linked response x-axis label is clipped: "
                f"label={label}, frame={frame}, status_top={status_top}"
            )


def _capture_solver_delivery(
    browser: Browser, base_url: str, output: Path, *, persona: str = "user"
) -> None:
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height, persona=persona)
        _open_materials_search(page, base_url)
        page.locator('table[aria-label="Material results"] tbody tr').filter(
            has_text="DP780"
        ).first.dblclick()
        page.wait_for_url(
            re.compile(
                r"/materials/[0-9a-f-]+\?record_id=[0-9a-f-]+"
                r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
            ),
            timeout=30_000,
        )
        if width == 1440:
            page.get_by_text(
                re.compile(r"^(Request review|Waiting for review|Approved|Changes requested)$")
            ).first.wait_for(timeout=30_000)
            _capture(
                page,
                output / "material-detail-1440x900.png",
                width,
                height,
            )
        page.get_by_role("tab", name="CAE Cards", exact=True).click()
        openradioss = page.locator(".cae-card-table tbody tr").filter(has_text="OpenRadioss").first
        openradioss.get_by_role("button", name=re.compile(r"^Preview(?: card)?$")).click()
        page.wait_for_url(
            re.compile(
                r"/materials/[0-9a-f-]+/cards/[0-9a-f-]+\?record_id=[0-9a-f-]+"
                r"&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$"
            ),
            timeout=30_000,
        )
        page.get_by_role("heading", name="Delivery check", exact=True).wait_for(timeout=30_000)
        download = page.get_by_role("button", name="Download .rad", exact=True)
        download.wait_for(timeout=30_000)
        native_preview = page.get_by_label("Native solver card preview")
        native_preview.wait_for(timeout=30_000)
        if native_preview.get_attribute("tabindex") != "0":
            raise RuntimeError("native solver card preview is not keyboard focusable")
        scroll_state = native_preview.evaluate(
            "element => ({"
            "clientHeight: element.clientHeight, "
            "scrollHeight: element.scrollHeight, "
            "scrollTop: element.scrollTop"
            "})"
        )
        if scroll_state["scrollHeight"] > scroll_state["clientHeight"] + 1:
            rail = page.locator(".preview-scroll-rail")
            if rail.get_attribute("data-scrollable") != "true":
                raise RuntimeError(
                    "long native solver card preview has no visible local scroll rail"
                )
            native_preview.focus()
            native_preview.press("End")
            page.wait_for_function(
                "element => element.scrollTop > 0",
                arg=native_preview.element_handle(),
            )
            native_preview.press("Home")
        linked_response = page.get_by_role(
            "img",
            name="Linked response chart showing true stress in MPa versus true plastic strain",
        )
        if width >= 1800:
            linked_response.wait_for(state="visible", timeout=30_000)
            if linked_response.get_attribute("data-x-label") != "True plastic strain [1]":
                raise RuntimeError("linked response graph has the wrong horizontal axis")
            y_domain = linked_response.get_attribute("data-y-domain") or ""
            try:
                y_bounds = [float(value) for value in y_domain.split(",")]
            except ValueError as cause:
                raise RuntimeError("linked response graph has an invalid stress range") from cause
            if len(y_bounds) != 2 or min(y_bounds) < 0 or max(y_bounds) >= 10_000:
                raise RuntimeError("linked response graph is not displayed in MPa")
            _assert_linked_response_labels_visible(page)
        elif linked_response.is_visible():
            raise RuntimeError("linked response graph must remain bounded to wide workspaces")
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
                raise RuntimeError("reviewed approximation did not enable solver-card delivery")
        elif acknowledgement.count() or not download.is_enabled():
            raise RuntimeError("exact solver-card delivery has a redundant confirmation")
        review_reason = page.get_by_role("textbox", name="Review request reason", exact=True)
        if (
            not review_reason.count()
            and page.get_by_role("button", name="Request review", exact=True).count()
        ):
            page.get_by_role("button", name="Request review", exact=True).click()
        review_reason = page.get_by_role("textbox", name="Review request reason", exact=True)
        if review_reason.count():
            review_reason.fill("Review the synthetic native card mapping before use.")
            page.get_by_role("button", name="Send request", exact=True).click()
        page.get_by_role("status").filter(has_text="Waiting for review").wait_for(timeout=30_000)
        _capture(
            page,
            output / f"solver-card-preview-{width}x{height}.png",
            width,
            height,
        )
        _ensure_activity_review_fixture(page, base_url)
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page, expect_review_action=False, expected_view="in-progress")
        page.get_by_role("heading", name="In progress", exact=True).wait_for(timeout=30_000)
        solver_review = page.get_by_role("row").filter(has_text="Solver card review").first
        solver_review.wait_for(timeout=30_000)
        solver_review.get_by_text("Waiting for review", exact=True).wait_for(timeout=30_000)
        if solver_review.get_by_role("button", name="Review", exact=True).count():
            raise RuntimeError("requester Activity row must not expose the Reviewer action")
        _capture(page, output / f"activity-{width}x{height}.png", width, height)
        page.context.close()


def _capture_activity(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height, persona="reviewer")
        _ensure_activity_review_fixture(page, base_url)
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page)
        _assert_activity_shared_density(page, width)
        _capture(page, output / f"activity-{width}x{height}.png", width, height)
        page.context.close()
    _capture_activity_history(browser, base_url, output)
    _capture_activity_role_default(browser, base_url, output, persona="user")
    _capture_activity_role_default(browser, base_url, output, persona="administrator")
    _capture_activity_decision_error(browser, base_url, output)
    _capture_activity_recovery(browser, base_url, output)


def _assert_activity_shared_density(page: Page, viewport_width: int) -> None:
    """Prove the shared desktop tokens reach the live Activity surface."""
    measurements = page.evaluate(
        """() => {
          const fontSize = selector =>
            getComputedStyle(document.querySelector(selector)).fontSize;
          const root = getComputedStyle(document.documentElement);
          const token = name => root.getPropertyValue(name).trim();
          const pixels = name => Number.parseFloat(token(name));
          const table = document.querySelector('.activity-table').getBoundingClientRect();
          const queue = document.querySelector('#activity-queue-scroll').getBoundingClientRect();
          const row = document.querySelector('.activity-table tbody tr').getBoundingClientRect();
          const action = document.querySelector('.activity-cell-action .ux-button').getBoundingClientRect();
          return {
            tab: fontSize('.activity-saved-view'),
            task: fontSize('.activity-cell-task strong'),
            data: fontSize('.activity-cell-reason'),
            metadata: fontSize('.activity-cell-status'),
            updated: fontSize('.activity-cell-updated'),
            heading: fontSize('.activity-table th'),
            action: fontSize('.activity-cell-action .ux-button'),
            rowHeight: row.height,
            actionHeight: action.height,
            tableLeft: table.left,
            tableRight: table.right,
            tableWidth: table.width,
            queueWidth: queue.width,
            queueLeft: queue.left,
            queueRight: queue.right,
            tokens: {
              data: token('--ux-data-font-size'),
              emphasis: token('--ux-emphasis-font-size'),
              metadata: token('--ux-metadata-font-size'),
              tableHeading: token('--ux-table-heading-font-size'),
              workRow: pixels('--ux-work-row-min-block-size'),
              control: pixels('--ux-control-min-block-size'),
            },
          };
        }"""
    )
    expected_fonts = {
        "tab": measurements["tokens"]["data"],
        "task": measurements["tokens"]["emphasis"],
        "data": measurements["tokens"]["data"],
        "metadata": measurements["tokens"]["metadata"],
        "updated": measurements["tokens"]["metadata"],
        "heading": measurements["tokens"]["tableHeading"],
        "action": measurements["tokens"]["data"],
    }
    actual_fonts = {name: measurements[name] for name in expected_fonts}
    if actual_fonts != expected_fonts:
        raise RuntimeError(
            f"Activity shared tokens are not live: expected {expected_fonts}, got {actual_fonts}"
        )
    if (
        measurements["rowHeight"] < measurements["tokens"]["workRow"]
        or measurements["actionHeight"] < measurements["tokens"]["control"]
    ):
        raise RuntimeError(f"Activity shared row/control bounds regressed: {measurements}")
    if measurements["tableWidth"] > 2656.5:
        raise RuntimeError(f"Activity table exceeded its readable wide bound: {measurements}")
    if viewport_width == 3840:
        left_gutter = measurements["tableLeft"] - measurements["queueLeft"]
        right_gutter = measurements["queueRight"] - measurements["tableRight"]
        if measurements["queueWidth"] > 2656.5:
            raise RuntimeError(
                f"Activity 4K local queue exceeded its readable wide bound: {measurements}"
            )
        if abs(left_gutter - right_gutter) > 1 or max(left_gutter, right_gutter) > 32:
            raise RuntimeError(
                f"Activity 4K table and local rail are not adjacent: {measurements}"
            )


def _capture_activity_history(browser: Browser, base_url: str, output: Path) -> None:
    """Capture truthful server outcomes plus bounded browser-local card history."""
    for width, height in ACTIVITY_HISTORY_VIEWPORTS:
        page = _new_page(browser, base_url, width, height, persona="reviewer")
        try:
            _ensure_activity_review_fixture(page, base_url)
            _seed_activity_delivery_history(page)
            _seed_activity_recovery_history(page, base_url)
            page.goto(f"{base_url}/activity")
            _wait_for_activity_queue(page, expected_view="needs-attention")
            page.get_by_role("tab", name="Recent outcomes", exact=True).click()
            page.get_by_role("tabpanel").filter(has=page.get_by_role("heading", name="Recent outcomes", exact=True)).wait_for(timeout=30_000)
            scroll = page.locator("#activity-queue-scroll")
            scroll.wait_for(timeout=30_000)
            scroll_metrics = scroll.evaluate(
                "element => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight })"
            )
            has_overflow = scroll_metrics["scrollHeight"] > scroll_metrics["clientHeight"] + 1
            rail_visible = (
                page.locator(".activity-queue-scroll-shell").get_attribute("data-scroll-y")
                == "true"
            )
            if not has_overflow:
                raise RuntimeError(
                    f"Activity Recent outcomes fixture did not produce a real local overflow rail at {width}x{height}"
                )
            if rail_visible != has_overflow:
                raise RuntimeError(
                    f"Activity Recent outcomes rail does not match its real overflow at {width}x{height}: {scroll_metrics}"
                )
            _capture(page, output / f"activity-history-{width}x{height}.png", width, height)
        finally:
            page.context.close()


def _seed_activity_delivery_history(page: Page) -> None:
    """Exercise the existing 20-item browser-local card history beside server outcomes."""
    activities = [
        {
            "version": 1,
            "action": "download" if index % 2 == 0 else "preview",
            "occurredAt": f"2026-08-08T{23 - index:02d}:30:00Z",
            "materialId": "material-dp780",
            "materialRevisionId": "material-dp780-r19",
            "materialLabel": "DP780 Dual-Phase Steel",
            "cardId": f"solver-card-history-{index + 1:02d}",
            "cardRevisionId": f"solver-card-history-{index + 1:02d}-r1",
            "cardLabel": f"DP780 OpenRadioss card {index + 1:02d}",
            "solver": "OpenRadioss",
            "extension": ".rad",
        }
        for index in range(20)
    ]
    page.evaluate(
        "items => sessionStorage.setItem('cmp.solver-card.recent-activity.v1', JSON.stringify(items))",
        activities,
    )


def _seed_activity_recovery_history(page: Page, base_url: str) -> None:
    """Add bounded successful recovery facts so the 4K long-history state truly overflows."""
    outcome = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const headers = {
            "Accept": "application/json",
            "Authorization": `Bearer ${config.accessToken}`,
          };
          const principalResponse = await fetch(`${baseUrl}/api/v1/me`, { headers });
          if (!principalResponse.ok) {
            throw new Error(`cannot load Activity recovery principal: ${principalResponse.status}`);
          }
          const principal = await principalResponse.json();
          const activities = Array.from({ length: 20 }, (_, index) => ({
            schemaVersion: 1,
            id: `activity-recovery-history-${String(index + 1).padStart(2, "0")}`,
            principalId: principal.principal_id,
            organizationId: principal.organization_id,
            projectId: principal.project_id,
            workspace: "activity",
            context: {
              kind: "solver_card",
              path: `/materials/material-dp780/cards/solver-card-recovery-${String(index + 1).padStart(2, "0")}`,
              materialId: "material-dp780",
              materialRevisionId: "material-dp780-r19",
              solverCardId: `solver-card-recovery-${String(index + 1).padStart(2, "0")}`,
              solverCardRevisionId: `solver-card-recovery-${String(index + 1).padStart(2, "0")}-r1`,
              target: "openradioss-2025",
            },
            status: "succeeded",
            message: `Recovered synthetic solver card delivery ${String(index + 1).padStart(2, "0")}`,
            occurredAt: `2026-08-07T${String(23 - index).padStart(2, "0")}:15:00Z`,
          }));
          const key = `cmp.activity.recovery.v1:${principal.organization_id}:${principal.project_id}:${principal.principal_id}:activity`;
          localStorage.setItem(key, JSON.stringify(activities));
          return { count: activities.length, key };
        }""",
        {"baseUrl": base_url},
    )
    if outcome.get("count") != 20 or not outcome.get("key"):
        raise RuntimeError(f"unexpected Activity recovery fixture result: {outcome}")


def _capture_activity_role_default(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    persona: str,
) -> None:
    page = _new_page(browser, base_url, 1440, 900, persona=persona)
    try:
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(
            page,
            expect_review_action=False,
            expected_view="in-progress",
        )
        if page.get_by_role("button", name="Approve", exact=True).count():
            raise RuntimeError(f"{persona} Activity default exposed a decision action")
        _capture(page, output / f"activity-{persona}-1440x900.png", 1440, 900)
    finally:
        page.context.close()


def _capture_activity_decision_error(browser: Browser, base_url: str, output: Path) -> None:
    page = _new_page(browser, base_url, 1440, 900, persona="reviewer")
    try:
        _ensure_activity_review_fixture(page, base_url)
        page.route(
            "**/api/v1/review-requests/*/decisions",
            lambda route: route.fulfill(
                status=503,
                content_type="application/problem+json",
                body=json.dumps(
                    {
                        "title": "Review service unavailable",
                        "status": 503,
                        "detail": "The selected request and reason remain available; retry when the review service is available.",
                    }
                ),
            ),
        )
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page)
        page.get_by_role("button", name="Review", exact=True).first.click()
        reason = page.get_by_role("textbox", name="Review reason", exact=True)
        retained_reason = (
            "Units, source text, test condition, and exact revision are complete; "
            "retain this reason while the review service recovers."
        )
        reason.fill(retained_reason)
        page.get_by_role("button", name="Approve", exact=True).click()
        page.get_by_role("alert").wait_for(timeout=30_000)
        if reason.input_value() != retained_reason:
            raise RuntimeError("Activity decision error did not retain the review reason")
        _capture(page, output / "activity-decision-error-1440x900.png", 1440, 900)
    finally:
        page.context.close()


def _capture_activity_recovery(browser: Browser, base_url: str, output: Path) -> None:
    page = _new_page(browser, base_url, 1440, 900, persona="reviewer")
    try:
        page.evaluate(
            """async ({ baseUrl }) => {
              const config = JSON.parse(localStorage.getItem("cmp.material-platform.api-config") || "{}");
              const response = await fetch(`${baseUrl}/api/v1/me`, {
                headers: { "Accept": "application/json", "Authorization": `Bearer ${config.accessToken}` },
              });
              if (!response.ok) throw new Error(`cannot read Activity principal: ${response.status}`);
              const principal = await response.json();
              const key = `cmp.activity.recovery.v1:${principal.organization_id}:${principal.project_id}:${principal.principal_id}:activity`;
              localStorage.setItem(key, JSON.stringify([{
                schemaVersion: 1,
                id: "activity-density-recovery",
                principalId: principal.principal_id,
                organizationId: principal.organization_id,
                projectId: principal.project_id,
                workspace: "activity",
                context: {
                  kind: "selected_model_json",
                  path: "/modeling?stage=fit&family=metal",
                  materialModelId: "dp780-selected-model",
                  materialModelRevisionId: "dp780-selected-model-r3",
                  target: "selected-model.json",
                },
                status: "failed",
                message: "Selected model download failed; the exact model revision remains selected for retry.",
                occurredAt: "2026-08-09T05:35:00Z",
              }]));
            }""",
            {"baseUrl": base_url},
        )
        page.goto(f"{base_url}/activity")
        _wait_for_activity_queue(page)
        page.get_by_role("heading", name="Recovery needed", exact=True).wait_for(timeout=30_000)
        page.get_by_role("button", name="Open exact selection", exact=True).wait_for(timeout=30_000)
        _capture(page, output / "activity-recovery-1440x900.png", 1440, 900)
    finally:
        page.context.close()


def _wait_for_activity_queue(
    page: Page,
    *,
    expect_review_action: bool = True,
    expected_view: str | None = None,
) -> None:
    page.get_by_role("heading", name="Activity", exact=True).wait_for(timeout=30_000)
    view = expected_view or ("needs-attention" if expect_review_action else "in-progress")
    view_label = {"needs-attention": "Needs attention", "in-progress": "In progress", "recent-outcomes": "Recent outcomes"}[view]
    page.get_by_role("tab", name=view_label, exact=True).click()
    page.get_by_role("heading", name=view_label, exact=True).wait_for(timeout=30_000)
    if not expect_review_action:
        if page.get_by_role("button", name="Review", exact=True).count():
            raise RuntimeError("requester Activity view exposed a Reviewer-only Review action")
    else:
        review_task = page.get_by_text(
            re.compile(r"^(Selected model review|Material data review|Solver card review|Test data review)$")
        ).first
        review_button = page.get_by_role("button", name="Review", exact=True)
        review_button.first.wait_for(timeout=30_000)
        review_task.wait_for(timeout=30_000)


def _ensure_activity_review_fixture(page: Page, base_url: str) -> None:
    """Reuse the clean-demo selected-model review or create the no-review fallback."""
    outcome = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": `Bearer ${config.accessToken}`,
          };
          const reviews = await fetch(`${baseUrl}/api/v1/review-requests?limit=50`, { headers });
          if (!reviews.ok) throw new Error(`cannot list review requests: ${reviews.status}`);
          if ((await reviews.json()).items.length) return "reused";
          const materials = await fetch(
            `${baseUrl}/api/v1/materials?limit=10&offset=0`, { headers }
          );
          if (!materials.ok) {
            throw new Error(`cannot list synthetic materials: ${materials.status}`);
          }
          const material = (await materials.json()).items.find(
            item => item.current_revision?.lifecycle_state === "draft"
          );
          if (!material) return "empty";
          const revision = material.current_revision;
          const created = await fetch(`${baseUrl}/api/v1/review-requests`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              classification: revision.classification,
              aggregate_type: "catalog.material",
              aggregate_id: material.material_id,
              revision_id: revision.id,
              manifest_sha256: revision.content_hash,
              reason: "Review synthetic material data for the Activity queue",
            }),
          });
          if (!created.ok) {
            throw new Error(`cannot create Activity review fixture: ${created.status}`);
          }
          return "created";
        }""",
        {"baseUrl": base_url},
    )
    if outcome not in {"created", "reused"}:
        raise RuntimeError(f"unexpected Activity fixture result: {outcome}")


def _open_modeling_stage(page: Page, stage: str) -> None:
    stage_title = stage.title()
    stage_button = page.locator(".modeling-stage-shell button:visible").filter(
        has=page.locator("strong").filter(
            has_text=re.compile(rf"^{re.escape(stage_title)}$")
        )
    )
    stage_button.wait_for(state="visible", timeout=30_000)
    if stage_button.count() != 1:
        raise RuntimeError(
            f"Modeling stage {stage_title!r} did not resolve to exactly one visible stage button"
        )
    stage_button.click()


def _wait_for_modeling_data_surface(page: Page) -> None:
    """Wait for the visible Data workspace, not an off-screen heading."""
    page.locator(".data-source-tabs").wait_for(state="visible", timeout=30_000)
    page.locator(".modeling-data-workspace").wait_for(state="visible", timeout=30_000)
    page.locator(".persistent-modeling-plot").wait_for(state="visible", timeout=30_000)


def _modeling_session(page: Page) -> dict[str, object]:
    raw = page.evaluate(
        "() => window.sessionStorage.getItem('cmp.modeling.recent-session.v4')"
    )
    if not raw:
        raise RuntimeError("Modeling Data session v4 is missing from sessionStorage")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as cause:
        raise RuntimeError("Modeling Data session v4 is not valid JSON") from cause
    if not isinstance(parsed, dict):
        raise RuntimeError("Modeling Data session v4 has an unexpected shape")
    return parsed


def _data_session_snapshot(page: Page) -> dict[str, object]:
    session = _modeling_session(page)
    workspace = session.get("workspace")
    if not isinstance(workspace, dict):
        raise RuntimeError("Modeling Data session has no workspace state")
    refs = workspace.get("selectedTestDataRefs")
    included = workspace.get("selectedDocumentIds")
    visible = workspace.get("visibleTestDataKeys")
    if not isinstance(refs, list) or not isinstance(included, list) or not isinstance(visible, list):
        raise RuntimeError("Modeling Data session is missing exact selection arrays")
    return {
        "selectedTestDataRefs": refs,
        "selectedDocumentIds": included,
        "visibleTestDataKeys": visible,
    }


def _session_list(snapshot: dict[str, object], key: str) -> list[object]:
    value = snapshot.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"Modeling Data session field {key!r} is not a list")
    return value


def _wait_for_data_session_counts(page: Page, refs: int, included: int, visible: int) -> None:
    page.wait_for_function(
        """expected => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          const workspace = JSON.parse(raw).workspace || {};
          return Array.isArray(workspace.selectedTestDataRefs)
            && workspace.selectedTestDataRefs.length === expected.refs
            && Array.isArray(workspace.selectedDocumentIds)
            && workspace.selectedDocumentIds.length === expected.included
            && Array.isArray(workspace.visibleTestDataKeys)
            && workspace.visibleTestDataKeys.length === expected.visible;
        }""",
        arg={"refs": refs, "included": included, "visible": visible},
        timeout=30_000,
    )


def _wait_for_exact_document_load_settled(page: Page) -> None:
    """Wait for the selected exact Test Data read to finish successfully."""
    page.wait_for_function(
        """() => {
          const selected = document.querySelector(
            '.modeling-data-record-button[aria-current="true"]'
          );
          return Boolean(
            selected
              && document.querySelectorAll('.curve-line.data-observed').length >= 1
              && !document.querySelector('.error-banner')
          );
        }""",
        timeout=60_000,
    )


def _wait_for_data_plot(page: Page, *, lines: int = 3, legends: int = 3) -> None:
    try:
        page.wait_for_function(
            """expected => document.querySelectorAll('.curve-line.data-observed').length === expected.lines
              && document.querySelectorAll('.persistent-modeling-plot .curve-legend.interactive button').length === expected.legends""",
            arg={"lines": lines, "legends": legends},
            timeout=60_000,
        )
    except Exception as error:
        diagnostics = page.evaluate(
            """() => ({
              lines: document.querySelectorAll('.curve-line.data-observed').length,
              legends: document.querySelectorAll('.persistent-modeling-plot .curve-legend.interactive button').length,
              comparisons: document.querySelectorAll('.modeling-data-results input[type="checkbox"]:checked').length,
              selectedRefs: (() => {
                try {
                  return JSON.parse(sessionStorage.getItem('cmp.modeling.recent-session.v4') || '{}')
                    ?.workspace?.selectedTestDataRefs ?? null;
                } catch { return 'malformed'; }
              })(),
              errors: [...document.querySelectorAll('.error-banner, [role="alert"]')]
                .filter(element => element.getClientRects().length)
                .map(element => element.textContent?.trim()),
              geometry: Object.fromEntries([
                ['workspace', document.querySelector('.modeling-workspace-stage-data')],
                ['main', document.querySelector('.modeling-main-surface')],
                ['plot', document.querySelector('.persistent-modeling-plot')],
                ['svg', document.querySelector('.persistent-modeling-plot svg')],
              ].map(([key, element]) => {
                if (!element) return [key, null];
                const box = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return [key, {
                  x: box.x,
                  y: box.y,
                  width: box.width,
                  height: box.height,
                  display: style.display,
                  minHeight: style.minHeight,
                  overflow: style.overflow,
                }];
              })),
              fetches: (window.__cmpCaptureFetchDiagnostics || []).slice(-24),
              runtimeErrors: window.__cmpCaptureRuntimeErrors || [],
              url: location.href,
              shellCount: document.querySelectorAll('.application-shell').length,
              bodyText: document.body?.innerText?.slice(0, 800) ?? '',
              readyState: document.readyState,
            })"""
        )
        raise RuntimeError(
            f"Modeling Data plot did not reach its exact {lines}-line/{legends}-legend contract: "
            f"{diagnostics}"
        ) from error


def _modeling_data_ribbon_height(page: Page) -> float:
    return (
        _css_token_px(page, "--ux-navigator-row-block-size") * 7
        + _css_token_px(page, "--ux-splitter-inline-size")
        + _css_token_px(page, "--ux-pane-padding")
    )


def _wait_for_modeling_data_ribbon(page: Page) -> None:
    expected_height = _modeling_data_ribbon_height(page)
    try:
        page.wait_for_function(
            """expected => {
              const panel = document.querySelector('#modeling-data-ribbon[data-panel]');
              if (!panel) return false;
              return Math.abs(panel.getBoundingClientRect().height - expected) <= 1;
            }""",
            arg=expected_height,
            timeout=30_000,
        )
    except Exception as error:
        layout = page.evaluate(
            """() => Object.fromEntries([
              ['ribbon', document.querySelector('#modeling-data-ribbon[data-panel]')],
              ['ribbonContent', document.querySelector('.modeling-data-ribbon-panel')],
              ['plot', document.querySelector('.modeling-data-plot-panel')],
              ['split', document.querySelector('.modeling-data-split')],
              ['main', document.querySelector('.modeling-main-surface')],
            ].map(([name, element]) => [name, element ? {
              top: element.getBoundingClientRect().top,
              height: element.getBoundingClientRect().height,
              minHeight: getComputedStyle(element).minHeight,
              style: element.getAttribute('style'),
              attributes: Object.fromEntries([...element.attributes].map(attribute => [attribute.name, attribute.value])),
            } : null]))"""
        )
        raise RuntimeError(
            "Modeling Data result/graph split did not reach its density-derived "
            f"height: expected={expected_height}, layout={layout}"
        ) from error


def _assert_modeling_data_surface(
    page: Page,
    width: int,
    height: int,
    *,
    comparison_open: bool,
) -> None:
    """Assert the owner-approved normal or deliberately opened comparison state."""
    if page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ):
        raise RuntimeError(f"Modeling Data has page horizontal overflow at {width}x{height}")

    workspace = page.locator(".modeling-workspace-stage-data")
    browser = page.locator(".modeling-data-browser")
    results = page.locator(".modeling-data-results")
    result_region = page.get_by_role("region", name="Test Data results")
    plot_panel = page.locator(".modeling-data-plot-panel")
    plot = page.locator(".modeling-data-plot")
    for locator, label in (
        (workspace, "workspace"),
        (browser, "search and browser rail"),
        (results, "Test Data results"),
        (plot, "persistent graph"),
    ):
        if locator.count() != 1 or not locator.is_visible():
            raise RuntimeError(
                f"Modeling Data {label} is not uniquely visible at {width}x{height}"
            )

    source_tabs = page.get_by_role("tablist", name="Test data source")
    if source_tabs.get_by_role("tab").all_inner_texts() != ["Library", "Local file"]:
        raise RuntimeError("Modeling Data must expose only Library and Local file sources")
    if source_tabs.get_by_role("tab", name="Library").get_attribute("aria-selected") != "true":
        raise RuntimeError("normal Modeling Data capture is not on the Library source")

    search = browser.get_by_role("search")
    if (
        search.get_by_role("searchbox", name="Find Test Data").count() != 1
        or search.get_by_role("button", name="Find", exact=True).count() != 1
        or browser.get_by_label("Test type", exact=True).count() != 1
        or browser.get_by_label("Condition", exact=True).count() != 1
    ):
        raise RuntimeError("Modeling Data search and filter controls are incomplete")

    headings = results.locator("thead th").all_inner_texts()
    expected_headings = [
        *(["Graph"] if comparison_open else []),
        "Test record",
        "Material",
        "Condition",
        "Test date",
        "Data points",
    ]
    if headings != expected_headings:
        raise RuntimeError(f"Modeling Data result columns drifted: {headings}")
    if result_region.get_attribute("tabindex") != "0":
        raise RuntimeError("Test Data results are not a keyboard-focusable local scroll region")
    if result_region.evaluate("element => element.scrollWidth > element.clientWidth + 1"):
        raise RuntimeError("Test Data results expose horizontal overflow")

    selected_rows = []
    for document_key in MODELING_DATA_DOCUMENT_KEYS:
        row = _modeling_data_library_row(page, document_key)
        row.scroll_into_view_if_needed()
        row_box = _bounding_box_edges(row.bounding_box())
        if row_box is None:
            raise RuntimeError(f"Test Data result row {document_key!r} has no geometry")
        selected_rows.append(row)
    if not any(
        row.locator(".modeling-data-record-button").get_attribute("aria-current") == "true"
        for row in selected_rows
    ):
        raise RuntimeError("Modeling Data has no primary Test Data row")
    checked_comparisons = results.locator('input[type="checkbox"]:checked').count()
    if comparison_open and checked_comparisons != 2:
        raise RuntimeError("Modeling Data comparison mode did not retain two optional comparisons")
    if not comparison_open and results.locator('input[type="checkbox"]').count():
        raise RuntimeError("normal Modeling Data surface exposes bulk comparison checkboxes")
    row_alignment = results.locator("tbody tr").evaluate_all(
        """rows => rows.map(row => {
          const box = row.getBoundingClientRect();
          const center = (box.top + box.bottom) / 2;
          return Math.max(...[...row.children].map(cell => {
            const cellBox = cell.getBoundingClientRect();
            return Math.abs((cellBox.top + cellBox.bottom) / 2 - center);
          }));
        })"""
    )
    if any(delta > 1.5 for delta in row_alignment):
        raise RuntimeError(f"Modeling Data table cells are not vertically aligned: {row_alignment}")

    normal_text = "\n".join(
        line.strip()
        for line in workspace.inner_text().splitlines()
        if line.strip()
    )
    for retired in (
        "Select specimen",
        "Observed ·",
        "Evidence available",
        "Specimen identifier from test record",
        "CSV · header row",
    ):
        if retired in normal_text:
            raise RuntimeError(f"retired helper or technical copy is still visible: {retired!r}")
    if re.search(r"\bRevision r\d+\b", normal_text):
        raise RuntimeError("technical Test Data revision leaked onto the normal surface")

    continue_action = plot.locator(".modeling-data-plot-actions").get_by_role(
        "button", name="Continue to Process", exact=True
    )
    if continue_action.count() != 1 or not continue_action.is_enabled():
        raise RuntimeError("Modeling Data graph is missing its enabled Continue to Process action")
    comparison_action = plot.locator(":scope > .section-heading").get_by_role(
        "button",
        name="Close comparison" if comparison_open else "Add comparison",
        exact=True,
    )
    if comparison_action.count() != 1:
        raise RuntimeError("optional comparison control is not graph-owned")
    comparison_colors = comparison_action.evaluate(
        """element => {
          const root = getComputedStyle(document.documentElement);
          const probe = document.createElement('span');
          document.body.appendChild(probe);
          const resolve = value => {
            probe.style.color = value;
            return getComputedStyle(probe).color;
          };
          const expected = [
            resolve(root.getPropertyValue('--ux-accent')),
            resolve(root.getPropertyValue('--ux-accent-hover')),
          ];
          probe.remove();
          return { actual: getComputedStyle(element).color, expected };
        }"""
    )
    if comparison_colors["actual"] not in comparison_colors["expected"]:
        raise RuntimeError(
            "optional comparison action drifted from the Modeling action color: "
            f"{comparison_colors}"
        )
    expected_curves = 3 if comparison_open else 1
    if plot.locator(".curve-line.data-observed").count() != expected_curves:
        raise RuntimeError(
            f"Modeling Data graph does not show its expected {expected_curves} exact curve(s)"
        )
    if plot.locator(".curve-legend.interactive button").count() != expected_curves:
        raise RuntimeError("Modeling Data graph legend does not match its exact selected curves")

    axis_labels = [
        (text or "").strip()
        for text in plot.locator(".chart-axis-label").all_text_contents()
    ]
    if not any(label.startswith("Engineering strain") for label in axis_labels):
        raise RuntimeError(
            f"engineering strain axis title is missing at {width}x{height}: {axis_labels}"
        )
    if not any(
        label.startswith("Engineering stress") and label.endswith("[MPa]")
        for label in axis_labels
    ):
        raise RuntimeError(
            f"engineering stress MPa axis title is missing at {width}x{height}: {axis_labels}"
        )

    ribbon_box = _bounding_box_edges(
        page.locator("#modeling-data-ribbon[data-panel]").bounding_box()
    )
    divider_box = _bounding_box_edges(
        page.locator("#modeling-data-ribbon-plot-divider").bounding_box()
    )
    workspace_box = _bounding_box_edges(workspace.bounding_box())
    plot_panel_box = _bounding_box_edges(plot_panel.bounding_box())
    plot_box = _bounding_box_edges(plot.bounding_box())
    page.wait_for_function(
        """() => {
          const svg = document.querySelector('.modeling-data-plot svg');
          if (!svg) return false;
          const box = svg.getBoundingClientRect();
          return box.width > 0 && box.height > 0;
        }""",
        timeout=30_000,
    )
    svg_rect = page.evaluate(
        """() => {
          const svg = document.querySelector('.modeling-data-plot svg');
          if (!svg) return null;
          const box = svg.getBoundingClientRect();
          return { x: box.x, y: box.y, width: box.width, height: box.height };
        }"""
    )
    svg_box = _bounding_box_edges(svg_rect)
    browser_box = _bounding_box_edges(browser.bounding_box())
    related_slot = browser.locator(".modeling-data-related-slot")
    if related_slot.count() != 1 or not related_slot.is_visible():
        raise RuntimeError("Modeling Data Related data slot is missing or not visible")
    related_box = _bounding_box_edges(related_slot.bounding_box())
    browser_heading_box = _bounding_box_edges(
        browser.locator(".modeling-data-tree > .modeling-data-rail-heading").bounding_box()
    )
    related_section = related_slot.locator(".modeling-data-related")
    related_count = related_section.count()
    if related_count > 1:
        raise RuntimeError("Modeling Data Related content is not unique")
    related_heading_box = (
        _bounding_box_edges(
            related_section.locator(".modeling-data-rail-heading").bounding_box()
        )
        if related_count == 1
        else None
    )
    if related_count == 1:
        if not related_section.is_visible():
            raise RuntimeError("Modeling Data Related data section is not uniquely visible")
        if related_section.locator(".modeling-data-rail-heading").count() != 1:
            raise RuntimeError("Modeling Data Related data heading is missing")
    else:
        forbidden_related_content = related_slot.locator(
            ".modeling-data-related, .modeling-data-rail-heading, .error-banner, [role=\"alert\"]"
        )
        if forbidden_related_content.count():
            raise RuntimeError(
                "Modeling Data Related data slot contains an unexpected section, heading, or error"
            )
    geometry = {
        "ribbon": ribbon_box,
        "divider": divider_box,
        "workspace": workspace_box,
        "plot_panel": plot_panel_box,
        "plot": plot_box,
        "svg": svg_box,
        "browser": browser_box,
        "related_slot": related_box,
        "browser_heading": browser_heading_box,
    }
    missing = [name for name, value in geometry.items() if value is None]
    if missing:
        raise RuntimeError(f"Modeling Data geometry is incomplete: missing={missing}")
    assert ribbon_box is not None
    assert divider_box is not None
    assert workspace_box is not None
    assert plot_panel_box is not None
    assert plot_box is not None
    assert svg_box is not None
    assert browser_box is not None
    assert related_box is not None
    assert browser_heading_box is not None
    if related_count == 1:
        if related_heading_box is None:
            raise RuntimeError("Modeling Data Related content has incomplete heading geometry")
        assert related_heading_box is not None
        if (
            abs(browser_heading_box["left"] - related_heading_box["left"]) > 1
            or abs(browser_heading_box["right"] - related_heading_box["right"]) > 1
        ):
            raise RuntimeError(
                "Modeling Data Browser and Related data headings are not aligned: "
                f"browser={browser_heading_box}, related={related_heading_box}"
            )
    else:
        if related_slot.inner_text().strip():
            raise RuntimeError(
                "Modeling Data empty Related slot contains unexpected content"
            )
        if related_slot.evaluate(
            "element => element.scrollWidth > element.clientWidth + 1"
        ):
            raise RuntimeError(
                "Modeling Data empty Related slot exposes horizontal overflow"
            )

    if abs(related_box["bottom"] - browser_box["bottom"]) > 1:
        raise RuntimeError(
            "Modeling Data Related data is not anchored below the scalable Browser: "
            f"browser={browser_box}, related={related_box}"
        )

    expected_ribbon_height = _modeling_data_ribbon_height(page)
    if abs(ribbon_box["height"] - expected_ribbon_height) > 1:
        raise RuntimeError(
            "Modeling Data result ribbon drifted from the shared density formula: "
            f"expected={expected_ribbon_height}, actual={ribbon_box['height']}"
        )
    if workspace_box["width"] < width * 0.8:
        raise RuntimeError(
            f"wide Modeling Data workspace collapsed into a fixed island: {workspace_box}"
        )
    panel_style = plot_panel.evaluate(
        """element => {
          const style = getComputedStyle(element);
          return {
            left: Number.parseFloat(style.paddingLeft),
            right: Number.parseFloat(style.paddingRight),
            top: Number.parseFloat(style.paddingTop),
            bottom: Number.parseFloat(style.paddingBottom),
          };
        }"""
    )
    available_width = (
        plot_panel_box["width"] - panel_style["left"] - panel_style["right"]
    )
    available_height = (
        plot_panel_box["height"] - panel_style["top"] - panel_style["bottom"]
    )
    expected_plot_width = min(available_width, 2800)
    expected_plot_height = min(available_height, 1200)
    if (
        abs(plot_box["width"] - expected_plot_width) > 1
        or abs(plot_box["height"] - expected_plot_height) > 1
    ):
        raise RuntimeError(
            f"Modeling Data useful graph bound drifted at {width}x{height}: "
            f"panel={plot_panel_box}, plot={plot_box}"
        )
    horizontal_gutter_delta = abs(
        (plot_box["left"] - plot_panel_box["left"])
        - (plot_panel_box["right"] - plot_box["right"])
    )
    vertical_gutter_delta = abs(
        (plot_box["top"] - plot_panel_box["top"] - panel_style["top"])
        - (plot_panel_box["bottom"] - panel_style["bottom"] - plot_box["bottom"])
    )
    if horizontal_gutter_delta > 1 or vertical_gutter_delta > 1:
        raise RuntimeError(
            f"Modeling Data graph is not balanced inside its available work surface: "
            f"horizontal={horizontal_gutter_delta}, vertical={vertical_gutter_delta}"
        )
    if plot_box["height"] < 280 or svg_box["height"] < 180:
        raise RuntimeError(
            f"Modeling Data graph is too short for axes and comparison: "
            f"plot={plot_box}, svg={svg_box}"
        )
    if plot_box["bottom"] > workspace_box["bottom"] + 1:
        raise RuntimeError(
            f"Modeling Data graph escapes its workspace: workspace={workspace_box}, plot={plot_box}"
        )



def _assert_import_file_control(page: Page) -> None:
    expected_input_height = _css_token_px(page, "--ux-engineering-control-block-size")
    expected_font_size = _css_token_px(page, "--ux-engineering-control-font-size")
    input_control = page.locator('input[name="import-test-data-file"]')
    input_control.wait_for(state="attached", timeout=30_000)
    visual_control = page.locator(".data-import-file-control")
    visual_control.wait_for(state="visible", timeout=30_000)
    if visual_control.locator(".data-import-file-button").inner_text().strip() != "Choose data file":
        raise RuntimeError("Import file control does not expose one clear choose-file action")
    if page.locator(".data-import-formats").count() or page.get_by_text(
        "CSV · TSV · XLSX · JSON", exact=True
    ).count():
        raise RuntimeError("Import file control still repeats accepted formats on the normal surface")
    metrics = visual_control.evaluate(
        """element => {
          const style = getComputedStyle(element);
          const box = element.getBoundingClientRect();
          const input = element.querySelector('input[type=file]');
          const inputStyle = input ? getComputedStyle(input) : null;
          const inputBox = input?.getBoundingClientRect();
          const button = element.querySelector('.data-import-file-button')?.getBoundingClientRect();
          const name = element.querySelector('.data-import-file-name')?.getBoundingClientRect();
          return {
            height: box.height,
            boxSizing: style.boxSizing,
            display: style.display,
            inputOpacity: inputStyle?.opacity,
            inputPosition: inputStyle?.position,
            inputCursor: inputStyle?.cursor,
            inputBox: inputBox ? { left: inputBox.left, right: inputBox.right, top: inputBox.top, bottom: inputBox.bottom } : null,
            controlBox: { left: box.left, right: box.right, top: box.top, bottom: box.bottom },
            button: button ? { top: button.top, bottom: button.bottom, height: button.height } : null,
            name: name ? { top: name.top, bottom: name.bottom, height: name.height } : null,
            buttonFontSize: parseFloat(getComputedStyle(element.querySelector('.data-import-file-button')).fontSize),
            nameFontSize: parseFloat(getComputedStyle(element.querySelector('.data-import-file-name')).fontSize),
          };
        }"""
    )
    if (
        abs(metrics["height"] - expected_input_height) > 1
        or metrics["boxSizing"] != "border-box"
        or metrics["display"] != "grid"
        or metrics["inputOpacity"] != "0"
        or metrics["inputPosition"] != "absolute"
        or metrics["inputCursor"] != "pointer"
        or metrics["inputBox"] is None
        or abs(metrics["inputBox"]["left"] - metrics["controlBox"]["left"]) > 1
        or abs(metrics["inputBox"]["right"] - metrics["controlBox"]["right"]) > 1
        or abs(metrics["inputBox"]["top"] - metrics["controlBox"]["top"]) > 1
        or abs(metrics["inputBox"]["bottom"] - metrics["controlBox"]["bottom"]) > 1
    ):
        raise RuntimeError(f"Import file control geometry drifted: {metrics}")
    if (
        metrics["button"] is None
        or metrics["name"] is None
        or abs(metrics["button"]["height"] - (expected_input_height - 2)) > 1
        or abs(metrics["buttonFontSize"] - expected_font_size) > 0.1
        or abs(metrics["nameFontSize"] - expected_font_size) > 0.1
        or metrics["button"]["top"] < metrics["controlBox"]["top"] - 1
        or metrics["button"]["bottom"] > metrics["controlBox"]["bottom"] + 1
        or metrics["name"]["top"] < metrics["controlBox"]["top"] - 1
        or metrics["name"]["bottom"] > metrics["controlBox"]["bottom"] + 1
    ):
        raise RuntimeError(f"Import file button and filename are not aligned: {metrics}")


def _modeling_data_library_row(page: Page, document_key: str) -> Locator:
    row = page.locator(
        f'.modeling-data-results tbody tr[data-document-key={json.dumps(document_key)}]'
    )
    row.wait_for(state="visible", timeout=30_000)
    if row.count() != 1:
        raise RuntimeError(
            f"expected one governed Test Data Library row for {document_key!r}, got {row.count()}"
        )
    return row



def _prepare_modeling(
    page: Page,
    base_url: str,
    *,
    verify_reload: bool = True,
    retain_comparisons: bool = False,
) -> None:
    """Prepare Data through the real primary-plus-optional-comparison workflow."""
    page.add_init_script(
        """() => {
          if (window.__cmpCaptureFetchDiagnosticsInstalled) return;
          window.__cmpCaptureFetchDiagnosticsInstalled = true;
          window.__cmpCaptureFetchDiagnostics = [];
          window.__cmpCaptureRuntimeErrors = [];
          window.addEventListener('error', event => {
            window.__cmpCaptureRuntimeErrors.push(`error: ${event.message}`);
          });
          window.addEventListener('unhandledrejection', event => {
            const reason = event.reason;
            window.__cmpCaptureRuntimeErrors.push(
              `unhandledrejection: ${reason instanceof Error ? `${reason.name}: ${reason.message}` : String(reason)}`
            );
          });
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const started = performance.now();
            const input = args[0];
            const url = typeof input === 'string' ? input : input?.url ?? String(input);
            try {
              const response = await originalFetch(...args);
              if (url.includes('/processing:preview') || url.includes('/test-data-documents/') || !response.ok) {
                window.__cmpCaptureFetchDiagnostics.push({
                  url,
                  status: response.status,
                  ok: response.ok,
                  durationMs: Math.round(performance.now() - started),
                });
              }
              return response;
            } catch (error) {
              window.__cmpCaptureFetchDiagnostics.push({
                url,
                error: error instanceof Error ? `${error.name}: ${error.message}` : String(error),
                durationMs: Math.round(performance.now() - started),
              });
              throw error;
            }
          };
        }"""
    )
    page.goto(f"{base_url}/modeling?stage=data&family=metal")
    _wait_for_modeling_data_surface(page)
    result_region = page.get_by_role("region", name="Test Data results")
    if result_region.get_attribute("tabindex") != "0":
        raise RuntimeError("Test Data results must expose local keyboard scrolling")

    primary_row = _modeling_data_library_row(page, PROCESS_SOURCE_DOCUMENT_KEY)
    primary_button = primary_row.locator(".modeling-data-record-button")
    primary_button.click()
    _wait_for_exact_document_load_settled(page)
    _wait_for_data_session_counts(page, refs=1, included=1, visible=1)
    _wait_for_data_plot(page, lines=1, legends=1)

    # Inspecting another row replaces the single Process input. It must not
    # turn the previous input into an undeclared comparison curve.
    alternate_row = _modeling_data_library_row(page, MODELING_DATA_DOCUMENT_KEYS[1])
    alternate_row.locator(".modeling-data-record-button").click()
    _wait_for_exact_document_load_settled(page)
    _wait_for_data_session_counts(page, refs=1, included=1, visible=1)
    _wait_for_data_plot(page, lines=1, legends=1)
    primary_button.click()
    _wait_for_exact_document_load_settled(page)
    _wait_for_data_session_counts(page, refs=1, included=1, visible=1)
    _wait_for_data_plot(page, lines=1, legends=1)

    page.get_by_role("button", name="Add comparison", exact=True).click()
    page.get_by_role("button", name="Close comparison", exact=True).wait_for(timeout=30_000)
    for count, document_key in enumerate(MODELING_DATA_DOCUMENT_KEYS[1:], start=2):
        row = _modeling_data_library_row(page, document_key)
        row.scroll_into_view_if_needed()
        checkbox = row.locator('input[type="checkbox"]')
        if checkbox.count() != 1:
            raise RuntimeError(
                f"optional comparison row {document_key!r} has no unique checkbox"
            )
        checkbox.check()
        _wait_for_data_session_counts(
            page,
            refs=count,
            included=1,
            visible=count,
        )
        _wait_for_data_plot(page, lines=count, legends=count)

    # Removing and restoring one optional comparison changes only graph
    # visibility while retaining the one focused Process input and exact links.
    recovery_row = _modeling_data_library_row(page, MODELING_DATA_DOCUMENT_KEYS[-1])
    recovery_checkbox = recovery_row.locator('input[type="checkbox"]')
    recovery_checkbox.uncheck()
    _wait_for_data_session_counts(page, refs=3, included=1, visible=2)
    _wait_for_data_plot(page, lines=2, legends=2)
    recovery_checkbox.check()
    _wait_for_data_session_counts(page, refs=3, included=1, visible=3)
    _wait_for_data_plot(page, lines=3, legends=3)

    technical = page.locator("details.modeling-data-technical-details")
    if not technical.get_attribute("open"):
        technical.locator(":scope > summary").click()
    profile = technical.get_by_role("combobox", name="Saved Mapping Profile")
    profile.wait_for(timeout=30_000)
    page.wait_for_function(
        """() => (document.querySelector(
          'details.modeling-data-technical-details select[aria-label="Saved Mapping Profile"]'
        )?.options.length ?? 0) >= 2""",
        timeout=30_000,
    )
    profile.select_option(index=1)
    page.wait_for_function(
        """() => Boolean(document.querySelector(
          'details.modeling-data-technical-details select[aria-label="Saved Mapping Profile"]'
        )?.value)""",
        timeout=30_000,
    )
    technical.locator(":scope > summary").click()

    _wait_for_settled(page)
    _wait_for_modeling_data_ribbon(page)
    viewport_size = page.viewport_size
    if viewport_size is None:
        raise RuntimeError("Modeling Data capture lost its viewport size")
    _assert_modeling_data_surface(
        page,
        viewport_size["width"],
        viewport_size["height"],
        comparison_open=True,
    )
    if retain_comparisons:
        page.get_by_role("button", name="Close comparison", exact=True).click()
        _wait_for_data_plot(page, lines=1, legends=1)
        _assert_modeling_data_surface(
            page,
            viewport_size["width"],
            viewport_size["height"],
            comparison_open=False,
        )
    else:
        for document_key in MODELING_DATA_DOCUMENT_KEYS[1:]:
            row = _modeling_data_library_row(page, document_key)
            row.locator('input[type="checkbox"]').uncheck()
        _wait_for_data_session_counts(page, refs=3, included=1, visible=1)
        _wait_for_data_plot(page, lines=1, legends=1)
        page.get_by_role("button", name="Close comparison", exact=True).click()
        _assert_modeling_data_surface(
            page,
            viewport_size["width"],
            viewport_size["height"],
            comparison_open=False,
        )
    if not verify_reload:
        return

    before_reload = _data_session_snapshot(page)
    if (
        len(_session_list(before_reload, "selectedTestDataRefs")) != 3
        or len(_session_list(before_reload, "selectedDocumentIds")) != 1
        or len(_session_list(before_reload, "visibleTestDataKeys")) != (3 if retain_comparisons else 1)
    ):
        raise RuntimeError(
            f"expected three exact Data selections before reload: {before_reload}"
        )

    page.reload()
    _wait_for_modeling_data_surface(page)
    _modeling_data_library_row(page, PROCESS_SOURCE_DOCUMENT_KEY).locator(
        '.modeling-data-record-button[aria-current="true"]'
    ).wait_for(timeout=30_000)
    _wait_for_data_plot(page, lines=1, legends=1)
    if retain_comparisons:
        page.get_by_role("button", name="Add comparison", exact=True).click()
        page.get_by_role("button", name="Close comparison", exact=True).wait_for(timeout=30_000)
        _wait_for_data_plot(page, lines=3, legends=3)
    after_reload = _data_session_snapshot(page)
    if after_reload != before_reload:
        raise RuntimeError(
            "exact Modeling Data selection changed across reload: "
            f"before={before_reload}, after={after_reload}"
        )
    if retain_comparisons:
        if page.locator(".modeling-data-results input[type='checkbox']:checked").count() != 2:
            raise RuntimeError("reload did not restore both optional comparisons")
        page.get_by_role("button", name="Close comparison", exact=True).click()
        _wait_for_data_plot(page, lines=1, legends=1)
    elif page.locator(".modeling-data-results input[type='checkbox']").count():
        raise RuntimeError("reload exposed comparison checkboxes in the normal Data state")
    _wait_for_settled(page)



def _prepare_modeling_process(
    page: Page,
    base_url: str,
    *,
    verify_data_reload: bool = True,
) -> None:
    """Prepare Process on the exact primary Test Data and retained comparisons."""
    _prepare_modeling(
        page,
        base_url,
        verify_reload=verify_data_reload,
        retain_comparisons=True,
    )
    primary_row = _modeling_data_library_row(page, PROCESS_SOURCE_DOCUMENT_KEY)
    primary_button = primary_row.locator(
        '.modeling-data-record-button[aria-current="true"]'
    )
    if primary_button.count() != 1:
        raise RuntimeError(
            "Data capture did not retain the exact primary Test Data row"
        )

    session = _modeling_session(page)
    focused = session.get("testData")
    workspace = session.get("workspace")
    mapping = session.get("mappingProfile")
    if (
        not isinstance(focused, dict)
        or focused.get("label") != PROCESS_SOURCE_DOCUMENT_KEY
        or focused.get("revisionNo") != 1
    ):
        raise RuntimeError(
            f"Process capture did not focus the exact primary Test Data r1: {focused}"
        )
    if not isinstance(workspace, dict):
        raise RuntimeError("Process capture session has no workspace state")
    refs = workspace.get("selectedTestDataRefs")
    if not isinstance(refs, list) or len(refs) != 3:
        raise RuntimeError(
            f"Process capture must retain three exact Test Data refs: {workspace}"
        )
    focused_ref = next(
        (
            ref for ref in refs
            if isinstance(ref, dict)
            and ref.get("id") == focused.get("id")
            and ref.get("revisionId") == focused.get("revisionId")
            and ref.get("label") == PROCESS_SOURCE_DOCUMENT_KEY
            and ref.get("revisionNo") == 1
        ),
        None,
    )
    if focused_ref is None:
        raise RuntimeError(
            f"Process capture primary ref is not the exact r1 pin: {refs}"
        )
    if (
        len(workspace.get("selectedDocumentIds", [])) != 1
        or len(workspace.get("visibleTestDataKeys", [])) != 3
    ):
        raise RuntimeError(
            f"Process capture must retain one primary input and two visible comparisons: {workspace}"
        )
    if (
        not isinstance(mapping, dict)
        or mapping.get("label") != "CMP demo tensile JSON mapping"
        or not str(mapping.get("id") or "").strip()
        or not str(mapping.get("revisionId") or "").strip()
        or mapping.get("revisionNo") != 1
    ):
        raise RuntimeError(
            f"Process capture did not retain the exact Mapping Profile r1: {mapping}"
        )
    _open_modeling_stage(page, "process")
    page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    page.locator(".modeling-work-title h1").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    _wait_modeling_process_panel(page)
    source = page.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process panel source drifted from the selected Test Data: {source.inner_text()!r}")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    preview.wait_for(state="visible", timeout=30_000)
    if preview.is_disabled():
        raise RuntimeError("Process capture settled with Preview changes disabled")


def _open_scalar_distribution_workbench(page: Page) -> Locator:
    trigger = page.get_by_role("button", name="Distribution analysis", exact=True)
    trigger.wait_for(state="visible", timeout=30_000)
    if trigger.get_attribute("aria-expanded") != "true":
        trigger.click()
    analysis = page.locator("#scalar-distribution-analysis")
    analysis.wait_for(state="visible", timeout=30_000)
    page.wait_for_function(
        """() => {
          const analysis = document.querySelector('#scalar-distribution-analysis');
          const rows = analysis?.querySelectorAll('.distribution-candidate-table tbody tr');
          return Boolean(analysis && rows?.length === 3 && analysis.textContent?.includes('n = 8'));
        }""",
        timeout=60_000,
    )
    _wait_for_settled(page)

    selection = page.get_by_label("Saved replicate set")
    selection_text = selection.locator("option:checked").inner_text()
    if "8 observations" not in selection_text or "Normalized alignment source" in selection_text:
        raise RuntimeError(
            "distribution capture did not retain the exact eight-member processed Selection: "
            f"{selection_text!r}"
        )
    if page.locator(".distribution-candidate-table tbody tr").count() != 3:
        raise RuntimeError("distribution capture must expose exactly three candidate rows")
    if page.get_by_text("Normal + Lognormal + Weibull", exact=True).count() < 1:
        raise RuntimeError(
            "deterministic demo distribution recommendation no longer exposes all "
            "three co-recommended candidates"
        )
    quality = page.get_by_text(
        "Observation quality: 8 observed · 0 missing · 0 non-finite · 0 censored.",
        exact=True,
    )
    if quality.count() != 1:
        raise RuntimeError("distribution capture lost the exact observation-quality surface")
    return analysis


def _ensure_scalar_distribution_decision(page: Page) -> None:
    expected_reason = (
        "Normal selected explicitly for bounded comparison; recommendation remains separate."
    )
    saved = page.locator(".distribution-decision-record")
    normal = page.get_by_role("button", name=re.compile(r"^Normal (select|edit selection)$"))
    if (
        saved.count()
        and saved.locator("p").inner_text().strip() == expected_reason
        and normal.get_attribute("aria-pressed") == "true"
    ):
        return
    normal.click()
    reason = page.get_by_label("Engineering rationale")
    reason.wait_for(state="visible", timeout=10_000)
    reason.fill(expected_reason)
    button_name = "Save revised selection" if saved.count() else "Save exact selection"
    page.get_by_role("button", name=button_name, exact=True).click()
    page.get_by_text(
        "Selected model and reason saved as an exact immutable revision.", exact=True
    ).wait_for(timeout=30_000)
    saved = page.locator(".distribution-decision-record")
    saved.wait_for(state="visible", timeout=10_000)
    if (
        saved.locator("p").inner_text().strip() != expected_reason
        or page.get_by_role("button", name="Normal edit selection", exact=True).get_attribute(
            "aria-pressed"
        )
        != "true"
    ):
        raise RuntimeError("distribution selection did not preserve the explicit model and reason")


def _capture_distribution_detail(
    page: Page,
    locator: Locator,
    path: Path,
    *,
    region: str,
) -> None:
    locator.scroll_into_view_if_needed()
    page.wait_for_timeout(100)
    locator.screenshot(path=str(path))


def _capture_modeling_distribution(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_detail_crops: bool = False,
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for viewport_index, (width, height) in enumerate((*VIEWPORTS, *WIDE_VIEWPORTS)):
        page = _new_page(browser, base_url, width, height)
        try:
            _prepare_modeling_process(
                page,
                base_url,
                verify_data_reload=viewport_index == 0,
            )
            analysis = _open_scalar_distribution_workbench(page)
            trigger = page.get_by_role("button", name="Distribution analysis", exact=True)

            if viewport_index == 0:
                page.wait_for_function(
                    "() => document.activeElement?.id === 'scalar-distribution-analysis'",
                    timeout=10_000,
                )
                page.keyboard.press("Escape")
                analysis.wait_for(state="hidden", timeout=10_000)
                page.wait_for_function(
                    """() => document.activeElement?.classList.contains('modeling-analysis-trigger')""",
                    timeout=10_000,
                )
                trigger.click()
                analysis = _open_scalar_distribution_workbench(page)
                _ensure_scalar_distribution_decision(page)

                page.reload()
                page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
                page.locator(".modeling-work-title h1").get_by_text(
                    STAGE_HEADINGS["process"], exact=True
                ).wait_for(timeout=30_000)
                _wait_modeling_process_panel(page)
                page.wait_for_function(
                    """expected => {
                      const source = document.querySelector('.process-band-source');
                      const rows = document.querySelectorAll(
                        '.modeling-workspace-rail .curve-row-label'
                      );
                      return source?.textContent?.trim() === expected && rows.length === 3;
                    }""",
                    arg=PROCESS_SOURCE_VISIBLE_IDENTITY,
                    timeout=30_000,
                )
                analysis = _open_scalar_distribution_workbench(page)
                if (
                    page.get_by_role(
                        "button", name="Normal edit selection", exact=True
                    ).get_attribute("aria-pressed")
                    != "true"
                    or page.locator(".distribution-decision-record p").inner_text().strip()
                    != "Normal selected explicitly for bounded comparison; recommendation remains separate."
                ):
                    raise RuntimeError(
                        "distribution selection did not read back after a full page reload"
                    )
            else:
                _ensure_scalar_distribution_decision(page)

            path = output / f"modeling-distribution-{width}x{height}.png"
            _capture(page, path, width, height)

            geometry = page.evaluate(
                """() => {
                  const analysis = document.querySelector('#scalar-distribution-analysis');
                  const sheet = document.querySelector('.distribution-analysis-sheet');
                  const workspace = document.querySelector('.modeling-workspace-shell');
                  const background = workspace?.querySelector('.modeling-split-workspace');
                  const tableScroll = document.querySelector('.distribution-table-scroll');
                  const lastCandidate = document.querySelector(
                    '.distribution-candidate-table tbody tr:last-child'
                  );
                  const decisionSurface = document.querySelector(
                    '.distribution-decision-record, .distribution-decision-note'
                  );
                  const plot = document.querySelector('.persistent-modeling-plot');
                  if (!analysis || !sheet || !workspace || !background || !tableScroll || !lastCandidate || !plot) return null;
                  const analysisBox = analysis.getBoundingClientRect();
                  const sheetBox = sheet.getBoundingClientRect();
                  const workspaceBox = workspace.getBoundingClientRect();
                  const plotBox = plot.getBoundingClientRect();
                  const lastCandidateBox = lastCandidate.getBoundingClientRect();
                  const candidateViewportBottom = decisionSurface
                    ? decisionSurface.getBoundingClientRect().top
                    : analysisBox.bottom;
                  return {
                    cssViewport: `${innerWidth}x${innerHeight}`,
                    devicePixelRatio,
                    browserZoomPercent: Math.round((outerWidth / innerWidth) * 100),
                    screen: `${screen.width}x${screen.height}`,
                    analysis: {
                      left: analysisBox.left,
                      right: analysisBox.right,
                      top: analysisBox.top,
                      bottom: analysisBox.bottom,
                      width: analysisBox.width,
                      height: analysisBox.height,
                    },
                    workspace: {
                      width: workspaceBox.width,
                      height: workspaceBox.height,
                      sheetWidth: sheetBox.width,
                      sheetHeight: sheetBox.height,
                    },
                    backgroundInert:
                      background.inert && background.getAttribute('aria-hidden') === 'true',
                    preservedProcessPlot: { width: plotBox.width, height: plotBox.height },
                    candidateRowsVisible:
                      lastCandidateBox.top >= analysisBox.top
                      && lastCandidateBox.bottom <= candidateViewportBottom + 1,
                    pageOverflow: document.documentElement.scrollWidth
                      - document.documentElement.clientWidth,
                    tableLocalOverflow: tableScroll.scrollWidth - tableScroll.clientWidth,
                  };
                }"""
            )
            if not isinstance(geometry, dict):
                raise RuntimeError(f"distribution geometry is unavailable for {path.name}")
            analysis_geometry = geometry["analysis"]
            if (
                geometry["pageOverflow"] != 0
                or analysis_geometry["left"] < 0
                or analysis_geometry["right"] > width + 1
                or analysis_geometry["top"] < 0
                or analysis_geometry["bottom"] > height + 1
                or analysis_geometry["height"] < 360
                or abs(
                    geometry["workspace"]["sheetWidth"]
                    - geometry["workspace"]["width"]
                )
                > 2
                or abs(
                    geometry["workspace"]["sheetHeight"]
                    - geometry["workspace"]["height"]
                )
                > 2
                or geometry["preservedProcessPlot"]["height"] < 280
                or not geometry["candidateRowsVisible"]
                or not geometry["backgroundInert"]
            ):
                raise RuntimeError(
                    f"distribution workbench is clipped or overflowing for {path.name}: {geometry}"
                )
            measurements.append(geometry)

            if include_detail_crops and (width, height) in (VIEWPORTS[2], *WIDE_VIEWPORTS):
                detail_locators = {
                    "header": page.locator(".distribution-drawer-heading"),
                    "table": page.locator(".distribution-candidate-table"),
                }
                for region, locator in detail_locators.items():
                    _capture_distribution_detail(
                        page,
                        locator,
                        output
                        / f"modeling-distribution-{region}-from-{width}x{height}-crop.png",
                        region=region,
                    )
                page.get_by_role("button", name="Normal edit selection", exact=True).click()
                selection_editor = page.locator(".distribution-decision-editor")
                selection_editor.wait_for(state="visible", timeout=10_000)
                _capture_distribution_detail(
                    page,
                    selection_editor,
                    output
                    / f"modeling-distribution-selection-form-from-{width}x{height}-crop.png",
                    region="selection-form",
                )
                page.get_by_role("button", name="Cancel", exact=True).click()
                page.locator(".distribution-drawer-state").get_by_role(
                    "button", name="Close", exact=True
                ).click()
                analysis.wait_for(state="hidden", timeout=10_000)
                for region, locator in {
                    "navigator": page.locator(".modeling-workspace-rail"),
                    "graph": page.locator(".persistent-modeling-plot"),
                }.items():
                    _capture_distribution_detail(
                        page,
                        locator,
                        output
                        / f"modeling-distribution-{region}-from-{width}x{height}-crop.png",
                        region=region,
                    )
        finally:
            page.context.close()
    return measurements


def _list_processing_outputs(page: Page, base_url: str) -> list[dict[str, object]]:
    """List immutable outputs through the capture page's authenticated session."""
    payload = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            window.localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const response = await fetch(`${baseUrl}/api/v1/processing-outputs`, {
            headers: {
              "Accept": "application/json",
              "Authorization": `Bearer ${config.accessToken}`,
            },
          });
          if (!response.ok) throw new Error(`cannot list Processing Outputs: ${response.status}`);
          return await response.json();
        }""",
        {"baseUrl": base_url},
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError(f"Processing Output list has an unexpected shape: {payload!r}")
    items = payload["items"]
    if any(not isinstance(item, dict) for item in items):
        raise RuntimeError("Processing Output list contains a non-object item")
    return [item for item in items if isinstance(item, dict)]


def _has_processing_output_revision(
    item: dict[str, object], output_id: object, revision_id: object
) -> bool:
    if item.get("processing_output_id") != output_id:
        return False
    revision = item.get("current_revision")
    return isinstance(revision, dict) and revision.get("id") == revision_id


def _process_session_pins(page: Page) -> tuple[dict[str, object], dict[str, object]]:
    session = _modeling_session(page)
    source = session.get("testData")
    profile = session.get("mappingProfile")
    if not isinstance(source, dict) or not isinstance(profile, dict):
        raise RuntimeError(f"Process capture session is missing exact source/profile pins: {session!r}")
    for name, pin in (("source", source), ("profile", profile)):
        if not all(isinstance(pin.get(key), str) and pin.get(key) for key in ("id", "revisionId")):
            raise RuntimeError(f"Process capture {name} pin is not an exact id/revision pair: {pin!r}")
    return source, profile


def _is_fit_method_id(method_id: object) -> bool:
    value = str(method_id or "")
    return any(token in value for token in ("hardening_fit", "prony_fit", "fit_compare"))


def _is_non_fit_process_output(output: dict[str, object]) -> bool:
    if output.get("fit_decision") is not None:
        return False
    steps = output.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"Process output has no ordered steps: {output.get('processing_output_id')!r}")
    for step in steps:
        if not isinstance(step, dict):
            raise RuntimeError(f"Process output contains a malformed step: {output.get('processing_output_id')!r}")
        if _is_fit_method_id(step.get("method_id")):
            return False
    return True


def _matching_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    source_id = source["id"]
    source_revision = source["revisionId"]
    profile_id = profile["id"]
    profile_revision = profile["revisionId"]
    matching: list[dict[str, object]] = []
    for output in outputs:
        output_source = output.get("source_document")
        output_profile = output.get("mapping_profile")
        if not isinstance(output_source, dict) or not isinstance(output_profile, dict):
            continue
        if (
            output_source.get("aggregate_id") == source_id
            and output_source.get("revision_id") == source_revision
            and output_profile.get("aggregate_id") == profile_id
            and output_profile.get("revision_id") == profile_revision
            and _is_non_fit_process_output(output)
        ):
            matching.append(output)
    return matching


_PROCESS_CAPTURE_LABELS = frozenset(
    {
        "Robust elastic",
        "Chord elastic",
        "Elastic window 0.0005-0.0025",
    }
)


def _as_float(value: object, default: float = 0.0) -> float:
    """Read a browser-measured scalar without laundering arbitrary objects."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _matching_capture_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    """Keep only the exact Process siblings owned by this capture journey."""

    return [
        output
        for output in _matching_process_outputs(outputs, source, profile)
        if output.get("label") in _PROCESS_CAPTURE_LABELS
    ]


def _filter_capture_process_output_list(
    page: Page,
    source: dict[str, object],
    profile: dict[str, object],
) -> None:
    """Keep Fit-source outputs out of the Process sibling disclosure during capture."""

    expected_source = {
        "aggregate_id": source["id"],
        "revision_id": source["revisionId"],
    }
    expected_profile = {
        "aggregate_id": profile["id"],
        "revision_id": profile["revisionId"],
    }

    def route_outputs(route: Route) -> None:
        if route.request.method != "GET":
            route.continue_()
            return
        response = route.fetch()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            payload["items"] = [
                item
                for item in payload["items"]
                if isinstance(item, dict)
                and item.get("label") in _PROCESS_CAPTURE_LABELS
                and item.get("source_document") == expected_source
                and item.get("mapping_profile") == expected_profile
            ]
        route.fulfill(response=response, json=payload)

    page.route("**/api/v1/processing-outputs", route_outputs)


def _assert_no_mis_pinned_capture_labels(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> None:
    """Reject capture-named outputs that belong to another exact input/profile."""
    expected_pins = {
        "source_document": {
            "aggregate_id": source["id"],
            "revision_id": source["revisionId"],
        },
        "mapping_profile": {
            "aggregate_id": profile["id"],
            "revision_id": profile["revisionId"],
        },
    }
    for output in outputs:
        if output.get("label") not in {
            "Robust elastic",
            "Chord elastic",
            "Elastic window 0.0005-0.0025",
        }:
            continue
        if not _is_non_fit_process_output(output):
            raise RuntimeError(
                f"Capture-named Process output is Fit or malformed: {output.get('processing_output_id')!r}"
            )
        if (
            output.get("source_document") != expected_pins["source_document"]
            or output.get("mapping_profile") != expected_pins["mapping_profile"]
        ):
            raise RuntimeError(
                f"Capture-named Process output has wrong exact pins: {output.get('processing_output_id')!r}"
            )


def _assert_process_output_configuration(
    output: dict[str, object],
    source: dict[str, object],
    profile: dict[str, object],
    *,
    expected_label: str,
    expected_method: str,
    expected_minimum: float,
    expected_maximum: float,
) -> None:
    output_id = output.get("processing_output_id")
    revision = output.get("current_revision")
    output_source = output.get("source_document")
    output_profile = output.get("mapping_profile")
    if not isinstance(output_id, str) or not output_id:
        raise RuntimeError(f"Saved Process output has no stable identity: {output!r}")
    if (
        not isinstance(revision, dict)
        or revision.get("revision_no") != 1
        or not isinstance(revision.get("id"), str)
        or not revision.get("id")
    ):
        raise RuntimeError(f"Saved Process output is not exact immutable r1: {output_id!r} {revision!r}")
    if output.get("fit_decision") is not None or not _is_non_fit_process_output(output):
        raise RuntimeError(f"Saved Process sibling must be non-Fit: {output_id!r}")
    if output_source != {
        "aggregate_id": source["id"],
        "revision_id": source["revisionId"],
    } or output_profile != {
        "aggregate_id": profile["id"],
        "revision_id": profile["revisionId"],
    }:
        raise RuntimeError(f"Saved Process sibling has wrong exact pins: {output_id!r}")
    if output.get("label") != expected_label:
        raise RuntimeError(
            f"Saved Process sibling label drifted: expected {expected_label!r}, got {output.get('label')!r}"
        )
    steps = output.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"Saved Process sibling has no ordered steps: {output_id!r}")
    modulus_steps = [
        step for step in steps
        if isinstance(step, dict) and step.get("method_id") == "metal.elastic_modulus"
    ]
    if len(modulus_steps) != 1:
        raise RuntimeError(f"Saved Process sibling must have one elastic modulus step: {output_id!r}")
    modulus = modulus_steps[0]
    if modulus.get("method_version") != "1.0.0" or not isinstance(modulus.get("options"), dict):
        raise RuntimeError(f"Saved Process sibling elastic step identity drifted: {output_id!r}")
    options = modulus["options"]
    if options.get("method") != expected_method:
        raise RuntimeError(
            f"Saved Process sibling method drifted: expected {expected_method!r}, got {options.get('method')!r}"
        )
    if (
        isinstance(options.get("minimum_strain"), bool)
        or not isinstance(options.get("minimum_strain"), (int, float))
        or float(options["minimum_strain"]) != expected_minimum
        or isinstance(options.get("maximum_strain"), bool)
        or not isinstance(options.get("maximum_strain"), (int, float))
        or float(options["maximum_strain"]) != expected_maximum
    ):
        raise RuntimeError(f"Saved Process sibling range drifted: {output_id!r} {options!r}")


def _assert_resumable_modeling_process_outputs(
    outputs: list[dict[str, object]],
    source: dict[str, object],
    profile: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Validate the one exact three-output state produced by the interrupted capture."""
    if len(outputs) != 3:
        raise RuntimeError(
            "Modeling Process resume requires exactly three matching outputs: "
            f"got {len(outputs)}"
        )
    labels = [output.get("label") for output in outputs]
    expected_labels = {
        "Robust elastic",
        "Chord elastic",
        "Elastic window 0.0005-0.0025",
    }
    if (
        any(not isinstance(label, str) for label in labels)
        or set(labels) != expected_labels
        or len(set(labels)) != 3
    ):
        raise RuntimeError(f"Interrupted Process outputs have wrong exact labels: {labels!r}")
    output_ids = [output.get("processing_output_id") for output in outputs]
    if (
        any(not isinstance(output_id, str) or not output_id for output_id in output_ids)
        or len({output_id for output_id in output_ids if isinstance(output_id, str)}) != 3
    ):
        raise RuntimeError(
            "Interrupted Process outputs have duplicate or missing identities: "
            f"{output_ids!r}"
        )
    revision_ids: list[object] = []
    for output in outputs:
        revision = output.get("current_revision")
        revision_ids.append(revision.get("id") if isinstance(revision, dict) else None)
    if (
        any(not isinstance(revision_id, str) or not revision_id for revision_id in revision_ids)
        or len({revision_id for revision_id in revision_ids if isinstance(revision_id, str)}) != 3
    ):
        raise RuntimeError(
            "Interrupted Process outputs have duplicate or missing revision identities: "
            f"{revision_ids!r}"
        )
    configurations: dict[str, dict[str, str | float]] = {
        "Robust elastic": {
            "expected_method": "robust_huber",
            "expected_minimum": 0.0002,
            "expected_maximum": 0.002,
        },
        "Chord elastic": {
            "expected_method": "chord",
            "expected_minimum": 0.001,
            "expected_maximum": 0.003,
        },
        "Elastic window 0.0005-0.0025": {
            "expected_method": "robust_huber",
            "expected_minimum": 0.0005,
            "expected_maximum": 0.0025,
        },
    }
    by_label: dict[str, dict[str, object]] = {}
    for output in outputs:
        label = output.get("label")
        if not isinstance(label, str):
            raise RuntimeError(f"Interrupted Process output label is not text: {output!r}")
        expected = configurations[label]
        _assert_process_output_configuration(
            output,
            source,
            profile,
            expected_label=label,
            expected_method=str(expected["expected_method"]),
            expected_minimum=float(expected["expected_minimum"]),
            expected_maximum=float(expected["expected_maximum"]),
        )
        by_label[label] = output
    return by_label


def _assert_modeling_process_saved_rows(
    page: Page,
    *,
    require_current_and_history: bool = False,
) -> list[str]:
    details = page.locator("details.process-saved-results")
    details.wait_for(state="visible", timeout=30_000)
    if details.get_attribute("open") is None:
        details.locator(":scope > summary").click()
    rows = details.locator(".process-comparison-row")
    rows.nth(1).wait_for(timeout=30_000)
    for scalar in ("210.0 GPa", "120.0 GPa"):
        rows.filter(has_text=scalar).first.wait_for(timeout=30_000)
    row_text = rows.all_inner_texts()
    if len(row_text) != 2:
        raise RuntimeError(f"Saved Process comparison must contain exactly two rows: {row_text}")
    for label, method, range_text, scalar in (
        ("Robust elastic", "Auto robust", "0.0002–0.002", "210.0 GPa"),
        ("Chord elastic", "Chord", "0.001–0.003", "120.0 GPa"),
    ):
        matching = [text for text in row_text if label in text]
        if (
            len(matching) != 1
            or method not in matching[0]
            or range_text not in matching[0]
            or scalar not in matching[0]
            or "r1" not in matching[0]
        ):
            raise RuntimeError(f"Saved Process row is missing exact {label} evidence: {row_text}")
    if require_current_and_history:
        robust = next(text for text in row_text if "Robust elastic" in text)
        chord = next(text for text in row_text if "Chord elastic" in text)
        if "history" not in robust or "current" not in chord:
            raise RuntimeError(f"Saved Process current/history pointers drifted: {row_text}")
    return row_text


def _is_modeling_process_saved_result_response(response: object) -> bool:
    """Identify one lazy saved-result content response from the Process disclosure."""
    request = getattr(response, "request", None)
    path = urlsplit(str(getattr(response, "url", ""))).path.rstrip("/")
    return (
        str(getattr(request, "method", "")).upper() == "GET"
        and re.fullmatch(r"/api/v1/processing-outputs/[^/]+/content", path) is not None
    )


def _wait_for_modeling_process_saved_rows_refresh(page: Page, summary: Locator) -> None:
    """Wait for the toggle-triggered content requests and their settled render."""
    content_responses: dict[str, object] = {}

    def record_response(response: object) -> None:
        if _is_modeling_process_saved_result_response(response):
            content_responses.setdefault(str(getattr(response, "url", "")), response)

    page.on("response", record_response)
    try:
        # The native disclosure toggle starts all three lazy content requests.
        # Require the first response before observing the settled DOM so a cached
        # ready render from before the toggle cannot satisfy the state check.
        with page.expect_response(
            _is_modeling_process_saved_result_response,
            timeout=30_000,
        ) as first_response_info:
            summary.click()
        first_response = first_response_info.value
        record_response(first_response)
        # The disclosure starts all three requests together.  Polling the real
        # disclosure DOM after the first response both proves that the render
        # consumed the responses and pumps Playwright's event loop so the
        # response listener observes every remaining callback.  A second
        # response wait would reintroduce the missed-event race.
        page.wait_for_function(
            """() => {
              const details = document.querySelector('details.process-saved-results');
              const rows = [...document.querySelectorAll(
                'details.process-saved-results .process-comparison-row'
              )];
              return details instanceof HTMLDetailsElement
                && details.open
                && rows.length === 3
                && rows.every(row => !(row.textContent ?? '').includes('Loading saved result…'));
            }""",
            timeout=30_000,
        )
        if len(content_responses) != 3:
            raise RuntimeError(
                "Saved Process content refresh expected exactly three unique content "
                f"responses, got {len(content_responses)}: {sorted(content_responses)!r}"
            )
        responses = list(content_responses.values())
        failed = []
        for response in responses:
            status = getattr(response, "status", None)
            if (
                not bool(getattr(response, "ok", False))
                or not isinstance(status, int)
                or not 200 <= status < 300
            ):
                failed.append(response)
        if failed:
            statuses = [getattr(response, "status", "unknown") for response in failed]
            raise RuntimeError(
                "Saved Process content refresh returned a non-2xx response: "
                f"{statuses!r}"
            )
        # Keep the two-frame render boundary after response validation and
        # before the scalar/current-history assertions in the caller.
        page.evaluate(
            """async () => {
              await new Promise(requestAnimationFrame);
              await new Promise(requestAnimationFrame);
            }"""
        )
    finally:
        page.remove_listener("response", record_response)


def _assert_modeling_process_saved_rows_three(
    page: Page,
    *,
    current_label: str,
) -> list[str]:
    """Verify the primary journey's current result plus two immutable siblings."""
    details = page.locator("details.process-saved-results")
    details.wait_for(state="visible", timeout=30_000)
    rows = details.locator(".process-comparison-row")
    disclosure_was_open = details.get_attribute("open") is not None
    if not disclosure_was_open:
        _wait_for_modeling_process_saved_rows_refresh(
            page,
            details.locator(":scope > summary"),
        )
    else:
        page.wait_for_function(
            """() => {
              const rows = [...document.querySelectorAll(
                'details.process-saved-results .process-comparison-row'
              )];
              return rows.length === 3
                && rows.every(row => !(row.textContent ?? '').includes('Loading saved result…'));
            }""",
            timeout=30_000,
        )
    row_text = rows.all_inner_texts()
    if len(row_text) != 3:
        raise RuntimeError(f"Saved Process comparison must contain exactly three rows: {row_text}")
    for label, scalar in (
        ("Robust elastic", "210.0 GPa"),
        ("Chord elastic", "120.0 GPa"),
        (current_label, "210.0 GPa"),
    ):
        matching = [text for text in row_text if label in text]
        if len(matching) != 1 or scalar not in matching[0] or "r1" not in matching[0]:
            raise RuntimeError(f"Saved Process row is missing exact {label} evidence: {row_text}")
    current_rows = [text for text in row_text if "current" in text]
    if len(current_rows) != 1 or current_label not in current_rows[0]:
        raise RuntimeError(f"Saved Process current pointer drifted: {row_text}")
    if sum("history" in text for text in row_text) != 2:
        raise RuntimeError(f"Saved Process history rows drifted: {row_text}")
    return row_text


def _assert_modeling_process_table_geometry(page: Page) -> None:
    """Verify semantic Saved-results columns and row actions stay reachable."""
    layout = page.evaluate(
        """() => {
          const table = document.querySelector('details.process-saved-results[open] .process-comparison-table');
          if (!table) return { present: false };
          const details = table.closest('details');
          const ribbon = document.querySelector('.modeling-task-ribbon');
          const plot = document.querySelector('.persistent-modeling-plot');
          const rect = node => node?.getBoundingClientRect() ?? null;
          const inside = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(childBox && parentBox
              && childBox.left >= parentBox.left - 1
              && childBox.right <= parentBox.right + 1
              && childBox.top >= parentBox.top - 1
              && childBox.bottom <= parentBox.bottom + 1);
          };
          const insideHorizontally = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(childBox && parentBox
              && childBox.left >= parentBox.left - 1
              && childBox.right <= parentBox.right + 1);
          };
          const hitWithin = (owner, box) => {
            if (!box || box.width <= 0 || box.height <= 0) return false;
            const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
            return hit instanceof Element && (hit === owner || owner.contains(hit));
          };
          const rows = [...table.querySelectorAll('tbody tr')];
          const headers = [...table.querySelectorAll('thead th')].map(header => header.textContent?.trim() || '');
          const rowChecks = rows.map(row => {
            const cells = [...row.querySelectorAll(':scope > td')];
            const cellBoxes = cells.map(rect);
            const action = cells.at(-1)?.querySelector('button');
            const actionBox = rect(action);
            const horizontalOrder = cellBoxes.every((box, index) => !index || !box || !cellBoxes[index - 1] || box.left >= cellBoxes[index - 1].right - 1);
            return {
              cellCount: cells.length,
              rowHorizontallyContained: insideHorizontally(row, table)
                && insideHorizontally(row, details)
                && insideHorizontally(row, ribbon),
              horizontalOrder,
              actionVisible: Boolean(actionBox && actionBox.width > 0 && actionBox.height > 0),
              actionTopmost: Boolean(action && hitWithin(action, actionBox)),
              actionLabel: action?.textContent?.trim() || '',
            };
          });
          return {
            present: true,
            tableHorizontallyContained: insideHorizontally(table, details)
              && insideHorizontally(table, ribbon),
            headers,
            rowChecks,
          };
        }"""
    )
    if not isinstance(layout, dict) or not layout.get("present"):
        return
    expected_headers = ["Label", "Method", "Range", "Result", "Revision", "State", "Action"]
    if (
        layout.get("headers") != expected_headers
        or not layout.get("tableHorizontallyContained")
        or not isinstance(layout.get("rowChecks"), list)
        or not layout["rowChecks"]
    ):
        raise RuntimeError(f"Saved Process semantic table is not contained/reachable: {layout!r}")
    for row in layout["rowChecks"]:
        if (
            not isinstance(row, dict)
            or row.get("cellCount") != 7
            or not row.get("rowHorizontallyContained")
            or not row.get("horizontalOrder")
            or row.get("actionLabel") not in {"Retry", "Use settings"}
            or not row.get("actionVisible")
        ):
            raise RuntimeError(f"Saved Process semantic row/action is not reachable: {layout!r}")


def _assert_modeling_process_saved_rows_reachable(page: Page) -> None:
    """Reject Process captures where the graph paints over saved-row actions."""
    _assert_modeling_process_table_geometry(page)
    actions = page.locator(
        "details.process-saved-results[open] .process-comparison-row button"
    )
    if actions.count() != 3:
        raise RuntimeError("Saved Process reachability requires exactly three row actions")
    if actions.all_inner_texts() != ["Use settings"] * 3:
        raise RuntimeError("Saved Process rows must expose exactly three Use settings actions")
    for index in range(actions.count()):
        action = actions.nth(index)
        action.locator("xpath=ancestor::tr").scroll_into_view_if_needed()
        action.focus()
        page.wait_for_timeout(50)
        reachability = action.evaluate(
            """node => {
              const row = node.closest('tr');
              const ribbon = node.closest('.modeling-task-ribbon');
              const plot = document.querySelector('.persistent-modeling-plot');
              const box = node.getBoundingClientRect();
              const rowBox = row?.getBoundingClientRect();
              const ribbonBox = ribbon?.getBoundingClientRect();
              const plotBox = plot?.getBoundingClientRect();
              const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
              const reachable = Boolean(row && ribbon && plot && ribbonBox && plotBox
                && rowBox
                && rowBox.left >= ribbonBox.left - 1
                && rowBox.right <= ribbonBox.right + 1
                && rowBox.top >= ribbonBox.top - 1
                && rowBox.bottom <= ribbonBox.bottom + 1
                && rowBox.bottom <= plotBox.top + 1
                && box.top >= ribbonBox.top - 1
                && box.bottom <= ribbonBox.bottom + 1
                && hit && (hit === node || node.contains(hit))
                && document.activeElement === node);
              const compact = value => value ? {
                left: value.left, right: value.right, top: value.top,
                bottom: value.bottom, width: value.width, height: value.height,
              } : null;
              return {
                reachable,
                row: compact(rowBox),
                action: compact(box),
                ribbon: compact(ribbonBox),
                plot: compact(plotBox),
                hit: hit?.textContent?.trim() || hit?.tagName || null,
                focused: document.activeElement === node,
                scrollTop: ribbon?.scrollTop ?? null,
              };
            }"""
        )
        if not isinstance(reachability, dict) or not reachability.get("reachable"):
            raise RuntimeError(
                "Saved Process row "
                f"{index + 1} action is not reachable after local scrolling: {reachability!r}"
            )
    checks = page.evaluate(
        """() => {
          const rows = [...document.querySelectorAll(
            'details.process-saved-results[open] .process-comparison-row'
          )];
          const details = document.querySelector('details.process-saved-results[open]');
          const region = details?.querySelector('.process-comparison-region');
          const ribbon = document.querySelector('.modeling-task-ribbon');
          const plot = document.querySelector('.persistent-modeling-plot');
          const heading = plot?.querySelector(':scope > .section-heading');
          const toolbar = plot?.querySelector(':scope > .modeling-plot-toolbar');
          const emptyPlot = plot?.querySelector(':scope > .modeling-plot-empty');
          const rect = node => node?.getBoundingClientRect() ?? null;
          const plotBox = rect(plot);
          const visible = node => {
            const box = rect(node);
            return Boolean(box && box.width > 0 && box.height > 0);
          };
          const inside = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(
              childBox && parentBox
                && childBox.left >= parentBox.left - 1
                && childBox.right <= parentBox.right + 1
                && childBox.top >= parentBox.top - 1
                && childBox.bottom <= parentBox.bottom + 1,
            );
          };
          const insideHorizontally = (child, parent) => {
            const childBox = rect(child);
            const parentBox = rect(parent);
            return Boolean(
              childBox && parentBox
                && childBox.left >= parentBox.left - 1
                && childBox.right <= parentBox.right + 1,
            );
          };
          const hitWithin = (owner, rect) => {
            if (!rect || rect.width <= 0 || rect.height <= 0) return false;
            const hit = document.elementFromPoint(
              rect.left + rect.width / 2,
              rect.top + rect.height / 2,
            );
            return hit instanceof Element && (hit === owner || owner.contains(hit));
          };
          return rows.map((row) => {
            const rowRect = row.getBoundingClientRect();
            const action = row.querySelector('button');
            const actionRect = action?.getBoundingClientRect() ?? null;
            return {
              label: row.textContent?.trim() || '',
              rowTopmost: hitWithin(row, rowRect),
              rowContained: inside(row, region) && inside(row, details) && inside(row, ribbon),
              rowAbovePlot: Boolean(plot && rowRect.bottom <= plot.getBoundingClientRect().top + 1),
              actionLabel: action?.textContent?.trim() || '',
              actionVisible: Boolean(actionRect && actionRect.width > 0 && actionRect.height > 0),
              actionEnabled: action instanceof HTMLButtonElement && !action.disabled,
              actionTopmost: Boolean(action && hitWithin(action, actionRect)),
            };
          }).concat([{
            layout: true,
            rowCount: rows.length,
            localScrollReady: Boolean(
              region
                && region.clientWidth >= region.scrollWidth - 1
                && ribbon
                && ribbon.clientWidth >= ribbon.scrollWidth - 1
                && (ribbon.scrollHeight <= ribbon.clientHeight + 1
                  || ['auto', 'scroll'].includes(getComputedStyle(ribbon).overflowY)),
            ),
            disclosureHorizontallyContained: insideHorizontally(details, ribbon),
            ribbonAbovePlot: Boolean(
              ribbon && plot
                && ribbon.getBoundingClientRect().bottom <= plot.getBoundingClientRect().top + 1,
            ),
            plotUseful: Boolean(
              visible(plot)
                && plotBox
                && plotBox.width >= 320
                && plotBox.height >= 240,
            ),
            plotHeadingVisible: visible(heading),
            plotHeadingTopmost: Boolean(heading && hitWithin(heading, rect(heading))),
            plotToolbarExists: Boolean(toolbar),
            plotToolbarVisible: visible(toolbar),
            plotToolbarTopmost: Boolean(toolbar && hitWithin(toolbar, rect(toolbar))),
            plotToolbarButtons: [...(toolbar?.querySelectorAll('button') ?? [])]
              .filter(button => ['Reset view', 'Pan', 'Select range'].includes(button.textContent?.trim() || ''))
              .map(button => ({
                label: button.textContent?.trim() || '',
                visible: visible(button),
                enabled: button instanceof HTMLButtonElement && !button.disabled,
                topmost: hitWithin(button, rect(button)),
              })),
            plotEmptyVisible: visible(emptyPlot),
            plotEmptyTopmost: Boolean(emptyPlot && hitWithin(emptyPlot, rect(emptyPlot))),
            plotEmptyContained: inside(emptyPlot, plot),
            plotEmptyMessage: emptyPlot?.querySelector(':scope > strong')?.textContent?.trim() || '',
            plotEmptyInstruction: emptyPlot?.querySelector(':scope > p')?.textContent?.trim() || '',
          }]);
        }"""
    )
    if not isinstance(checks, list) or len(checks) != 4:
        raise RuntimeError(f"Saved Process reachability check found {checks!r}")
    layout = checks[-1]
    if (
        not isinstance(layout, dict)
        or layout.get("layout") is not True
        or layout.get("rowCount") != 3
        or not layout.get("localScrollReady")
        or not layout.get("disclosureHorizontallyContained")
        or not layout.get("ribbonAbovePlot")
        or not layout.get("plotUseful")
        or not layout.get("plotHeadingVisible")
        or not layout.get("plotHeadingTopmost")
    ):
        raise RuntimeError(f"Saved Process disclosure or persistent plot is not contained/reachable: {checks!r}")
    if layout.get("plotToolbarExists"):
        if not layout.get("plotToolbarVisible") or not layout.get("plotToolbarTopmost"):
            raise RuntimeError(f"Saved Process plot toolbar is not visible/reachable: {checks!r}")
        toolbar_buttons = layout.get("plotToolbarButtons")
        if (
            not isinstance(toolbar_buttons, list)
            or len(toolbar_buttons) != 3
            or any(
                not isinstance(button, dict)
                or not button.get("visible")
                or not button.get("enabled")
                or not button.get("topmost")
                for button in toolbar_buttons
            )
        ):
            raise RuntimeError(f"Saved Process plot toolbar controls are not reachable: {checks!r}")
    else:
        if (
            not layout.get("plotEmptyVisible")
            or not layout.get("plotEmptyTopmost")
            or not layout.get("plotEmptyContained")
            or layout.get("plotEmptyMessage")
            != "The graph stays here while you prepare the curves."
            or layout.get("plotEmptyInstruction")
            != PROCESS_NO_PREVIEW_SAVED_INSTRUCTION
        ):
            raise RuntimeError(f"Saved Process reload plot is missing its honest no-preview state: {checks!r}")


def _patch_capture_processing_output_pointer(
    page: Page, output: dict[str, object]
) -> None:
    revision = output.get("current_revision")
    output_id = output.get("processing_output_id")
    if not isinstance(revision, dict) or not isinstance(output_id, str):
        raise RuntimeError(f"Cannot patch capture pointer from malformed output: {output!r}")
    pointer = {
        "id": output_id,
        "revisionId": revision.get("id"),
        "label": output.get("label"),
        "revisionNo": revision.get("revision_no"),
    }
    if not isinstance(pointer["revisionId"], str) or pointer["revisionNo"] != 1:
        raise RuntimeError(f"Cannot patch capture pointer from non-r1 output: {output!r}")
    page.evaluate(
        """pointer => {
          const key = "cmp.modeling.recent-session.v4";
          const raw = window.sessionStorage.getItem(key);
          if (!raw) throw new Error("Modeling session v4 is missing before pointer patch");
          const session = JSON.parse(raw);
          session.processingOutput = pointer;
          window.sessionStorage.setItem(key, JSON.stringify(session));
        }""",
        pointer,
    )


def _assert_capture_processing_output_pointer(
    page: Page, output: dict[str, object]
) -> None:
    """Require session state to pin the exact immutable output after recovery."""
    revision = output.get("current_revision")
    output_id = output.get("processing_output_id")
    if not isinstance(revision, dict) or not isinstance(output_id, str):
        raise RuntimeError(f"Cannot verify capture pointer from malformed output: {output!r}")
    expected = {
        "id": output_id,
        "revisionId": revision.get("id"),
        "label": output.get("label"),
        "revisionNo": revision.get("revision_no"),
    }
    pointer = page.evaluate(
        """() => {
          const raw = window.sessionStorage.getItem("cmp.modeling.recent-session.v4");
          if (!raw) throw new Error("Modeling session v4 is missing after pointer restore");
          return JSON.parse(raw).processingOutput || null;
        }"""
    )
    if pointer != expected:
        raise RuntimeError(f"Capture pointer did not restore the exact current output: {pointer!r}")


def _save_exact_fit_selection(
    page: Page,
    *,
    allow_expected_exact_restore_failure: bool = False,
    candidate_key: str | None = None,
    require_warning: bool = True,
) -> None:
    """Save the selected Fit output and leave the workflow on the Fit stage."""
    _open_modeling_stage(page, "fit")
    page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
    page.locator(".modeling-work-title h1").get_by_text(
        STAGE_HEADINGS["fit"], exact=True
    ).wait_for(timeout=30_000)
    if parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]:
        raise RuntimeError(f"Fit selection started on an unexpected route: {page.url}")
    show_settings = page.get_by_role("button", name="Show current-stage settings", exact=True)
    if show_settings.count():
        show_settings.click()
    trigger, _body, candidate_table = _open_fit_evidence(page)
    _assert_fit_candidate_surface(page, candidate_table)
    if candidate_key is None:
        _select_warned_fit_candidate(candidate_table)
    else:
        _select_exact_fit_candidate(candidate_table, candidate_key=candidate_key)
    page.get_by_role("textbox", name="Candidate selection reason").fill(
        "Best agreement over the measured strain range."
    )
    warning_acknowledgement = page.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning"
    )
    if warning_acknowledgement.count():
        warning_acknowledgement.check()
    elif require_warning:
        raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
    _assert_fit_selected_evidence(page)
    previous_pointer = _modeling_session(page).get("processingOutput")
    save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
    page.wait_for_function(
        """() => [...document.querySelectorAll("button")].some(
            button => button.textContent?.trim() === "Save fit & continue"
              && !button.disabled
        )""",
        timeout=30_000,
    )
    _close_fit_evidence(page, trigger)
    save_candidate.click()
    saved_current = page.locator(".fit-surface-state").get_by_text(
        "Saved current", exact=True
    )
    if allow_expected_exact_restore_failure:
        try:
            wait_argument = {
                "allowError": allow_expected_exact_restore_failure,
                "error": EXPECTED_EXACT_FIT_RESTORE_ERROR,
            }
            page.wait_for_function(
                """expected => {
                  const state = document.querySelector('.fit-surface-state');
                  const saved = state?.textContent?.trim() === 'Saved current';
                  const expectedError = expected.error;
                  const error = [...document.querySelectorAll('.error-banner')]
                    .some(element => element.textContent?.trim().startsWith(expectedError));
                  return Boolean(saved || (expected.allowError && error));
                }""",
                arg=wait_argument,
                timeout=30_000,
            )
        except Exception as error:
            diagnostics = page.evaluate(
                """() => ({
                  state: [...document.querySelectorAll('.fit-surface-state')]
                    .filter(element => element.getClientRects().length)
                    .map(element => element.textContent?.trim()),
                  errors: [...document.querySelectorAll('.error-banner')]
                    .filter(element => element.getClientRects().length)
                    .map(element => element.textContent?.trim()),
                  url: window.location.href,
                })"""
            )
            raise RuntimeError(
                "Fit save did not reach its exact Saved current/error boundary: "
                f"allow_error={allow_expected_exact_restore_failure}, diagnostics={diagnostics!r}"
            ) from error
    else:
        saved_current.wait_for(timeout=30_000)
    if parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]:
        raise RuntimeError(f"Fit save unexpectedly navigated away from Fit: {page.url}")
    page.wait_for_function(
        """() => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          const pointer = JSON.parse(raw).processingOutput;
          return Boolean(
            pointer
              && typeof pointer.id === 'string'
              && pointer.id
              && typeof pointer.revisionId === 'string'
              && pointer.revisionId
          );
        }""",
        timeout=30_000,
    )
    pointer = _modeling_session(page).get("processingOutput")
    if not isinstance(pointer, dict) or not all(
        isinstance(pointer.get(key), str) and pointer.get(key)
        for key in ("id", "revisionId")
    ):
        raise RuntimeError(f"Fit save did not pin an exact session output pointer: {pointer!r}")
    if isinstance(previous_pointer, dict) and all(
        isinstance(previous_pointer.get(key), str) and previous_pointer.get(key)
        for key in ("id", "revisionId")
    ) and all(pointer.get(key) == previous_pointer.get(key) for key in ("id", "revisionId")):
        raise RuntimeError(
            f"Fit save did not advance to a new immutable output pointer: {pointer!r}"
        )
    error_banner = page.locator(".error-banner")
    if error_banner.count() and error_banner.is_visible():
        error_text = error_banner.inner_text().strip()
        if not allow_expected_exact_restore_failure or not error_text.startswith(
            EXPECTED_EXACT_FIT_RESTORE_ERROR
        ):
            raise RuntimeError(f"Fit selected-output save failed: {error_text}")


def _prepare_exact_metal_source_if_needed(page: Page) -> None:
    """Recover the exact metal model chain before entering target preview.

    A newly saved Fit Output intentionally starts without a Material Model IR or
    Neutral pin.  The Export page therefore opens on the bounded recovery
    surface.  Existing current sources render the three-pane target workspace
    directly, so this helper is a no-op in that case.  Native browser dialogs
    are dismissed and reported instead of being allowed to block the capture.
    """
    recovery_heading = page.get_by_role(
        "heading", name="Prepare selected model", exact=True
    )
    target = page.get_by_role("combobox", name="Solver target", exact=True)
    page.wait_for_function(
        """() => Boolean(
          [...document.querySelectorAll('h1, h2, h3')]
            .some(heading => heading.textContent?.trim() === 'Prepare selected model')
          || document.querySelector('[aria-label="Solver target"]')
        )""",
        timeout=30_000,
    )
    if not recovery_heading.count():
        target.wait_for(state="visible", timeout=30_000)
        return

    acknowledgement = page.get_by_role(
        "checkbox",
        name="I reviewed the extrapolated range used by this model.",
        exact=True,
    )
    acknowledgement.wait_for(state="visible", timeout=30_000)
    if acknowledgement.count() != 1:
        raise RuntimeError("Exact metal recovery must expose one bounded-extrapolation acknowledgement")
    if not acknowledgement.is_checked():
        acknowledgement.check()
    reason = page.get_by_role("textbox", name="Reason for preparing model", exact=True)
    reason.wait_for(state="visible", timeout=30_000)
    reason.fill(EXPORT_RECOVERY_REASON)
    prepare = page.get_by_role(
        "button", name="Prepare selected model", exact=True
    )
    if not prepare.count():
        # A pinned model can leave the recovery surface visible while only the
        # Neutral promotion needs retrying.  Reuse that immutable model rather
        # than creating another one.
        prepare = page.get_by_role("button", name="Retry preparation", exact=True)
    prepare.wait_for(state="visible", timeout=30_000)
    if prepare.is_disabled():
        raise RuntimeError("Exact metal recovery action stayed disabled after acknowledgement and reason")

    rejected_dialogs: list[str] = []

    def reject_dialog(dialog: Dialog) -> None:
        rejected_dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", reject_dialog)
    try:
        prepare.click()
        page.wait_for_function(
            """() => Boolean(
              document.querySelector('section.modeling-target-preview.export-workspace .export-workspace-grid [aria-label="Solver target"]')
              || document.querySelector('[role="alert"]')
            )""",
            timeout=30_000,
        )
    finally:
        page.remove_listener("dialog", reject_dialog)
    if rejected_dialogs:
        raise RuntimeError(f"Exact metal recovery raised a browser alert: {rejected_dialogs!r}")
    recovery_error = page.get_by_role("alert")
    if recovery_error.count() and recovery_error.first.is_visible():
        raise RuntimeError(
            f"Exact model/Neutral recovery failed: {recovery_error.first.inner_text().strip()}"
        )
    page.locator("section.modeling-target-preview.export-workspace").wait_for(
        state="visible", timeout=30_000
    )
    page.locator(".export-workspace-grid").wait_for(state="visible", timeout=30_000)
    target.wait_for(state="visible", timeout=30_000)


def _resolve_exact_material_record(page: Page, base_url: str) -> dict[str, str]:
    """Resolve the exact session Material to its current Materials Record."""

    outcome = page.evaluate(
        """async ({ baseUrl }) => {
          const config = JSON.parse(
            localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          const session = JSON.parse(
            sessionStorage.getItem("cmp.modeling.recent-session.v4") || "{}"
          );
          const material = session.material;
          if (!config.accessToken || !material?.id || !material?.revisionId) {
            throw new Error("exact Material session pointer is required");
          }
          const headers = {
            "Accept": "application/json",
            "Authorization": `Bearer ${config.accessToken}`,
          };
          const params = new URLSearchParams({
            kind: "material",
            object_id: material.id,
            revision_id: material.revisionId,
          });
          const response = await fetch(
            `${baseUrl}/api/v1/catalog/domain-bindings:resolve?${params}`,
            { headers },
          );
          const text = await response.text();
          if (!response.ok) {
            throw new Error(
              `resolve exact Material Record: ${response.status} ${text.slice(0, 500)}`
            );
          }
          const record = text ? JSON.parse(text) : null;
          if (!record?.record_id || !record?.record_revision_id) {
            throw new Error("exact Material revision has no current Materials Record binding");
          }
          return {
            record_id: record.record_id,
            record_revision_id: record.record_revision_id,
          };
        }""",
        {"baseUrl": base_url},
    )
    if (
        not isinstance(outcome, dict)
        or not isinstance(outcome.get("record_id"), str)
        or not isinstance(outcome.get("record_revision_id"), str)
    ):
        raise RuntimeError(f"unexpected exact Material Record resolution: {outcome!r}")
    return {
        "record_id": outcome["record_id"],
        "record_revision_id": outcome["record_revision_id"],
    }


def _prepare_exact_target_preview(
    page: Page,
    *,
    target_value: str = "abaqus/2025/kg_m_s",
    acknowledge: bool = True,
    create: bool = False,
) -> None:
    export_region = page.locator("section.modeling-target-preview.export-workspace")
    export_region.wait_for(state="visible", timeout=30_000)
    export_grid = export_region.locator(":scope > .export-workspace-grid")
    export_grid.wait_for(state="visible", timeout=30_000)
    target = export_grid.get_by_role("combobox", name="Solver target", exact=True)
    target.wait_for(timeout=30_000)
    if target_value == "abaqus/2025/kg_m_s":
        target.select_option("abaqus/2025/kg_m_s")
    else:
        target.select_option(target_value)
    advanced = page.locator("details.export-advanced-input")
    if advanced.count() != 1:
        raise RuntimeError("Export must expose exactly one native card options disclosure")
    summary = advanced.locator(":scope > summary")
    if summary.count() != 1:
        raise RuntimeError("Native card options disclosure must expose exactly one summary")
    summary.wait_for(state="visible", timeout=30_000)
    if summary.inner_text().strip() != "Native card options":
        raise RuntimeError("Native card options disclosure label drifted")
    if advanced.get_attribute("open") is None:
        summary.click()
    if advanced.get_attribute("open") is None:
        raise RuntimeError("Native card options disclosure did not open")
    native_name = page.get_by_role("textbox", name="Native material name", exact=True)
    native_name.wait_for(state="visible", timeout=30_000)
    if native_name.count() != 1:
        raise RuntimeError("Export must expose exactly one visible native material name input")
    native_name.fill("DP780_C1_REFERENCE")
    if advanced.get_attribute("open") is not None:
        summary.click()
    if advanced.get_attribute("open") is not None:
        raise RuntimeError("Native card options disclosure must close before C1")
    initial_primary = page.locator(".export-check .ux-button.primary:visible")
    if initial_primary.count() != 1:
        raise RuntimeError("Export task must expose exactly one visible primary action before C1")
    page.get_by_role("button", name="Run Export check", exact=True).click()
    page.wait_for_function(
        """() => {
          const visible = element => Boolean(
            element
              && element.getClientRects().length > 0
              && getComputedStyle(element).visibility !== "hidden"
              && getComputedStyle(element).display !== "none"
          );
          const terminalHeading = [...document.querySelectorAll(
            '.export-main .export-preview-state'
          )]
            .some(heading => visible(heading)
              && heading.textContent?.trim() === "Not created");
          const visibleAlert = [...document.querySelectorAll('[role="alert"]')]
            .some(alert => visible(alert));
          return terminalHeading || visibleAlert;
        }""",
        timeout=30_000,
    )
    preview_error = page.locator('[role="alert"]:visible')
    if preview_error.count():
        raise RuntimeError(f"Exact target preview failed: {preview_error.first.inner_text().strip()}")
    terminal_state = page.locator(".export-main .export-preview-state")
    terminal_state.wait_for(state="visible", timeout=30_000)
    page.get_by_label("Native preview", exact=True).locator("pre").wait_for(
        timeout=30_000
    )
    if terminal_state.count() != 1 or terminal_state.inner_text().strip() != "Not created":
        raise RuntimeError("Export check must expose the current not-created preview state")
    primary = page.locator(".export-check .ux-button.primary:visible")
    if primary.count() != 1:
        raise RuntimeError("Current Export task must expose exactly one visible primary action")
    create_button = page.get_by_role("button", name="Create solver card", exact=True)
    create_button.wait_for(state="visible", timeout=30_000)
    if create_button.count() != 1:
        raise RuntimeError(
            "Current preview must expose exactly one Create solver card action before delivery"
        )
    acknowledgement = page.get_by_role(
        "checkbox", name="Acknowledge mapped approximations", exact=True
    )
    acknowledgement.wait_for(state="visible", timeout=30_000)
    if acknowledgement.count() != 1:
        raise RuntimeError("Current preview must expose exactly one mapping acknowledgement control")
    if acknowledge:
        acknowledgement.check()
    elif acknowledgement.is_checked():
        acknowledgement.uncheck()
    status = page.locator(".export-check .export-status")
    status.wait_for(state="visible", timeout=30_000)
    expected_status = "Ready to create" if acknowledge else "Review required"
    page.wait_for_function(
        """expected => {
          const status = document.querySelector('.export-check .export-status');
          const create = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Create solver card');
          return Boolean(
            status
              && status.textContent?.trim() === expected
              && create
              && create.disabled === (expected === 'Review required')
          );
        }""",
        arg=expected_status,
        timeout=30_000,
    )
    if status.inner_text().strip() != expected_status:
        raise RuntimeError(
            f"Export preview status drifted: expected {expected_status!r}, got {status.inner_text()!r}"
        )
    should_be_disabled = not acknowledge
    if create_button.is_disabled() != should_be_disabled:
        state = "disabled" if create_button.is_disabled() else "enabled"
        expected_state = "disabled" if not acknowledge else "enabled"
        raise RuntimeError(
            f"Export preview Create solver card must be {expected_state}, got {state}"
        )
    if not create:
        if page.get_by_role("status").filter(has_text="Solver card created").count():
            raise RuntimeError("preview_only Export must not expose a delivered success status")
        if page.locator(".export-delivery-details").count():
            raise RuntimeError("preview_only Export must not expose a delivery receipt")
        if page.get_by_role("button", name="Open solver card", exact=True).count():
            raise RuntimeError("preview_only Export must not expose an Open solver card pointer")
        session = _modeling_session(page)
        if session.get("exportArtifact") is not None:
            raise RuntimeError("preview_only Export must not pin a delivered card pointer")
        _wait_for_settled(page)
        return
    page.wait_for_function(
        """() => ![...document.querySelectorAll("button")].some(
          button => button.textContent?.trim() === "Create solver card" && button.disabled
        )""",
        timeout=30_000,
    )
    if create_button.is_disabled():
        raise RuntimeError("UXC-06C2 Create solver card must be enabled after its exact acknowledgement")
    create_button.click()
    page.wait_for_function(
        """() => document.querySelector('[role="alert"]')
          || [...document.querySelectorAll('[role="status"]')].some(
            element => element.textContent?.includes("Solver card created")
          )""",
        timeout=30_000,
    )
    delivery_error = page.locator('[role="alert"]:visible')
    if delivery_error.count():
        messages = [message.strip() for message in delivery_error.all_inner_texts()]
        raise RuntimeError(f"UXC-06C2 delivery failed: {' | '.join(messages)}")
    delivery_status = page.get_by_role("status").filter(has_text="Solver card created")
    delivery_status.wait_for(timeout=30_000)
    delivery_details = page.locator("details.export-delivery-details")
    delivery_details.wait_for(state="visible", timeout=30_000)
    delivery_details.locator("summary").click()
    for resource in ("solver_card", "preview", "download", "receipt"):
        if delivery_details.get_by_role("link", name=resource, exact=True).count() != 1:
            raise RuntimeError(f"delivered solver card must expose its typed {resource} resource link")
    if page.get_by_role("button", name=re.compile(r"^Create solver card\b")).count():
        raise RuntimeError("completed C2 delivery must not retain an active Create action")
    if page.get_by_role("button", name="Open solver card", exact=True).count() != 1:
        raise RuntimeError("completed delivery must expose its immutable solver-card link")
    if page.locator(".export-check .ux-button.primary:visible").count() != 1:
        raise RuntimeError("Delivered Export task must expose exactly one visible primary action")
    if page.locator(".modeling-curve-tree, .neutral-solver-export").count():
        raise RuntimeError(
            "Export must not restore the curve rail or legacy Neutral export surface"
        )
    _wait_for_settled(page)


def _assert_saved_fit_survives_export_reload(page: Page, base_url: str) -> None:
    """Prove the exact saved Fit context survives the pre-Export reload."""
    before = _modeling_session(page)
    context_text, context_title = _read_fit_context_header(page)
    pointer = before.get("processingOutput")
    if not isinstance(pointer, dict) or not all(
        isinstance(pointer.get(key), str) and pointer.get(key)
        for key in ("id", "revisionId")
    ):
        raise RuntimeError("Export preflight requires one exact saved Fit pointer")
    before_outputs = _list_processing_outputs(page, base_url)
    before_persisted = next(
        (
            item
            for item in before_outputs
            if _has_processing_output_revision(
                item, pointer.get("id"), pointer.get("revisionId")
            )
        ),
        None,
    )
    before_decision = (
        before_persisted.get("fit_decision")
        if isinstance(before_persisted, dict)
        else None
    )
    if (
        not isinstance(before_decision, dict)
        or not before_decision.get("candidate_key")
        or not before_decision.get("selection_reason")
        or not isinstance(before_decision.get("warning_acknowledged"), bool)
    ):
        raise RuntimeError("Export preflight requires complete exact Fit decision evidence")
    expected_warning_acknowledged = before_decision["warning_acknowledged"]
    requests: list[tuple[str, str]] = []
    def record_request(request: object) -> None:
        requests.append((str(getattr(request, "method", "")), str(getattr(request, "url", ""))))

    page.on("request", record_request)
    try:
        page.reload()
        page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
        _wait_for_fit_title_state(page, "Saved current")
        _wait_for_fit_context_header(page, context_text, context_title)
        page.get_by_role(
            "img", name="Hardening candidate and selected extrapolation curves", exact=True
        ).wait_for(state="visible", timeout=30_000)
        after = _modeling_session(page)
        for key in (
            "material",
            "materialState",
            "workspace",
            "processingOutput",
            "materialModelIr",
            "neutralModel",
        ):
            if after.get(key) != before.get(key):
                raise RuntimeError(
                    f"Export preflight reload changed exact Fit session field {key}: "
                    f"before={before.get(key)!r}, after={after.get(key)!r}"
                )
        persisted_outputs = _list_processing_outputs(page, base_url)
        persisted = next(
            (
                item for item in persisted_outputs
                if _has_processing_output_revision(
                    item, pointer.get("id"), pointer.get("revisionId")
                )
            ),
            None,
        )
        decision = persisted.get("fit_decision") if isinstance(persisted, dict) else None
        if (
            not isinstance(decision, dict)
            or not decision.get("candidate_key")
            or not decision.get("selection_reason")
            or decision.get("warning_acknowledged") is not expected_warning_acknowledged
        ):
            raise RuntimeError("Export preflight reload lost the exact Fit decision evidence")
        source_pin = persisted.get("source_processing_output") if isinstance(persisted, dict) else None
        if not isinstance(source_pin, dict) or not source_pin.get("aggregate_id") or not source_pin.get("revision_id"):
            raise RuntimeError("Export preflight reload lost the exact Process source pin")
        trigger, _body, table = _open_fit_evidence(page)
        _assert_fit_selected_evidence(page)
        if table.locator("tbody tr.selected").count() != 1:
            raise RuntimeError("Export preflight reload lost the selected Fit candidate")
        if page.get_by_role(
            "textbox", name="Candidate selection reason", exact=True
        ).input_value() != "Best agreement over the measured strain range.":
            raise RuntimeError("Export preflight reload changed the Fit selection reason")
        warning_acknowledgement = page.get_by_role(
            "checkbox", name="Acknowledge selected candidate warning", exact=True
        )
        if warning_acknowledgement.count():
            if warning_acknowledgement.is_checked() is not expected_warning_acknowledged:
                raise RuntimeError(
                    "Export preflight reload changed the Fit warning acknowledgement"
                )
        elif expected_warning_acknowledged:
            raise RuntimeError("Export preflight reload lost the Fit warning acknowledgement")
        _close_fit_evidence(page, trigger)
    finally:
        page.remove_listener("request", record_request)
    unexpected = [
        f"{method} {url}"
        for method, url in requests
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}
    ]
    if unexpected:
        raise RuntimeError(
            f"Export preflight reload issued a mutation request: {unexpected!r}"
        )


def _read_delivered_card_identity(page: Page) -> tuple[str, str]:
    """Read the actual immutable card and revision IDs from Delivery details."""
    details = page.locator("details.export-delivery-details")
    details.wait_for(state="visible", timeout=30_000)
    summary = details.locator(":scope > summary")
    if details.get_attribute("open") is None:
        summary.click()
    values = details.evaluate(
        """element => Object.fromEntries(
          [...element.querySelectorAll('dl > dt')].map(label => [
            label.textContent?.trim() || '',
            label.nextElementSibling?.matches('dd')
              ? label.nextElementSibling.textContent?.trim() || ''
              : '',
          ])
        )"""
    )
    card_id = values.get("Solver card") if isinstance(values, dict) else None
    revision_id = values.get("Card revision") if isinstance(values, dict) else None
    uuid_like = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    if not isinstance(card_id, str) or not uuid_like.fullmatch(card_id):
        raise RuntimeError(f"Delivery details did not expose a UUID-like solver card id: {card_id!r}")
    if not isinstance(revision_id, str) or not uuid_like.fullmatch(revision_id):
        raise RuntimeError(
            f"Delivery details did not expose a UUID-like solver card revision id: {revision_id!r}"
        )
    return card_id, revision_id


def _assert_exact_material_solver_card_readback(
    page: Page,
    base_url: str,
) -> None:
    """Open the delivered card through Materials and verify its exact API record."""
    card_id, card_revision_id = _read_delivered_card_identity(page)
    material = _modeling_session(page).get("material")
    material_id = material.get("id") if isinstance(material, dict) else None
    if not isinstance(material_id, str) or not material_id:
        raise RuntimeError("Delivery read-back requires the exact session Material id")
    expected_path = f"/materials/{material_id}/cards/{card_id}"
    open_card = page.get_by_role("button", name="Open solver card", exact=True)
    if open_card.count() != 1:
        raise RuntimeError("Delivered Export must expose one exact Open solver card action")
    open_card.click()
    page.wait_for_url(re.compile(re.escape(expected_path) + r"$"), timeout=30_000)
    if urlsplit(page.url).path != expected_path:
        raise RuntimeError(
            f"Materials card read-back used a non-exact route: expected={expected_path!r}, "
            f"actual={urlsplit(page.url).path!r}"
        )
    expected_api_url = (
        f"{base_url.rstrip('/')}/api/v1/neutral-solver-cards/"
        f"{quote(card_id, safe='')}?revision_id={quote(card_revision_id, safe='')}"
    )
    try:
        page.wait_for_function(
            """expected => {
              const visible = element => Boolean(element && element.getClientRects().length);
              const heading = document.querySelector('.card-preview-header h1');
              const preview = document.querySelector('[aria-label="Native solver card preview"]');
              const pending = [...document.querySelectorAll('[role="status"], .delivery-progress-line')]
                .some(element => visible(element)
                  && /^(?:Loading|Preparing|Checking)\\b/i.test(element.textContent?.trim() || ''));
              const alert = [...document.querySelectorAll('[role="alert"]')].some(visible);
              return window.location.pathname === expected.path
                && visible(heading)
                && Boolean(heading.textContent?.trim())
                && heading.textContent.trim() !== 'Card preview'
                && visible(preview)
                && Boolean(preview.textContent?.trim())
                && !/Loading native card preview…?/i.test(preview.textContent || '')
                && !pending
                && !alert;
            }""",
            arg={"path": expected_path},
            timeout=30_000,
        )
    except Exception as error:
        diagnostics = page.evaluate(
            """() => ({
              url: window.location.href,
              h1: document.querySelector('.card-preview-header h1')?.textContent?.trim() || null,
              preview: document.querySelector('[aria-label="Native solver card preview"]')?.textContent?.trim() || null,
              alerts: [...document.querySelectorAll('[role="alert"]')]
                .filter(element => element.getClientRects().length)
                .map(element => element.textContent?.trim()),
              statuses: [...document.querySelectorAll('[role="status"], .delivery-progress-line')]
                .filter(element => element.getClientRects().length)
                .map(element => element.textContent?.trim()),
            })"""
        )
        raise RuntimeError(
            f"Materials solver-card read-back did not settle: diagnostics={diagnostics!r}"
        ) from error
    readback = page.evaluate(
        """async ({ url, cardId, cardRevisionId }) => {
          const config = JSON.parse(
            localStorage.getItem('cmp.material-platform.api-config') || '{}'
          );
          const response = await fetch(url, {
            headers: {
              Accept: 'application/json',
              Authorization: `Bearer ${config.accessToken || ''}`,
            },
          });
          const text = await response.text();
          let payload = null;
          try { payload = text ? JSON.parse(text) : null; } catch { /* fail below */ }
          return { url, status: response.status, cardId, cardRevisionId, payload, text };
        }""",
        {
            "url": expected_api_url,
            "cardId": card_id,
            "cardRevisionId": card_revision_id,
        },
    )
    if not isinstance(readback, dict) or readback.get("url") != expected_api_url or readback.get("status") != 200:
        raise RuntimeError(f"Exact delivered solver-card read-back failed: {readback!r}")
    payload = readback.get("payload")
    current_revision = payload.get("current_revision") if isinstance(payload, dict) else None
    content = current_revision.get("content") if isinstance(current_revision, dict) else None
    target = payload.get("target") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("solver_card_id") != card_id
        or not isinstance(current_revision, dict)
        or current_revision.get("id") != card_revision_id
        or not isinstance(target, dict)
        or target.get("solver") != "abaqus"
        or target.get("version") != "2025"
        or target.get("unit_system") != "kg_m_s"
        or not isinstance(content, dict)
        or content.get("material_name") != "DP780_C1_REFERENCE"
    ):
        raise RuntimeError(f"Delivered solver-card API identity drifted: {readback!r}")
    heading = page.locator(".card-preview-header h1")
    heading_text = heading.inner_text().strip()
    if not heading_text or heading_text in {"Card preview", "Solver card"}:
        raise RuntimeError(f"Materials read-back lost the exact card label: {heading_text!r}")
    native_preview = page.get_by_label("Native solver card preview", exact=True)
    native_preview.wait_for(state="visible", timeout=30_000)
    preview_text = native_preview.inner_text().strip()
    if not preview_text or preview_text.startswith("Loading native card preview"):
        raise RuntimeError("Materials read-back lost the completed native solver-card preview")
    download = page.get_by_role("button", name=re.compile(r"^Download\b"))
    if download.count() != 1:
        raise RuntimeError("Materials read-back must expose one exact card download action")
    review_acknowledgement = page.get_by_role("checkbox")
    if review_acknowledgement.count() == 1:
        if review_acknowledgement.is_checked():
            raise RuntimeError("Materials read-back review acknowledgement must start unchecked")
        review_acknowledgement.check()
    elif review_acknowledgement.count() > 1:
        raise RuntimeError("Materials read-back must expose at most one delivery acknowledgement")
    if download.is_disabled():
        raise RuntimeError(
            "Materials read-back exact card download remained disabled after delivery checks"
        )
    expected_download_url = (
        f"{base_url.rstrip('/')}/api/v1/neutral-solver-cards/"
        f"{quote(card_id, safe='')}/download?revision_id={quote(card_revision_id, safe='')}"
    )
    with page.expect_response(
        lambda response: response.url == expected_download_url,
        timeout=30_000,
    ) as download_response:
        download.click()
    response = download_response.value
    if response.status != 200:
        raise RuntimeError(f"Materials exact solver-card download failed: {response.status}")


def _read_delivered_solver_card_identity(delivery_details: Locator) -> tuple[str, str]:
    """Read and validate the immutable IDs displayed by Delivery details."""

    values: dict[str, str] = {}
    for label in ("Solver card", "Card revision"):
        definition = delivery_details.locator("dt").filter(
            has_text=re.compile(rf"^{re.escape(label)}$")
        )
        if definition.count() != 1:
            raise RuntimeError(f"Delivery details must expose exactly one {label} value")
        code = definition.locator("xpath=following-sibling::dd[1]").locator("code")
        if code.count() != 1:
            raise RuntimeError(f"Delivery details {label} value is not a code value")
        value = code.inner_text().strip()
        if not UUID_LIKE_PATTERN.fullmatch(value):
            raise RuntimeError(f"Delivery details {label} is not a UUID-like immutable ID: {value!r}")
        values[label] = value
    return values["Solver card"], values["Card revision"]


def _assert_delivered_solver_card_readback(
    page: Page,
    base_url: str,
    *,
    solver_card_id: str,
    solver_card_revision_id: str,
) -> None:
    """Read back the delivered Abaqus card at its exact immutable revision."""

    outcome = page.evaluate(
        """async ({ baseUrl, solverCardId, solverCardRevisionId }) => {
          const config = JSON.parse(
            localStorage.getItem("cmp.material-platform.api-config") || "{}"
          );
          if (!config.accessToken) throw new Error("authenticated card read-back requires an access token");
          const path = `${baseUrl}/api/v1/neutral-solver-cards/${encodeURIComponent(solverCardId)}?revision_id=${encodeURIComponent(solverCardRevisionId)}`;
          const response = await fetch(path, {
            headers: {
              "Accept": "application/json",
              "Authorization": `Bearer ${config.accessToken}`,
            },
          });
          const text = await response.text();
          return {
            status: response.status,
            payload: text ? JSON.parse(text) : null,
          };
        }""",
        {
            "baseUrl": base_url,
            "solverCardId": solver_card_id,
            "solverCardRevisionId": solver_card_revision_id,
        },
    )
    if not isinstance(outcome, dict) or outcome.get("status") != 200:
        raise RuntimeError(f"exact delivered solver-card read-back failed: {outcome!r}")
    payload = outcome.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError(f"exact delivered solver-card response is malformed: {payload!r}")
    current_revision = payload.get("current_revision")
    target = payload.get("target")
    if (
        payload.get("solver_card_id") != solver_card_id
        or not isinstance(current_revision, dict)
        or current_revision.get("id") != solver_card_revision_id
        or not isinstance(target, dict)
        or target.get("solver") != "abaqus"
        or target.get("version") != "2025"
        or target.get("unit_system") != "kg_m_s"
    ):
        raise RuntimeError(f"exact delivered solver-card identity/target drifted: {payload!r}")
    content = current_revision.get("content")
    if not isinstance(content, dict) or content.get("material_name") != "DP780_C1_REFERENCE":
        raise RuntimeError(f"exact delivered solver-card material name drifted: {payload!r}")
    native_preview = page.get_by_label("Native solver card preview", exact=True)
    native_preview.wait_for(state="visible", timeout=30_000)
    if page.locator('[role="alert"]:visible').count():
        raise RuntimeError("exact delivered Materials card read-back exposes a visible alert")
    heading = page.get_by_role("heading", level=1)
    heading.wait_for(state="visible", timeout=30_000)
    heading_text = heading.inner_text().strip()
    expected_label = str(content["material_name"])
    if not heading_text or heading_text == "Card preview" or expected_label not in heading_text:
        raise RuntimeError(
            "exact delivered Materials card read-back did not expose its card label: "
            f"heading={heading_text!r}, expected={expected_label!r}"
        )
    native_text = native_preview.inner_text().strip()
    if not native_text or native_text == "Loading native card preview…":
        raise RuntimeError("exact delivered Materials card read-back has no completed native preview")


def _capture_modeling_export_only(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_delivered: bool = True,
) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_fit_for_export(
            page,
            base_url,
            label=f"Fit source Process result {width}x{height}",
        )
        _save_exact_fit_selection(page, candidate_key="swift+voce", require_warning=False)
        _open_modeling_stage(page, "export")
        page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
        _prepare_exact_metal_source_if_needed(page)
        _prepare_exact_target_preview(page)
        if page.get_by_role("heading", name="Prepare selected model", exact=True).count():
            raise RuntimeError("normal Export capture did not expose a current exact model source")
        _assert_export_exact_source_surface(
            page,
            verify_neutral_download=(width, height) == (1440, 900),
        )
        _capture(
            page,
            output / f"modeling-export-{width}x{height}.png",
            width,
            height,
            focus_selector=".modeling-target-preview .export-native-preview-shell",
            before_screenshot=lambda page=page: _assert_export_action_visible(page, "Create solver card"),
            after_animation=lambda page=page: _assert_export_capture_shell(page),
        )
        page.context.close()

    source_blocked_page = _new_page(browser, base_url, 1440, 900)
    _prepare_fit_for_export(
        source_blocked_page,
        base_url,
        label="Export source-blocked Process result",
    )
    _save_exact_fit_selection(source_blocked_page, candidate_key="swift+voce", require_warning=False)
    _open_modeling_stage(source_blocked_page, "export")
    source_blocked_page.get_by_role("heading", name="Prepare selected model", exact=True).wait_for(timeout=30_000)
    if source_blocked_page.get_by_role("button", name=re.compile(r"^(Run|Retry) Export check$"), exact=True).count():
        raise RuntimeError("source-blocked Export must not expose a preview action")
    _capture(
        source_blocked_page,
        output / "modeling-export-source-blocked-1440x900.png",
        1440,
        900,
        focus_selector=".modeling-export-recovery",
        before_screenshot=lambda: _assert_export_recovery_capture(source_blocked_page),
    )
    source_blocked_page.context.close()

    approximation = _new_page(browser, base_url, 1440, 900)
    _prepare_fit_for_export(
        approximation,
        base_url,
        label="Export approximation Process result",
    )
    _save_exact_fit_selection(approximation, candidate_key="swift+voce", require_warning=False)
    _open_modeling_stage(approximation, "export")
    _prepare_exact_metal_source_if_needed(approximation)
    _prepare_exact_target_preview(
        approximation,
        target_value="openradioss/2025/kg_m_s",
        acknowledge=False,
        create=False,
    )
    if approximation.get_by_text("Review required", exact=True).count() != 1:
        raise RuntimeError("approximation-blocked Export must expose one Review required state")
    if approximation.get_by_role("checkbox", name="Acknowledge mapped approximations", exact=True).is_checked():
        raise RuntimeError("approximation-blocked Export must retain an unchecked acknowledgement")
    _capture(
        approximation,
        output / "modeling-export-approximation-blocked-1440x900.png",
        1440,
        900,
        focus_selector=".export-check .export-status",
        before_screenshot=lambda: _assert_export_action_visible(approximation, "Create solver card"),
        after_animation=lambda: _assert_export_capture_shell(approximation),
    )
    approximation.context.close()

    if not include_delivered:
        return

    delivered = _new_page(browser, base_url, 1440, 900)
    _prepare_fit_for_export(
        delivered,
        base_url,
        label="Export delivered Process result",
    )
    _save_exact_fit_selection(delivered, candidate_key="swift+voce", require_warning=False)
    _assert_saved_fit_survives_export_reload(delivered, base_url)
    _open_modeling_stage(delivered, "export")
    _prepare_exact_metal_source_if_needed(delivered)
    _prepare_exact_target_preview(delivered, acknowledge=True, create=True)
    delivery_details = delivered.locator("details.export-delivery-details")
    delivery_details.wait_for(state="visible", timeout=30_000)
    if delivery_details.get_attribute("open") is None:
        delivery_details.locator(":scope > summary").click()
    solver_card_id, solver_card_revision_id = _read_delivered_solver_card_identity(
        delivery_details
    )
    session = _modeling_session(delivered)
    material = session.get("material")
    if (
        not isinstance(material, dict)
        or not isinstance(material.get("id"), str)
        or not material["id"]
    ):
        raise RuntimeError(f"delivered Export session has no exact Material identity: {material!r}")
    expected_card_path = f"/materials/{material['id']}/cards/{solver_card_id}"
    _assert_export_exact_source_surface(
        delivered,
        verify_neutral_download=True,
        require_review_action=True,
    )
    _capture(
        delivered,
        output / "modeling-export-delivered-1440x900.png",
        1440,
        900,
        focus_selector=".ux-notice.success",
        before_screenshot=lambda: _assert_export_action_visible(delivered, "Open solver card"),
        after_animation=lambda: _assert_export_capture_shell(delivered),
    )
    _assert_exact_material_solver_card_readback(delivered, base_url)
    open_card = delivered.get_by_role("button", name="Open solver card", exact=True)
    if open_card.count() == 1:
        open_card.wait_for(timeout=30_000)
        open_card.click()
    delivered.wait_for_url(re.compile(rf"{re.escape(expected_card_path)}$"), timeout=30_000)
    if urlsplit(delivered.url).path != expected_card_path:
        raise RuntimeError(
            f"Open solver card navigated to an unexpected pathname: {delivered.url!r}"
        )
    _wait_for_delivered_solver_card_route(delivered, expected_card_path)
    _assert_delivered_solver_card_readback(
        delivered,
        base_url,
        solver_card_id=solver_card_id,
        solver_card_revision_id=solver_card_revision_id,
    )
    delivered.context.close()


def _capture_modeling(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_process_normals: bool = True,
) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling(
            page,
            base_url,
            verify_reload=False,
            retain_comparisons=True,
        )
        plot = page.locator(".persistent-modeling-plot svg[role=img]")
        for stage, heading in STAGE_HEADINGS.items():
            if stage == "export" and (width, height) not in VIEWPORTS:
                continue
            if stage == "export":
                # Export has its own dedicated three-pane workspace and no
                # persistent modeling plot locator.  The complete Export
                # evidence set is produced by _capture_modeling_export_only.
                continue
            _open_modeling_stage(page, stage)
            page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
            page.locator(".modeling-work-title h1").get_by_text(heading, exact=True).wait_for(
                timeout=30_000
            )
            if stage == "process":
                _save_process_output_for_fit(
                    page,
                    label=f"Fit source Process result {width}x{height}",
                    reason="Bind one immutable Process result as the exact Fit source.",
                )
            if stage == "fit":
                _click_modeling_fit_preview_and_wait(page)
                show_settings = page.get_by_role(
                    "button", name="Show current-stage settings", exact=True
                )
                if show_settings.count():
                    show_settings.click()
                _wait_for_settled(page)
                trigger, _body, candidate_table = _open_fit_evidence(page)
                if candidate_table.locator("tbody tr").count() != 5:
                    raise RuntimeError(
                        "Fit must expose four calculated single-law candidates "
                        "and the exact calculated preview blend"
                    )
                _assert_fit_candidate_surface(page, candidate_table)
                curve_legend = page.locator(
                    ".persistent-modeling-plot .curve-legend.interactive"
                )
                curve_legend.get_by_role(
                    "button", name=re.compile(r"^Preview .+\/.+ blend$")
                ).wait_for(timeout=30_000)
                save_candidate = page.get_by_role("button", name="Save fit & continue", exact=True)
                if save_candidate.count() != 1:
                    raise RuntimeError("Fit is missing its sole top-row save action")
                if not save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save must remain disabled before an explicit row selection"
                    )
                _select_warned_fit_candidate(candidate_table)
                curve_legend.get_by_role(
                    "button", name=re.compile(r"^Selected · .+$")
                ).wait_for(timeout=30_000)
                parameter_table = page.get_by_role(
                    "table", name="Selected candidate parameters and bounds"
                )
                parameter_table.wait_for(timeout=30_000)
                if parameter_table.locator("tbody tr").count() < 1:
                    raise RuntimeError(
                        "Selected Fit candidate must expose parameter and bound evidence"
                    )
                selection_reason = page.get_by_role("textbox", name="Candidate selection reason")
                selection_reason.fill("Best agreement over the measured strain range.")
                warning_acknowledgement = page.get_by_role(
                    "checkbox", name="Acknowledge selected candidate warning"
                )
                if warning_acknowledgement.count():
                    warning_acknowledgement.check()
                else:
                    raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
                _assert_fit_selected_evidence(page)
                if save_candidate.is_disabled():
                    raise RuntimeError(
                        "Fit save did not become ready after selection evidence was completed"
                    )
                _close_fit_evidence(page, trigger)
            if stage == "export":
                _prepare_exact_target_preview(page)
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
            if stage != "process" or include_process_normals:
                _capture(
                    page,
                    output / f"modeling-{stage}-{width}x{height}.png",
                    width,
                    height,
                    focus_selector=None,
                )
            if stage == "fit":
                _save_exact_fit_selection(page)
        page.context.close()


def _measure_process_fit(
    page: Page,
    stage: str,
    width: int,
    height: int,
    *,
    minimum_svg_height: int | None = None,
    expected_fit_included: int = 2,
) -> dict[str, float]:
    blocked_plot = page.locator(
        '.persistent-modeling-plot .engineering-curve-plot-empty-frame[data-plot-state="blocked"]'
    )
    if blocked_plot.count():
        raise RuntimeError(
            f"{stage} full-plot geometry received a blocked plot; "
            "use the dedicated blocked-state assertion instead"
        )
    # Computed-style checks below compare the resting action hierarchy. Move
    # away from the action row so the click that settled a preview cannot leave
    # one secondary action in :hover while its peer remains at rest.
    page.mouse.move(width // 2, max(1, height - 2))
    page.wait_for_timeout(50)
    measurement = cast(dict[str, float], page.evaluate(
        """() => {
          const box = selector => document.querySelector(selector)?.getBoundingClientRect();
          const rect = node => {
            const value = node?.getBoundingClientRect?.();
            return value && node?.getClientRects?.().length
              ? { left: value.left, right: value.right, top: value.top, bottom: value.bottom, width: value.width, height: value.height }
              : null;
          };
          const overlaps = (first, second) => Boolean(
            first && second
              && first.left < Math.max(second.right, second.left + 1)
              && Math.max(first.right, first.left + 1) > second.left
              && first.top < Math.max(second.bottom, second.top + 1)
              && Math.max(first.bottom, first.top + 1) > second.top
          );
          const segmentIntersectsRect = (first, second, target) => {
            if (!first || !second || !target) return false;
            const dx = second.x - first.x;
            const dy = second.y - first.y;
            let enter = 0;
            let leave = 1;
            const clip = (p, q) => {
              if (Math.abs(p) < 1e-9) return q >= 0;
              const ratio = q / p;
              if (p < 0) {
                if (ratio > leave) return false;
                if (ratio > enter) enter = ratio;
              } else {
                if (ratio < enter) return false;
                if (ratio < leave) leave = ratio;
              }
              return true;
            };
            return clip(-dx, first.x - target.left)
              && clip(dx, target.right - first.x)
              && clip(-dy, first.y - target.top)
              && clip(dy, target.bottom - first.y)
              && enter <= leave;
          };
          const screenPoint = (element, x, y) => {
            const matrix = element?.getScreenCTM?.();
            if (!matrix || !Number.isFinite(x) || !Number.isFinite(y)) return null;
            const point = new DOMPoint(x, y).matrixTransform(matrix);
            return { x: point.x, y: point.y };
          };
          const svg = document.querySelector('.persistent-modeling-plot svg[role=img]');
          const axis = [...(svg?.querySelectorAll('.chart-axis') ?? [])]
            .find(
              line => line.getAttribute('x1') !== line.getAttribute('x2')
            )?.getBoundingClientRect();
          const workspace = box('.modeling-split-workspace');
          const processCluster = box('.modeling-workspace-stage-process');
          const fitCluster = box('.modeling-workspace-stage-fit');
          const rail = box('.modeling-workspace-rail');
          const ribbon = box('.modeling-task-ribbon');
          const plot = box('.persistent-modeling-plot');
          const plotFrame = box('.persistent-modeling-plot .engineering-plot-frame');
          const legend = rect(document.querySelector('.persistent-modeling-plot .engineering-plot-frame > .curve-legend'));
          const svgBox = svg?.getBoundingClientRect();
          const ticks = [...(svg?.querySelectorAll('.chart-tick') ?? [])].map(rect).filter(Boolean);
          const axisLabels = [...(svg?.querySelectorAll('.chart-axis-label') ?? [])].map(rect).filter(Boolean);
          const axes = [...(svg?.querySelectorAll('.chart-axis') ?? [])].map(rect).filter(Boolean);
          const xAxisLabel = axisLabels.at(-2);
          const xTickLabels = [...(svg?.querySelectorAll('g') ?? [])]
            .filter(group => [...group.querySelectorAll('line.chart-grid')]
              .some(line => line.getAttribute('x1') === line.getAttribute('x2')))
            .map(group => group.querySelector('text.chart-tick'))
            .map(rect)
            .filter(Boolean);
          const lastXTick = xTickLabels.at(-1) ?? null;
          const xTicksWithinSvg = Boolean(svgBox) && xTickLabels.every(tick => (
            tick.left >= svgBox.left - 1
              && tick.right <= svgBox.right + 1
              && tick.top >= svgBox.top - 1
              && tick.bottom <= svgBox.bottom + 1
          ));
          const curveSegments = [...(svg?.querySelectorAll('polyline.curve-line') ?? [])]
            .filter(polyline => polyline.getClientRects().length)
            .flatMap(polyline => {
              const values = (polyline.getAttribute('points') ?? '')
                .trim()
                .split(/\\s+/)
                .map(pair => pair.split(',').map(Number))
                .filter(pair => pair.length === 2 && pair.every(Number.isFinite));
              const points = values.map(pair => screenPoint(polyline, pair[0], pair[1])).filter(Boolean);
              return points.slice(1).map((point, index) => ({ first: points[index], second: point }));
            });
          const extrapolationBoundary = rect(svg?.querySelector('.extrapolation-region line'));
          const extrapolationLabel = rect(svg?.querySelector('.extrapolation-annotation-layer text'));
          const stateOverlays = [...(svg?.querySelectorAll(
            '.graph-range-selection, .graph-point-selection, .graph-point-marker, .engineering-result-marker, .chart-crosshair',
          ) ?? [])].map(rect).filter(Boolean);
          const processRows = [...document.querySelectorAll('.modeling-workspace-stage-process .modeling-dataset-list .curve-row-label')].map(row => {
            const text = (row.textContent ?? '').replace(/\\s+/g, ' ').trim();
            const descendants = [row, ...row.querySelectorAll('strong, small')];
            const clipped = descendants.some(node => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1);
            return { text, clipped };
          });
          const processRoot = document.querySelector('.processing-workbench-page.stage-process');
          const toeMode = Boolean(processRoot?.querySelector('.toe-compensation-options'));
          const processRibbon = rect(processRoot?.querySelector('.modeling-task-ribbon'));
          const processPanel = rect(processRoot?.querySelector('[data-modeling-process-panel="ready"]'));
          const saveBand = rect(processRoot?.querySelector('.process-band-save'));
          const controlNodes = [
            processRoot?.querySelector('.elastic-modulus-method select'),
            processRoot?.querySelector('[aria-label="Elastic range start"]'),
            processRoot?.querySelector('[aria-label="Elastic range end"]'),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus"]`),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus unit"]`),
            processRoot?.querySelector(`[aria-label="Manual Young's modulus reason"]`),
            processRoot?.querySelector('[aria-label="Toe estimation range start"]'),
            processRoot?.querySelector('[aria-label="Toe estimation range end"]'),
            processRoot?.querySelector('[aria-label="Acknowledge toe quality warning"]'),
            processRoot?.querySelector('[aria-label="Process result name"]'),
            processRoot?.querySelector('[aria-label="Reason for saving Process result"]'),
            processRoot?.querySelector('.process-band-save > .button'),
          ].filter(Boolean);
          const processControls = controlNodes.map(node => {
            const box = rect(node);
            const style = node ? getComputedStyle(node) : null;
            const text = node?.textContent?.trim() ?? '';
            return {
              label: node?.getAttribute('aria-label') ?? text,
              box,
              height: box?.height ?? 0,
              whiteSpace: style?.whiteSpace ?? '',
              scrollHeight: node?.scrollHeight ?? 0,
              clientHeight: node?.clientHeight ?? 0,
              scrollWidth: node?.scrollWidth ?? 0,
              clientWidth: node?.clientWidth ?? 0,
            };
          });
          const topActionNodes = [
            processRoot?.querySelector('.modeling-context-actions > .modeling-advanced-menu > summary'),
            processRoot?.querySelector('.modeling-context-actions > button.modeling-analysis-trigger'),
            [...(processRoot?.querySelectorAll('.modeling-context-actions > button.button.secondary') ?? [])]
              .find(node => node.textContent?.trim() === 'Preview changes'),
          ];
          const topActions = topActionNodes.map(node => {
            const box = rect(node);
            const style = node ? getComputedStyle(node) : null;
            return {
              label: node?.textContent?.trim() ?? '',
              box,
              height: box?.height ?? 0,
              whiteSpace: style?.whiteSpace ?? '',
              scrollHeight: node?.scrollHeight ?? 0,
              clientHeight: node?.clientHeight ?? 0,
              scrollWidth: node?.scrollWidth ?? 0,
              clientWidth: node?.clientWidth ?? 0,
            };
          });
          const fitRoot = document.querySelector('.processing-workbench-page.stage-fit');
          const fitPlotHeadingNodes = fitRoot?.querySelectorAll('.persistent-modeling-plot .fit-plot-heading') ?? [];
          const fitPlotHeadingNode = fitPlotHeadingNodes[0];
          const fitPlotHeadingBox = rect(fitPlotHeadingNode);
          const fitPlotHeadingStyle = fitPlotHeadingNode ? getComputedStyle(fitPlotHeadingNode) : null;
          const fitPlotHeading = {
            count: fitPlotHeadingNodes.length,
            text: fitPlotHeadingNode?.textContent?.trim() ?? '',
            display: fitPlotHeadingStyle?.display ?? '',
            box: fitPlotHeadingBox,
            scrollHeight: fitPlotHeadingNode?.scrollHeight ?? 0,
            clientHeight: fitPlotHeadingNode?.clientHeight ?? 0,
            scrollWidth: fitPlotHeadingNode?.scrollWidth ?? 0,
            clientWidth: fitPlotHeadingNode?.clientWidth ?? 0,
          };
          const fitTopActionNodes = [
            fitRoot?.querySelector('.modeling-context-actions > .modeling-advanced-menu > summary'),
            fitRoot?.querySelector('.modeling-context-actions > button.button.secondary'),
            fitRoot?.querySelector('.modeling-context-actions > button.button.primary'),
          ];
          const fitTopActions = fitTopActionNodes.map(node => {
            const value = rect(node);
            const style = node ? getComputedStyle(node) : null;
            return {
              label: node?.textContent?.trim() ?? '',
              box: value,
              height: value?.height ?? 0,
              borderRadius: style?.borderRadius ?? '',
              fontSize: style?.fontSize ?? '',
              fontWeight: style?.fontWeight ?? '',
              backgroundColor: style?.backgroundColor ?? '',
              borderColor: style?.borderColor ?? '',
              color: style?.color ?? '',
              whiteSpace: style?.whiteSpace ?? '',
              scrollHeight: node?.scrollHeight ?? 0,
              clientHeight: node?.clientHeight ?? 0,
              scrollWidth: node?.scrollWidth ?? 0,
              clientWidth: node?.clientWidth ?? 0,
            };
          });
          const fitTopActionsContainer = rect(fitRoot?.querySelector('.modeling-context-actions'));
          const fitRibbon = rect(fitRoot?.querySelector('.modeling-task-ribbon'));
          const fitGroups = [...(fitRoot?.querySelectorAll('.fit-stage-options .fit-control-group') ?? [])].map(group => {
            const paired = group.querySelector('.fit-paired-controls');
            const pairedStyle = paired ? getComputedStyle(paired) : null;
            return {
            label: group.querySelector('legend')?.textContent?.trim() ?? '',
            box: rect(group),
            gridTemplateColumns: getComputedStyle(group).gridTemplateColumns,
            paired: paired ? {
              box: rect(paired),
              display: pairedStyle?.display ?? '',
              widthStyle: pairedStyle?.width ?? '',
              minWidth: pairedStyle?.minWidth ?? '',
              maxWidth: pairedStyle?.maxWidth ?? '',
              overflow: pairedStyle?.overflow ?? '',
              labels: [...paired.children].map(label => {
                const labelStyle = getComputedStyle(label);
                return {
                  box: rect(label),
                  flex: labelStyle.flex,
                  widthStyle: labelStyle.width,
                  minWidth: labelStyle.minWidth,
                  maxWidth: labelStyle.maxWidth,
                  overflow: labelStyle.overflow,
                  contain: labelStyle.contain,
                };
              }),
            } : null,
            controls: [...group.querySelectorAll('input, select, button')].map(control => {
              const controlRect = rect(control);
              const style = getComputedStyle(control);
              return controlRect ? {
                ...controlRect,
                tagName: control.tagName.toLowerCase(),
                boxSizing: style.boxSizing,
                widthStyle: style.width,
                minWidth: style.minWidth,
                maxWidth: style.maxWidth,
              } : null;
            }).filter(Boolean),
          };
          });
          const fitRemoveStep = rect(fitRoot?.querySelector('.fit-heading-actions .text-button'));
          const fitEvidenceTrigger = rect(fitRoot?.querySelector('.fit-evidence-trigger'));
          const fitHeaderSource = rect(fitRoot?.querySelector('.fit-context-source'));
          const fitHeaderState = rect(fitRoot?.querySelector('.fit-surface-state'));
          const method = rect(document.querySelector('.modeling-workspace-stage-process .elastic-modulus-method select'));
          const range = rect(document.querySelector('.modeling-workspace-stage-process .elastic-modulus-range'));
          return {
            svgHeight: svgBox?.height ?? 0,
            svgWidth: svgBox?.width ?? 0,
            svgBottom: svgBox?.bottom ?? 0,
            svgBox: svgBox ? { left: svgBox.left, right: svgBox.right, top: svgBox.top, bottom: svgBox.bottom, width: svgBox.width, height: svgBox.height } : null,
            legendBox: legend,
            horizontalAxisBox: axis ? { left: axis.left, right: axis.right, top: axis.top, bottom: axis.bottom, width: axis.width, height: axis.height } : null,
            drawableRatio: plot && axis ? axis.width / plot.width : 0,
            processClusterWidth: processCluster?.width ?? 0,
            processClusterHeight: processCluster?.height ?? 0,
            processClusterLeft: processCluster?.left ?? 0,
            processClusterTop: processCluster?.top ?? 0,
            fitClusterWidth: fitCluster?.width ?? 0,
            fitClusterHeight: fitCluster?.height ?? 0,
            fitClusterLeft: fitCluster?.left ?? 0,
            fitClusterTop: fitCluster?.top ?? 0,
            workspaceLeft: workspace?.left ?? 0,
            workspaceTop: workspace?.top ?? 0,
            workspaceWidth: workspace?.width ?? 0,
            workspaceHeight: workspace?.height ?? 0,
            railWidth: rail?.width ?? 0, ribbonHeight: ribbon?.height ?? 0,
            plotBottom: plot?.bottom ?? 0, xAxisLabelBottom: xAxisLabel?.bottom ?? 0,
            plotFrameBox: plotFrame ? { left: plotFrame.left, right: plotFrame.right, top: plotFrame.top, bottom: plotFrame.bottom, width: plotFrame.width, height: plotFrame.height } : null,
            legendBottom: legend?.bottom ?? 0,
            legendInPlot: Boolean(legend && plot
              && legend.left >= plot.left - 1
              && legend.right <= plot.right + 1
              && legend.top >= plot.top - 1
              && legend.bottom <= plot.bottom + 1),
            legendOutsideSvg: Boolean(legend && svgBox
              && (legend.left < svgBox.left - 1
                || legend.right > svgBox.right + 1
                || legend.top < svgBox.top - 1
                || legend.bottom > svgBox.bottom + 1)),
            legendAfterPlotAxis: Boolean(legend && axis && legend.left >= axis.right - 1),
            legendTickOverlap: ticks.some(tick => overlaps(legend, tick)),
            legendAxisLabelOverlap: axisLabels.some(label => overlaps(legend, label)),
            legendAxisOverlap: axes.some(axisLine => overlaps(legend, axisLine)),
            legendCurveSegmentOverlap: curveSegments.some(segment => segmentIntersectsRect(segment.first, segment.second, legend)),
            legendExtrapolationBoundaryOverlap: overlaps(legend, extrapolationBoundary),
            legendExtrapolationLabelOverlap: overlaps(legend, extrapolationLabel),
            legendStateOverlayOverlap: stateOverlays.some(overlay => overlaps(legend, overlay)),
            lastXTickWithinSvg: Boolean(lastXTick && xTicksWithinSvg),
            xTicksWithinSvg,
            xTickCount: xTickLabels.length,
            processRows,
            processRowClipped: processRows.some(row => row.clipped),
            fitInput: (() => {
              const row = document.querySelector('.modeling-workspace-stage-fit .fit-input-row');
              const rowBox = row?.getBoundingClientRect();
              const clipped = row ? [row, ...row.querySelectorAll('strong, span')]
                .some(node => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1) : true;
              return row && rowBox ? {
                text: (row.textContent ?? '').replace(/\\s+/g, ' ').trim(),
                visible: row.getClientRects().length > 0,
                clipped,
                box: { top: rowBox.top, bottom: rowBox.bottom },
              } : null;
            })(),
            fitStepCount: document.querySelectorAll('.modeling-workspace-stage-fit .configured-step-list > button').length,
            methodRangeGap: method && range ? range.left - method.right : null,
            processControls,
            topActions,
            fitTopActions,
            fitTopActionsContainer,
            fitPlotHeading,
            fitRibbon,
            fitGroups,
            fitRemoveStep,
            fitEvidenceTrigger,
            fitHeaderSource,
            fitHeaderState,
            toeMode,
            processRibbon,
            processPanel,
            saveBand,
            viewportHeight: window.innerHeight
          };
        }"""
    ))
    # Production caps the shared plot minimum at 42vh. The rendered SVG sits
    # below one density-derived interactive chrome row, the shared inter-row
    # spacing, and the one-pixel frame divider; validate that semantic contract
    # instead of a Standard-only pixel threshold.
    default_minimum = max(
        240,
        min(_css_token_px(page, "--ux-plot-min-block-size"), height * 0.42)
        - _css_token_px(page, "--ux-interactive-min-block-size")
        - _css_token_px(page, "--ux-space-2")
        - 1,
    )
    minimum = (
        minimum_svg_height
        if minimum_svg_height is not None
        else 180 if stage == "data" else default_minimum
    )
    if measurement["svgHeight"] + 1 < minimum:
        raise RuntimeError(f"{stage} geometry gate failed at {width}x{height}: {measurement}")
    shared_right_reservation = (
        _css_token_px(page, "--ux-navigator-min-inline-size")
        + _css_token_px(page, "--ux-pane-padding")
    )
    expected_drawable_width = measurement["svgWidth"] - 80 - (
        24 if stage == "data" else shared_right_reservation
    )
    horizontal_axis = measurement.get("horizontalAxisBox")
    if (
        not isinstance(horizontal_axis, dict)
        or abs(_as_float(horizontal_axis.get("width")) - expected_drawable_width) > 2
    ):
        raise RuntimeError(
            f"{stage} drawable plot width drifted from the shared legend reservation "
            f"at {width}x{height}: expected={expected_drawable_width}, measurement={measurement}"
        )
    if width == 1440 and measurement["svgWidth"] < 1050:
        raise RuntimeError(f"{stage} 1440 graph-width gate failed: {measurement}")
    legend_box = measurement.get("legendBox")
    svg_box = measurement.get("svgBox")
    if stage == "data":
        data_legend_invalid = (
            not measurement.get("legendInPlot")
            or not measurement.get("legendOutsideSvg")
            or not isinstance(legend_box, dict)
            or not isinstance(svg_box, dict)
            or _as_float(legend_box.get("top")) < _as_float(svg_box.get("bottom")) - 1
        )
    else:
        data_legend_invalid = (
            not measurement.get("legendInPlot")
            or measurement.get("legendOutsideSvg")
            or not measurement.get("legendAfterPlotAxis")
        )
    if (
        data_legend_invalid
        or measurement.get("legendTickOverlap")
        or measurement.get("legendAxisLabelOverlap")
        or measurement.get("legendAxisOverlap")
        or measurement.get("legendCurveSegmentOverlap")
        or measurement.get("legendExtrapolationBoundaryOverlap")
        or measurement.get("legendExtrapolationLabelOverlap")
        or measurement.get("legendStateOverlayOverlap")
    ):
        raise RuntimeError(
            f"{stage} legend escapes its stage-owned plot reservation at "
            f"{width}x{height}: {measurement}"
        )
    if not measurement.get("lastXTickWithinSvg") or not measurement.get("xTicksWithinSvg"):
        raise RuntimeError(f"{stage} final x tick is clipped at {width}x{height}: {measurement}")
    expected_input_height = _css_token_px(page, "--ux-input-min-block-size")
    expected_interactive_height = _css_token_px(page, "--ux-interactive-min-block-size")
    if stage == "process":
        rows = measurement.get("processRows")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"Process rail rows are missing at {width}x{height}: {measurement}")
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(r"Tensile test \d{4}", str(row.get("text", ""))):
                raise RuntimeError(f"Process rail identity drifted at {width}x{height}: {measurement}")
        if measurement.get("processRowClipped"):
            raise RuntimeError(f"Process rail identity is clipped at {width}x{height}: {measurement}")
        toe_mode = measurement.get("toeMode") is True
        if not toe_mode:
            method_range_gap = measurement.get("methodRangeGap")
            maximum_control_gap = _css_token_px(page, "--ux-space-4") + 2
            if not isinstance(method_range_gap, (int, float)) or method_range_gap < 0 or method_range_gap > maximum_control_gap:
                raise RuntimeError(f"Process elastic method/range gap exceeds the shared spacing token at {width}x{height}: {measurement}")
        controls = measurement.get("processControls")
        if not isinstance(controls, list):
            raise RuntimeError(f"Process control geometry is missing at {width}x{height}: {measurement}")
        required_controls = (
            {
                "Toe estimation range start",
                "Toe estimation range end",
                "Process result name",
                "Reason for saving Process result",
                "Save Process result",
            }
            if toe_mode
            else {
                "Evaluation method",
                "Elastic range start",
                "Elastic range end",
                "Process result name",
                "Reason for saving Process result",
                "Save Process result",
            }
        )
        visible_controls = {
            str(control.get("label"))
            for control in controls
            if isinstance(control, dict) and isinstance(control.get("box"), dict)
        }
        if not required_controls <= visible_controls:
            raise RuntimeError(
                f"Process normal controls are missing at {width}x{height}: {sorted(visible_controls)}"
            )
        ribbon_box = measurement.get("processRibbon")
        panel_box = measurement.get("processPanel")
        if not isinstance(ribbon_box, dict) or not isinstance(panel_box, dict):
            raise RuntimeError(f"Process control containment boxes are missing at {width}x{height}: {measurement}")
        def _inside(child: dict[str, object], parent: dict[str, object]) -> bool:
            return (
                _as_float(child.get("left")) >= _as_float(parent.get("left")) - 1
                and _as_float(child.get("right")) <= _as_float(parent.get("right")) + 1
                and _as_float(child.get("top")) >= _as_float(parent.get("top")) - 1
                and _as_float(child.get("bottom")) <= _as_float(parent.get("bottom")) + 1
            )
        visible_control_boxes = [
            control.get("box")
            for control in controls
            if isinstance(control, dict) and isinstance(control.get("box"), dict)
        ]
        if any(not _inside(box, panel_box) for box in visible_control_boxes if isinstance(box, dict)):
            raise RuntimeError(f"Process controls escaped their panel at {width}x{height}: {measurement}")
        normal_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in (
                {"Toe estimation range start", "Toe estimation range end"}
                if toe_mode
                else {"Evaluation method", "Elastic range start", "Elastic range end"}
            )
        ]
        save_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in {"Process result name", "Reason for saving Process result", "Save Process result"}
        ]
        manual_row = [
            control for control in controls
            if isinstance(control, dict) and control.get("label") in {
                "Manual Young's modulus",
                "Manual Young's modulus unit",
                "Manual Young's modulus reason",
            }
        ]
        def _aligned(items: Sequence[object], tolerance: float = 2) -> bool:
            boxes = [item.get("box") for item in items if isinstance(item, dict) and isinstance(item.get("box"), dict)]
            if len(boxes) < 2:
                return False
            tops = [_as_float(box.get("top")) for box in boxes]
            bottoms = [_as_float(box.get("bottom")) for box in boxes]
            return max(tops) - min(tops) <= tolerance and max(bottoms) - min(bottoms) <= tolerance
        save_fields = [
            control for control in save_row
            if isinstance(control, dict) and control.get("label") in {"Process result name", "Reason for saving Process result"}
        ]
        save_actions = [
            control for control in save_row
            if isinstance(control, dict) and control.get("label") == "Save Process result"
        ]
        save_band = measurement.get("saveBand")
        stacked_save_action = False
        if (
            len(save_fields) == 2
            and len(save_actions) == 1
            and isinstance(save_band, dict)
            and isinstance(save_actions[0].get("box"), dict)
        ):
            field_boxes = [control.get("box") for control in save_fields]
            action_box = save_actions[0]["box"]
            stacked_save_action = bool(
                all(isinstance(box, dict) for box in field_boxes)
                and _aligned(save_fields)
                and _as_float(action_box.get("top"))
                >= max(_as_float(box.get("bottom")) for box in field_boxes if isinstance(box, dict)) - 1
                and _inside(action_box, save_band)
            )
        if not _aligned(normal_row) or not (_aligned(save_row) or stacked_save_action):
            raise RuntimeError(f"Process control baselines drifted at {width}x{height}: {measurement}")
        if manual_row and len(manual_row) == 3 and not _aligned(manual_row):
            raise RuntimeError(f"Process manual control baselines drifted at {width}x{height}: {measurement}")
        for control in controls:
            if not isinstance(control, dict) or not isinstance(control.get("box"), dict):
                continue
            height_px = float(control.get("height", 0))
            if abs(height_px - expected_input_height) > 1:
                raise RuntimeError(f"Process control height drifted at {width}x{height}: {control}")
            if str(control.get("label")) == "Save Process result":
                if control.get("whiteSpace") != "nowrap" or float(control.get("scrollHeight", 0)) > float(control.get("clientHeight", 0)) + 1:
                    raise RuntimeError(f"Process Save button wraps at {width}x{height}: {control}")
            if str(control.get("label")) in {"Process result name", "Reason for saving Process result"}:
                if control.get("whiteSpace") != "nowrap":
                    raise RuntimeError(f"Process save label wraps at {width}x{height}: {control}")
        top_actions = measurement.get("topActions")
        if not isinstance(top_actions, list) or len(top_actions) != 3:
            raise RuntimeError(f"Process top actions are missing at {width}x{height}: {measurement}")
        expected_top_action_labels = ["Advanced", "Distribution analysis", "Preview changes"]
        actual_top_action_labels = [
            str(action.get("label", "")).strip()
            for action in top_actions
            if isinstance(action, dict)
        ]
        if actual_top_action_labels != expected_top_action_labels:
            raise RuntimeError(
                f"Process top action labels drifted at {width}x{height}: {measurement}"
            )
        if not _aligned(top_actions):
            raise RuntimeError(f"Process top action baselines drifted at {width}x{height}: {measurement}")
        for action in top_actions:
            box = action.get("box") if isinstance(action, dict) else None
            if (
                not isinstance(action, dict)
                or not isinstance(box, dict)
                or float(box.get("width", 0)) <= 0
                or float(box.get("height", 0)) <= 0
                or abs(float(action.get("height", 0)) - expected_input_height) > 1
            ):
                raise RuntimeError(f"Process top action height drifted at {width}x{height}: {action}")
    def _assert_elastic_stage_workspace(prefix: str, label: str) -> None:
        cluster_width = measurement[f"{prefix}ClusterWidth"]
        cluster_height = measurement[f"{prefix}ClusterHeight"]
        workspace_width = measurement["workspaceWidth"]
        workspace_height = measurement["workspaceHeight"]
        if (
            cluster_width <= 0
            or cluster_height <= 0
            or workspace_width <= 0
            or workspace_height <= 0
            or cluster_width < workspace_width * 0.97
            or cluster_width > workspace_width + 1
            or cluster_height < workspace_height * 0.97
            or cluster_height > workspace_height + 1
            or abs(measurement[f"{prefix}ClusterLeft"] - measurement["workspaceLeft"]) > 1
            or abs(measurement[f"{prefix}ClusterTop"] - measurement["workspaceTop"]) > 1
        ):
            raise RuntimeError(
                f"{label} elastic workspace fill/alignment failed at {width}x{height}: {measurement}"
            )

    if stage == "process" and width >= 1920:
        _assert_elastic_stage_workspace("process", "Process")
    if stage == "fit":
        fit_input = measurement.get("fitInput")
        if (
            not isinstance(fit_input, dict)
            or fit_input.get("visible") is not True
            or fit_input.get("clipped") is True
            or "Saved Process result" not in str(fit_input.get("text", ""))
            or "Tensile test" not in str(fit_input.get("text", ""))
        ):
            raise RuntimeError(f"Fit input summary is missing or clipped at {width}x{height}: {measurement}")
        if measurement.get("fitStepCount") != 4:
            raise RuntimeError(f"Fit rail must expose the four engineering steps at {width}x{height}: {measurement}")
        if measurement["fitClusterWidth"] <= 0:
            raise RuntimeError(f"Fit workspace is unavailable at {width}x{height}: {measurement}")
        if width >= 1920:
            _assert_elastic_stage_workspace("fit", "Fit")
        minimum_rail_width = _css_token_px(page, "--ux-navigator-min-inline-size")
        default_rail_width = _css_token_px(page, "--ux-navigator-default-inline-size")
        if not minimum_rail_width - 1 <= measurement["railWidth"] <= default_rail_width + 1:
            raise RuntimeError(
                f"Fit curve rail escaped the shared density range at {width}x{height}: {measurement}"
            )
        expected_ribbon_height = _css_token_px(page, "--ux-workbench-ribbon-block-size")
        if abs(measurement["ribbonHeight"] - expected_ribbon_height) > 1:
            raise RuntimeError(
                f"Fit ribbon drifted from the shared density token at {width}x{height}: {measurement}"
            )
        fit_plot_heading = measurement.get("fitPlotHeading")
        fit_plot_heading_box = fit_plot_heading.get("box") if isinstance(fit_plot_heading, dict) else None
        if (
            not isinstance(fit_plot_heading, dict)
            or fit_plot_heading.get("count") != 1
            or fit_plot_heading.get("text") != "Hardening response"
            or fit_plot_heading.get("display") == "none"
            or not isinstance(fit_plot_heading_box, dict)
            or _as_float(fit_plot_heading_box.get("width")) <= 0
            or _as_float(fit_plot_heading_box.get("height")) <= 0
            or _as_float(fit_plot_heading.get("scrollHeight")) > _as_float(fit_plot_heading.get("clientHeight")) + 1
            or _as_float(fit_plot_heading.get("scrollWidth")) > _as_float(fit_plot_heading.get("clientWidth")) + 1
        ):
            raise RuntimeError(f"Fit plot heading is hidden, clipped, duplicated, or mislabeled at {width}x{height}: {measurement}")
        fit_top_actions = measurement.get("fitTopActions")
        if not isinstance(fit_top_actions, list) or len(fit_top_actions) != 3:
            raise RuntimeError(f"Fit top actions are missing at {width}x{height}: {measurement}")
        expected_fit_top_actions = ["Advanced", "Preview changes", "Save fit & continue"]
        actual_fit_top_actions = [
            str(action.get("label", "")).strip()
            for action in fit_top_actions
            if isinstance(action, dict)
        ]
        if actual_fit_top_actions != expected_fit_top_actions:
            raise RuntimeError(f"Fit top action labels drifted at {width}x{height}: {measurement}")
        fit_top_actions_container = measurement.get("fitTopActionsContainer")
        if not isinstance(fit_top_actions_container, dict) or _as_float(fit_top_actions_container.get("width")) <= 0 or _as_float(fit_top_actions_container.get("height")) <= 0:
            raise RuntimeError(f"Fit top action container is not visible at {width}x{height}: {measurement}")
        fit_top_boxes = [
            action.get("box") for action in fit_top_actions
            if isinstance(action, dict) and isinstance(action.get("box"), dict)
        ]
        if len(fit_top_boxes) != 3 or max(_as_float(box.get("top")) for box in fit_top_boxes) - min(_as_float(box.get("top")) for box in fit_top_boxes) > 2 or max(_as_float(box.get("bottom")) for box in fit_top_boxes) - min(_as_float(box.get("bottom")) for box in fit_top_boxes) > 2:
            raise RuntimeError(f"Fit top action baselines drifted at {width}x{height}: {measurement}")
        for style_key in ("borderRadius", "fontSize", "fontWeight"):
            style_values = {str(action.get(style_key, "")) for action in fit_top_actions if isinstance(action, dict)}
            if len(style_values) != 1:
                raise RuntimeError(f"Fit top action {style_key} drifted at {width}x{height}: {measurement}")
        for style_key in ("backgroundColor", "borderColor", "color"):
            advanced_style = fit_top_actions[0].get(style_key) if isinstance(fit_top_actions[0], dict) else None
            preview_style = fit_top_actions[1].get(style_key) if isinstance(fit_top_actions[1], dict) else None
            if advanced_style != preview_style:
                raise RuntimeError(f"Fit Advanced/Preview secondary {style_key} drifted at {width}x{height}: {measurement}")
        def fit_top_action_inside(child: dict[str, object], parent: dict[str, object]) -> bool:
            return (
                _as_float(child.get("left")) >= _as_float(parent.get("left")) - 1
                and _as_float(child.get("right")) <= _as_float(parent.get("right")) + 1
                and _as_float(child.get("top")) >= _as_float(parent.get("top")) - 1
                and _as_float(child.get("bottom")) <= _as_float(parent.get("bottom")) + 1
            )
        if any(not fit_top_action_inside(box, fit_top_actions_container) for box in fit_top_boxes):
            raise RuntimeError(f"Fit top actions escaped their action container at {width}x{height}: {measurement}")
        ordered_fit_top_boxes = sorted(fit_top_boxes, key=lambda box: _as_float(box.get("left")))
        if any(_as_float(first.get("right")) > _as_float(second.get("left")) + 1 for first, second in pairwise(ordered_fit_top_boxes)):
            raise RuntimeError(f"Fit top actions overlap at {width}x{height}: {measurement}")
        for action in fit_top_actions:
            box = action.get("box") if isinstance(action, dict) else None
            if (
                not isinstance(action, dict)
                or not isinstance(box, dict)
                or _as_float(box.get("width")) <= 0
                or _as_float(box.get("height")) <= 0
                or abs(_as_float(action.get("height")) - expected_interactive_height) > 1
                or action.get("whiteSpace") != "nowrap"
                or _as_float(action.get("scrollHeight")) > _as_float(action.get("clientHeight")) + 1
                or _as_float(action.get("scrollWidth")) > _as_float(action.get("clientWidth")) + 1
            ):
                raise RuntimeError(f"Fit top action height drifted at {width}x{height}: {action}")
        fit_ribbon = measurement.get("fitRibbon")
        fit_groups = measurement.get("fitGroups")
        required_fit_groups = (
            "Candidate models",
            "Fit range",
            "Preview blend",
            "Blend ratio",
            "Output range",
            "Graph selection",
        )
        if not isinstance(fit_ribbon, dict) or not isinstance(fit_groups, list):
            raise RuntimeError(f"Fit ribbon group geometry is missing at {width}x{height}: {measurement}")
        group_by_label = {
            str(group.get("label")): group.get("box")
            for group in fit_groups
            if isinstance(group, dict) and isinstance(group.get("box"), dict)
        }
        if any(label not in group_by_label for label in required_fit_groups):
            raise RuntimeError(f"Fit ribbon groups are missing at {width}x{height}: {measurement}")
        def fit_inside(child: object, parent: dict[str, object]) -> bool:
            return isinstance(child, dict) and (
                _as_float(child.get("left")) >= _as_float(parent.get("left")) - 1
                and _as_float(child.get("right")) <= _as_float(parent.get("right")) + 1
                and _as_float(child.get("top")) >= _as_float(parent.get("top")) - 1
                and _as_float(child.get("bottom")) <= _as_float(parent.get("bottom")) + 1
            )
        ordered_group_boxes = []
        for label in required_fit_groups:
            box = group_by_label.get(label)
            if not isinstance(box, dict) or _as_float(box.get("width")) <= 0 or _as_float(box.get("height")) <= 0:
                raise RuntimeError(f"Fit ribbon group is not visible at {width}x{height}: {label!r} {box!r}")
            if not fit_inside(box, fit_ribbon):
                raise RuntimeError(f"Fit ribbon group escaped the shared ribbon at {width}x{height}: {label!r} {box!r}")
            group = next(
                (
                    item
                    for item in fit_groups
                    if isinstance(item, dict) and item.get("label") == label
                ),
                None,
            )
            controls = group.get("controls") if isinstance(group, dict) else None
            if not isinstance(controls, list) or any(
                not isinstance(control, dict) or not fit_inside(control, box)
                for control in controls
            ):
                raise RuntimeError(
                    f"Fit ribbon controls escaped their shared group at {width}x{height}: {label!r} {group!r}"
                )
            ordered_group_boxes.append(box)
        ordered_group_boxes.sort(key=lambda box: _as_float(box.get("left")))
        if any(_as_float(first.get("right")) > _as_float(second.get("left")) + 1 for first, second in pairwise(ordered_group_boxes)):
            raise RuntimeError(f"Fit ribbon groups overlap at {width}x{height}: {fit_groups!r}")
        for key in ("fitRemoveStep", "fitEvidenceTrigger"):
            box = measurement.get(key)
            if not isinstance(box, dict) or _as_float(box.get("width")) <= 0 or _as_float(box.get("height")) <= 0 or not fit_inside(box, fit_ribbon):
                raise RuntimeError(f"Fit {key} is not visible/reachable inside the ribbon at {width}x{height}: {box!r}")
        for key in ("fitHeaderSource", "fitHeaderState"):
            box = measurement.get(key)
            if not isinstance(box, dict) or _as_float(box.get("width")) <= 0 or _as_float(box.get("height")) <= 0:
                raise RuntimeError(f"Fit header {key} is not visible at {width}x{height}: {box!r}")
    plot_frame = measurement.get("plotFrameBox")
    svg_box = measurement.get("svgBox")
    legend_box = measurement.get("legendBox")
    expected_frame_height = (
        _as_float(svg_box.get("height")) if isinstance(svg_box, dict) else 0
    )
    if stage == "data" and isinstance(legend_box, dict):
        expected_frame_height += _as_float(legend_box.get("height"))
    if (
        not isinstance(plot_frame, dict)
        or not isinstance(svg_box, dict)
        or abs(_as_float(svg_box.get("width")) - _as_float(plot_frame.get("width"))) > 2
        or abs(expected_frame_height - _as_float(plot_frame.get("height"))) > 2
    ):
        raise RuntimeError(f"{stage} SVG does not follow its semantic plot frame at {width}x{height}: {measurement}")
    if (
        measurement["svgBottom"] > measurement["plotBottom"] + 2.5
        or measurement["xAxisLabelBottom"] > measurement["plotBottom"] + 1
    ):
        raise RuntimeError(f"{stage} axis is clipped at {width}x{height}: {measurement}")
    if measurement["legendBottom"] > measurement["viewportHeight"]:
        raise RuntimeError(f"{stage} legend is clipped at {width}x{height}: {measurement}")
    return measurement


def _wait_modeling_process_panel(page: Page) -> None:
    page.locator('[data-modeling-process-panel="ready"]').wait_for(timeout=30_000)
    if page.get_by_role("status", name="Loading Process controls").count():
        raise RuntimeError("Process capture settled with the lazy loading fallback visible")


def _wait_for_modeling_process_destination_state(page: Page) -> None:
    """Wait for the Process destination to retain its deliberately blocked session."""
    page.wait_for_function(
        """() => {
          const raw = window.sessionStorage.getItem('cmp.modeling.recent-session.v4');
          if (!raw) return false;
          try {
            const session = JSON.parse(raw);
            const workspace = session.workspace;
            return session.testData === undefined
              && workspace !== null
              && typeof workspace === 'object'
              && Array.isArray(workspace.selectedTestDataRefs)
              && workspace.selectedTestDataRefs.length === 0
              && Array.isArray(workspace.selectedDocumentIds)
              && workspace.selectedDocumentIds.length === 0
              && Array.isArray(workspace.visibleTestDataKeys)
              && workspace.visibleTestDataKeys.length === 0;
          } catch {
            return false;
          }
        }""",
        timeout=30_000,
    )


def _wait_for_modeling_process_plot_size(page: Page) -> None:
    """Wait until the responsive Process SVG viewBox matches its rendered frame."""
    page.wait_for_function(
        """() => {
          const svg = document.querySelector('.persistent-modeling-plot svg[role="img"]');
          if (!svg || svg.getClientRects().length === 0) return false;
          const viewBox = svg.viewBox.baseVal;
          const rendered = svg.getBoundingClientRect();
          return viewBox.width > 0
            && viewBox.height > 0
            && rendered.width > 0
            && rendered.height > 0
            && Math.abs(viewBox.width - rendered.width) < 1
            && Math.abs(viewBox.height - rendered.height) < 1;
        }""",
        timeout=30_000,
    )


def _wait_for_process_plot_before_capture(page: Page) -> None:
    _wait_for_modeling_process_plot_size(page)


def _process_plot_capture_callback(page: Page) -> Callable[[], None]:
    def callback() -> None:
        _wait_for_process_plot_before_capture(page)

    return callback


def _click_modeling_process_preview_and_wait(page: Page) -> None:
    """Wait for the new Process preview POST, then require an idle action bar."""
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    with page.expect_response(
        lambda response: response.request.method == "POST"
        and urlsplit(response.url).path.endswith("/processing:preview"),
        timeout=30_000,
    ) as response_info:
        preview.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Process preview request failed: {response.status}")
    page.get_by_role("button", name="Preview changes", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          const updating = [...document.querySelectorAll('button')]
            .some(button => button.textContent?.trim() === 'Updating…');
          return Boolean(preview && !preview.disabled && !updating);
        }""",
        timeout=30_000,
    )
    page.get_by_text("Preview ready", exact=False).wait_for(timeout=30_000)


def _click_modeling_fit_preview_and_wait(page: Page) -> None:
    """Wait for the one persisted exact-source Fit run and its settled result."""
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    with page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path.endswith("/metal-fit-runs")
        ),
        timeout=30_000,
    ) as response_info:
        preview.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Fit calculation request failed: {response.status} {response.text()}")
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          const updating = [...document.querySelectorAll('button')]
            .some(button => button.textContent?.trim() === 'Updating…');
          return Boolean(preview && !preview.disabled && !updating);
        }""",
        timeout=30_000,
    )
    page.locator(".fit-surface-state").get_by_text(
        "Preview not saved", exact=True
    ).wait_for(timeout=30_000)
    page.get_by_role("button", name="Candidate parameters", exact=True).wait_for(
        state="visible", timeout=30_000
    )


def _save_process_output_for_fit(
    page: Page,
    *,
    label: str,
    reason: str,
    verify_default_preview: bool = True,
) -> dict[str, object]:
    """Persist one Process-only result before any Fit preview is requested."""
    if verify_default_preview:
        _assert_modeling_process_preview(page)
    panel = page.locator('[data-modeling-process-panel="ready"]')
    output_label = panel.get_by_role("textbox", name="Process result name", exact=True)
    output_reason = panel.get_by_role("textbox", name="Reason for saving Process result", exact=True)
    save = panel.get_by_role("button", name="Save Process result", exact=True)
    output_label.fill(label)
    output_reason.fill(reason)
    with page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and urlsplit(response.url).path.endswith("/processing-outputs")
        ),
        timeout=30_000,
    ) as response_info:
        save.click()
    response = response_info.value
    if not response.ok:
        raise RuntimeError(f"Process source save failed before Fit: {response.status}")
    saved = response.json()
    if not isinstance(saved, dict):
        raise RuntimeError("Process source save returned a malformed response")
    if not verify_default_preview:
        saved_steps = saved.get("steps")
        toe_steps = (
            [
                step
                for step in saved_steps
                if isinstance(step, dict) and step.get("method_id") == "tensile.toe_zero_intercept"
            ]
            if isinstance(saved_steps, list)
            else []
        )
        if (
            len(toe_steps) != 1
            or toe_steps[0].get("method_version") != "1.0.0"
            or not isinstance(toe_steps[0].get("options"), dict)
            or toe_steps[0]["options"].get("minimum_strain") != 0
            or toe_steps[0]["options"].get("maximum_strain") != 0.002
            or toe_steps[0]["options"].get("equipment_compliance") != "not_provided"
            or toe_steps[0]["options"].get("warning_acknowledged") is not False
        ):
            raise RuntimeError(
                f"Saved Process source lost exact toe compensation evidence: {saved_steps!r}"
            )
    page.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
    session = _modeling_session(page)
    pointer = session.get("processingOutput")
    if not isinstance(pointer, dict):
        raise RuntimeError("Process save did not pin an exact Processing Output for Fit")
    if not all(
        isinstance(pointer.get(key), str) and pointer.get(key)
        for key in ("id", "revisionId", "label")
    ):
        raise RuntimeError(f"Process save pinned an incomplete output identity: {pointer!r}")
    if pointer.get("revisionNo") != 1:
        raise RuntimeError(f"Process save did not pin Processing Output revision r1: {pointer!r}")
    return pointer



def _assert_toe_warning_layout(panel: Locator) -> dict[str, object]:
    geometry = cast(
        dict[str, object],
        panel.evaluate(
            """panel => {
              const rect = element => {
                const box = element?.getBoundingClientRect();
                return box ? {
                  left: box.left,
                  right: box.right,
                  top: box.top,
                  bottom: box.bottom,
                  width: box.width,
                  height: box.height,
                } : null;
              };
              const measure = element => ({
                box: rect(element),
                scrollWidth: element?.scrollWidth ?? 0,
                clientWidth: element?.clientWidth ?? 0,
                scrollHeight: element?.scrollHeight ?? 0,
                clientHeight: element?.clientHeight ?? 0,
              });
              return {
                controls: measure(panel.querySelector('.process-band-controls')),
                acknowledgement: measure(panel.querySelector('.toe-warning-acknowledgement')),
                checkbox: measure(panel.querySelector('[aria-label="Acknowledge toe quality warning"]')),
                acknowledgementText: measure(panel.querySelector('.toe-warning-acknowledgement span')),
                result: measure(panel.querySelector('.process-band-preview')),
                resultWarning: measure(panel.querySelector('.toe-result-warning')),
              };
            }"""
        ),
    )

    def measurement(name: str) -> dict[str, object]:
        value = geometry.get(name)
        if not isinstance(value, dict) or not isinstance(value.get("box"), dict):
            raise RuntimeError(f"Toe warning layout lost {name}: {geometry!r}")
        return cast(dict[str, object], value)

    def box(name: str) -> dict[str, float]:
        return cast(dict[str, float], measurement(name)["box"])

    controls = box("controls")
    acknowledgement = box("acknowledgement")
    checkbox = box("checkbox")
    result = box("result")

    def clipped(name: str) -> bool:
        value = measurement(name)
        return (
            float(value["scrollWidth"]) > float(value["clientWidth"]) + 1
            or float(value["scrollHeight"]) > float(value["clientHeight"]) + 1
        )

    overlaps_result = not (
        acknowledgement["right"] <= result["left"] + 1
        or acknowledgement["left"] >= result["right"] - 1
        or acknowledgement["bottom"] <= result["top"] + 1
        or acknowledgement["top"] >= result["bottom"] - 1
    )
    acknowledgement_inside_controls = (
        acknowledgement["left"] >= controls["left"] - 1
        and acknowledgement["right"] <= controls["right"] + 1
        and acknowledgement["top"] >= controls["top"] - 1
        and acknowledgement["bottom"] <= controls["bottom"] + 1
    )
    checkbox_is_compact = (
        12 <= checkbox["width"] <= 20
        and 12 <= checkbox["height"] <= 20
        and abs(checkbox["width"] - checkbox["height"]) <= 1
    )
    if (
        overlaps_result
        or not acknowledgement_inside_controls
        or not checkbox_is_compact
        or clipped("acknowledgementText")
        or clipped("resultWarning")
    ):
        raise RuntimeError(
            f"Toe warning controls overlap or clip at the live viewport: {geometry!r}"
        )
    return geometry


def _prepare_toe_compensation_preview(
    page: Page,
    *,
    warning_capture_path: Path | None = None,
) -> dict[str, object]:
    """Exercise the explicit warning/review path and settle a saveable toe preview."""

    toe = page.get_by_role("button", name="Add tensile toe compensation", exact=True)
    toe.wait_for(state="visible", timeout=30_000)
    if toe.is_disabled():
        raise RuntimeError("Tensile toe compensation is unavailable for the Metal Process track")
    toe.click()

    panel = page.locator('[data-modeling-process-panel="ready"]')
    start = panel.get_by_role("spinbutton", name="Toe estimation range start", exact=True)
    end = panel.get_by_role("spinbutton", name="Toe estimation range end", exact=True)
    start.wait_for(state="visible", timeout=30_000)
    end.wait_for(state="visible", timeout=30_000)
    start.fill("0.0005")
    end.fill("0.003")
    ordered = json.loads(page.get_by_label("Ordered processing steps").input_value())
    method_ids = [step.get("method_id") for step in ordered if isinstance(step, dict)]
    if "tensile.toe_zero_intercept" not in method_ids or method_ids.index(
        "tensile.toe_zero_intercept"
    ) >= method_ids.index("metal.elastic_modulus"):
        raise RuntimeError(f"Toe compensation did not precede elastic evaluation: {method_ids!r}")

    _click_modeling_process_preview_and_wait(page)
    panel.get_by_text("OLS zero intercept", exact=True).wait_for(timeout=30_000)
    panel.get_by_text("1 quality warning · acknowledgement required", exact=True).wait_for(
        timeout=30_000
    )
    acknowledgement = panel.get_by_role(
        "checkbox", name="Acknowledge toe quality warning", exact=True
    )
    acknowledgement.wait_for(state="visible", timeout=30_000)
    if acknowledgement.is_checked():
        raise RuntimeError("Toe warning was acknowledged before the explicit browser action")
    if not panel.get_by_role("button", name="Save Process result", exact=True).is_disabled():
        raise RuntimeError("Toe warning did not block Process save")
    warning_geometry = _assert_toe_warning_layout(panel)
    if warning_capture_path is not None:
        panel.get_by_text(
            "Review and acknowledge the toe quality warning, then preview again before saving.",
            exact=True,
        ).wait_for(state="visible", timeout=30_000)
        _capture(
            page,
            warning_capture_path,
            1440,
            900,
            before_screenshot=_process_plot_capture_callback(page),
        )
    acknowledgement.check()
    panel.get_by_text("Result retained; preview again to save changes.", exact=True).wait_for(
        timeout=30_000
    )
    _click_modeling_process_preview_and_wait(page)
    if not acknowledgement.is_checked():
        raise RuntimeError("Toe warning acknowledgement did not survive exact preview replay")

    # The warning case is deliberately unsuitable as hardening input: its
    # acknowledged negative offset leaves the zero-stress point at positive
    # plastic strain. Recover through the normal controls and prove the exact
    # Fit hand-off from a clean early-linear domain instead of weakening Fit.
    start.fill("0")
    end.fill("0.002")
    if acknowledgement.is_checked():
        raise RuntimeError("Changing the toe domain did not reset acknowledgement")
    panel.get_by_text("Result retained; preview again to save changes.", exact=True).wait_for(
        timeout=30_000
    )
    _click_modeling_process_preview_and_wait(page)
    panel.get_by_text("Quality checks passed · stress unchanged", exact=True).wait_for(
        timeout=30_000
    )
    if panel.get_by_role("checkbox", name="Acknowledge toe quality warning", exact=True).count():
        raise RuntimeError("Recovered toe preview retained a stale warning acknowledgement")
    for label in ("Focused mapped input", "Selected stage", "Toe estimation fit"):
        page.get_by_text(label, exact=True).wait_for(state="visible", timeout=30_000)
    if page.locator(".toe-result-evidence dd").count() != 4:
        raise RuntimeError(
            "Toe Process result lost offset, slope, R-squared, or point-count evidence"
        )
    _wait_for_modeling_process_plot_size(page)
    return warning_geometry


def _prepare_fit_from_saved_process(
    page: Page,
    base_url: str,
    *,
    label: str = "Fit source Process result",
    require_material_record: bool = False,
) -> dict[str, object]:
    """Prepare Fit from a real exact Process Output rather than a raw Test Data preview."""
    _prepare_modeling_process(page, base_url, verify_data_reload=False)
    if require_material_record:
        _resolve_exact_material_record(page, base_url)
    pointer = _save_process_output_for_fit(
        page,
        label=label,
        reason="Bind one immutable Process result as the exact Fit source.",
    )
    _open_modeling_stage(page, "fit")
    page.wait_for_url(re.compile(r"stage=fit"), timeout=30_000)
    page.locator(".modeling-work-title h1").get_by_text(
        STAGE_HEADINGS["fit"], exact=True
    ).wait_for(timeout=30_000)
    page.wait_for_function(
        """() => {
          const source = document.querySelector('.fit-context-source');
          return Boolean(source && source.getClientRects().length
            && !source.textContent?.includes('No saved Process Output'));
        }""",
        timeout=30_000,
    )
    return pointer


def _prepare_fit_for_export(
    page: Page,
    base_url: str,
    *,
    label: str,
) -> None:
    """Calculate the exact Fit candidates before selecting one for Export."""
    _prepare_fit_from_saved_process(
        page,
        base_url,
        label=label,
        require_material_record=True,
    )
    _click_modeling_fit_preview_and_wait(page)


def _open_fit_evidence(page: Page) -> tuple[Locator, Locator, Locator]:
    """Open the controlled Fit drawer and expose its single local body scrollport."""
    trigger = page.get_by_role("button", name="Candidate parameters", exact=True)
    trigger.wait_for(state="visible", timeout=30_000)
    if trigger.get_attribute("aria-expanded") != "true":
        trigger.click()
    if trigger.get_attribute("aria-expanded") != "true":
        raise RuntimeError("Fit evidence trigger did not expose aria-expanded=true")
    if trigger.get_attribute("aria-controls") != "fit-evidence-dock":
        raise RuntimeError("Fit evidence trigger lost its controlled dock identity")
    drawer = page.locator(".fit-evidence-drawer#fit-evidence-dock")
    drawer.wait_for(state="visible", timeout=30_000)
    if page.get_by_role("region", name="Candidate parameters", exact=True).count() != 1:
        raise RuntimeError("Fit evidence dock lost its Candidate parameters outer label")
    drawer.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)
    drawer.get_by_role("status").wait_for(state="visible", timeout=30_000)
    body = drawer.locator(".fit-evidence-body")
    body.wait_for(state="visible", timeout=30_000)
    if body.get_attribute("tabindex") != "0":
        raise RuntimeError("Fit evidence body must be the focusable local scrollport")
    if drawer.locator(".fit-evidence-scroll-rail").count():
        raise RuntimeError("Fit evidence drawer contains a fake scrollbar rail")
    table = page.get_by_role("table", name="Hardening candidate comparison")
    table.wait_for(state="visible", timeout=30_000)
    return trigger, body, table


def _close_fit_evidence(page: Page, trigger: Locator) -> None:
    """Close through the explicit action and require React focus restoration."""
    drawer = page.locator(".fit-evidence-drawer#fit-evidence-dock")
    drawer.get_by_role("button", name="Close", exact=True).click()
    page.wait_for_function(
        """() => {
          const trigger = document.querySelector('button.fit-evidence-trigger');
          const drawer = document.querySelector('.fit-evidence-drawer#fit-evidence-dock');
          return Boolean(trigger && trigger.getAttribute('aria-expanded') === 'false' && !drawer);
        }""",
        timeout=30_000,
    )
    if page.evaluate("() => document.activeElement?.textContent?.trim()") != "Candidate parameters":
        raise RuntimeError("Fit evidence Close did not restore trigger focus")
    if trigger.get_attribute("aria-expanded") != "false":
        raise RuntimeError("Fit evidence trigger remained expanded after Close")


def _assert_fit_candidate_surface(page: Page, table: Locator) -> None:
    """Assert the numerical identity, decision, and recovery fields in Fit."""
    source_evidence = page.locator(".fit-source-evidence")
    source_evidence.wait_for(state="visible", timeout=30_000)
    source_evidence.get_by_text("Process source", exact=True).wait_for(state="visible", timeout=30_000)
    source_evidence.get_by_text("Source digest", exact=True).wait_for(state="visible", timeout=30_000)
    source_evidence.get_by_text("Fit method", exact=True).wait_for(state="visible", timeout=30_000)
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
        if table.get_by_role("columnheader", name=column, exact=True).count() != 1:
            raise RuntimeError(f"Fit candidate table is missing {column}")
    for text, message in (
        ("RMSE", "RMSE evidence"),
        ("Converged", "convergence evidence"),
        ("active bound", "active-bound evidence"),
        ("identifiability", "identifiability evidence"),
        ("Select candidate", "candidate selection action"),
    ):
        if table.get_by_text(re.compile(text, re.IGNORECASE)).count() == 0:
            raise RuntimeError(f"Fit candidate table is missing {message}")
    page.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)


def _assert_fit_display_scale(page: Page, context: str) -> None:
    """Keep Ghosh's epsilon_0 tail out of the normal graph scale only."""
    plot = page.locator(".persistent-modeling-plot")
    plot.wait_for(state="visible", timeout=30_000)
    axis_labels = [text.strip() for text in plot.locator(".chart-axis-label").all_text_contents()]
    if not any(label.startswith("Hardening stress") and "[MPa]" in label for label in axis_labels):
        raise RuntimeError(f"Fit {context} graph is not readable in MPa: {axis_labels!r}")
    plot_text = plot.inner_text()
    if re.search(r"1e\d+\s*GPa", plot_text, re.IGNORECASE):
        raise RuntimeError(f"Fit {context} graph exposed an epsilon_0-scale GPa label: {plot_text!r}")
    note = plot.locator(".ghosh-display-scale-note")
    note.wait_for(state="visible", timeout=30_000)
    if note.inner_text().strip() != "Ghosh exceeds chart scale":
        raise RuntimeError(f"Fit {context} graph exposed verbose scale helper text")
    note_metrics = note.evaluate(
        "element => ({ height: element.getBoundingClientRect().height, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight, text: element.textContent?.trim() || '' })"
    )
    if note_metrics["scrollHeight"] > note_metrics["clientHeight"] + 1:
        raise RuntimeError(f"Fit {context} Ghosh display note is clipped: {note_metrics!r}")
    extrapolation_geometry = plot.locator("svg[role=img]").evaluate(
        """svg => {
          const box = node => {
            if (!node || typeof node.getBBox !== 'function') return null;
            const value = node.getBBox();
            return {
              left: value.x,
              top: value.y,
              right: value.x + value.width,
              bottom: value.y + value.height,
              width: value.width,
              height: value.height,
            };
          };
          const attributeBox = node => {
            if (!node) return null;
            const x = Number(node.getAttribute('x'));
            const y = Number(node.getAttribute('y'));
            const width = Number(node.getAttribute('width'));
            const height = Number(node.getAttribute('height'));
            if (![x, y, width, height].every(Number.isFinite)) return null;
            return { left: x, top: y, right: x + width, bottom: y + height, width, height };
          };
          const label = box(svg.querySelector('.extrapolation-annotation-layer text'));
          const shade = attributeBox(svg.querySelector('.extrapolation-region rect'));
          const hardeningGroup = svg.querySelector('.hardening-series-clip');
          const clipPathUrl = hardeningGroup?.getAttribute('clip-path') || '';
          const clipPathMatch = clipPathUrl.match(/^url\\(\\s*["']?#([^"')]+)["']?\\s*\\)$/);
          const clipPathId = clipPathMatch?.[1] || '';
          const clipPath = clipPathId ? svg.ownerDocument?.getElementById(clipPathId) : null;
          const clipRect = attributeBox(clipPath?.querySelector('rect'));
          const curveLines = [...svg.querySelectorAll('polyline.curve-line')];
          const curveLinesContained = Boolean(hardeningGroup)
            && curveLines.length > 0
            && curveLines.every(line => hardeningGroup.contains(line));
          const verticalAxis = [...svg.querySelectorAll('line.chart-axis')]
            .find(line => line.getAttribute('x1') === line.getAttribute('x2'));
          const horizontalAxis = [...svg.querySelectorAll('line.chart-axis')]
            .find(line => line.getAttribute('y1') === line.getAttribute('y2'));
          const viewBox = svg.viewBox?.baseVal;
          const plotLeft = Number(verticalAxis?.getAttribute('x1'));
          const plotRight = Number(horizontalAxis?.getAttribute('x2'));
          const svgLeft = Number(viewBox?.x);
          const svgRight = svgLeft + Number(viewBox?.width);
          if (!label || !shade || !Number.isFinite(plotLeft) || !Number.isFinite(plotRight)
            || !Number.isFinite(svgLeft) || !Number.isFinite(svgRight)) return null;
          return {
            label,
            shade,
            plot: { left: plotLeft, right: plotRight },
            svg: { left: svgLeft, right: svgRight },
            hardeningClip: {
              groupPresent: Boolean(hardeningGroup),
              clipPathUrl,
              clipPathId,
              rect: clipRect,
              curveLineCount: curveLines.length,
              curveLinesContained,
            },
          };
        }"""
    )
    if not isinstance(extrapolation_geometry, dict):
        raise RuntimeError(f"Fit {context} extrapolation label/shade geometry is unavailable")
    label_geometry = extrapolation_geometry.get("label")
    shade_geometry = extrapolation_geometry.get("shade")
    plot_geometry = extrapolation_geometry.get("plot")
    svg_geometry = extrapolation_geometry.get("svg")
    hardening_clip_geometry = extrapolation_geometry.get("hardeningClip")
    if not all(isinstance(value, dict) for value in (label_geometry, shade_geometry, plot_geometry, svg_geometry, hardening_clip_geometry)):
        raise RuntimeError(f"Fit {context} extrapolation label/shade geometry is malformed: {extrapolation_geometry!r}")
    label_geometry = cast(dict[str, object], label_geometry)
    shade_geometry = cast(dict[str, object], shade_geometry)
    plot_geometry = cast(dict[str, object], plot_geometry)
    svg_geometry = cast(dict[str, object], svg_geometry)
    hardening_clip_geometry = cast(dict[str, object], hardening_clip_geometry)
    hardening_clip_rect = hardening_clip_geometry.get("rect")
    if (
        hardening_clip_geometry.get("groupPresent") is not True
        or not isinstance(hardening_clip_geometry.get("clipPathUrl"), str)
        or not hardening_clip_geometry.get("clipPathUrl")
        or not isinstance(hardening_clip_geometry.get("clipPathId"), str)
        or not hardening_clip_geometry.get("clipPathId")
        or hardening_clip_geometry.get("curveLinesContained") is not True
        or not isinstance(hardening_clip_rect, dict)
    ):
        raise RuntimeError(f"Fit {context} hardening curves are not contained by a resolved clipPath: {extrapolation_geometry!r}")
    hardening_clip_rect = cast(dict[str, object], hardening_clip_rect)
    geometry_tolerance = 1.0
    if (
        _as_float(label_geometry.get("width")) <= 0
        or _as_float(label_geometry.get("height")) <= 0
        or _as_float(shade_geometry.get("width")) <= 0
        or _as_float(shade_geometry.get("height")) <= 0
        or _as_float(hardening_clip_rect.get("width")) <= 0
        or _as_float(hardening_clip_rect.get("height")) <= 0
        or abs(_as_float(hardening_clip_rect.get("top")) - _as_float(shade_geometry.get("top"))) > geometry_tolerance
        or _as_float(label_geometry.get("bottom")) > _as_float(hardening_clip_rect.get("top")) + geometry_tolerance
    ):
        raise RuntimeError(f"Fit {context} extrapolation label overlaps the clipped hardening data area: {extrapolation_geometry!r}")
    horizontal_left = max(_as_float(plot_geometry.get("left")), _as_float(svg_geometry.get("left")))
    horizontal_right = min(_as_float(plot_geometry.get("right")), _as_float(svg_geometry.get("right")))
    if (
        _as_float(label_geometry.get("left")) < horizontal_left - geometry_tolerance
        or _as_float(label_geometry.get("right")) > horizontal_right + geometry_tolerance
    ):
        raise RuntimeError(f"Fit {context} extrapolation label escaped the SVG/plot bounds: {extrapolation_geometry!r}")


def _select_warned_fit_candidate(table: Locator) -> None:
    """Select the first candidate whose Warning column contains a warning."""
    rows = table.locator("tbody tr")
    for index in range(rows.count()):
        row = rows.nth(index)
        warning = row.locator("td").last.inner_text().strip()
        if warning and warning.casefold() != "none":
            if row.get_by_role(
                "button", name=re.compile(r"^.+ candidate selected$")
            ).count():
                return
            candidate = row.get_by_role(
                "button", name=re.compile(r"^Select .+ candidate$")
            )
            if candidate.count() != 1:
                raise RuntimeError("Warned Fit candidate does not expose one selection action")
            candidate.click()
            return
    raise RuntimeError("Fit candidate table did not expose a warned candidate")


def _select_exact_fit_candidate(table: Locator, *, candidate_key: str) -> None:
    """Select the approved combined Swift + Voce 50/50 candidate by identity."""
    labels = {
        "swift+voce": re.compile(
            r"^Select swift \+ voce 50[/]50 candidate$",
            re.IGNORECASE,
        ),
    }
    label = labels.get(candidate_key)
    if label is None:
        raise RuntimeError(f"Unsupported exact Fit capture candidate: {candidate_key}")
    candidate = table.get_by_role("button", name=label)
    if candidate.count() != 1:
        raise RuntimeError(
            f"Fit candidate table did not expose exactly one {candidate_key!r} action"
        )
    candidate.click()


def _assert_fit_selected_evidence(page: Page) -> None:
    parameter_table = page.get_by_role(
        "table", name="Selected candidate parameters and bounds"
    )
    parameter_table.wait_for(state="visible", timeout=30_000)
    for column in ("Law", "Parameter", "Unit", "Lower", "Initial", "Fitted", "Upper", "Bound / condition"):
        if parameter_table.get_by_role("columnheader", name=column, exact=True).count() != 1:
            raise RuntimeError(f"Selected Fit parameter table is missing {column}")
    if parameter_table.locator("tbody tr").count() < 1:
        raise RuntimeError("Selected Fit candidate must expose parameter and bound evidence")
    page.get_by_role("textbox", name="Candidate selection reason", exact=True).wait_for(state="visible", timeout=30_000)
    page.get_by_role("button", name="Close", exact=True).wait_for(state="visible", timeout=30_000)


def _scroll_fit_evidence_locally(
    page: Page,
    body: Locator,
    *,
    close_escape: bool = True,
) -> None:
    """Exercise PageDown, wheel, native-thumb drag, and optionally Escape on one body."""
    body.evaluate(
        """el => {
          el.scrollTop = 0;
          el.scrollLeft = 0;
          el.focus({ preventScroll: true });
        }"""
    )
    before = page.evaluate("() => window.scrollY")
    metrics = body.evaluate(
        """el => ({
          scrollTop: el.scrollTop,
          scrollLeft: el.scrollLeft,
          scrollHeight: el.scrollHeight,
          scrollWidth: el.scrollWidth,
          clientHeight: el.clientHeight,
          clientWidth: el.clientWidth,
          offsetHeight: el.offsetHeight,
          offsetWidth: el.offsetWidth,
          rect: el.getBoundingClientRect().toJSON(),
        })"""
    )
    if metrics["scrollHeight"] <= metrics["clientHeight"]:
        raise RuntimeError(f"Fit evidence body is not vertically overflowing: {metrics!r}")
    gutter = metrics["offsetWidth"] - metrics["clientWidth"]
    if not 12 <= gutter <= 16:
        raise RuntimeError(
            "Fit evidence body must reserve a genuine native scrollbar gutter "
            f"of 12-16 px inclusive: {metrics!r}"
        )
    body.press("PageDown")
    page.wait_for_function(
        """() => {
          const body = document.querySelector('.fit-evidence-body');
          return Boolean(body && body.scrollTop > 0 && body.scrollTop < body.scrollHeight - body.clientHeight + 1);
        }""",
        timeout=30_000,
    )
    after_page_down = body.evaluate("el => el.scrollTop")
    if after_page_down <= 0:
        raise RuntimeError("Fit evidence PageDown proof did not move the local body")
    # PageDown can land at the bottom of a short drawer.  Reset only this
    # focusable local scrollport before the wheel proof so the wheel has a
    # deterministic, observable range; the page itself remains untouched.
    body.evaluate(
        """el => {
          el.scrollTop = 0;
          el.scrollLeft = 0;
          el.focus({ preventScroll: true });
        }"""
    )
    page.wait_for_function(
        """() => {
          const body = document.querySelector('.fit-evidence-body');
          return Boolean(body && body.scrollTop === 0 && body.scrollLeft === 0);
        }""",
        timeout=30_000,
    )
    wheel_before = body.evaluate(
        """el => ({
          scrollLeft: el.scrollLeft,
          rectLeft: el.getBoundingClientRect().left,
          rectRight: el.getBoundingClientRect().right,
        })"""
    )
    before_wheel_left = wheel_before["scrollLeft"]
    before_wheel_page_scroll = page.evaluate("() => window.scrollY")
    page.mouse.move(metrics["rect"]["left"] + metrics["clientWidth"] / 2, metrics["rect"]["top"] + metrics["clientHeight"] / 2)
    page.mouse.wheel(0, 92)
    page.wait_for_function(
        """() => {
          const body = document.querySelector('.fit-evidence-body');
          return Boolean(body && body.scrollTop > 0);
        }""",
        timeout=30_000,
    )
    after_wheel = body.evaluate("el => el.scrollTop")
    wheel_after = body.evaluate(
        """el => ({
          scrollTop: el.scrollTop,
          scrollLeft: el.scrollLeft,
          rectLeft: el.getBoundingClientRect().left,
          rectRight: el.getBoundingClientRect().right,
        })"""
    )
    if after_wheel <= 0:
        raise RuntimeError("Fit evidence wheel did not move the local body")
    if wheel_after["scrollLeft"] != wheel_before["scrollLeft"]:
        raise RuntimeError(
            "Fit evidence wheel horizontally shifted the local body: "
            f"before={wheel_before!r}, after={wheel_after!r}"
        )
    if (
        wheel_after["rectLeft"] != wheel_before["rectLeft"]
        or wheel_after["rectRight"] != wheel_before["rectRight"]
    ):
        raise RuntimeError(
            "Fit evidence wheel horizontally shifted the scrollport geometry: "
            f"before={wheel_before!r}, after={wheel_after!r}"
        )
    if body.evaluate("el => el.scrollLeft") != before_wheel_left:
        raise RuntimeError("Fit evidence wheel shifted the local body horizontally")
    if page.evaluate("() => window.scrollY") != before_wheel_page_scroll:
        raise RuntimeError("Fit evidence wheel changed the page scroll position")
    body.evaluate("el => { el.scrollTop = 0; el.scrollLeft = 0; }")
    refreshed = body.evaluate(
        """el => ({
          rect: el.getBoundingClientRect().toJSON(),
          clientHeight: el.clientHeight,
          clientWidth: el.clientWidth,
          offsetHeight: el.offsetHeight,
          offsetWidth: el.offsetWidth,
          scrollHeight: el.scrollHeight,
        })"""
    )
    vertical_gutter = refreshed["offsetWidth"] - refreshed["clientWidth"]
    horizontal_gutter = refreshed["offsetHeight"] - refreshed["clientHeight"]
    track_height = refreshed["rect"]["height"] - horizontal_gutter
    track_x = refreshed["rect"]["right"] - vertical_gutter / 2
    thumb_height = max(
        20,
        track_height * refreshed["clientHeight"] / refreshed["scrollHeight"],
    )
    thumb_start = refreshed["rect"]["top"] + thumb_height / 2
    page.mouse.move(track_x, thumb_start)
    page.mouse.down()
    page.mouse.move(track_x, thumb_start + min(48, track_height / 3), steps=8)
    page.mouse.up()
    after_drag = body.evaluate("el => el.scrollTop")
    if after_drag <= 0:
        raise RuntimeError("Fit evidence native scrollbar thumb drag did not move the local body")
    if page.evaluate("() => window.scrollY") != before:
        raise RuntimeError("Fit evidence local scrolling changed the page scroll position")
    if close_escape:
        page.keyboard.press("Escape")
        active_after_escape = page.evaluate(
            """() => ({
              tag: document.activeElement?.tagName || null,
              text: document.activeElement?.textContent?.trim() || null,
              triggerExpanded: document.querySelector('button.fit-evidence-trigger')?.getAttribute('aria-expanded') || null,
            })"""
        )
        if active_after_escape["text"] != "Candidate parameters" or active_after_escape["triggerExpanded"] != "false":
            raise RuntimeError(f"Fit evidence Escape recovery did not restore trigger focus: {active_after_escape!r}")


def _position_fit_evidence_decision_surface(page: Page, body: Locator) -> None:
    """Place the final evidence capture on the local decision surface.

    The drawer is intentionally a short, native scrollport at the 1440 x 900
    reference viewport.  The full parameter table and the decision controls do
    not fit at once, so solve for a local scroll position where the selected
    parameter table, selection reason, warning checkbox, and actual warning
    text each have a meaningful visible intersection.  The warning text is
    measured from a DOM Range over its rendered text nodes, rather than from
    the surrounding label, so a visible checkbox cannot mask clipped warning
    copy.  The table bottom and warning text receive an inset as well, keeping
    those decision landmarks inside the body rather than on a one-pixel edge.
    The body is the only element whose scroll position may change; page scroll
    must remain untouched.
    """
    before = page.evaluate("() => window.scrollY")
    metrics = body.evaluate(
        """el => {
          const table = el.querySelector('table[aria-label="Selected candidate parameters and bounds"]');
          const reason = el.querySelector('[aria-label="Candidate selection reason"]');
          const acknowledgement = el.querySelector('[aria-label="Acknowledge selected candidate warning"]');
          const warningLabel = acknowledgement?.closest('label');
          if (!table || !reason || !acknowledgement || !warningLabel) {
            throw new Error('Fit decision surface is missing table, selection reason, warning checkbox, or warning label');
          }
          const bodyRect = el.getBoundingClientRect();
          const surface = (node) => {
            const rect = node.getBoundingClientRect();
            return {
              top: rect.top - bodyRect.top + el.scrollTop,
              bottom: rect.bottom - bodyRect.top + el.scrollTop,
            };
          };
          const labelledSurface = (node) => surface(node.closest('label') || node);
          const textRangeSurface = (root) => {
            const range = document.createRange();
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
            const rects = [];
            while (walker.nextNode()) {
              const text = walker.currentNode;
              if (!text.textContent?.trim()) continue;
              range.selectNodeContents(text);
              for (const rect of range.getClientRects()) {
                if (rect.width > 0 && rect.height > 0) {
                  rects.push({
                    top: rect.top - bodyRect.top + el.scrollTop,
                    bottom: rect.bottom - bodyRect.top + el.scrollTop,
                  });
                }
              }
            }
            if (!rects.length) throw new Error('Fit warning text range has no rendered text rects');
            return {
              top: Math.min(...rects.map((rect) => rect.top)),
              bottom: Math.max(...rects.map((rect) => rect.bottom)),
              rects,
            };
          };
          const tableSurface = surface(table);
          const reasonSurface = labelledSurface(reason);
          const acknowledgementSurface = labelledSurface(acknowledgement);
          const acknowledgementInputSurface = surface(acknowledgement);
          const warningTextSurface = textRangeSurface(warningLabel);
          const maxScrollTop = Math.max(0, el.scrollHeight - el.clientHeight);
          const meaningfulVisiblePx = 12;
          const intersectionBounds = ({ top, bottom }) => ({
            lower: top + meaningfulVisiblePx - el.clientHeight,
            upper: bottom - meaningfulVisiblePx,
          });
          const tableIntersection = intersectionBounds(tableSurface);
          const reasonIntersection = intersectionBounds(reasonSurface);
          const acknowledgementIntersection = intersectionBounds(acknowledgementSurface);
          const acknowledgementInputIntersection = intersectionBounds(acknowledgementInputSurface);
          const warningTextIntersection = intersectionBounds(warningTextSurface);
          // Keep the table bottom and actual warning text comfortably inside
          // the body.  These content-coordinate bounds are intersected with
          // the normal visibility bounds above before selecting a scrollTop.
          const tableBottomBounds = {
            lower: tableSurface.bottom - el.clientHeight + meaningfulVisiblePx,
            upper: tableSurface.bottom - meaningfulVisiblePx,
          };
          const feasibleLower = Math.max(
            0,
            tableIntersection.lower,
            reasonIntersection.lower,
            acknowledgementIntersection.lower,
            acknowledgementInputIntersection.lower,
            warningTextIntersection.lower,
            tableBottomBounds.lower,
          );
          const feasibleUpper = Math.min(
            maxScrollTop,
            tableIntersection.upper,
            reasonIntersection.upper,
            acknowledgementIntersection.upper,
            acknowledgementInputIntersection.upper,
            warningTextIntersection.upper,
            tableBottomBounds.upper,
          );
          const integerLower = Math.ceil(feasibleLower);
          const integerUpper = Math.floor(feasibleUpper);
          const hasFeasibleInteger = integerLower <= integerUpper;
          const targetScrollTop = hasFeasibleInteger
            ? Math.floor((integerLower + integerUpper) / 2)
            : null;
          if (targetScrollTop !== null) {
            // This is a deterministic local scroll, not a screenshot crop or
            // UI resize.  No ancestor or window scroll position is mutated.
            el.scrollTop = targetScrollTop;
          }
          const viewportTop = bodyRect.top;
          const viewportBottom = viewportTop + el.clientHeight;
          const visible = (node) => {
            const target = node.closest('label') || node;
            const rect = target.getBoundingClientRect();
            const intersection = Math.max(
              0,
              Math.min(rect.bottom, viewportBottom) - Math.max(rect.top, viewportTop),
            );
            return {
              top: rect.top,
              bottom: rect.bottom,
              intersection,
              intersects: intersection >= meaningfulVisiblePx,
            };
          };
          const visibleRange = (rangeSurface) => {
            const intersections = rangeSurface.rects.map((contentRect) => {
              const top = viewportTop + contentRect.top - el.scrollTop;
              const bottom = viewportTop + contentRect.bottom - el.scrollTop;
              return Math.max(0, Math.min(bottom, viewportBottom) - Math.max(top, viewportTop));
            });
            const intersection = Math.max(0, ...intersections);
            return {
              top: viewportTop + rangeSurface.top - el.scrollTop,
              bottom: viewportTop + rangeSurface.bottom - el.scrollTop,
              intersection,
              intersects: intersection >= meaningfulVisiblePx,
            };
          };
          return {
            scrollTop: el.scrollTop,
            maxScrollTop,
            windowScrollY: window.scrollY,
            meaningfulVisiblePx,
            feasibleLower,
            feasibleUpper,
            integerLower,
            integerUpper,
            targetScrollTop,
            tableSurface,
            reasonSurface,
            acknowledgementSurface,
            acknowledgementInputSurface,
            warningTextSurface,
            table: visible(table),
            reason: visible(reason.closest('label') || reason),
            acknowledgement: visible(acknowledgement.closest('label') || acknowledgement),
            acknowledgementInput: visible(acknowledgement),
            warningText: visibleRange(warningTextSurface),
          };
        }"""
    )
    if page.evaluate("() => window.scrollY") != before or metrics["windowScrollY"] != before:
        raise RuntimeError("Fit decision surface positioning changed the page scroll position")
    if metrics["targetScrollTop"] is None:
        raise RuntimeError(f"Fit decision surface has no feasible local scroll interval: {metrics!r}")
    if metrics["scrollTop"] <= 0:
        raise RuntimeError(f"Fit decision surface did not move the local body: {metrics!r}")
    for key in ("table", "reason", "acknowledgementInput", "warningText"):
        if not metrics[key]["intersects"] or metrics[key]["intersection"] < metrics["meaningfulVisiblePx"]:
            raise RuntimeError(f"Fit decision surface is not visible in the local body: {metrics!r}")


def _assert_modeling_process_preview(
    page: Page,
    expected_modulus: str = "210.0 GPa",
    method_label: str = "Auto robust",
) -> None:
    """Run the focused Process preview and assert its normal non-Fit surface."""
    _click_modeling_process_preview_and_wait(page)
    _wait_modeling_process_panel(page)
    _wait_for_modeling_process_plot_size(page)
    panel = page.locator('[data-modeling-process-panel="ready"]')
    if panel.count() != 1 or not panel.is_visible():
        raise RuntimeError("Process preview did not settle on its ready panel")
    source = panel.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process preview source is not the selected Test Data: {source.inner_text()!r}")
    heading = page.locator(".persistent-modeling-plot > .section-heading")
    heading.locator("h2").wait_for(state="visible", timeout=30_000)
    toolbar = page.locator(".persistent-modeling-plot > .modeling-plot-toolbar")
    toolbar.wait_for(state="visible", timeout=30_000)
    for control in ("Reset view", "Pan", "Select range"):
        button = toolbar.get_by_role("button", name=control, exact=True)
        button.wait_for(state="visible", timeout=30_000)
        if button.is_disabled():
            raise RuntimeError(f"Process plot control is unexpectedly disabled: {control}")
    result = panel.locator(".process-band-result")
    result.get_by_text(expected_modulus, exact=True).wait_for(timeout=30_000)
    save = panel.get_by_role("button", name="Save Process result", exact=True)
    save.wait_for(state="visible", timeout=30_000)
    controls = panel.locator(".process-band-controls")
    method = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    method.wait_for(state="visible", timeout=30_000)
    expected_methods = [
        ("robust_huber", "Auto robust"),
        ("linear_regression", "Linear regression"),
        ("chord", "Chord"),
        ("secant", "Secant"),
        ("manual", "Manual slope"),
    ]
    if method.locator("option").all_inner_texts() != [label for _, label in expected_methods]:
        raise RuntimeError("Process Evaluation method options drifted")
    method_by_label = {label: value for value, label in expected_methods}
    for value, label in expected_methods:
        # select_option exercises the pointer path; Home/ArrowDown exercises
        # the native keyboard path without replacing the native select.
        method.select_option(value)
        if method.input_value() != value:
            raise RuntimeError(f"Process pointer method selection drifted: {label!r}")
        method.focus()
        method.press("Home")
        for _ in range(expected_methods.index((value, label))):
            method.press("ArrowDown")
        if method.input_value() != value:
            raise RuntimeError(f"Process keyboard method selection drifted: {label!r}")
    method.select_option(method_by_label[method_label])
    _wait_modeling_process_panel(page)
    _click_modeling_process_preview_and_wait(page)
    _wait_for_modeling_process_plot_size(page)
    if method.locator("option:checked").inner_text() != method_label:
        raise RuntimeError(f"Process preview method drifted: expected {method_label!r}")
    for label in ("Elastic range start", "Elastic range end"):
        controls.get_by_role("spinbutton", name=label, exact=True).wait_for(state="visible", timeout=30_000)
    if page.locator(".fit-evidence-drawer").count() or page.get_by_text("Candidate equations", exact=True).count() or page.get_by_text("Fit domain", exact=True).count() or page.get_by_text("Selected blend", exact=True).count():
        raise RuntimeError("Process preview exposed Fit candidate controls")
    _assert_modeling_process_geometry(page)


def _assert_modeling_process_manual_surface(
    page: Page,
    *,
    capture_path: Path | None = None,
) -> None:
    """Exercise the compact Process manual workup, then restore Auto robust."""
    panel = page.locator('[data-modeling-process-panel="ready"]')
    controls = panel.locator(".process-band-controls")
    manual = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    # Locator.click is a real pointer click in the live capture (not a
    # synthetic React event), so the helper proves the normal interaction path.
    manual.select_option("manual")
    value = controls.get_by_role("spinbutton", name="Manual Young's modulus", exact=True)
    unit = controls.get_by_role("combobox", name="Manual Young's modulus unit", exact=True)
    reason = controls.get_by_role("textbox", name="Manual Young's modulus reason", exact=True)
    for control in (value, unit, reason):
        control.wait_for(state="visible", timeout=30_000)
    panel_box = _bounding_box_edges(panel.bounding_box())
    if panel_box is None:
        raise RuntimeError("Process manual controls have no current-step panel bounds")
    for name, control in (("value", value), ("unit", unit), ("reason", reason)):
        control_box = _bounding_box_edges(control.bounding_box())
        if control_box is None or control_box["left"] < panel_box["left"] or control_box["right"] > panel_box["right"] or control_box["top"] < panel_box["top"] or control_box["bottom"] > panel_box["bottom"]:
            raise RuntimeError(f"Process manual {name} control escaped the current-step band: panel={panel_box}, control={control_box}")
    hit_tests = page.evaluate(
        """() => [
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus"]',
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus unit"]',
          '[data-modeling-process-panel="ready"] [aria-label="Manual Young\\'s modulus reason"]',
        ].map(selector => {
          const node = document.querySelector(selector);
          const box = node?.getBoundingClientRect();
          const hit = box ? document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) : null;
          return { selector, own: Boolean(node && hit && (hit === node || node.contains(hit))) };
        })"""
    )
    if not isinstance(hit_tests, list) or any(not isinstance(item, dict) or not item.get("own") for item in hit_tests):
        raise RuntimeError(f"Process manual controls failed center hit-testing: {hit_tests!r}")
    overflow = page.evaluate(
        """() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth })"""
    )
    if not isinstance(overflow, dict) or float(overflow.get("scrollWidth", 0)) > float(overflow.get("clientWidth", 0)):
        raise RuntimeError(f"Process manual surface introduced page horizontal overflow: {overflow!r}")
    value.focus()
    page.keyboard.press("Tab")
    if page.evaluate("() => document.activeElement?.getAttribute('aria-label')") != "Manual Young's modulus unit":
        raise RuntimeError("Process manual value did not Tab to Unit")
    page.keyboard.press("Tab")
    if page.evaluate("() => document.activeElement?.getAttribute('aria-label')") != "Manual Young's modulus reason":
        raise RuntimeError("Process manual Unit did not Tab to reason")
    plot_box = page.locator(".persistent-modeling-plot").bounding_box()
    svg_box = page.locator(".persistent-modeling-plot svg[role=img]").bounding_box()
    if plot_box is None or plot_box["height"] < 280 or svg_box is None or svg_box["height"] < 230:
        raise RuntimeError(f"Process manual surface compressed the plot: plot={plot_box}, svg={svg_box}")
    viewport = page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
    _measure_process_fit(
        page,
        "process",
        int(viewport["width"]),
        int(viewport["height"]),
        minimum_svg_height=230,
    )
    save = panel.get_by_role("button", name="Save Process result", exact=True)
    panel.locator(".process-band-save").scroll_into_view_if_needed()
    page.wait_for_timeout(100)
    save_hit = save.evaluate(
        """node => {
          const ribbon = node?.closest('.modeling-task-ribbon');
          const box = node?.getBoundingClientRect();
          const ribbonBox = ribbon?.getBoundingClientRect();
          const hit = box ? document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) : null;
          return Boolean(node && box && ribbonBox
            && box.top >= ribbonBox.top - 1 && box.bottom <= ribbonBox.bottom + 1
            && hit && (hit === node || node.contains(hit)));
        }"""
    )
    if not save_hit:
        raise RuntimeError("Process manual Save action is not reachable after local ribbon scrolling")
    if capture_path is not None:
        _capture(page, capture_path, 1366, 768, focus_selector=None)
    auto = controls.get_by_role("combobox", name="Evaluation method", exact=True)
    auto.select_option("robust_huber")
    page.wait_for_function(
        """() => document.querySelector('[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]')
          ?.value === 'robust_huber'""",
        timeout=30_000,
    )
    _click_modeling_process_preview_and_wait(page)
    _wait_modeling_process_panel(page)
    _wait_for_modeling_process_plot_size(page)
    controls = page.locator('[data-modeling-process-panel="ready"] .process-band-controls')
    if controls.get_by_role("combobox", name="Evaluation method", exact=True).input_value() != "robust_huber":
        raise RuntimeError("Process manual helper did not restore Auto robust")
    page.locator('[data-modeling-process-panel="ready"] .process-band-result').get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    _assert_modeling_process_geometry(page)


def _assert_modeling_process_geometry(page: Page) -> None:
    ribbon = _bounding_box_edges(page.locator(".modeling-task-ribbon").bounding_box())
    panel = _bounding_box_edges(page.locator('[data-modeling-process-panel="ready"]').bounding_box())
    plot = _bounding_box_edges(page.locator(".persistent-modeling-plot").bounding_box())
    svg = _bounding_box_edges(page.locator(".persistent-modeling-plot svg[role='img']").bounding_box())
    save_band = _bounding_box_edges(page.locator(".process-band-save").bounding_box())
    save = page.get_by_role("button", name="Save Process result", exact=True)
    save_box = _bounding_box_edges(save.bounding_box())
    if ribbon is None or panel is None or plot is None or svg is None or save_band is None or save_box is None:
        raise RuntimeError("Process preview geometry is unavailable")
    if plot["height"] < 280 or svg["height"] < 230:
        raise RuntimeError(f"Process plot geometry fell below the required minima: plot={plot}, svg={svg}")
    if panel["left"] < ribbon["left"] - 1 or panel["right"] > ribbon["right"] + 1 or panel["top"] < ribbon["top"] - 1 or panel["bottom"] > ribbon["bottom"] + 1:
        raise RuntimeError(f"Process panel escaped the task ribbon: panel={panel}, ribbon={ribbon}")
    if save_band["bottom"] > plot["top"] + 1 or save_box["bottom"] > plot["top"] + 1:
        raise RuntimeError(f"Process save band crosses the plot top: save_band={save_band}, save={save_box}, plot={plot}")
    hit = page.evaluate(
        """button => {
          const box = button.getBoundingClientRect();
          const element = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
          return {
            insideSave: Boolean(element && button.contains(element)),
            tag: element?.tagName ?? null,
            graph: Boolean(element?.closest('.persistent-modeling-plot')),
            svg: Boolean(element?.closest('svg')),
          };
        }""",
        save.element_handle(),
    )
    if not hit["insideSave"] or hit["graph"] or hit["svg"]:
        raise RuntimeError(f"Process Save center is intercepted by graph/SVG: {hit}")
    _assert_modeling_process_table_geometry(page)


def _assert_modeling_process_draft_geometry(page: Page) -> None:
    """Exercise the action-needed draft height and restore a settled preview."""
    method = page.locator(
        '[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]'
    )
    method.wait_for(state="visible", timeout=30_000)
    current = method.input_value()
    draft = "chord" if current != "chord" else "linear_regression"
    method.select_option(draft)
    page.wait_for_function(
        """() => {
          const preview = [...document.querySelectorAll('button')]
            .find(button => button.textContent?.trim() === 'Preview changes');
          return Boolean(preview && !preview.disabled);
        }""",
        timeout=30_000,
    )
    _assert_modeling_process_geometry(page)
    method.select_option(current)
    _click_modeling_process_preview_and_wait(page)
    _wait_for_modeling_process_plot_size(page)


def _assert_modeling_process_stage_round_trip(
    page: Page,
    base_url: str,
    *,
    expected_current_output: dict[str, object],
    expected_current_label: str,
) -> None:
    """Keep one copied history draft and the saved current through Data→Fit→Export→Process."""
    panel = page.locator('[data-modeling-process-panel="ready"]')
    panel.wait_for(state="visible", timeout=30_000)
    source = panel.locator(".process-band-source")
    if source.inner_text().strip() != PROCESS_SOURCE_VISIBLE_IDENTITY:
        raise RuntimeError(f"Process round-trip source drifted: {source.inner_text()!r}")
    label = panel.get_by_role("textbox", name="Process result name", exact=True)
    reason = panel.get_by_role("textbox", name="Reason for saving Process result", exact=True)
    draft_label = label.input_value()
    draft_reason = reason.input_value()
    method = panel.get_by_role("combobox", name="Evaluation method", exact=True)
    draft_method = method.input_value()
    draft_range_start = panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value()
    draft_range_end = panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value()
    if draft_method != "chord" or draft_range_start != "0.001" or draft_range_end != "0.003":
        raise RuntimeError(
            "Process round-trip did not start from the copied Chord draft settings: "
            f"method={draft_method!r}, range={draft_range_start!r}–{draft_range_end!r}"
        )
    panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    graph = page.locator(".persistent-modeling-plot svg[role='img']")
    graph.wait_for(state="visible", timeout=30_000)
    graph_label = graph.get_attribute("aria-label")
    graph_box = graph.bounding_box()
    if not graph_label or graph_box is None or graph_box["width"] <= 0 or graph_box["height"] <= 0:
        raise RuntimeError("Process round-trip graph is not a visible retained engineering graph")

    expected_current_output_id = expected_current_output.get("processing_output_id")
    if not isinstance(expected_current_output_id, str) or not expected_current_output_id:
        raise RuntimeError(
            "Process round-trip expected current output has no stable identity: "
            f"{expected_current_output!r}"
        )
    source_pin, profile_pin = _process_session_pins(page)
    before_outputs = _matching_process_outputs(
        _list_processing_outputs(page, base_url), source_pin, profile_pin
    )
    before_by_id = {
        str(item.get("processing_output_id")): item
        for item in before_outputs
        if item.get("processing_output_id")
    }
    before_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if not any(expected_current_label in row and "current" in row for row in before_rows):
        raise RuntimeError("Process round-trip did not expose the newly saved output as the sole current row")
    if expected_current_output_id not in before_by_id:
        raise RuntimeError("Process round-trip current output identity is missing before stage navigation")

    _assert_capture_processing_output_pointer(page, expected_current_output)

    mutation_requests: list[str] = []
    data_preview_requests: list[str] = []
    forbidden_preview_requests: list[str] = []
    mutation_tokens = ("processing-outputs", "selection", "export")
    preview_path = "/processing:preview"
    active_stage = "process"

    def record_mutation(request: object) -> None:
        method_name = str(getattr(request, "method", "")).upper()
        path = urlsplit(str(getattr(request, "url", ""))).path.lower()
        if method_name not in {"GET", "HEAD", "OPTIONS"} and any(
            token in path for token in mutation_tokens
        ):
            mutation_requests.append(f"{method_name} {path}")
        if path.endswith(preview_path):
            try:
                payload = getattr(request, "post_data_json", None)
            except Exception:
                payload = None
            steps = payload.get("steps") if isinstance(payload, dict) else None
            request_label = (
                f"{method_name} {path} stage={active_stage} steps={steps!r}"
            )
            if active_stage == "data" and steps == []:
                data_preview_requests.append(request_label)
            else:
                forbidden_preview_requests.append(request_label)

    page.on("request", record_mutation)
    # Close first so the row helper owns the new opening toggle and can gate its
    # refresh responses before any stage navigation begins.
    details = page.locator("details.process-saved-results")
    if details.get_attribute("open") is not None:
        details.locator(":scope > summary").click()
    rerender_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if rerender_rows != before_rows:
        raise RuntimeError("Process rerender changed saved row identities/settings or current pointer")
    for stage in ("data", "fit", "export", "process"):
        active_stage = stage
        _open_modeling_stage(page, stage)
        page.wait_for_url(re.compile(rf"stage={stage}"), timeout=30_000)
        page.locator(".modeling-work-title h1").get_by_text(
            STAGE_HEADINGS[stage], exact=True
        ).wait_for(timeout=30_000)
        _wait_for_settled(page)

    _wait_modeling_process_panel(page)
    returned_panel = page.locator('[data-modeling-process-panel="ready"]')
    returned_panel.locator(".process-band-source").get_by_text(
        PROCESS_SOURCE_VISIBLE_IDENTITY, exact=True
    ).wait_for(timeout=30_000)
    if returned_panel.get_by_role("textbox", name="Process result name", exact=True).input_value() != draft_label:
        raise RuntimeError("Process round-trip lost the draft output label")
    if returned_panel.get_by_role("textbox", name="Reason for saving Process result", exact=True).input_value() != draft_reason:
        raise RuntimeError("Process round-trip lost the draft save reason")
    returned_method = returned_panel.get_by_role("combobox", name="Evaluation method", exact=True)
    if returned_method.input_value() != draft_method:
        raise RuntimeError("Process round-trip lost the copied Evaluation method")
    if returned_panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value() != draft_range_start:
        raise RuntimeError("Process round-trip lost the copied elastic range start")
    if returned_panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value() != draft_range_end:
        raise RuntimeError("Process round-trip lost the copied elastic range end")
    if not returned_panel.get_by_role("button", name="Save Process result", exact=True).is_disabled():
        raise RuntimeError("Copied Process settings unexpectedly became saveable without a new preview")
    returned_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    returned_graph = page.locator(".persistent-modeling-plot svg[role='img']")
    returned_graph.wait_for(state="visible", timeout=30_000)
    returned_graph_box = returned_graph.bounding_box()
    if returned_graph.get_attribute("aria-label") != graph_label or returned_graph_box is None or returned_graph_box["width"] <= 0 or returned_graph_box["height"] <= 0:
        raise RuntimeError("Process round-trip did not retain the same visible engineering graph")
    after_outputs = _matching_process_outputs(
        _list_processing_outputs(page, base_url), source_pin, profile_pin
    )
    after_by_id = {
        str(item.get("processing_output_id")): item
        for item in after_outputs
        if item.get("processing_output_id")
    }
    _assert_capture_processing_output_pointer(page, expected_current_output)
    if mutation_requests:
        raise RuntimeError(f"Data→Fit→Export→Process navigation sent a forbidden mutation request: {mutation_requests!r}")
    if forbidden_preview_requests:
        raise RuntimeError(
            "Data→Fit→Export→Process navigation sent a forbidden Process preview: "
            f"{forbidden_preview_requests!r}"
        )
    if set(after_by_id) != set(before_by_id) or any(after_by_id[key] != before_by_id[key] for key in before_by_id):
        raise RuntimeError("Data→Fit→Export→Process navigation changed saved output ids or settings")
    after_rows = _assert_modeling_process_saved_rows_three(
        page,
        current_label=expected_current_label,
    )
    if after_rows != before_rows:
        raise RuntimeError("Process stage round-trip changed saved row identities/settings or current pointer")
    if expected_current_output_id not in after_by_id:
        raise RuntimeError("Process round-trip current output identity is missing after stage navigation")


def _assert_modeling_process_blocked(page: Page) -> None:
    frame = page.locator(
        '.engineering-curve-plot-empty-frame[data-plot-state="blocked"]'
    )
    frame.wait_for(state="visible", timeout=30_000)
    if frame.locator("svg .chart-axis").count() < 2 or frame.locator("svg .chart-grid").count() < 2:
        raise RuntimeError("Process blocked capture lost the visible plot axes or grid")
    if not frame.get_by_text("Restore inputs.", exact=True).is_visible():
        raise RuntimeError("Process blocked capture is missing its Restore inputs reason")
    if not page.get_by_role("button", name="Back to Data", exact=True).is_visible():
        raise RuntimeError("Process blocked capture is missing the Back to Data recovery")
    _wait_modeling_process_panel(page)
    if page.get_by_role("status", name="Loading Process controls").count():
        raise RuntimeError("Process blocked capture retained the lazy loading fallback")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    save = page.get_by_role("button", name="Save Process result", exact=True)
    if not preview.is_disabled() or not save.is_disabled():
        raise RuntimeError("Process blocked capture left Preview or Save enabled")
    method_buttons = page.locator(".method-library .method-pill")
    configured_step_buttons = page.locator(
        ".configured-step-list > button:not(.configured-step-add):visible"
    )
    toe_add_button = page.locator(
        ".configured-step-list > button.configured-step-add:visible"
    )
    method_buttons.first.wait_for(state="attached", timeout=30_000)
    configured_step_buttons.first.wait_for(timeout=30_000)
    toe_add_button.wait_for(timeout=30_000)
    if method_buttons.count() == 0 or any(not button.is_disabled() for button in method_buttons.all()):
        raise RuntimeError("Process blocked capture left an Add operation registry method enabled")
    if configured_step_buttons.count() != 5:
        raise RuntimeError("Process blocked capture did not retain five configured Process steps")
    if any(not button.is_disabled() for button in configured_step_buttons.all()):
        raise RuntimeError("Process blocked capture left a configured Process rail button enabled")
    if toe_add_button.count() != 1:
        raise RuntimeError("Process blocked capture is missing the optional toe compensation action")
    if not toe_add_button.is_disabled():
        raise RuntimeError("Process blocked capture left the optional toe compensation action enabled")
    if page.locator('.method-library > summary[aria-disabled="true"]').count() != 1:
        raise RuntimeError("Process blocked capture is missing the disabled Add operation summary")
    process_inputs = page.locator(".process-band-controls input, .rail-statistics-action input")
    if any(not control.is_disabled() for control in process_inputs.all()):
        raise RuntimeError("Process blocked capture left a Process range or manual input enabled")


def _assert_modeling_process_exact_read_failed(page: Page, content_gets: int | None = None) -> None:
    """Assert the settled selected-ref exact-read failure without a fallback."""
    _wait_modeling_process_panel(page)
    page.locator(".error-banner").wait_for(state="visible", timeout=30_000)
    source = page.locator(".process-band-source")
    source.wait_for(state="visible", timeout=30_000)
    if not re.fullmatch(r"Exact source unavailable · r[1-9]\d*", source.inner_text().strip()):
        raise RuntimeError(f"Exact-read failure lost the selected revision identity: {source.inner_text()!r}")
    if page.get_by_role("button", name="Retry exact source", exact=True).count() != 1:
        raise RuntimeError("Exact-read failure is missing its explicit Retry exact source action")
    if not page.get_by_role("button", name="Back to Data", exact=True).is_visible():
        raise RuntimeError("Exact-read failure is missing the Back to Data recovery")
    preview = page.get_by_role("button", name="Preview changes", exact=True)
    save = page.get_by_role("button", name="Save Process result", exact=True)
    if not preview.is_disabled() or not save.is_disabled():
        raise RuntimeError("Exact-read failure left Preview or Save enabled")
    if page.get_by_text(re.compile(r"\b(?:210\.0|120\.0) GPa\b"), exact=False).count():
        raise RuntimeError("Exact-read failure exposed a stale Process scalar")
    frame = page.locator('.engineering-curve-plot-empty-frame[data-plot-state="blocked"]')
    frame.wait_for(state="visible", timeout=30_000)
    if frame.locator("svg .chart-axis").count() < 2 or frame.locator("svg .chart-grid").count() < 2:
        raise RuntimeError("Exact-read failure lost the retained axes/grid recovery frame")
    if content_gets is not None and content_gets != 1:
        raise RuntimeError(f"Exact-read failure made {content_gets} content GETs instead of one settled attempt")


def _assert_modeling_process_capture_ready(page: Page) -> None:
    """Re-check blocked state and responsive plot geometry after capture settling."""
    _wait_for_modeling_process_destination_state(page)
    _wait_for_modeling_process_plot_size(page)
    _assert_modeling_process_blocked(page)


def _assert_fit_title_state(page: Page, expected: str) -> None:
    """Assert the normal Fit title-row state, never a drawer or overlay copy."""
    state = page.locator(
        ".processing-workbench-page.stage-fit .modeling-work-title > .fit-surface-state"
    )
    if state.count() != 1 or not state.is_visible():
        raise RuntimeError(f"Fit title-row state is not uniquely visible: {state.count()}")
    actual = state.inner_text().strip()
    if actual != expected:
        raise RuntimeError(f"Fit title-row state drifted: expected {expected!r}, got {actual!r}")


def _read_fit_context_header(page: Page) -> tuple[str, str]:
    """Read the human Material/Test Data context owned by the Fit header."""
    source = page.locator(".fit-context-source")
    source.wait_for(state="visible", timeout=30_000)
    text = source.inner_text().strip()
    title = (source.get_attribute("title") or "").strip()
    if not text or not title or text != title:
        raise RuntimeError(
            "Fit context header must expose one non-empty matching text/title pair: "
            f"text={text!r}, title={title!r}"
        )
    if text in {"Select Test Data", "No saved Process Output"}:
        raise RuntimeError(f"Fit context header is not a Material/Test Data identity: {text!r}")
    return text, title


def _wait_for_fit_context_header(
    page: Page,
    expected_text: str,
    expected_title: str,
) -> None:
    """Wait bounded/fail-closed for the exact restored Fit header identity."""
    try:
        page.wait_for_function(
            """expected => {
              const source = document.querySelector('.fit-context-source');
              const visible = Boolean(source && source.getClientRects().length);
              const text = source?.textContent?.trim() || '';
              const title = source?.getAttribute('title')?.trim() || '';
              return visible
                && text === expected.text
                && title === expected.title
                && Boolean(text)
                && text !== 'Select Test Data'
                && text !== 'No saved Process Output';
            }""",
            arg={"text": expected_text, "title": expected_title},
            timeout=30_000,
        )
    except Exception as error:
        diagnostics = page.evaluate(
            """() => {
              const source = document.querySelector('.fit-context-source');
              return {
                text: source?.textContent?.trim() || null,
                title: source?.getAttribute('title') || null,
                url: window.location.href,
              };
            }"""
        )
        raise RuntimeError(
            "Fit context header did not settle to its recorded Material/Test Data identity: "
            f"expected={{text:{expected_text!r}, title:{expected_title!r}}}, observed={diagnostics!r}"
        ) from error


def _wait_for_fit_title_state(page: Page, expected: str) -> None:
    """Wait bounded/fail-closed for the exact Fit title-row state."""
    try:
        page.wait_for_function(
            """expected => {
              const state = document.querySelector(
                '.processing-workbench-page.stage-fit .modeling-work-title > .fit-surface-state'
              );
              return Boolean(state && state.getClientRects().length
                && state.textContent?.trim() === expected);
            }""",
            arg=expected,
            timeout=30_000,
        )
    except Exception as error:
        diagnostics = page.evaluate(
            """() => ({
              state: document.querySelector(
                '.processing-workbench-page.stage-fit .modeling-work-title > .fit-surface-state'
              )?.textContent?.trim() || null,
              url: window.location.href,
            })"""
        )
        raise RuntimeError(
            f"Fit title-row state did not settle to {expected!r}: {diagnostics!r}"
        ) from error


def _capture_modeling_fit_states(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_restored: bool = True,
) -> None:
    """Capture the Fit failure, exact-source, and restored states."""

    def prepared_fit(label: str, width: int = 1440, height: int = 900) -> Page:
        page = _new_page(browser, base_url, width, height)
        _prepare_fit_from_saved_process(page, base_url, label=label)
        _click_modeling_fit_preview_and_wait(page)
        _assert_fit_title_state(page, "Preview not saved")
        return page

    calculation_failed = prepared_fit("Fit calculation failure source", 1920, 1080)
    calculation_failed.route(
        "**/api/v1/metal-fit-runs",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic Fit calculation failure"}',
        ),
    )
    calculation_failed.get_by_role("button", name="Preview changes", exact=True).click()
    calculation_failed.get_by_role("alert").wait_for(state="visible", timeout=30_000)
    calculation_failed.locator(".persistent-modeling-plot svg[role=img]").wait_for(
        state="visible", timeout=30_000
    )
    _assert_fit_title_state(calculation_failed, "Preview not saved")
    _assert_fit_display_scale(calculation_failed, "calculation-failed")
    if calculation_failed.get_by_role(
        "button", name=re.compile(r"Preview changes|Update candidates"), exact=False
    ).count() != 1:
        raise RuntimeError("Fit calculation failure lost its explicit retry/update action")
    _capture(
        calculation_failed,
        output / "modeling-fit-calculation-failed-1920x1080.png",
        1920,
        1080,
    )
    calculation_failed.context.close()

    save_failed = prepared_fit("Fit save failure source", 1920, 1080)
    save_trigger, _save_body, save_table = _open_fit_evidence(save_failed)
    _assert_fit_candidate_surface(save_failed, save_table)
    _select_warned_fit_candidate(save_table)
    save_failed.get_by_role("textbox", name="Candidate selection reason", exact=True).fill(
        "Persist the selected candidate only after reviewing numerical evidence."
    )
    save_acknowledgement = save_failed.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning"
    )
    if save_acknowledgement.count():
        save_acknowledgement.check()
    else:
        raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
    _assert_fit_selected_evidence(save_failed)
    _close_fit_evidence(save_failed, save_trigger)
    save_failed.route(
        "**/api/v1/processing-outputs",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic Fit save failure"}',
        ),
    )
    save_failed.get_by_role("button", name="Save fit & continue", exact=True).click()
    save_failed.get_by_role("alert").wait_for(state="visible", timeout=30_000)
    if (
        save_failed.get_by_role(
            "button", name=re.compile(r"Save fit & continue|Retry save"), exact=False
        ).count()
        < 1
    ):
        raise RuntimeError("Fit save failure lost its explicit retry action")
    save_failed.locator(".persistent-modeling-plot svg[role=img]").wait_for(
        state="visible", timeout=30_000
    )
    _assert_fit_title_state(save_failed, "Preview not saved")
    _capture(save_failed, output / "modeling-fit-save-failed-1920x1080.png", 1920, 1080)
    save_failed.context.close()

    fit_blocked = _new_page(browser, base_url, 1920, 1080)
    _prepare_fit_from_saved_process(fit_blocked, base_url, label="Fit blocked source")
    fit_source_binding = fit_blocked.locator(".fit-context-source")
    fit_source_binding.wait_for(state="visible", timeout=30_000)
    fit_source_context = fit_source_binding.inner_text().strip()
    fit_source_context_title = fit_source_binding.get_attribute("title")
    if (
        not fit_source_context
        or not fit_source_context_title
        or fit_source_context == "No saved Process Output"
        or fit_source_context_title == "No saved Process Output"
    ):
        raise RuntimeError("Fit exact-source preparation lost its material/Test Data source context")
    blocked_context_text = fit_source_context
    blocked_context_title = fit_source_context_title
    fit_blocked.evaluate(
        """() => {
          const key = 'cmp.modeling.recent-session.v4';
          const session = JSON.parse(window.sessionStorage.getItem(key) || '{}');
          delete session.processingOutput;
          window.sessionStorage.setItem(key, JSON.stringify(session));
        }"""
    )
    fit_blocked.goto(f"{base_url}/modeling?stage=fit&family=metal")
    fit_blocked.wait_for_function(
        """([expectedText, expectedTitle]) => {
          const source = document.querySelector('.fit-context-source');
          return Boolean(source && source.getClientRects().length
            && source.textContent?.trim() === expectedText
            && source.getAttribute('title') === expectedTitle);
        }""",
        arg=[fit_source_context, fit_source_context_title],
        timeout=30_000,
    )
    fit_blocker_message = "No saved Process Output is bound. Save Process before calculating Fit."
    fit_plot_overlay = fit_blocked.locator(
        "#modeling-fit .engineering-curve-plot-empty-overlay"
    )
    fit_plot_overlay.get_by_text(
        fit_blocker_message,
        exact=True,
    ).wait_for(state="visible", timeout=30_000)
    _wait_for_fit_context_header(
        fit_blocked,
        blocked_context_text,
        blocked_context_title,
    )
    fit_source_binding.wait_for(state="visible", timeout=30_000)
    blocked_source_context = fit_source_binding.inner_text().strip()
    blocked_source_context_title = fit_source_binding.get_attribute("title")
    if (
        blocked_source_context != fit_source_context
        or blocked_source_context_title != fit_source_context_title
        or blocked_source_context == "No saved Process Output"
        or blocked_source_context_title == "No saved Process Output"
    ):
        raise RuntimeError(
            "Fit exact-source blocker lost its material/Test Data source context: "
            f"recorded text={fit_source_context!r}, title={fit_source_context_title!r}; "
            f"blocked text={blocked_source_context!r}, title={blocked_source_context_title!r}"
        )
    _assert_fit_title_state(fit_blocked, "Not calculated")
    fit_blocked.get_by_role("button", name="Back to Process", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    process_stage = fit_blocked.get_by_role("button", name=re.compile(r"^Process\b"))
    if process_stage.count() != 1 or not process_stage.is_visible():
        raise RuntimeError("Fit exact-source blocker lost its visible return-to-Process recovery")
    blocked_session = _modeling_session(fit_blocked)
    blocked_workspace = blocked_session.get("workspace")
    if not isinstance(blocked_workspace, dict):
        raise RuntimeError("Fit blocked capture lost its workspace session state")
    blocked_history = {
        item.get("processing_output_id")
        for item in _list_processing_outputs(fit_blocked, base_url)
    }
    _capture(fit_blocked, output / "modeling-fit-exact-source-blocked-1920x1080.png", 1920, 1080)
    # Arm the recovery-only request assertion after the blocked screenshot has
    # settled.  The screenshot path may refresh read-only data while it settles;
    # only the explicit Back to Process action and its readback belong here.
    blocked_requests: list[str] = []

    def record_blocked_recovery_request(request: object) -> None:
        method = str(getattr(request, "method", "")).upper()
        url = str(getattr(request, "url", ""))
        blocked_requests.append(f"{method} {url}")

    fit_blocked.on("request", record_blocked_recovery_request)
    try:
        fit_blocked.get_by_role("button", name="Back to Process", exact=True).click()
        fit_blocked.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        recovered_session = _modeling_session(fit_blocked)
        recovered_workspace = recovered_session.get("workspace")
        if not isinstance(recovered_workspace, dict):
            raise RuntimeError("Fit blocked recovery lost its workspace session state")
        if recovered_workspace.get("selectedTestDataRefs") != blocked_workspace.get("selectedTestDataRefs"):
            raise RuntimeError("Fit blocked recovery changed the exact selected Test Data refs")
        if recovered_workspace.get("visibleTestDataKeys") != blocked_workspace.get("visibleTestDataKeys"):
            raise RuntimeError("Fit blocked recovery changed visible exact Test Data identities")
        if recovered_session.get("processingOutput") != blocked_session.get("processingOutput"):
            raise RuntimeError("Fit blocked recovery changed the saved-output pointer")
        recovered_history = {
            item.get("processing_output_id")
            for item in _list_processing_outputs(fit_blocked, base_url)
        }
        if recovered_history != blocked_history:
            raise RuntimeError("Fit blocked recovery changed Processing Output history")
        allowed_preview_path = "/api/v1/processing:preview"
        unexpected = [
            request for request in blocked_requests
            if not request.startswith("GET ")
            and not (
                request.startswith("POST ")
                and urlsplit(request.split(" ", 1)[1]).path == allowed_preview_path
            )
        ]
        if unexpected:
            raise RuntimeError(f"Fit blocked recovery issued a forbidden mutation request: {unexpected!r}")
    finally:
        fit_blocked.remove_listener("request", record_blocked_recovery_request)
    fit_blocked.context.close()

    exact_read_failed = prepared_fit("Fit exact-read failure source", 1920, 1080)
    fit_saved = False
    exact_content_requests: list[str] = []
    request_methods: list[str] = []
    exact_read_failed.on(
        "request",
        lambda request: request_methods.append(request.method),
    )

    def arm_after_fit_save(route: Route) -> None:
        nonlocal fit_saved
        if route.request.method == "POST":
            fit_saved = True
        route.continue_()

    def fail_saved_fit_content(route: Route) -> None:
        if not fit_saved:
            route.continue_()
            return
        exact_content_requests.append(route.request.url)
        route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic saved Fit exact-read failure"}',
        )

    # The Fit save itself remains real.  Once its immutable pointer exists,
    # fail only the exact saved-output content GET; this keeps the previously
    # valid Fit graph/selection visible while exercising the restore retry.
    exact_read_failed.route("**/api/v1/processing-outputs", arm_after_fit_save)
    exact_read_failed.route(
        "**/api/v1/processing-outputs/*/content", fail_saved_fit_content
    )
    _save_exact_fit_selection(
        exact_read_failed,
        allow_expected_exact_restore_failure=True,
    )
    saved_fit_pointer = _modeling_session(exact_read_failed).get("processingOutput")
    if not isinstance(saved_fit_pointer, dict) or not isinstance(saved_fit_pointer.get("id"), str):
        raise RuntimeError("Fit exact-read failure setup did not produce an exact saved pointer")
    exact_read_failed.get_by_text(
        "Saved Fit result unavailable", exact=False
    ).wait_for(timeout=30_000)
    _assert_fit_title_state(exact_read_failed, "Preview not saved")
    retry_saved_fit = exact_read_failed.get_by_role(
        "button", name="Retry saved Fit", exact=True
    )
    if retry_saved_fit.count() != 1:
        raise RuntimeError("Fit exact saved-output read failure lost its explicit retry action")
    if exact_read_failed.get_by_role(
        "img", name="Hardening candidate and selected extrapolation curves", exact=True
    ).count() != 1:
        raise RuntimeError("Fit exact-read failure replaced the last valid graph")
    failed_trigger, _failed_body, _failed_table = _open_fit_evidence(exact_read_failed)
    _assert_fit_selected_evidence(exact_read_failed)
    if exact_read_failed.get_by_role(
        "textbox", name="Candidate selection reason", exact=True
    ).input_value() != "Best agreement over the measured strain range.":
        raise RuntimeError("Fit exact-read failure lost the original selection reason")
    if exact_read_failed.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning", exact=True
    ).is_checked() is not True:
        raise RuntimeError("Fit exact-read failure lost the warning acknowledgement")
    _close_fit_evidence(exact_read_failed, failed_trigger)
    if len(exact_content_requests) != 1:
        raise RuntimeError(
            f"Fit exact-read failure made {len(exact_content_requests)} exact content GETs before retry"
        )
    expected_content_url = (
        f"{base_url}/api/v1/processing-outputs/{saved_fit_pointer['id']}/content"
    )
    if exact_content_requests != [expected_content_url]:
        raise RuntimeError(
            f"Fit exact-read failure did not read the pinned saved Fit URL: {exact_content_requests!r}"
        )
    methods_before_retry = len(request_methods)
    pointer_before_retry = _modeling_session(exact_read_failed).get("processingOutput")
    retry_saved_fit.click()
    exact_read_failed.get_by_text(
        "Saved Fit result unavailable", exact=False
    ).wait_for(timeout=30_000)
    _assert_fit_title_state(exact_read_failed, "Preview not saved")
    if len(exact_content_requests) != 2 or exact_content_requests[1] != expected_content_url:
        raise RuntimeError(
            f"Fit exact saved-output retry did not repeat the same exact URL: {exact_content_requests!r}"
        )
    if any(method != "GET" for method in request_methods[methods_before_retry:]):
        raise RuntimeError(
            f"Fit exact saved-output retry issued a non-GET mutation: {request_methods[methods_before_retry:]!r}"
        )
    if _modeling_session(exact_read_failed).get("processingOutput") != pointer_before_retry:
        raise RuntimeError("Fit exact saved-output retry mutated the current pointer")
    _capture(
        exact_read_failed,
        output / "modeling-fit-exact-read-failed-1920x1080.png",
        1920,
        1080,
    )
    exact_read_failed.context.close()

    if not include_restored:
        return

    restored = prepared_fit("Fit restored source", 1920, 1080)
    restored_context_text, restored_context_title = _read_fit_context_header(restored)
    _save_exact_fit_selection(restored)
    restored_session = _modeling_session(restored)
    restored_pointer = restored_session.get("processingOutput")
    if not isinstance(restored_pointer, dict) or not all(
        isinstance(restored_pointer.get(key), str) and restored_pointer.get(key)
        for key in ("id", "revisionId", "label")
    ):
        raise RuntimeError("Fit save did not leave an exact session output pointer for restore")
    restore_requests: list[tuple[str, str]] = []
    restored.on(
        "request",
        lambda request: restore_requests.append((request.method, request.url)),
    )
    restored.goto(f"{base_url}/modeling?stage=fit&family=metal")
    _wait_for_settled(restored)
    restored.locator(".fit-surface-state").get_by_text(
        "Saved current", exact=True
    ).wait_for(timeout=30_000)
    _wait_for_fit_title_state(restored, "Saved current")
    _wait_for_fit_context_header(
        restored,
        restored_context_text,
        restored_context_title,
    )
    _assert_fit_title_state(restored, "Saved current")
    source_binding = restored.locator(".fit-context-source")
    source_binding.wait_for(state="visible", timeout=30_000)
    source_binding_text = source_binding.inner_text().strip()
    source_binding_title = source_binding.get_attribute("title")
    source_context_parts = [part.strip() for part in source_binding_text.split("/", 1)]
    if (
        not source_binding_text
        or source_binding_text != source_binding_title
        or source_binding_text in {"Select Test Data", "No saved Process Output"}
        or source_binding_title in {"Select Test Data", "No saved Process Output"}
        or len(source_context_parts) != 2
        or any(not part for part in source_context_parts)
    ):
        raise RuntimeError(
            "Restored Fit source header lost its material/Test Data context: "
            f"text={source_binding_text!r}, title={source_binding_title!r}"
        )
    restored.get_by_role("img", name="Hardening candidate and selected extrapolation curves", exact=True).wait_for(
        state="visible", timeout=30_000
    )
    restored.get_by_role("button", name="Preview changes", exact=True).wait_for(timeout=30_000)
    persisted_outputs = _list_processing_outputs(restored, base_url)
    persisted = next(
        (
            item for item in persisted_outputs
            if _has_processing_output_revision(
                item, restored_pointer.get("id"), restored_pointer.get("revisionId")
            )
        ),
        None,
    )
    decision = persisted.get("fit_decision") if isinstance(persisted, dict) else None
    if (
        not isinstance(decision, dict)
        or not decision.get("candidate_key")
        or not decision.get("selection_reason")
    ):
        raise RuntimeError("Restored Fit output lost its selected candidate/reason evidence")
    if decision.get("warning_acknowledged") is not True:
        raise RuntimeError("Restored Fit output lost its warning acknowledgement")
    if not isinstance(persisted.get("steps") if isinstance(persisted, dict) else None, list):
        raise RuntimeError("Restored Fit output lost its ordered calculation steps")
    source_pin = persisted.get("source_processing_output") if isinstance(persisted, dict) else None
    source_output = next(
        (
            item for item in persisted_outputs
            if isinstance(source_pin, dict)
            and _has_processing_output_revision(
                item, source_pin.get("aggregate_id"), source_pin.get("revision_id")
            )
        ),
        None,
    )
    if not isinstance(source_output, dict) or not isinstance(source_output.get("current_revision"), dict):
        raise RuntimeError("Restored Fit output lost its exact Process source identity")
    source_revision_record = source_output.get("current_revision")
    if not isinstance(source_revision_record, dict):
        raise RuntimeError("Restored Fit source revision record is unavailable")
    source_revision = source_revision_record.get("revision_no")
    source_digest = source_output.get("output_sha256")
    source_label = source_output.get("label")
    if not isinstance(source_label, str) or not source_label or not isinstance(source_digest, str) or not source_digest:
        raise RuntimeError("Restored Fit source evidence identity is unavailable")
    saved_revision_record = persisted.get("current_revision") if isinstance(persisted, dict) else None
    if not isinstance(saved_revision_record, dict):
        raise RuntimeError("Restored Fit output revision identity is unavailable")
    saved_revision_no = saved_revision_record.get("revision_no")
    restore_trigger, _restore_body, restore_table = _open_fit_evidence(restored)
    source_evidence_text = restored.locator(".fit-source-evidence").inner_text()
    if (
        source_label not in source_evidence_text
        or f"r{source_revision}" not in source_evidence_text
        or source_digest not in source_evidence_text
    ):
        raise RuntimeError("Restored Fit candidate evidence lost the exact source label/revision/digest")
    if restored_pointer["label"] not in source_evidence_text or f"r{saved_revision_no}" not in source_evidence_text:
        raise RuntimeError("Restored Fit candidate evidence lost the saved output identity")
    _assert_fit_selected_evidence(restored)
    selected_rows = restore_table.locator("tbody tr.selected")
    if selected_rows.count() != 1:
        raise RuntimeError("Restored Fit output lost the selected candidate row")
    if restored.get_by_role("textbox", name="Candidate selection reason", exact=True).input_value() != "Best agreement over the measured strain range.":
        raise RuntimeError("Restored Fit output lost the original selection reason")
    if restored.get_by_role("checkbox", name="Acknowledge selected candidate warning", exact=True).is_checked() is not True:
        raise RuntimeError("Restored Fit output lost the checked warning acknowledgement")
    _close_fit_evidence(restored, restore_trigger)
    content_urls = [
        url
        for method, url in restore_requests
        if method == "GET"
        and re.fullmatch(
            r"/api/v1/processing-outputs/[^/]+/content",
            urlsplit(url).path,
        )
    ]
    if len(content_urls) != 1:
        raise RuntimeError(f"Restored Fit reload made {len(content_urls)} exact content GETs: {restore_requests!r}")
    expected_restore_url = f"{base_url}/api/v1/processing-outputs/{restored_pointer['id']}/content"
    if content_urls != [expected_restore_url]:
        raise RuntimeError(f"Restored Fit reload used a non-exact content URL: {content_urls!r}")
    if any(method != "GET" for method, _url in restore_requests):
        raise RuntimeError(f"Restored Fit reload issued a non-GET request: {restore_requests!r}")
    _capture(restored, output / "modeling-fit-restored-1920x1080.png", 1920, 1080)
    restored.context.close()


def _capture_modeling_fit_restored_only(
    browser: Browser,
    base_url: str,
    output: Path,
) -> None:
    """Capture the final Fit reload contract independently of earlier risk states."""
    restored = _new_page(browser, base_url, 1920, 1080)
    _prepare_fit_from_saved_process(restored, base_url, label="Fit restored source")
    _click_modeling_fit_preview_and_wait(restored)
    _assert_fit_title_state(restored, "Preview not saved")
    restored_context_text, restored_context_title = _read_fit_context_header(restored)
    _save_exact_fit_selection(restored)
    restored_pointer = _modeling_session(restored).get("processingOutput")
    if not isinstance(restored_pointer, dict) or not all(
        isinstance(restored_pointer.get(key), str) and restored_pointer.get(key)
        for key in ("id", "revisionId", "label")
    ):
        raise RuntimeError("Fit save did not leave an exact session output pointer for restore")

    restore_requests: list[tuple[str, str]] = []
    restore_responses: list[tuple[int, str]] = []
    restored.on(
        "request",
        lambda request: restore_requests.append((request.method, request.url)),
    )
    restored.on(
        "response",
        lambda response: restore_responses.append((response.status, response.url)),
    )
    restored.goto(f"{base_url}/modeling?stage=fit&family=metal")
    _wait_for_settled(restored)
    restored.locator(".fit-surface-state").get_by_text(
        "Saved current", exact=True
    ).wait_for(timeout=30_000)
    _wait_for_fit_title_state(restored, "Saved current")
    _wait_for_fit_context_header(
        restored,
        restored_context_text,
        restored_context_title,
    )
    _assert_fit_title_state(restored, "Saved current")
    source_binding = restored.locator(".fit-context-source")
    source_binding.wait_for(state="visible", timeout=30_000)
    source_binding_text = source_binding.inner_text().strip()
    source_binding_title = source_binding.get_attribute("title")
    source_context_parts = [part.strip() for part in source_binding_text.split("/", 1)]
    if (
        not source_binding_text
        or source_binding_text != source_binding_title
        or source_binding_text in {"Select Test Data", "No saved Process Output"}
        or source_binding_title in {"Select Test Data", "No saved Process Output"}
        or len(source_context_parts) != 2
        or any(not part for part in source_context_parts)
    ):
        raise RuntimeError(
            "Restored Fit source header lost its material/Test Data context: "
            f"text={source_binding_text!r}, title={source_binding_title!r}"
        )
    restored.get_by_role(
        "img", name="Hardening candidate and selected extrapolation curves", exact=True
    ).wait_for(state="visible", timeout=30_000)
    restored.get_by_role("button", name="Preview changes", exact=True).wait_for(timeout=30_000)
    persisted_outputs = _list_processing_outputs(restored, base_url)
    persisted = next(
        (
            item for item in persisted_outputs
            if _has_processing_output_revision(
                item, restored_pointer.get("id"), restored_pointer.get("revisionId")
            )
        ),
        None,
    )
    decision = persisted.get("fit_decision") if isinstance(persisted, dict) else None
    if (
        not isinstance(decision, dict)
        or not decision.get("candidate_key")
        or not decision.get("selection_reason")
        or decision.get("warning_acknowledged") is not True
    ):
        raise RuntimeError("Restored Fit output lost its selected decision evidence")
    source_pin = persisted.get("source_processing_output") if isinstance(persisted, dict) else None
    if not isinstance(source_pin, dict):
        raise RuntimeError("Restored Fit output lost its exact Process source identity")
    source_output = next(
        (
            item for item in persisted_outputs
            if _has_processing_output_revision(
                item, source_pin.get("aggregate_id"), source_pin.get("revision_id")
            )
        ),
        None,
    )
    if not isinstance(source_output, dict) or not isinstance(source_output.get("current_revision"), dict):
        raise RuntimeError("Restored Fit output lost its exact Process source evidence")
    source_revision_record = source_output["current_revision"]
    source_revision = source_revision_record.get("revision_no")
    source_label = source_output.get("label")
    source_digest = source_output.get("output_sha256")
    if not isinstance(source_label, str) or not source_label or not isinstance(source_digest, str) or not source_digest:
        raise RuntimeError("Restored Fit source evidence identity is unavailable")

    restore_trigger, _restore_body, restore_table = _open_fit_evidence(restored)
    source_evidence_text = restored.locator(".fit-source-evidence").inner_text()
    if (
        source_label not in source_evidence_text
        or f"r{source_revision}" not in source_evidence_text
        or source_digest not in source_evidence_text
    ):
        raise RuntimeError("Restored Fit candidate evidence lost the exact source label/revision/digest")
    _assert_fit_selected_evidence(restored)
    source_evidence_text = restored.locator(".fit-source-evidence").inner_text()
    if not isinstance(source_digest, str) or not source_digest or source_digest not in source_evidence_text:
        raise RuntimeError("Restored Fit candidate evidence lost the full source digest")
    if (
        not isinstance(source_label, str)
        or not source_label
        or source_label not in source_evidence_text
        or f"r{source_revision}" not in source_evidence_text
    ):
        raise RuntimeError("Restored Fit candidate evidence lost its source label/revision")
    if restore_table.locator("tbody tr.selected").count() != 1:
        raise RuntimeError("Restored Fit output lost the selected candidate row")
    if restored.get_by_role(
        "textbox", name="Candidate selection reason", exact=True
    ).input_value() != "Best agreement over the measured strain range.":
        raise RuntimeError("Restored Fit output lost the original selection reason")
    if restored.get_by_role(
        "checkbox", name="Acknowledge selected candidate warning", exact=True
    ).is_checked() is not True:
        raise RuntimeError("Restored Fit output lost the warning acknowledgement")
    _close_fit_evidence(restored, restore_trigger)

    content_urls = [
        url
        for method, url in restore_requests
        if method == "GET"
        and re.fullmatch(
            r"/api/v1/processing-outputs/[^/]+/content",
            urlsplit(url).path,
        )
    ]
    expected_restore_url = (
        f"{base_url}/api/v1/processing-outputs/{restored_pointer['id']}/content"
    )
    if content_urls != [expected_restore_url]:
        raise RuntimeError(f"Restored Fit reload used a non-exact content URL: {content_urls!r}")
    if any(method != "GET" for method, _url in restore_requests):
        raise RuntimeError(f"Restored Fit reload issued a non-GET request: {restore_requests!r}")
    _capture(restored, output / "modeling-fit-restored-1920x1080.png", 1920, 1080)
    restored.context.close()


def _capture_modeling_process_fit(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    include_fit_states: bool = True,
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling_process(page, base_url, verify_data_reload=False)
        if page.locator(".modeling-stage-number:visible").count():
            raise RuntimeError("Process/Fit capture received the retired numbered stage strip")
        if page.locator(".stage-process > .section-heading:visible").count():
            raise RuntimeError("Process capture received the retired duplicate workspace heading")
        page.locator(".modeling-workspace-rail .rail-heading").get_by_text(
            "Test Data", exact=True
        ).wait_for(timeout=30_000)
        _prepare_toe_compensation_preview(page)
        _save_process_output_for_fit(
            page,
            label=f"Toe-corrected Process result {width}x{height}",
            reason="Bind reviewed toe compensation as the exact Fit source.",
            verify_default_preview=False,
        )
        _capture(
            page,
            output / f"modeling-process-{width}x{height}.png",
            width,
            height,
            before_screenshot=_process_plot_capture_callback(page),
        )
        measurements.append(
            {
                "stage": "process",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "process", width, height),
            }
        )

        _open_modeling_stage(page, "fit")
        page.locator(".modeling-work-title h1").get_by_text(
            STAGE_HEADINGS["fit"], exact=True
        ).wait_for(timeout=30_000)
        _click_modeling_fit_preview_and_wait(page)
        trigger, body, table = _open_fit_evidence(page)
        body.get_by_text(
            "OLS zero intercept · v1.0.0 · exact saved Process step", exact=True
        ).wait_for(state="visible", timeout=30_000)
        _assert_fit_candidate_surface(page, table)
        if page.get_by_role("button", name="Save fit & continue", exact=True).count() != 1:
            raise RuntimeError("Fit must expose one top-row Save fit & continue action")
        _select_warned_fit_candidate(table)
        page.get_by_role("textbox", name="Candidate selection reason").fill(
            "Best agreement over the measured strain range."
        )
        acknowledgement = page.get_by_role(
            "checkbox", name="Acknowledge selected candidate warning"
        )
        if acknowledgement.count():
            acknowledgement.check()
        else:
            raise RuntimeError("Selected warned Fit candidate is missing its acknowledgement")
        _assert_fit_selected_evidence(page)
        if page.get_by_role("button", name="Save fit & continue", exact=True).is_disabled():
            raise RuntimeError("Fit selection did not enable the top-row save action")
        _close_fit_evidence(page, trigger)
        _assert_fit_display_scale(page, "normal")
        _capture(page, output / f"modeling-fit-{width}x{height}.png", width, height)
        measurements.append(
            {
                "stage": "fit",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "fit", width, height),
            }
        )
        page.context.close()

    if include_fit_states:
        _capture_modeling_fit_states(browser, base_url, output)
    return measurements


def _capture_modeling_polymer_fit_source_blocked(
    browser: Browser,
    base_url: str,
    output: Path,
) -> None:
    """Capture the deterministic Polymer Fit recovery surface without a fixture fallback."""
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/modeling?stage=fit&family=polymer")
        page.locator(".polymer-calibration-fit").wait_for(timeout=30_000)
        page.get_by_role("heading", name="Select Test Data", exact=True).wait_for(
            timeout=30_000
        )
        _capture(
            page,
            output / f"modeling-fit-polymer-source-blocked-{width}x{height}.png",
            width,
            height,
        )
        page.context.close()


def _capture_modeling_process_only(
    browser: Browser,
    base_url: str,
    output: Path,
    *,
    resume_modeling_process: bool = False,
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        _prepare_modeling_process(page, base_url, verify_data_reload=False)
        page.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        page.locator(".modeling-work-title h1").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        page.locator(".modeling-workspace-rail .rail-heading").get_by_text(
            "Test Data", exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(page)
        _assert_modeling_process_preview(page)
        _assert_modeling_process_draft_geometry(page)
        if width == 1366:
            linear_method = page.locator(
                '[data-modeling-process-panel="ready"] select[aria-label="Evaluation method"]'
            )
            linear_method.select_option("linear_regression")
            _click_modeling_process_preview_and_wait(page)
            _wait_for_modeling_process_plot_size(page)
            if linear_method.input_value() != "linear_regression":
                raise RuntimeError("Linear regression Process capture did not settle on its target method")
            _assert_modeling_process_geometry(page)
            _capture(
                page,
                output / "modeling-process-linear-regression-1366x768.png",
                width,
                height,
                before_screenshot=_process_plot_capture_callback(page),
            )
            _assert_modeling_process_manual_surface(
                page,
                capture_path=output / "modeling-process-manual-1366x768.png",
            )
        _capture(
            page,
            output / f"modeling-process-{width}x{height}.png",
            width,
            height,
            before_screenshot=_process_plot_capture_callback(page),
        )
        measurements.append(
            {
                "stage": "process",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "process", width, height),
            }
        )
        page.context.close()

    blocked = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(blocked, base_url, verify_data_reload=False)
    blocked.add_init_script(
        """(() => {
          const key = 'cmp.modeling.recent-session.v4';
          const session = JSON.parse(window.sessionStorage.getItem(key) || '{}');
          delete session.testData;
          session.workspace = {
            ...(session.workspace || {}),
            selectedTestDataRefs: [], selectedDocumentIds: [], visibleTestDataKeys: []
          };
          window.sessionStorage.setItem(key, JSON.stringify(session));
        })();"""
    )
    blocked.goto(f"{base_url}/modeling?stage=process&family=metal")
    _wait_for_settled(blocked)
    _wait_for_modeling_process_destination_state(blocked)
    _wait_for_modeling_process_plot_size(blocked)
    _assert_modeling_process_blocked(blocked)
    _capture(
        blocked,
        output / "modeling-process-blocked-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_capture_ready(blocked),
    )
    blocked.context.close()

    failed = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(failed, base_url, verify_data_reload=False)
    failed_content_gets = 0

    def fail_exact_source(route: Route) -> None:
        nonlocal failed_content_gets
        failed_content_gets += 1
        route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"deterministic exact source read failure"}',
        )

    failed.route("**/api/v1/test-data-documents/**/content", fail_exact_source)
    failed.reload()
    failed.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    failed.locator(".modeling-work-title h1").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    failed.get_by_role("button", name="Retry exact source", exact=True).wait_for(timeout=30_000)
    _assert_modeling_process_exact_read_failed(failed, failed_content_gets)
    _capture(
        failed,
        output / "modeling-process-exact-read-failed-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_exact_read_failed(failed, failed_content_gets),
    )
    failed.context.close()

    siblings = _new_page(browser, base_url, 1440, 900)
    _prepare_modeling_process(siblings, base_url, verify_data_reload=False)
    source_pin, profile_pin = _process_session_pins(siblings)
    listed_outputs = _list_processing_outputs(siblings, base_url)
    _assert_no_mis_pinned_capture_labels(listed_outputs, source_pin, profile_pin)
    initial_outputs = _matching_capture_process_outputs(
        listed_outputs, source_pin, profile_pin
    )
    _filter_capture_process_output_list(siblings, source_pin, profile_pin)
    siblings.reload()
    siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
    siblings.locator(".modeling-work-title h1").get_by_text(
        STAGE_HEADINGS["process"], exact=True
    ).wait_for(timeout=30_000)
    _wait_modeling_process_panel(siblings)
    resumed_existing_primary = False
    resume_output_posts: list[str] = []
    if resume_modeling_process and len(initial_outputs) != 3:
        raise RuntimeError(
            "Modeling Process resume requires exactly three matching saved outputs; "
            f"got {len(initial_outputs)}"
        )
    if len(initial_outputs) == 3:
        resumed_by_label = _assert_resumable_modeling_process_outputs(
            initial_outputs, source_pin, profile_pin
        )
        elastic_output = resumed_by_label["Elastic window 0.0005-0.0025"]
        def record_resume_output_post(request: object) -> None:
            if (
                getattr(request, "method", "") == "POST"
                and urlsplit(getattr(request, "url", "")).path.endswith("/processing-outputs")
            ):
                resume_output_posts.append(str(getattr(request, "url", "")))

        siblings.on("request", record_resume_output_post)
        _patch_capture_processing_output_pointer(siblings, elastic_output)
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        siblings.reload()
        siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        siblings.locator(".modeling-work-title h1").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(siblings)
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        )
        if resume_output_posts:
            raise RuntimeError(
                "Modeling Process resume unexpectedly posted a Processing Output: "
                f"{resume_output_posts!r}"
            )
        siblings.remove_listener("request", record_resume_output_post)
        resumed_existing_primary = True
        final_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if {
            output.get("processing_output_id") for output in final_outputs
        } != {
            output.get("processing_output_id") for output in initial_outputs
        }:
            raise RuntimeError("Modeling Process resume changed the immutable output identities")
        final_output = final_outputs[
            next(
                index
                for index, output in enumerate(final_outputs)
                if output.get("processing_output_id") == elastic_output.get("processing_output_id")
            )
        ]
    elif len(initial_outputs) not in (0, 2):
        raise RuntimeError(
            "Process capture requires zero, two, or three exact matching saved outputs before the sibling flow; "
            f"got {len(initial_outputs)}"
        )
    elif len(initial_outputs) == 2:
        labels = [output.get("label") for output in initial_outputs]
        if set(labels) != {"Robust elastic", "Chord elastic"} or len(set(labels)) != 2:
            raise RuntimeError(f"Existing Process siblings have duplicate or missing labels: {labels!r}")
        output_ids = [output.get("processing_output_id") for output in initial_outputs]
        if any(not isinstance(output_id, str) or not output_id for output_id in output_ids) or len(set(output_ids)) != 2:
            raise RuntimeError(f"Existing Process siblings have duplicate or missing identities: {output_ids!r}")
        for saved_output in initial_outputs:
            label = saved_output.get("label")
            if label == "Robust elastic":
                _assert_process_output_configuration(
                    saved_output,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label == "Chord elastic":
                _assert_process_output_configuration(
                    saved_output,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected Process sibling label: {label!r}")
        _assert_modeling_process_saved_rows(siblings)

        # Read the real persisted Chord identity again from the authenticated
        # browser session.  The pointer must never be manufactured from a
        # capture constant or inferred from row order.
        resumed_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(resumed_outputs) != 2 or {
            output.get("processing_output_id") for output in resumed_outputs
        } != {
            output.get("processing_output_id") for output in initial_outputs
        }:
            raise RuntimeError("Process sibling list changed while resuming the existing outputs")
        for resumed_output in resumed_outputs:
            label = resumed_output.get("label")
            if label == "Robust elastic":
                _assert_process_output_configuration(
                    resumed_output,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label == "Chord elastic":
                _assert_process_output_configuration(
                    resumed_output,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected resumed Process sibling label: {label!r}")
        chord_output = next(
            resumed_output
            for resumed_output in resumed_outputs
            if resumed_output.get("label") == "Chord elastic"
        )
        _patch_capture_processing_output_pointer(siblings, chord_output)
        siblings.reload()
        siblings.wait_for_url(re.compile(r"stage=process"), timeout=30_000)
        siblings.locator(".modeling-work-title h1").get_by_text(
            STAGE_HEADINGS["process"], exact=True
        ).wait_for(timeout=30_000)
        _wait_modeling_process_panel(siblings)
        _assert_modeling_process_saved_rows(siblings, require_current_and_history=True)
    else:
        _assert_modeling_process_preview(siblings)
        label = siblings.get_by_role("textbox", name="Process result name")
        reason = siblings.get_by_role("textbox", name="Reason for saving Process result")
        save = siblings.get_by_role("button", name="Save Process result", exact=True)
        label.fill("Robust elastic")
        reason.fill("Capture deterministic saved-result sibling one")
        save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        siblings.get_by_role("combobox", name="Evaluation method", exact=True).select_option("chord")
        siblings.get_by_role("spinbutton", name="Elastic range start", exact=True).fill("0.001")
        siblings.get_by_role("spinbutton", name="Elastic range end", exact=True).fill("0.003")
        _assert_modeling_process_preview(siblings, expected_modulus="120.0 GPa", method_label="Chord")
        label.fill("Chord elastic")
        reason.fill("Capture deterministic saved-result sibling two")
        save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        saved_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(saved_outputs) != 2:
            raise RuntimeError(f"Process capture did not create exactly two matching outputs: {saved_outputs!r}")
        saved_ids = [output_item.get("processing_output_id") for output_item in saved_outputs]
        if any(not isinstance(output_id, str) or not output_id for output_id in saved_ids) or len(set(saved_ids)) != 2:
            raise RuntimeError(f"Newly saved Process siblings have duplicate or missing identities: {saved_ids!r}")
        for output_item in saved_outputs:
            label_value = output_item.get("label")
            if label_value == "Robust elastic":
                _assert_process_output_configuration(
                    output_item,
                    source_pin,
                    profile_pin,
                    expected_label="Robust elastic",
                    expected_method="robust_huber",
                    expected_minimum=0.0002,
                    expected_maximum=0.002,
                )
            elif label_value == "Chord elastic":
                _assert_process_output_configuration(
                    output_item,
                    source_pin,
                    profile_pin,
                    expected_label="Chord elastic",
                    expected_method="chord",
                    expected_minimum=0.001,
                    expected_maximum=0.003,
                )
            else:
                raise RuntimeError(f"Unexpected newly saved Process sibling label: {label_value!r}")
        _assert_modeling_process_saved_rows(siblings, require_current_and_history=True)
    if resumed_existing_primary:
        # Resume keeps the three exact immutable outputs.  Copy the current
        # Elastic window through the real row action so the saved current
        # pointer survives while the exact draft is restored.
        resume_preview_posts: list[str] = []

        def record_resume_action_request(request: object) -> None:
            if getattr(request, "method", "") != "POST":
                return
            path = urlsplit(getattr(request, "url", "")).path
            if path.endswith("/processing-outputs"):
                resume_output_posts.append(str(getattr(request, "url", "")))
            elif path.endswith("/processing:preview"):
                resume_preview_posts.append(str(getattr(request, "url", "")))

        siblings.on("request", record_resume_action_request)
        resume_details = siblings.locator("details.process-saved-results")
        resume_current_row = resume_details.locator(".process-comparison-row").filter(
            has_text="Elastic window 0.0005-0.0025"
        )
        if resume_current_row.count() != 1:
            raise RuntimeError(
                "Resumed Process could not resolve exactly one current Elastic window row"
            )
        resume_current_row.get_by_role("button", name="Use settings", exact=True).click()
        siblings.get_by_text(
            "Saved Process settings restored as a new draft", exact=False
        ).wait_for(timeout=30_000)
        siblings.wait_for_timeout(350)
        if resume_preview_posts:
            raise RuntimeError(
                "Current Elastic Use settings implicitly posted a Process preview: "
                f"{resume_preview_posts!r}"
            )
        if resume_output_posts:
            raise RuntimeError(
                "Current Elastic Use settings unexpectedly posted a Processing Output: "
                f"{resume_output_posts!r}"
            )
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        resume_panel = siblings.locator('[data-modeling-process-panel="ready"]')
        resume_method = resume_panel.get_by_role(
            "combobox", name="Evaluation method", exact=True
        )
        resume_start = resume_panel.get_by_role(
            "spinbutton", name="Elastic range start", exact=True
        )
        resume_end = resume_panel.get_by_role(
            "spinbutton", name="Elastic range end", exact=True
        )
        if (
            resume_method.input_value() != "robust_huber"
            or resume_start.input_value() != "0.0005"
            or resume_end.input_value() != "0.0025"
        ):
            raise RuntimeError(
                "Current Elastic Use settings did not copy robust_huber 0.0005–0.0025"
            )
        if not resume_panel.get_by_role(
            "button", name="Save Process result", exact=True
        ).is_disabled():
            raise RuntimeError(
                "Current Elastic Use settings enabled Save before a new preview"
            )
        resume_rows_after_use = _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        )
        if not any(
            "Elastic window 0.0005-0.0025" in row and "current" in row
            for row in resume_rows_after_use
        ):
            raise RuntimeError("Current Elastic Use settings changed the current pointer")

        # Only the explicit Preview action may issue the Process preview; it
        # must keep the exact current output and produce no new saved output.
        preview_posts_before_explicit = len(resume_preview_posts)
        _click_modeling_process_preview_and_wait(siblings)
        resume_panel.locator(".process-band-result").get_by_text(
            "210.0 GPa", exact=True
        ).wait_for(timeout=30_000)
        if (
            len(resume_preview_posts) != preview_posts_before_explicit + 1
            or resume_output_posts
        ):
            raise RuntimeError(
                "Resumed Process explicit preview changed the forbidden request set: "
                f"previews={resume_preview_posts!r}, outputs={resume_output_posts!r}"
            )
        if (
            resume_method.input_value() != "robust_huber"
            or resume_start.input_value() != "0.0005"
            or resume_end.input_value() != "0.0025"
        ):
            raise RuntimeError(
                "Resumed Process explicit preview drifted from the saved Elastic window settings"
            )
        _assert_capture_processing_output_pointer(siblings, elastic_output)
        _wait_for_modeling_process_plot_size(siblings)
        siblings.locator('.persistent-modeling-plot svg[role="img"]').wait_for(
            state="visible", timeout=30_000
        )
        siblings.remove_listener("request", record_resume_action_request)
    if not resumed_existing_primary:
        # The primary journey adds one new immutable result after the deterministic
        # two-sibling setup. Preview and save exactly once with the approved Auto
        # robust elastic window before exercising historical Use settings.
        primary_panel = siblings.locator('[data-modeling-process-panel="ready"]')
        primary_method = primary_panel.get_by_role("combobox", name="Evaluation method", exact=True)
        primary_start = primary_panel.get_by_role("spinbutton", name="Elastic range start", exact=True)
        primary_end = primary_panel.get_by_role("spinbutton", name="Elastic range end", exact=True)
        primary_method.select_option("robust_huber")
        primary_start.fill("0.0005")
        primary_end.fill("0.0025")
        _click_modeling_process_preview_and_wait(siblings)
        _wait_for_modeling_process_plot_size(siblings)
        if primary_method.input_value() != "robust_huber":
            raise RuntimeError("Primary Process preview method drifted from Auto robust")
        if primary_start.input_value() != "0.0005" or primary_end.input_value() != "0.0025":
            raise RuntimeError("Primary Process preview elastic range drifted from 0.0005–0.0025")
        primary_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
        primary_label = siblings.get_by_role("textbox", name="Process result name", exact=True)
        primary_reason = siblings.get_by_role("textbox", name="Reason for saving Process result", exact=True)
        primary_save = siblings.get_by_role("button", name="Save Process result", exact=True)
        primary_label.fill("Elastic window 0.0005-0.0025")
        primary_reason.fill("Baseline elastic evaluation for DP780 review")
        primary_save.click()
        siblings.get_by_text("Processed result saved and current", exact=False).wait_for(timeout=30_000)
        final_outputs = _matching_capture_process_outputs(
            _list_processing_outputs(siblings, base_url), source_pin, profile_pin
        )
        if len(final_outputs) != 3:
            raise RuntimeError(f"Process primary journey did not reach exactly three outputs: {final_outputs!r}")
        try:
            final_output = next(
                item
                for item in final_outputs
                if item.get("label") == "Elastic window 0.0005-0.0025"
            )
        except StopIteration as cause:
            raise RuntimeError("Process primary journey lost the new Elastic window output") from cause
        _assert_process_output_configuration(
            final_output,
            source_pin,
            profile_pin,
            expected_label="Elastic window 0.0005-0.0025",
            expected_method="robust_huber",
            expected_minimum=0.0005,
            expected_maximum=0.0025,
        )
        _assert_modeling_process_saved_rows_three(siblings, current_label="Elastic window 0.0005-0.0025")

    # History settings are a local draft action.  It must not create another
    # persisted output or replace the newly saved output identity on the server.
    history_output_posts: list[str] = []
    history_preview_posts: list[str] = []

    def record_history_output_post(request: object) -> None:
        if getattr(request, "method", "") != "POST":
            return
        path = urlsplit(getattr(request, "url", "")).path
        if path.endswith("/processing-outputs"):
            history_output_posts.append(str(getattr(request, "url", "")))
        elif path.endswith("/processing:preview"):
            history_preview_posts.append(str(getattr(request, "url", "")))

    siblings.on("request", record_history_output_post)
    preview_posts_before_history = len(history_preview_posts)
    details = siblings.locator("details.process-saved-results")
    history_row = details.locator(".process-comparison-row").filter(has_text="Chord elastic")
    history_row.get_by_role("button", name="Use settings", exact=True).click()
    siblings.get_by_text("Saved Process settings restored as a new draft", exact=False).wait_for(timeout=30_000)
    siblings.wait_for_timeout(350)
    if len(history_preview_posts) != preview_posts_before_history:
        raise RuntimeError(
            "Use settings implicitly posted a Process preview: "
            f"{history_preview_posts[preview_posts_before_history:]!r}"
        )
    if history_output_posts:
        raise RuntimeError(f"Use settings unexpectedly posted a Processing Output: {history_output_posts!r}")
    after_history_outputs = _matching_capture_process_outputs(
        _list_processing_outputs(siblings, base_url), source_pin, profile_pin
    )
    if {item.get("processing_output_id") for item in after_history_outputs} != {
        item.get("processing_output_id") for item in final_outputs
    }:
        raise RuntimeError("Use settings changed the persisted Process output identities")
    if not any(item.get("processing_output_id") == final_output.get("processing_output_id") for item in after_history_outputs):
        raise RuntimeError("Use settings lost the newly saved current Process output identity")
    history_panel = siblings.locator('[data-modeling-process-panel="ready"]')
    if history_panel.get_by_role("combobox", name="Evaluation method", exact=True).input_value() != "chord":
        raise RuntimeError("Chord Use settings did not copy Evaluation method=chord")
    if (
        history_panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value() != "0.001"
        or history_panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value() != "0.003"
    ):
        raise RuntimeError("Chord Use settings did not copy the 0.001–0.003 elastic range")
    if not history_panel.get_by_role("button", name="Save Process result", exact=True).is_disabled():
        raise RuntimeError("Chord Use settings enabled Save before a new preview")
    history_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True).wait_for(timeout=30_000)
    history_rows = _assert_modeling_process_saved_rows_three(
        siblings,
        current_label="Elastic window 0.0005-0.0025",
    )
    if sum("current" in row for row in history_rows) != 1 or not any(
        "Elastic window 0.0005-0.0025" in row and "current" in row
        for row in history_rows
    ):
        raise RuntimeError("Chord Use settings changed the sole visible current Process row")
    if siblings.locator('[data-modeling-process-panel="ready"]').count() != 1:
        raise RuntimeError("Saved sibling capture lost the ready Process panel")
    _wait_modeling_process_panel(siblings)
    _assert_modeling_process_saved_rows_reachable(siblings)
    _assert_modeling_process_stage_round_trip(
        siblings,
        base_url,
        expected_current_output=final_output,
        expected_current_label="Elastic window 0.0005-0.0025",
    )
    _capture(
        siblings,
        output / "modeling-process-siblings-1440x900.png",
        1440,
        900,
        before_screenshot=lambda: _assert_modeling_process_saved_rows_three(
            siblings,
            current_label="Elastic window 0.0005-0.0025",
        ),
    )
    siblings.unroute_all(behavior="wait")
    siblings.context.close()
    return measurements


def _assert_modeling_normal_shell(page: Page) -> None:
    shell = page.get_by_role("navigation", name="Modeling workflow stages")
    buttons = shell.get_by_role("button")
    if buttons.count() != 4 or buttons.all_inner_texts() != ["Data", "Process", "Fit", "Export"]:
        raise RuntimeError(
            "normal Modeling shell must visibly contain only Data, Process, Fit and Export"
        )
    if shell.get_by_text(re.compile(r"Validate|Review")).count():
        raise RuntimeError("Validate/Review must not appear in the normal Modeling stage strip")


def _capture_modeling_consistency(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    _capture_modeling_session_shell(browser, base_url, output)
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        # Data now preserves the user's exact focused revision across stage
        # changes. Select the Process source explicitly instead of relying on
        # the retired first-included-row fallback, then return for the Data
        # geometry capture before continuing the four-stage journey.
        _prepare_modeling_process(page, base_url)
        _open_modeling_stage(page, "data")
        _wait_for_modeling_data_surface(page)
        _assert_modeling_normal_shell(page)
        rail = page.locator(".modeling-workspace-rail")
        rail.get_by_role("search").wait_for(timeout=30_000)
        page.get_by_role("button", name="Add comparison", exact=True).click()
        _assert_modeling_data_surface(
            page,
            width,
            height,
            comparison_open=True,
        )
        page.get_by_role("button", name="Close comparison", exact=True).click()
        _assert_modeling_data_surface(
            page,
            width,
            height,
            comparison_open=False,
        )
        rail_box = rail.bounding_box()
        expected_rail_width = _css_token_px(page, "--ux-navigator-default-inline-size")
        if rail_box is None or abs(rail_box["width"] - expected_rail_width) > 1:
            raise RuntimeError(f"Data compact curve rail width drifted: {rail_box}")
        _capture(page, output / f"modeling-data-{width}x{height}.png", width, height)
        measurements.append(
            {
                "stage": "data",
                "viewport": f"{width}x{height}",
                **_measure_process_fit(page, "data", width, height),
            }
        )
        for stage in ("process", "fit", "export"):
            _open_modeling_stage(page, stage)
            page.locator(".modeling-work-title h1").get_by_text(
                STAGE_HEADINGS[stage], exact=True
            ).wait_for(timeout=30_000)
            _assert_modeling_normal_shell(page)
            if stage in ("process", "fit"):
                stage_rail = page.locator(".modeling-workspace-rail")
                stage_rail_box = stage_rail.bounding_box()
                minimum_rail_width = _css_token_px(
                    page, "--ux-navigator-min-inline-size"
                )
                default_rail_width = _css_token_px(
                    page, "--ux-navigator-default-inline-size"
                )
                if (
                    stage_rail_box is None
                    or stage_rail_box["width"] < minimum_rail_width - 1
                    or stage_rail_box["width"] > default_rail_width + 1
                ):
                    raise RuntimeError(
                        f"{stage} curve rail escaped the shared readable range: {stage_rail_box}"
                    )
                if page.get_by_role("button", name="Mean & band", exact=True).count():
                    raise RuntimeError(
                        f"{stage} must omit Mean & band before a real ensemble preview"
                    )
            elif page.locator(".modeling-workspace-rail").count():
                raise RuntimeError("Export must remain graph-only without a curve rail")
            if stage == "process":
                _save_process_output_for_fit(
                    page,
                    label=f"Consistency Fit source {width}x{height}",
                    reason="Bind the exact Process result for the Modeling consistency journey.",
                )
            if stage == "fit":
                _click_modeling_fit_preview_and_wait(page)
            if stage == "export":
                _save_exact_fit_selection(page)
                _open_modeling_stage(page, "export")
                page.wait_for_url(re.compile(r"stage=export"), timeout=30_000)
                _prepare_exact_metal_source_if_needed(page)
                _prepare_exact_target_preview(page)
                _assert_export_exact_source_surface(page)
                _capture(
                    page,
                    output / f"modeling-{stage}-{width}x{height}.png",
                    width,
                    height,
                    focus_selector=".modeling-target-preview .export-native-preview-shell",
                    before_screenshot=lambda page=page: _assert_export_action_visible(
                        page, "Create solver card"
                    ),
                    after_animation=lambda page=page: _assert_export_capture_shell(page),
                )
                measurements.append(
                    {
                        "stage": stage,
                        "viewport": f"{width}x{height}",
                        "surface": "exact-target-preview",
                    }
                )
                continue
            _capture(page, output / f"modeling-{stage}-{width}x{height}.png", width, height)
            measurements.append(
                {
                    "stage": stage,
                    "viewport": f"{width}x{height}",
                    **_measure_process_fit(
                        page,
                        stage,
                        width,
                        height,
                        expected_fit_included=1,
                    ),
                }
            )
        page.context.close()
    return measurements


def _capture_modeling_data_viewports(
    browser: Browser,
    base_url: str,
    output: Path,
    viewports: tuple[tuple[int, int], ...],
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for index, (width, height) in enumerate(viewports):
        page = _new_page(browser, base_url, width, height)
        try:
            _prepare_modeling(page, base_url, verify_reload=index == 0)
            _assert_modeling_normal_shell(page)
            rail = page.locator(".modeling-workspace-rail")
            rail.get_by_role("search").wait_for(timeout=30_000)
            rail_box = rail.bounding_box()
            expected_rail_width = _css_token_px(page, "--ux-navigator-default-inline-size")
            if rail_box is None or abs(rail_box["width"] - expected_rail_width) > 1:
                raise RuntimeError(f"Data search/browser rail width drifted: {rail_box}")
            _capture(page, output / f"modeling-data-{width}x{height}.png", width, height)
            data_measurement = _measure_process_fit(page, "data", width, height)
            if width > 1920:
                workspace_box = page.locator(".modeling-workspace-stage-data").bounding_box()
                plot_box = page.locator(".persistent-modeling-plot").bounding_box()
                if workspace_box is None or plot_box is None or workspace_box["width"] < width * 0.8:
                    raise RuntimeError(
                        f"wide Modeling Data workspace collapsed into a fixed-width island at {width}x{height}: "
                        f"workspace={workspace_box}, plot={plot_box}"
                    )
                data_measurement.update({"elasticWorkspaceWidth": workspace_box["width"], "elasticPlotWidth": plot_box["width"]})
            measurements.append(
                {
                    "stage": "data",
                    "viewport": f"{width}x{height}",
                    **data_measurement,
                }
            )
        finally:
            page.context.close()
    return measurements


def _capture_modeling_process_manual_only(
    browser: Browser,
    base_url: str,
    output: Path,
) -> None:
    page = _new_page(browser, base_url, 1366, 768)
    try:
        _prepare_modeling_process(page, base_url, verify_data_reload=False)
        _wait_modeling_process_panel(page)
        _assert_modeling_process_preview(page)
        _assert_modeling_process_manual_surface(
            page,
            capture_path=output / MODELING_PROCESS_MANUAL_OUTPUTS[0],
        )
    finally:
        page.context.close()


def _capture_modeling_data_session(
    browser: Browser, base_url: str, output: Path
) -> list[dict[str, object]]:
    """Capture exact Library selection, reload persistence, and Data exceptions."""
    _capture_modeling_session_shell(browser, base_url, output)
    measurements = _capture_modeling_data_viewports(
        browser, base_url, output, (*VIEWPORTS, *WIDE_VIEWPORTS)
    )
    _capture_modeling_data_exceptions(browser, base_url, output)
    return measurements


def _capture_modeling_session_shell(browser: Browser, base_url: str, output: Path) -> None:
    """Capture the pin-free Data-first state separately from the populated Data workflow."""
    for width, height in VIEWPORTS:
        page = _new_page(browser, base_url, width, height)
        try:
            page.goto(f"{base_url}/modeling?stage=data&family=metal")
            page.locator(".modeling-stage-shell button").filter(has_text="Data").wait_for(
                timeout=30_000
            )
            page.wait_for_function(
                """() => document.querySelector(
                  ".modeling-stage-shell button.active strong"
                )?.textContent?.trim() === "Data" """,
                timeout=30_000,
            )
            page.evaluate(
                """() => window.dispatchEvent(new CustomEvent(
                  "cmp:workspace-command", { detail: { command: "modeling:new" } }
                ))"""
            )
            page.wait_for_url(re.compile(r"stage=data"), timeout=30_000)
            page.wait_for_function(
                """() => {
                  const raw = sessionStorage.getItem("cmp.modeling.recent-session.v4");
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
            shell_buttons = shell.get_by_role("button")
            shell_buttons.nth(3).wait_for(timeout=30_000)
            if shell_buttons.count() != 4 or shell_buttons.all_inner_texts() != [
                "Data",
                "Process",
                "Fit",
                "Export",
            ]:
                raise RuntimeError("new-session shell must visibly contain exactly four normal stages")
            retired_terms = page.get_by_text(re.compile(r"exact Test Data|Advanced data contract"))
            if any(retired_terms.nth(index).is_visible() for index in range(retired_terms.count())):
                raise RuntimeError("new-session shell exposed retired implementation terminology")

            local_tab = page.get_by_role("tab", name="Local file", exact=True)
            if (
                local_tab.get_attribute("aria-selected") != "true"
                or page.locator(".modeling-workspace-rail").count()
            ):
                raise RuntimeError(
                    "new-session Data must start with Local file and no empty browser rail"
                )
            file_control = page.get_by_label("Import Test Data file")
            if file_control.count() != 1 or not file_control.is_visible():
                raise RuntimeError(
                    "new-session Data must expose the local Test Data file control"
                )
            empty_plot = page.locator(".engineering-curve-plot-empty-frame")
            empty_plot.wait_for(state="visible", timeout=30_000)
            empty_svg = empty_plot.locator(
                'svg[role="img"][aria-label="Empty engineering curve plot"]'
            )
            if empty_svg.count() != 1 or not empty_svg.is_visible():
                raise RuntimeError(
                    "new-session Data must retain one visible empty engineering plot"
                )
            _capture(page, output / f"modeling-session-{width}x{height}.png", width, height)
        finally:
            page.context.close()


def _capture_modeling_data_exceptions(
    browser: Browser,
    base_url: str,
    output: Path,
) -> None:
    """Capture the empty state and a recoverable local-file mapping blocker."""
    page = _new_page(browser, base_url, 1440, 900)
    try:
        page.goto(f"{base_url}/modeling?stage=data&family=metal")
        _wait_for_modeling_data_surface(page)
        page.evaluate(
            """() => window.dispatchEvent(new CustomEvent(
              "cmp:workspace-command", { detail: { command: "modeling:new" } }
            ))"""
        )
        _wait_for_modeling_data_surface(page)
        page.wait_for_function(
            """() => {
              const raw = sessionStorage.getItem("cmp.modeling.recent-session.v4");
              if (!raw) return false;
              const session = JSON.parse(raw);
              const workspace = session.workspace || {};
              return session.contextSelectionRequired === true
                && !session.material
                && !session.materialState
                && !session.testData
                && !session.mappingProfile
                && Array.isArray(workspace.selectedTestDataRefs)
                && workspace.selectedTestDataRefs.length === 0
                && Array.isArray(workspace.selectedDocumentIds)
                && workspace.selectedDocumentIds.length === 0
                && Array.isArray(workspace.visibleTestDataKeys)
                && workspace.visibleTestDataKeys.length === 0;
            }""",
            timeout=30_000,
        )
        local_tab = page.get_by_role("tab", name="Local file", exact=True)
        if (
            local_tab.get_attribute("aria-selected") != "true"
            or page.locator(".modeling-workspace-rail").count()
        ):
            raise RuntimeError(
                "empty Data must start at Local file without an unused browser rail"
            )
        if page.locator(".modeling-notice-line").count():
            raise RuntimeError(
                "empty Data exposes a redundant session-status sentence"
            )
        _assert_import_file_control(page)
        empty_plot = page.locator(".engineering-curve-plot-empty-frame")
        empty_svg = empty_plot.locator(
            'svg[role="img"][aria-label="Empty engineering curve plot"]'
        )
        empty_svg.wait_for(state="visible", timeout=30_000)
        if (
            empty_svg.locator(".chart-grid").count() < 2
            or empty_svg.locator(".chart-axis").count() != 2
            or not empty_svg.get_by_text("Engineering strain [1]").count()
            or not empty_svg.get_by_text("Engineering stress [MPa]").count()
        ):
            raise RuntimeError("empty Data graph is missing its engineering axes")
        if empty_plot.get_by_role("button", name="Import file", exact=True).count():
            raise RuntimeError(
                "empty Data duplicates the already visible local-file action inside the graph"
            )
        # Keep the pin-free session evidence on the default Local file task,
        # then record the separate empty-Library decision state. This proves
        # both entry paths without registering two byte-identical current
        # screenshots or changing the production default.
        library_tab = page.get_by_role("tab", name="Library", exact=True)
        library_tab.click()
        page.wait_for_function(
            """() => document.querySelector(
              '[role="tablist"][aria-label="Test data source"] [role="tab"][aria-selected="true"]'
            )
              ?.textContent?.trim() === 'Library'""",
            timeout=30_000,
        )
        page.get_by_role("region", name="Test Data results").wait_for(
            state="visible", timeout=30_000
        )
        if page.locator('.modeling-data-record-button[aria-current="true"]').count():
            raise RuntimeError("empty Library state selected a Test Data row implicitly")
        if page.get_by_role("button", name="Continue to Process", exact=True).count():
            raise RuntimeError("empty Library state exposes a premature Process action")
        _capture(page, output / "modeling-data-empty-1440x900.png", 1440, 900)
    finally:
        page.context.close()

    page = _new_page(browser, base_url, 1440, 900)
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        _prepare_modeling(
            page,
            base_url,
            verify_reload=False,
            retain_comparisons=False,
        )
        before_session = _data_session_snapshot(page)
        _wait_for_data_plot(page, lines=1, legends=1)
        page.get_by_role("tab", name="Local file", exact=True).click()

        long_strain = (
            "Engineering strain measurement channel from extensometer "
            "(longitudinal)"
        )
        long_stress = "True stress observed channel [MPa]"
        temporary_directory = tempfile.TemporaryDirectory(prefix="cmp-invalid-")
        temporary_csv = Path(temporary_directory.name) / "modeling-data-invalid.csv"
        temporary_csv.write_text(
            f"{long_strain},{long_stress},Specimen identifier\n"
            "0.0000,0.0,Specimen 03\n"
            "0.0100,410.0,Specimen 03\n"
            "0.0200,520.0,Specimen 03\n"
            "0.0300,610.0,Specimen 03\n",
            encoding="utf-8",
        )
        page.get_by_label("Import Test Data file", exact=True).set_input_files(
            str(temporary_csv)
        )
        test_record = page.get_by_role(
            "combobox", name="Imported file Test record", exact=True
        )
        test_record.wait_for(timeout=30_000)
        if test_record.locator("option").count() <= 1:
            raise RuntimeError(
                "no governed Test record is available for local-file recovery"
            )
        test_record.select_option(index=1)
        inspect = page.get_by_role("button", name="Inspect file", exact=True)
        if not inspect.is_enabled():
            raise RuntimeError(
                "Inspect file is disabled after choosing a Test record and CSV"
            )
        inspect.click()

        mapping_table = page.get_by_role(
            "region",
            name="Axis and unit mapping decision table",
            exact=True,
        )
        mapping_table.wait_for(state="visible", timeout=30_000)
        if mapping_table.locator("thead th").all_inner_texts() != [
            "Modeling data",
            "Column in file",
            "File unit",
            "Modeling unit",
        ]:
            raise RuntimeError("local-file mapping columns are not concise and aligned")
        if mapping_table.evaluate(
            "element => element.scrollWidth > element.clientWidth + 1"
        ):
            raise RuntimeError("local-file mapping table exposes horizontal clipping")

        file_details = page.locator("details.data-source-advanced")
        if (
            file_details.count() != 1
            or file_details.get_attribute("open") is not None
            or page.locator(".data-raw-table").is_visible()
        ):
            raise RuntimeError(
                "raw file evidence must remain collapsed under File details"
            )

        strain_column = page.get_by_role(
            "combobox",
            name="Engineering strain source column",
            exact=True,
        )
        stress_column = page.get_by_role(
            "combobox",
            name="Engineering stress source column",
            exact=True,
        )
        strain_column.select_option(value=long_strain)
        stress_column.select_option(value=long_strain)
        page.get_by_role(
            "combobox",
            name="Engineering stress original unit",
            exact=True,
        ).select_option(label="%")

        blockers = page.locator(".data-mapping-blockers[role=alert]")
        blockers.wait_for(state="visible", timeout=30_000)
        for message in (
            "Fix the test data mapping.",
            "Use a different source column for each required channel.",
            "Engineering stress cannot use “%”. Choose Pa, kPa, MPa, or GPa.",
        ):
            if not blockers.get_by_text(message, exact=True).count():
                raise RuntimeError(
                    f"local-file recovery is missing blocker {message!r}"
                )
        blocker_box = blockers.bounding_box()
        local_box = page.get_by_role(
            "region", name="Local Test Data import", exact=True
        ).bounding_box()
        if (
            blocker_box is None
            or local_box is None
            or blocker_box["y"] < local_box["y"] - 1
            or blocker_box["y"] + blocker_box["height"]
              > local_box["y"] + local_box["height"] + 1
        ):
            raise RuntimeError(
                "invalid mapping cause is not visible beside the mapping controls"
            )
        for action in ("Update preview", "Save Test Data"):
            button = page.get_by_role("button", name=action, exact=True)
            if button.count():
                raise RuntimeError(
                    f"invalid mapping exposes premature {action} action"
                )

        _wait_for_data_plot(page, lines=1, legends=1)
        if _data_session_snapshot(page) != before_session:
            raise RuntimeError(
                "inspecting an invalid local mapping changed the exact session"
            )
        local_region = page.get_by_role(
            "region", name="Local Test Data import", exact=True
        )
        scroll_metrics = local_region.evaluate(
            """element => ({
              clientHeight: element.clientHeight,
              scrollHeight: element.scrollHeight,
              overflowY: getComputedStyle(element).overflowY,
              tabIndex: element.tabIndex,
            })"""
        )
        if (
            scroll_metrics["overflowY"] not in ("auto", "scroll")
            or scroll_metrics["tabIndex"] != 0
            or scroll_metrics["scrollHeight"] <= scroll_metrics["clientHeight"] + 1
        ):
            raise RuntimeError(
                f"local-file recovery is not keyboard-scrollable: {scroll_metrics}"
            )

        divider = page.locator("#modeling-data-ribbon-plot-divider")
        if (
            divider.count() != 1
            or divider.get_attribute("role") != "separator"
            or divider.get_attribute("aria-orientation") != "horizontal"
        ):
            raise RuntimeError("Data source/graph splitter semantics drifted")
        before_ribbon = _bounding_box_edges(
            page.locator("#modeling-data-ribbon[data-panel]").bounding_box()
        )
        before_plot = _bounding_box_edges(
            page.locator(".modeling-data-plot-panel").bounding_box()
        )
        if before_ribbon is None or before_plot is None:
            raise RuntimeError("Data split panels are not measurable")
        divider.focus()
        divider.press("ArrowDown")
        page.wait_for_timeout(100)
        after_ribbon = _bounding_box_edges(
            page.locator("#modeling-data-ribbon[data-panel]").bounding_box()
        )
        after_plot = _bounding_box_edges(
            page.locator(".modeling-data-plot-panel").bounding_box()
        )
        if (
            after_ribbon is None
            or after_plot is None
            or after_ribbon["height"] <= before_ribbon["height"]
            or after_plot["height"] >= before_plot["height"]
            or after_plot["height"] < 240
        ):
            raise RuntimeError(
                "keyboard splitter resize did not preserve a usable graph"
            )
        divider.dblclick()
        page.wait_for_timeout(100)
        reset_ribbon = _bounding_box_edges(
            page.locator("#modeling-data-ribbon[data-panel]").bounding_box()
        )
        reset_plot = _bounding_box_edges(
            page.locator(".modeling-data-plot-panel").bounding_box()
        )
        if (
            reset_ribbon is None
            or reset_plot is None
            or abs(reset_ribbon["height"] - before_ribbon["height"]) > 1
            or abs(reset_plot["height"] - before_plot["height"]) > 1
        ):
            raise RuntimeError("double-click did not reset the Data splitter")

        local_region.evaluate(
            "element => { element.scrollTop = 0; element.focus(); }"
        )
        _capture(
            page,
            output / "modeling-data-invalid-1440x900.png",
            1440,
            900,
        )
        local_region.press("PageDown")
        page.wait_for_timeout(100)
        if local_region.evaluate("element => element.scrollTop") < 1:
            raise RuntimeError("local-file recovery does not respond to PageDown")
        _capture(
            page,
            output / "modeling-data-invalid-scrolled-1440x900.png",
            1440,
            900,
        )

        stress_column.select_option(value=long_stress)
        page.get_by_role(
            "combobox",
            name="Engineering stress original unit",
            exact=True,
        ).select_option(label="MPa")
        page.wait_for_function(
            """() => !document.querySelector(
                '.data-mapping-blockers[role="alert"]'
            )""",
            timeout=30_000,
        )
        reason = page.get_by_role(
            "textbox", name="Mapping change reason", exact=True
        )
        reason.fill("Correct the stress column and recorded file unit.")
        if page.get_by_role(
            "button", name="Update preview", exact=True
        ).is_disabled():
            raise RuntimeError(
                "corrected local mapping did not expose its preview recovery action"
            )
        if not page.get_by_role(
            "button", name="Save Test Data", exact=True
        ).is_disabled():
            raise RuntimeError(
                "local Test Data must remain unsaved until the corrected preview succeeds"
            )
        if _data_session_snapshot(page) != before_session:
            raise RuntimeError(
                "correcting an unsaved local mapping changed the exact session"
            )
    finally:
        page.context.close()
        if temporary_directory is not None:
            temporary_directory.cleanup()



def _capture_administration_database(browser: Browser, base_url: str, output: Path) -> None:
    resolver_page = _new_page(browser, base_url, *VIEWPORTS[1])
    pins = _resolve_administration_source_v2(resolver_page, base_url)
    resolver_page.context.close()
    layout_url = _administration_database_url(base_url, pins)
    preview_url = _administration_database_url(base_url, pins, include_record=True)
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(layout_url)
        page.get_by_role("navigation", name="Administration tasks", exact=True).wait_for(timeout=30_000)
        _wait_for_administration_layout(page, pins, layout_url)
        page.reload()
        _wait_for_administration_layout(page, pins, layout_url)
        page.wait_for_load_state("networkidle")
        if page.get_by_role("alert").count():
            raise RuntimeError(f"Administration shows an error at {width}x{height}")
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise RuntimeError(f"Administration has horizontal overflow at {width}x{height}")
        _assert_semantic_three_pane_geometry(
            page,
            group_selector=".schema-editor-grid",
            form_selector=".schema-property-editor .property-sheet",
            path_name=f"administration-database-{width}x{height}.png",
        )
        _capture(page, output / f"administration-database-{width}x{height}.png", width, height)
        page.get_by_role("button", name="Preview", exact=True).click()
        picker = page.get_by_role("combobox", name="Preview with", exact=True)
        picker.wait_for(timeout=30_000)
        picker.select_option(pins["record_id"])
        _wait_for_administration_preview(page, pins, preview_url)
        page.reload()
        _wait_for_administration_layout(
            page, pins, preview_url, require_property_form=False
        )
        _wait_for_administration_preview(page, pins, preview_url)
        _capture(
            page,
            output / f"administration-database-preview-{width}x{height}.png",
            width,
            height,
        )
        page.context.close()


def _capture_administration_records(browser: Browser, base_url: str, output: Path) -> None:
    resolver_page = _new_page(browser, base_url, *VIEWPORTS[1])
    pins = _resolve_administration_source_v2(resolver_page, base_url)
    resolver_page.context.close()
    records_url = _administration_records_url(base_url, pins)
    exact_record_url = _administration_records_url(base_url, pins, include_record=True)
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(records_url)
        page.get_by_role("navigation", name="Administration tasks", exact=True).wait_for(timeout=30_000)
        page.get_by_role("region", name="Record scope and search", exact=True).wait_for(timeout=30_000)
        _wait_for_administration_record_type(page, pins)
        search = page.get_by_role("textbox", name="Search", exact=True)
        search.fill("CMP-246-TECH-DP780")
        page.get_by_role("button", name="Search", exact=True).click()
        record_rows = page.locator(".record-result")
        expected_record_row = "DP780 technical data\nCMP-246-TECH-DP780\n1\nDraft"
        deadline = time.monotonic() + 30
        while (
            record_rows.count() != 1
            or record_rows.all_inner_texts() != [expected_record_row]
        ):
            if time.monotonic() >= deadline:
                raise RuntimeError("Administration search did not return one exact DP780 record")
            page.wait_for_timeout(100)
        record_rows.click()
        _wait_for_administration_record(page, pins, exact_record_url)
        page.reload()
        _wait_for_administration_record(page, pins, exact_record_url)
        if page.get_by_role("alert").count():
            raise RuntimeError(f"Administration records shows an error at {width}x{height}")
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise RuntimeError(
                f"Administration records has horizontal overflow at {width}x{height}"
            )
        _assert_administration_record_editor_geometry(
            page,
            group_selector=".catalog-record-grid",
            form_selector=".catalog-datasheet > form",
            path_name=f"administration-records-{width}x{height}.png",
        )
        _capture(page, output / f"administration-records-{width}x{height}.png", width, height)
        page.context.close()


def _capture_product_access(browser: Browser, base_url: str, output: Path) -> None:
    for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS):
        page = _new_page(browser, base_url, width, height)
        page.goto(f"{base_url}/administration/access")
        page.get_by_role("heading", name="Access", exact=True).wait_for(timeout=30_000)
        page.get_by_role("table", name="Access grants", exact=True).wait_for(
            timeout=30_000
        )
        for column in ("Member", "Role", "Permissions", "Action"):
            page.get_by_role("columnheader", name=column, exact=True).wait_for(
                timeout=30_000
            )
        _capture(
            page,
            output / f"administration-access-{width}x{height}.png",
            width,
            height,
        )
        page.context.close()

def _capture_supporting_screens(browser: Browser, base_url: str, output: Path) -> None:
    _capture_administration_database(browser, base_url, output)
    _capture_administration_records(browser, base_url, output)
    _capture_product_access(browser, base_url, output)


def _preserve_issue_owned_contract_captures(output: Path) -> None:
    """Carry contract-backed browser captures into a full current-set recapture."""
    current = Path(__file__).resolve().parents[1] / "docs" / "user-guide" / "images" / "current"
    for name in (
        "material-database-categories-1440x900.png",
        "material-database-linked-test-1440x900.png",
        "administration-format-definitions-1440x900.png",
        "demo-session-recovery-1440x900.png",
        "modeling-process-polymer-dma-tts-1366x768.png",
        "modeling-process-polymer-dma-tts-1440x900.png",
        "modeling-process-polymer-dma-tts-1920x1080.png",
        "modeling-process-polymer-dma-tts-2560x1440.png",
        "modeling-process-polymer-dma-tts-3840x2160.png",
        "modeling-process-polymer-dma-tts-saved-1366x768.png",
        "modeling-process-polymer-dma-tts-saved-1440x900.png",
        "modeling-process-polymer-dma-tts-saved-1920x1080.png",
        "modeling-process-polymer-dma-tts-saved-2560x1440.png",
        "modeling-process-polymer-dma-tts-saved-3840x2160.png",
        "modeling-fit-polymer-saved-1366x768.png",
        "modeling-fit-polymer-saved-1440x900.png",
        "modeling-fit-polymer-saved-1920x1080.png",
        "modeling-fit-polymer-saved-2560x1440.png",
        "modeling-fit-polymer-saved-3840x2160.png",
        "modeling-fit-polymer-input-1920x1080.png",
        "modeling-fit-polymer-residual-1920x1080.png",
        "modeling-fit-polymer-calculation-settings-1920x1080.png",
        "modeling-fit-polymer-stale-1920x1080.png",
        "modeling-fit-polymer-stale-restored-saved-input-1920x1080.png",
        "modeling-fit-polymer-stale-recovered-1920x1080.png",
        *ADMINISTRATION_RECORDS_IMPORT_JSON_OUTPUTS,
    ):
        source = current / name
        if not source.is_file():
            raise RuntimeError(f"registered contract-backed capture is missing: {source}")
        shutil.copy2(source, output / name)


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
        minimum_size = 1_000 if name in MODELING_DISTRIBUTION_DETAIL_OUTPUTS else 10_000
        if (
            len(value) < minimum_size
            or value[:8] != PNG_SIGNATURE
            or value[12:16] != b"IHDR"
        ):
            raise RuntimeError(f"current capture is not a plausible PNG: {name}")
        width, height = struct.unpack(">II", value[16:24])
        expected = re.search(r"-(\d+)x(\d+)\.png$", name)
        if name in MODELING_DISTRIBUTION_DETAIL_OUTPUTS:
            if width < 100 or height < 40:
                raise RuntimeError(
                    f"current distribution detail crop is implausibly small for {name}: "
                    f"{width}x{height}"
                )
        elif expected is None or (width, height) != (
            int(expected.group(1)), int(expected.group(2))
        ):
            raise RuntimeError(f"current capture viewport drift for {name}: {width}x{height}")
    return len(actual_outputs)


def _replace_capture_directory(staged: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{target.name}-previous-", dir=target.parent))
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
    global CAPTURE_DISPLAY_DENSITY

    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/user-guide/images/current"),
    )
    parser.add_argument(
        "--density",
        choices=DISPLAY_DENSITIES,
        default="standard",
        help=(
            "Install the product-wide browser-local density preference before the "
            "first application paint."
        ),
    )
    parser.add_argument(
        "--only-materials",
        action="store_true",
        help="Capture and replace the Materials workspace, detail/card states, and wide card previews.",
    )
    parser.add_argument(
        "--only-materials-workspace",
        action="store_true",
        help="Capture only Materials explorer/result/empty/browse states, without datasheet preparation.",
    )
    parser.add_argument(
        "--only-product-access",
        action="store_true",
        help="Capture and replace only the five Product Access role-preset viewports.",
    )
    parser.add_argument(
        "--only-administration-database",
        action="store_true",
        help="Capture and replace only the five Administration database-design viewports.",
    )
    parser.add_argument(
        "--only-administration-records",
        action="store_true",
        help="Capture and replace only the five Administration registration viewports.",
    )
    parser.add_argument(
        "--only-activity",
        action="store_true",
        help="Capture the five Activity viewports plus wide history, role defaults, decision error, and recovery states.",
    )
    parser.add_argument(
        "--only-review-submission",
        action="store_true",
        help="Capture Native Solver Card review submission and Activity status at all viewports.",
    )
    parser.add_argument(
        "--only-modeling-export",
        action="store_true",
        help="Capture and replace the five Modeling Export viewports plus source-blocked, approximation-blocked, and delivered states.",
    )
    parser.add_argument(
        "--only-modeling-export-pre-delivered",
        action="store_true",
        help="Capture the five Export viewports and two blocked states without the append-only delivered fixture.",
    )
    parser.add_argument(
        "--only-modeling-process-fit",
        action="store_true",
        help=(
            "Capture and replace the five Process/Fit viewports plus candidate-evidence, "
            "calculation/save failure, exact-source/read failure, and restored Fit states."
        ),
    )
    parser.add_argument(
        "--only-modeling-process-fit-viewports",
        action="store_true",
        help="Capture only the five normal Process/Fit viewport pairs.",
    )
    parser.add_argument(
        "--only-modeling-fit-states",
        action="store_true",
        help="Capture only candidate-evidence, failure, and exact-source Fit states.",
    )
    parser.add_argument(
        "--only-modeling-fit-restored",
        action="store_true",
        help="Capture only the final saved Fit reload/restore state.",
    )
    parser.add_argument(
        "--only-modeling-process",
        action="store_true",
        help="Capture and replace only the ten Modeling Process viewports and settled states.",
    )
    parser.add_argument(
        "--resume-modeling-process",
        action="store_true",
        help=(
            "Resume only the interrupted three-output Modeling Process capture; "
            "requires --only-modeling-process."
        ),
    )
    parser.add_argument(
        "--only-modeling-consistency",
        action="store_true",
        help=(
            "Capture all 15 current Modeling Data/Process/Fit/Export/session screens "
            "with consistency gates."
        ),
    )
    parser.add_argument(
        "--only-modeling-data-session",
        action="store_true",
        help=(
            "Capture the ten current Modeling Data/session screens with the same consistency gates."
        ),
    )
    parser.add_argument(
        "--only-modeling-process-manual",
        action="store_true",
        help="Capture only the 1366x768 manual Process local-scroll boundary.",
    )
    parser.add_argument(
        "--only-modeling-distribution",
        action="store_true",
        help="Capture the five scalar-distribution viewports.",
    )
    parser.add_argument(
        "--include-distribution-detail-crops",
        action="store_true",
        help=(
            "With --only-modeling-distribution, also capture original-pixel "
            "header, navigator, table, selection-form, and graph crops."
        ),
    )
    parser.add_argument(
        "--only-modeling-data-exceptions",
        action="store_true",
        help="Capture only the empty and invalid-mapping Modeling Data risk states.",
    )
    args = parser.parse_args()
    CAPTURE_DISPLAY_DENSITY = args.density
    if args.resume_modeling_process and not args.only_modeling_process:
        parser.error("--resume-modeling-process requires --only-modeling-process")
    if args.include_distribution_detail_crops and not args.only_modeling_distribution:
        parser.error(
            "--include-distribution-detail-crops requires --only-modeling-distribution"
        )
    if args.resume_modeling_process and any(
        (
            args.only_materials,
            args.only_product_access,
            args.only_administration_database,
            args.only_administration_records,
            args.only_activity,
            args.only_review_submission,
            args.only_modeling_export,
            args.only_modeling_process_fit,
            args.only_modeling_process_manual,
            args.only_modeling_distribution,
            args.only_modeling_fit_states,
            args.only_modeling_fit_restored,
            args.only_modeling_consistency,
            args.only_modeling_data_session,
            args.only_modeling_data_exceptions,
        )
    ):
        parser.error("--resume-modeling-process cannot be combined with another capture selector")

    def produce(output: Path) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                _capture_materials(browser, args.base_url, output)
                _capture_solver_delivery(browser, args.base_url, output)
                _capture_activity(browser, args.base_url, output)
                _capture_modeling_session_shell(browser, args.base_url, output)
                _capture_modeling(
                    browser,
                    args.base_url,
                    output,
                    include_process_normals=False,
                )
                _capture_modeling_export_only(browser, args.base_url, output)
                _capture_modeling_process_only(browser, args.base_url, output)
                _capture_modeling_distribution(browser, args.base_url, output)
                _capture_modeling_fit_states(browser, args.base_url, output)
                _capture_modeling_polymer_fit_source_blocked(
                    browser, args.base_url, output
                )
                _capture_modeling_data_viewports(
                    browser, args.base_url, output, WIDE_VIEWPORTS
                )
                _capture_modeling_data_exceptions(browser, args.base_url, output)
                _capture_supporting_screens(browser, args.base_url, output)
                _preserve_issue_owned_contract_captures(output)
            finally:
                browser.close()

    selected_output_names: Sequence[str] = CURRENT_CAPTURE_OUTPUTS
    if (
        args.only_materials
        or args.only_materials_workspace
        or args.only_modeling_export
        or args.only_modeling_export_pre_delivered
        or args.only_modeling_process_fit
        or args.only_modeling_process_fit_viewports
        or args.only_modeling_fit_states
        or args.only_modeling_fit_restored
        or args.only_modeling_process
        or args.only_modeling_process_manual
        or args.only_modeling_distribution
        or args.only_modeling_consistency
        or args.only_modeling_data_session
        or args.only_modeling_data_exceptions
        or args.only_product_access
        or args.only_administration_database
        or args.only_administration_records
        or args.only_activity
        or args.only_review_submission
    ):
        names = (
            MATERIALS_OUTPUTS
            if args.only_materials
            else MATERIALS_WORKSPACE_OUTPUTS
            if args.only_materials_workspace
            else MODELING_EXPORT_OUTPUTS
            if args.only_modeling_export
            else MODELING_EXPORT_PRE_DELIVERED_OUTPUTS
            if args.only_modeling_export_pre_delivered
            else MODELING_PROCESS_FIT_OUTPUTS
            if args.only_modeling_process_fit
            else MODELING_PROCESS_FIT_VIEWPORT_OUTPUTS
            if args.only_modeling_process_fit_viewports
            else MODELING_FIT_PRE_RESTORE_OUTPUTS
            if args.only_modeling_fit_states
            else MODELING_FIT_RESTORED_OUTPUTS
            if args.only_modeling_fit_restored
            else MODELING_PROCESS_OUTPUTS
            if args.only_modeling_process
            else MODELING_PROCESS_MANUAL_OUTPUTS
            if args.only_modeling_process_manual
            else (
                MODELING_DISTRIBUTION_OUTPUTS
                if args.include_distribution_detail_crops
                else MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS
            )
            if args.only_modeling_distribution
            else MODELING_CONSISTENCY_OUTPUTS
            if args.only_modeling_consistency
            else MODELING_DATA_SESSION_OUTPUTS
            if args.only_modeling_data_session
            else MODELING_DATA_EXCEPTION_OUTPUTS
            if args.only_modeling_data_exceptions
            else ACTIVITY_OUTPUTS
            if args.only_activity
            else REVIEW_SUBMISSION_OUTPUTS
            if args.only_review_submission
            else PRODUCT_ACCESS_OUTPUTS
            if args.only_product_access
            else ADMINISTRATION_RECORDS_OUTPUTS
            if args.only_administration_records
            else ADMINISTRATION_DATABASE_OUTPUTS
        )
        selected_output_names = names
        args.output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".modeling-stage-capture-", dir=args.output.parent
        ) as temporary:
            staged = Path(temporary)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    measurements: list[dict[str, object]] = []
                    if args.only_materials:
                        _capture_materials(browser, args.base_url, staged)
                    elif args.only_materials_workspace:
                        _capture_materials_workspace(browser, args.base_url, staged)
                    elif args.only_modeling_export:
                        _capture_modeling_export_only(browser, args.base_url, staged)
                    elif args.only_modeling_export_pre_delivered:
                        _capture_modeling_export_only(
                            browser,
                            args.base_url,
                            staged,
                            include_delivered=False,
                        )
                    elif args.only_modeling_process_fit:
                        measurements = _capture_modeling_process_fit(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_process_fit_viewports:
                        measurements = _capture_modeling_process_fit(
                            browser,
                            args.base_url,
                            staged,
                            include_fit_states=False,
                        )
                    elif args.only_modeling_fit_states:
                        _capture_modeling_fit_states(
                            browser, args.base_url, staged, include_restored=False
                        )
                    elif args.only_modeling_fit_restored:
                        _capture_modeling_fit_restored_only(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_process:
                        measurements = _capture_modeling_process_only(
                            browser,
                            args.base_url,
                            staged,
                            resume_modeling_process=args.resume_modeling_process,
                        )
                    elif args.only_modeling_process_manual:
                        _capture_modeling_process_manual_only(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_distribution:
                        measurements = _capture_modeling_distribution(
                            browser,
                            args.base_url,
                            staged,
                            include_detail_crops=args.include_distribution_detail_crops,
                        )
                    elif args.only_modeling_consistency:
                        measurements = _capture_modeling_consistency(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_data_session:
                        measurements = _capture_modeling_data_session(
                            browser, args.base_url, staged
                        )
                    elif args.only_modeling_data_exceptions:
                        _capture_modeling_data_exceptions(
                            browser, args.base_url, staged
                        )
                    elif args.only_activity:
                        _capture_activity(browser, args.base_url, staged)
                    elif args.only_review_submission:
                        _capture_solver_delivery(browser, args.base_url, staged)
                    elif args.only_product_access:
                        _capture_product_access(browser, args.base_url, staged)
                    elif args.only_administration_records:
                        _capture_administration_records(browser, args.base_url, staged)
                    else:
                        _capture_administration_database(browser, args.base_url, staged)
                finally:
                    browser.close()
            actual_outputs = {path.name for path in staged.iterdir() if path.is_file()}
            if actual_outputs != set(names):
                raise RuntimeError(
                    f"targeted capture output drift: actual={sorted(actual_outputs)}"
                )
            for name in names:
                image = staged / name
                value = image.read_bytes()
                minimum_size = 1_000 if name in MODELING_DISTRIBUTION_DETAIL_OUTPUTS else 10_000
                if (
                    len(value) < minimum_size
                    or value[:8] != PNG_SIGNATURE
                    or value[12:16] != b"IHDR"
                ):
                    raise RuntimeError(f"targeted Modeling capture is not a plausible PNG: {name}")
            for name in names:
                os.replace(staged / name, args.output / name)
        capture_count = len(names)
    else:
        capture_count = _capture_to_empty_directory(args.output, produce)
    result = {
        "output": args.output.as_posix(),
        "captures": capture_count,
        "density": CAPTURE_DISPLAY_DENSITY,
        "viewports": [
            f"{width}x{height}"
            for width, height in (*VIEWPORTS, *WIDE_VIEWPORTS)
            if any(
                name.endswith(f"-{width}x{height}.png")
                for name in selected_output_names
            )
        ],
    }
    if (
        args.only_modeling_process_fit
        or args.only_modeling_process_fit_viewports
        or args.only_modeling_distribution
        or args.only_modeling_consistency
        or args.only_modeling_data_session
    ):
        result["measurements"] = measurements
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

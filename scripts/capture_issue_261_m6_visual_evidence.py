"""Capture #261 M6 five-viewport evidence and audit the frozen selector set live.

This bounded wrapper reuses the accepted FE-06 13-topology capture implementation.  It
adds a DOM-selector observation immediately before each original screenshot so the M6
removal decision is tied to the exact settled route/state and viewport evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import tempfile
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / "scripts/capture_issue_261_m4_visual_evidence.py"))
TOPOLOGIES = tuple(HARNESS["TOPOLOGIES"])
VIEWPORTS = tuple(HARNESS["VIEWPORTS"])
PHASES = ("before", "after")
SCHEMA = "cmp.issue-261.m6.visual-and-selector-evidence.v1"
HANDOFF_PATH = ROOT / "scripts/fixtures/issue-261-residual-owner-boundary.json"
INVENTORY_PATH = ROOT / "docs/17-evidence/issue-261-css-selector-inventory.json"
FIXTURE_PATH = ROOT / "scripts/fixtures/issue-261-m6-zero-consumer-audit.json"
DEFAULT_OUTPUT = ROOT / "docs/17-evidence/images/issue-261-m6-zero-consumer-audit-and-removal/live"
# The current-guide manifest remains a cumulative accepted image set. Keep this
# declaration literal for the documentation checker; M6 promotes only the
# matching Export original identified in screenshot-manifest.yaml.
CURRENT_CAPTURE_OUTPUTS = (
    "materials-search-1366x768.png",
    "materials-search-1440x900.png",
    "materials-search-1920x1080.png",
    "materials-search-2560x1440.png",
    "materials-search-3840x2160.png",
    "materials-search-long-1366x768.png",
    "materials-search-long-1440x900.png",
    "materials-search-long-1920x1080.png",
    "materials-search-short-1440x900.png",
    "materials-search-empty-1440x900.png",
    "materials-browse-1440x900.png",
    "demo-session-recovery-1440x900.png",
    "material-database-categories-1440x900.png",
    "material-database-linked-test-1440x900.png",
    "material-detail-1440x900.png",
    "material-detail-1366x768.png",
    "material-detail-1920x1080.png",
    "material-detail-2560x1440.png",
    "material-detail-3840x2160.png",
    "material-curves-1366x768.png",
    "material-curves-1440x900.png",
    "material-curves-1920x1080.png",
    "material-curves-2560x1440.png",
    "material-curves-3840x2160.png",
    "material-cae-cards-1440x900.png",
    "solver-card-preview-1366x768.png",
    "solver-card-preview-1440x900.png",
    "solver-card-preview-1920x1080.png",
    "modeling-data-1366x768.png",
    "modeling-session-1366x768.png",
    "modeling-session-1440x900.png",
    "modeling-session-1920x1080.png",
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
    "modeling-fit-1366x768.png",
    "modeling-fit-1440x900.png",
    "modeling-fit-1920x1080.png",
    "modeling-fit-2560x1440.png",
    "modeling-fit-3840x2160.png",
    "modeling-fit-candidate-parameters-long-1440x900.png",
    "modeling-fit-candidate-evidence-scrolled-1440x900.png",
    "modeling-fit-calculation-failed-1920x1080.png",
    "modeling-fit-save-failed-1920x1080.png",
    "modeling-fit-exact-source-blocked-1920x1080.png",
    "modeling-fit-exact-read-failed-1920x1080.png",
    "modeling-fit-restored-1920x1080.png",
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
    "administration-schema-bundle-1440x900.png",
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
    "administration-access-1366x768.png",
    "administration-access-role-control-1366x768.png",
    "administration-access-1440x900.png",
    "administration-access-1920x1080.png",
    "administration-access-2560x1440.png",
    "administration-access-3840x2160.png",
    "modeling-distribution-1366x768.png",
    "modeling-distribution-1440x900.png",
    "modeling-distribution-1920x1080.png",
    "modeling-distribution-2560x1440.png",
    "modeling-distribution-3840x2160.png",
)


class EvidenceError(RuntimeError):
    """Raised when the M6 runtime or visual proof is incomplete."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selector_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    handoff = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))["m6Handoff"]
    if FIXTURE_PATH.is_file():
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        rows = fixture["auditRows"]
        if fixture["handoff"]["tupleSha256"] != handoff["tupleSha256"]:
            raise EvidenceError("M6 fixture and FE-06 handoff digests disagree")
        return rows, handoff

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    rows = [
        {
            "id": row["id"],
            "selector": row["selector"],
            "source": row["source"],
            "declarationSignature": row["declarations"]["signatureSha256"],
        }
        for row in inventory["selectors"]
        if row["owner"]["migrationBatch"] == "M6-zero-consumer-removal-candidate"
    ]
    if len(rows) != handoff["rows"]:
        raise EvidenceError(f"M6 inventory row drift: {len(rows)} != {handoff['rows']}")
    return rows, handoff


def _audit_page(page: Page, selectors: list[str]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for start in range(0, len(selectors), 100):
        result = page.evaluate(
            """selectors => selectors.map(selector => {
              try {
                const nodes = [...document.querySelectorAll(selector)];
                return {
                  selector,
                  count: nodes.length,
                  samples: nodes.slice(0, 3).map(node => ({
                    tag: node.tagName.toLowerCase(),
                    id: node.id || null,
                    classes: [...node.classList],
                  })),
                };
              } catch (error) {
                return { selector, error: String(error) };
              }
            })""",
            selectors[start : start + 100],
        )
        for item in result:
            if item.get("error"):
                errors.append({"selector": item["selector"], "error": item["error"]})
            elif item["count"]:
                matches.append(item)
    return {"matches": matches, "queryErrors": errors}


def _capture_phase(
    source_root: Path,
    project: str,
    phase: str,
    output: Path,
    *,
    selector_only: bool = False,
) -> None:
    rows, handoff = _selector_rows()
    selectors = sorted({row["selector"] for row in rows})
    active_viewports = ((1440, 900),) if selector_only else VIEWPORTS
    topology_contracts = HARNESS["TOPOLOGIES"]
    expected_by_filename = {
        contract["source"].format(viewport=f"{width}x{height}"): {
            "topology": topology,
            "viewport": f"{width}x{height}",
        }
        for topology, contract in topology_contracts.items()
        for width, height in active_viewports
    }
    expected_snapshots = {
        f"{item['topology']}@{item['viewport']}" for item in expected_by_filename.values()
    }
    snapshots: list[dict[str, Any]] = []
    harness_globals = HARNESS["_capture_phase"].__globals__
    original_capture_raw = harness_globals["_capture_raw"]
    capture_module = HARNESS["CAPTURE"]
    capture_globals = HARNESS["CAPTURE_GLOBALS"]
    original_new_page = capture_module["_new_page"]
    original_harness_viewports = harness_globals["VIEWPORTS"]
    original_capture_viewports = capture_globals["VIEWPORTS"]
    harness_globals["VIEWPORTS"] = active_viewports
    capture_globals["VIEWPORTS"] = active_viewports

    def audited_screenshot(page: Page, *args: Any, **kwargs: Any) -> Any:
        path_value = kwargs.get("path")
        if path_value is None and args:
            path_value = args[0]
        name = Path(path_value).name if path_value else ""
        if name in expected_by_filename:
            topology = expected_by_filename[name]["topology"]
            viewport = expected_by_filename[name]["viewport"]
            observation = _audit_page(page, selectors)
            snapshots.append(
                {
                    "topology": topology,
                    "viewport": viewport,
                    "url": page.url,
                    **observation,
                }
            )
        return page.screenshot(*args, **kwargs)

    class AuditedPage:
        """Transparent Page proxy that intercepts the harness's original screenshots."""

        def __init__(self, page: Page) -> None:
            self._page = page

        def __getattr__(self, name: str) -> Any:
            return getattr(self._page, name)

        def screenshot(self, *args: Any, **kwargs: Any) -> Any:
            return audited_screenshot(self._page, *args, **kwargs)

    def audited_new_page(*args: Any, **kwargs: Any) -> AuditedPage:
        return AuditedPage(original_new_page(*args, **kwargs))

    def audited_capture_raw(base_url: str, raw: Path) -> None:
        capture_module["_new_page"] = audited_new_page
        capture_globals["_new_page"] = audited_new_page
        original_capture_raw(base_url, raw)

    harness_globals["_capture_raw"] = audited_capture_raw
    temporary_output: tempfile.TemporaryDirectory[str] | None = None
    capture_output = output
    if selector_only:
        temporary_output = tempfile.TemporaryDirectory(prefix=f"cmp-261-m6-{phase}-audit-")
        capture_output = Path(temporary_output.name)
    try:
        HARNESS["_capture_phase"](source_root, project, phase, capture_output)
    finally:
        harness_globals["_capture_raw"] = original_capture_raw
        capture_module["_new_page"] = original_new_page
        capture_globals["_new_page"] = original_new_page
        harness_globals["VIEWPORTS"] = original_harness_viewports
        capture_globals["VIEWPORTS"] = original_capture_viewports

    raw_snapshot_count = len(snapshots)
    snapshots_by_identity: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        identity = f"{snapshot['topology']}@{snapshot['viewport']}"
        if identity not in snapshots_by_identity:
            snapshots_by_identity[identity] = {**snapshot, "captureCount": 1}
            continue
        aggregate = snapshots_by_identity[identity]
        if aggregate["url"] != snapshot["url"]:
            raise EvidenceError(
                f"M6 repeated screenshot identity changed URL: {identity}: "
                f"{aggregate['url']} != {snapshot['url']}"
            )
        aggregate["captureCount"] += 1
        matches_by_selector = {item["selector"]: item for item in aggregate["matches"]}
        for item in snapshot["matches"]:
            previous = matches_by_selector.get(item["selector"])
            if previous is None or item["count"] > previous["count"]:
                matches_by_selector[item["selector"]] = item
        aggregate["matches"] = list(matches_by_selector.values())
        aggregate["queryErrors"].extend(snapshot["queryErrors"])
    snapshots = list(snapshots_by_identity.values())
    observed = set(snapshots_by_identity)
    if observed != expected_snapshots:
        missing = sorted(expected_snapshots - observed)
        raise EvidenceError(
            f"M6 selector audit coverage drifted; missing={missing}; "
            f"unexpected={sorted(observed - expected_snapshots)}"
        )

    selector_summary: dict[str, dict[str, Any]] = {
        selector: {"selector": selector, "matchingSnapshots": [], "queryErrors": []}
        for selector in selectors
    }
    for snapshot in snapshots:
        identity = {
            "topology": snapshot["topology"],
            "viewport": snapshot["viewport"],
            "url": snapshot["url"],
        }
        for item in snapshot["matches"]:
            selector_summary[item["selector"]]["matchingSnapshots"].append(
                {**identity, "count": item["count"], "samples": item["samples"]}
            )
        for item in snapshot["queryErrors"]:
            selector_summary[item["selector"]]["queryErrors"].append(
                {**identity, "error": item["error"]}
            )

    output.mkdir(parents=True, exist_ok=True)
    audit = {
        "schemaVersion": "cmp.issue-261.m6.live-selector-audit.v1",
        "phase": phase,
        "sourceRoot": source_root.resolve().as_posix(),
        "handoff": {
            "rows": handoff["rows"],
            "groups": handoff["groups"],
            "tupleSha256": handoff["tupleSha256"],
        },
        "method": (
            "document.querySelectorAll for every unique frozen M6 selector immediately before "
            "each settled original screenshot in the accepted 13-topology/five-viewport harness"
        ),
        "coverage": {
            "topologies": list(TOPOLOGIES),
            "viewports": [f"{width}x{height}" for width, height in active_viewports],
            "snapshots": len(snapshots),
            "rawScreenshotAudits": raw_snapshot_count,
            "selectorRows": len(rows),
            "uniqueSelectors": len(selectors),
        },
        "summary": {
            "selectorsWithMatches": sum(
                1 for item in selector_summary.values() if item["matchingSnapshots"]
            ),
            "selectorsWithQueryErrors": sum(
                1 for item in selector_summary.values() if item["queryErrors"]
            ),
            "zeroMatchSelectors": sum(
                1
                for item in selector_summary.values()
                if not item["matchingSnapshots"] and not item["queryErrors"]
            ),
        },
        "selectors": list(selector_summary.values()),
    }
    (output / f"selector-runtime-{phase}.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    if temporary_output is not None:
        temporary_output.cleanup()


def _write_manifest(output: Path, *, accepted: bool) -> None:
    HARNESS["_write_manifest"](output, accepted=accepted)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    before = output / "selector-runtime-before.json"
    after = output / "selector-runtime-after.json"
    if not before.is_file() or not after.is_file():
        raise EvidenceError("both M6 selector runtime audits are required")
    selector_audits = {}
    for phase, path in (("before", before), ("after", after)):
        audit = json.loads(path.read_text(encoding="utf-8"))
        selector_audits[phase] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(path),
            "coverage": audit["coverage"],
            "summary": audit["summary"],
        }
    manifest["schemaVersion"] = SCHEMA
    manifest["unit"] = "M6-zero-consumer-audit-and-removal"
    manifest["baseSha"] = fixture["baseSha"]
    manifest["ownership"] = {
        "handoffSelectorRows": fixture["handoff"]["rows"],
        "handoffGroups": fixture["handoff"]["groups"],
        "removedSelectorRows": fixture["remove"]["rows"],
        "touchedGroups": fixture["remove"]["touchedGroups"],
        "fullyRemovedGroups": fixture["remove"]["fullyRemovedGroups"],
        "partiallyShrunkGroups": fixture["remove"]["partiallyShrunkGroups"],
        "holdRows": fixture["hold"]["rows"],
        "holdGroups": fixture["hold"]["groups"],
        "remainingSelectorRows": fixture["expectedAfter"]["selectorRows"],
        "remainingGroups": fixture["expectedAfter"]["cssRuleGroups"],
        "tupleSha256": fixture["handoff"]["tupleSha256"],
    }
    manifest["selectorRuntimeAudits"] = selector_audits
    manifest["physicalWindows4K"] = "DEFERRED_TO_223"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _check(output: Path) -> None:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != SCHEMA:
        raise EvidenceError("M6 visual manifest schema drifted")
    if manifest.get("status") != "ACCEPTED_MAIN_VISUAL_AND_RUNTIME":
        raise EvidenceError(f"M6 evidence is not accepted: {manifest.get('status')}")
    if manifest.get("baseSha") != fixture["baseSha"]:
        raise EvidenceError("M6 visual manifest base SHA drifted")
    ownership = manifest.get("ownership", {})
    expected_ownership = {
        "handoffSelectorRows": fixture["handoff"]["rows"],
        "handoffGroups": fixture["handoff"]["groups"],
        "removedSelectorRows": fixture["remove"]["rows"],
        "touchedGroups": fixture["remove"]["touchedGroups"],
        "fullyRemovedGroups": fixture["remove"]["fullyRemovedGroups"],
        "partiallyShrunkGroups": fixture["remove"]["partiallyShrunkGroups"],
        "holdRows": fixture["hold"]["rows"],
        "holdGroups": fixture["hold"]["groups"],
        "remainingSelectorRows": fixture["expectedAfter"]["selectorRows"],
        "remainingGroups": fixture["expectedAfter"]["cssRuleGroups"],
        "tupleSha256": fixture["handoff"]["tupleSha256"],
    }
    if ownership != expected_ownership:
        raise EvidenceError("M6 visual manifest ownership summary drifted")
    for phase in PHASES:
        audit = json.loads((output / f"selector-runtime-{phase}.json").read_text(encoding="utf-8"))
        audit_viewports = audit["coverage"]["viewports"]
        required_viewports = [f"{width}x{height}" for width, height in VIEWPORTS]
        if not audit_viewports or any(
            viewport not in required_viewports for viewport in audit_viewports
        ):
            raise EvidenceError(f"M6 {phase} selector audit viewport set drifted")
        if audit["coverage"]["snapshots"] != len(TOPOLOGIES) * len(audit_viewports):
            raise EvidenceError(f"M6 {phase} selector audit coverage drifted")
        if audit["summary"]["selectorsWithQueryErrors"]:
            raise EvidenceError(f"M6 {phase} selector audit has query errors")
    print(
        "M6 evidence PASS: "
        f"status={manifest['status']}; topologies={len(TOPOLOGIES)}; "
        f"pairs={manifest['comparison']['artifactPairs']}; "
        f"pixel-identical={manifest['comparison']['pixelIdenticalPairs']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument(
        "--selector-only",
        action="store_true",
        help=(
            "Audit all settled route/state topologies at 1440x900 without replacing visual "
            "evidence."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--accept", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actions = sum((args.phase is not None, args.compare, args.accept, args.check))
    if actions != 1:
        parser.error("choose exactly one of --phase, --compare, --accept, or --check")
    output = args.output.resolve()
    if args.phase:
        if args.source_root is None or not args.project:
            parser.error("capture requires --source-root and --project")
        _capture_phase(
            args.source_root,
            args.project,
            args.phase,
            output,
            selector_only=args.selector_only,
        )
    elif args.selector_only:
        parser.error("--selector-only requires --phase")
    elif args.compare:
        _write_manifest(output, accepted=False)
    elif args.accept:
        _write_manifest(output, accepted=True)
    else:
        _check(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

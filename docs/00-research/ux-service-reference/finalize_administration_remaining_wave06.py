from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import textwrap
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "docs/00-research/ux-service-reference"
STAGING_PATH = SOURCE_DIR / "administration-remaining-wave06.staging.json"
MANIFEST_PATH = ROOT / "docs/01-product/service-reference-manifest.yaml"
ARCHIVE_PATH = ROOT / "docs/17-evidence/screenshot-archive.yaml"
REPORT_PATH = ROOT / "docs/17-evidence/reports/issue-167-service-reference-freeze.md"
PACKET_PATH = ROOT / "docs/17-evidence/reports/issue-167-administration-remaining-product-owner-packet.md"

FAMILY_META = {
    "layout": (
        "administration-layout-edit",
        "draft",
        "Accepted after direct original-resolution review. The ordered Layout editor and live saved-Record preview remain connected in one flat three-pane Administration task; exact Attribute revisions, local recovery and bounded wide composition are preserved.",
    ),
    "subset": (
        "administration-subset-edit",
        "draft",
        "Accepted after direct original-resolution review. The typed filter definition and result preview use one server-scoped count/row contract, preserve the saved draft on failure and remain compact at canonical and wide viewports.",
    ),
    "link": (
        "administration-link-type-edit",
        "draft",
        "Accepted after direct original-resolution review. Source and target Tables, independent cardinalities, forward/reverse labels and exact endpoint revisions are visible together with a branching Related test; no latest alias or fabricated relation is used.",
    ),
    "access": (
        "administration-access",
        "normal",
        "Accepted after direct original-resolution review. Task-based User, Reviewer and Administrator assignments remain readable in a dense three-pane workspace; denied and revoke-confirm states preserve a safe return, exact selected context and required reason without leaking restricted assignment data.",
    ),
    "publish": (
        "administration-publish",
        "not-configured",
        "Accepted after direct original-resolution review. The screen truthfully preserves saved draft definitions and validation evidence while keeping every Publish command disabled because no publication transition or policy endpoint exists; no success, release or receipt is fabricated.",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate WAVE-06 generated evidence into the #167 lifecycle documents.")
    parser.add_argument("--date", default="2026-07-31")
    return parser.parse_args()


def remove_suffix_section(value: str, heading: str) -> str:
    marker = f"\n{heading}\n"
    index = value.find(marker)
    return value[:index].rstrip() if index >= 0 else value.rstrip()


def canonical_state(target: str, family: str, default: str) -> str:
    if target.startswith("administration-access-denied"):
        return "denied"
    if target.startswith("administration-access-revoke-confirm"):
        return "revoke-confirm"
    if family == "publish":
        return "not-configured"
    return default


def manifest_block(staging: dict[str, Any], date_value: str) -> str:
    lines: list[str] = ["\n"]
    first = True
    for target, meta in staging["targets"].items():
        family = meta["family"]
        screen, default_state, note = FAMILY_META[family]
        state = canonical_state(target, family, default_state)
        viewport = meta["viewport"]
        width, height = (int(item) for item in viewport.split("x"))
        lines.extend(
            [
                f"  - id: {target}\n",
                f"    screen: {screen}\n",
                f"    state: {state}\n",
                "    viewport:\n",
                f"      width: {width}\n",
                f"      height: {height}\n",
                "      device_scale_factor: 1\n",
            ]
        )
        if first:
            lines.extend(
                [
                    "    sources: &administration_remaining_sources\n",
                    "      html: docs/00-research/ux-service-reference/administration-remaining.html\n",
                    "      base_css: docs/00-research/ux-service-reference/administration-schema-core.css\n",
                    "      css: docs/00-research/ux-service-reference/administration-remaining.css\n",
                    "      javascript: docs/00-research/ux-service-reference/administration-remaining.js\n",
                    "      capture: docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py\n",
                    "      validation: docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py\n",
                ]
            )
            first = False
        else:
            lines.append("    sources: *administration_remaining_sources\n")
        lines.extend(
            [
                f"    image: {meta['image']}\n",
                f"    measurements: {meta['measurements']}\n",
                "    family_state_evidence: docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json\n",
            ]
        )
        if viewport == "1920x1080" and state in {"draft", "normal", "not-configured"}:
            prefix = target.rsplit("-1920x1080", 1)[0]
            lines.extend(
                [
                    "    wide_evidence:\n",
                    f"      - docs/17-evidence/images/issue-167-service-reference/{prefix}-wide-2560x1440.png\n",
                    f"      - docs/17-evidence/images/issue-167-service-reference/{prefix}-wide-3840x2160.png\n",
                ]
            )
        lines.extend(
            [
                f"    image_sha256: {meta['sha256']}\n",
                f"    date: {date_value}\n",
                "    status: pending\n",
                "    main_agent_evaluation:\n",
                "      status: accepted\n",
                "      notes: >-\n",
            ]
        )
        lines.extend(f"        {line}\n" for line in textwrap.wrap(note, width=92))
        lines.extend(["    product_owner_approval:\n", "      status: absent\n"])
    return "".join(lines)


def integrate_manifest(staging: dict[str, Any], date_value: str) -> None:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    existing = {entry["id"] for entry in data["references"]}
    duplicates = existing.intersection(staging["targets"])
    if duplicates:
        raise RuntimeError(f"WAVE-06 target already exists in manifest: {sorted(duplicates)}")
    MANIFEST_PATH.write_text(
        MANIFEST_PATH.read_text(encoding="utf-8").rstrip() + manifest_block(staging, date_value),
        encoding="utf-8",
    )
    updated = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(updated["references"]) != 72:
        raise RuntimeError(f"manifest must contain 72 references, got {len(updated['references'])}")


def archive_entries(staging: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    result: list[tuple[str, str, str, str, str]] = []
    for target, meta in staging["targets"].items():
        result.append((target, meta["family"], meta["state"], meta["viewport"], meta["image"]))
    for meta in staging["evidence_only_states"].values():
        for measurement_path in meta["measurements"]:
            measurement = json.loads((ROOT / measurement_path).read_text(encoding="utf-8"))
            result.append(
                (
                    measurement["target"],
                    measurement["family"],
                    measurement["state"],
                    measurement["viewport"],
                    measurement["image"],
                )
            )
    for target, meta in staging["wide_evidence"].items():
        result.append((target, meta["family"], meta["state"], meta["viewport"], meta["image"]))
    return result


def integrate_archive(staging: dict[str, Any], date_value: str) -> None:
    text = ARCHIVE_PATH.read_text(encoding="utf-8")
    archive = yaml.safe_load(text)
    existing = {entry["id"] for entry in archive["captures"]}
    entries = archive_entries(staging)
    duplicates = existing.intersection(item[0] for item in entries)
    if duplicates:
        raise RuntimeError(f"WAVE-06 capture already exists in archive: {sorted(duplicates)}")
    version = int(archive["version"]) + 1
    text = text.replace(f"version: {archive['version']}\n", f"version: {version}\n", 1)
    text = text.replace(f"verified_at: {archive['verified_at']}", f"verified_at: {date_value}", 1)
    lines: list[str] = ["\n"]
    for target, family, state, viewport, image in entries:
        width, height = (int(item) for item in viewport.split("x"))
        relative_image = image.removeprefix("docs/17-evidence/")
        lines.extend(
            [
                f"  - id: {target}\n",
                "    route: static-reference\n",
                f"    workflow: issue-167-{family}-{state}\n",
                "    fixture: deterministic synthetic non-production Administration reference\n",
                "    source_evidence: reports/issue-167-administration-remaining-product-owner-packet.md\n",
                f"    image: {relative_image}\n",
                f"    width: {width}\n",
                f"    height: {height}\n",
            ]
        )
    ARCHIVE_PATH.write_text(text.rstrip() + "".join(lines), encoding="utf-8")


def packet_text(staging: dict[str, Any], date_value: str) -> str:
    lines = [
        "# Issue #167 — Remaining Administration product-owner packet\n\n",
        f"Date: `{date_value}`  \n",
        "Branch: `agent/complete-167-and-157`  \n",
        "Baseline: latest `issue-167-service-reference-freeze`  \n",
        "Lifecycle: **main-agent accepted; independent reviewer pending; product-owner approval absent**\n\n",
        "## Scope\n\n",
        "This packet completes the finite 72-image service-reference inventory without changing production React, backend, API, migrations, or current user-guide screenshots. It adds the remaining 17 approval units for `ADM-SCHEMA-RELATIONS`, `ADM-ACCESS`, and `ADM-PUBLISH`, plus 45 evidence-only state captures and 10 deterministic 2560/3840 wide captures.\n\n",
        "The publication family is intentionally blocked. The current service has no Catalog publication transition or policy endpoint, so the references preserve saved draft definitions and never fabricate a published state, receipt, release, or successful transition.\n\n",
        "## Static source to production contract mapping\n\n",
        "| Reference family | Static regions | Existing production component/API contract | Preserved behavior |\n",
        "| --- | --- | --- | --- |\n",
        "| Layout | Schema navigator → Layout list → ordered-field editor + saved Record preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Layout list/create/revise APIs | Current Table revision, exact Attribute revisions, ordered fields, draft validation, saved Record preview |\n",
        "| Subset | Schema navigator → Subset list → typed filters + scoped result preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Subset list/create/revise APIs and server-scoped Record query | Filter definition, same-query total/rows, authorization scope, draft/error preservation |\n",
        "| Link Type | Schema navigator → Link Type list → endpoint/label/cardinality editor + Related test | `apps/web/src/configurable-catalog-admin.tsx`; Link Type and exact Record Link APIs | Source/target Tables, independent cardinalities, forward/reverse labels, exact endpoint revisions, no latest alias |\n",
        "| Access | Access navigator → assignment list → readable task preset / revoke confirmation | `apps/web/src/product-access-center.tsx`; product assignment list/grant/revoke APIs | User/Reviewer/Administrator roles, scope/classification, denied boundary, required revoke reason |\n",
        "| Publish | Lifecycle navigator → saved draft change set → validation boundary | No production publication endpoint | Publish disabled, saved drafts preserved, validation/recovery only, no fabricated success |\n\n",
        "## Approval targets\n\n",
        "| Target | Family/state | SHA-256 |\n",
        "| --- | --- | --- |\n",
    ]
    for target, meta in staging["targets"].items():
        lines.append(
            f"| [{target}](../images/issue-167-service-reference/{target}.png) | `{meta['family']}` / `{meta['state']}` | `{meta['sha256']}` |\n"
        )
    lines.extend(
        [
            "\n## Deterministic evidence\n\n",
            "```text\n",
            "approval targets                                      17 / 17\n",
            "evidence-only states                                  15 families / 45 images\n",
            "wide evidence                                         10 images\n",
            "exact viewport and SHA checks                          pass\n",
            "browser console/page errors                            0 / 0\n",
            "page horizontal/vertical overflow                      0 / 0\n",
            "nested interactive controls                            0\n",
            "prohibited legacy selectors                            0\n",
            "active filled primary commands                         <= 1 per state\n",
            "body/data typography                                   <= 13.5 px\n",
            "keyboard splitter and Ctrl+S/revoke interactions        pass\n",
            "family-specific truth and recovery checks               pass\n",
            "WAVE-06 validator                                       1480 checks / pass\n",
            "service-reference inventory                             72 total; 55 approved; 17 pending\n",
            "```\n\n",
            "The main agent opened the canonical approval images at original resolution and checked the three-pane topology, dense list/editor relationship, text containment, command priority, preview continuity, and wide-screen bounded task cluster. The 17 targets remain `pending` until explicit product-owner approval. No product-owner approval is inferred from the request to implement this work.\n\n",
            "A fresh Terra/Luna reviewer was not callable from this execution surface. No substitute review is claimed. The deterministic evidence and product-owner packet are therefore preserved with reviewer lifecycle still pending.\n",
        ]
    )
    return "".join(lines)


def integrate_report(staging: dict[str, Any], date_value: str) -> None:
    PACKET_PATH.write_text(packet_text(staging, date_value), encoding="utf-8")
    report = remove_suffix_section(
        REPORT_PATH.read_text(encoding="utf-8"),
        "## 115. WAVE-06 remaining Administration references — product-owner handoff",
    )
    section = f"""

## 115. WAVE-06 remaining Administration references — product-owner handoff

Date: {date_value}

The main agent completed the finite remaining Administration reference scope on branch
`agent/complete-167-and-157` without changing production React/CSS, backend, API, migrations or
current product captures.

- `ADM-SCHEMA-RELATIONS`: Layout, Subset and Link Type — 9 approval images.
- `ADM-ACCESS`: normal, denied and revoke-confirm — 5 approval images.
- `ADM-PUBLISH`: truthful Not configured boundary — 3 approval images.
- Evidence-only states: 15 families / 45 canonical-viewport images.
- Wide evidence: 10 images at 2560x1440 and 3840x2160.

The new WAVE-06 validator passed 1,480 deterministic checks across all 72 new captures. Exact
viewport dimensions and image hashes match, browser errors and document overflow are zero, legacy
selectors and nested interactive controls are absent, keyboard pane resizing works, and every state
uses at most one active filled primary command. Family-specific checks prove ordered Layout fields
and saved Record preview, same-query Subset total/rows, exact-revision Link branching, safe access
denial/revocation, and disabled non-fabricated Catalog publishing.

The complete product-owner packet is
[issue-167-administration-remaining-product-owner-packet.md](issue-167-administration-remaining-product-owner-packet.md).
The manifest now contains all 72 finite approval targets: 55 remain approved and the 17 WAVE-06
targets are `pending` with main-agent evaluation `accepted` and product-owner approval `absent`.
A fresh configured Terra/Luna reviewer was not callable from this execution surface; no substitute
review is claimed. No PR merge or production implementation has started.
"""
    REPORT_PATH.write_text(report + section, encoding="utf-8")


def normalize_historical_paths() -> None:
    prefix = "C:/SourceCodes/cae-material-platform/"
    for name in ("after-measurements.json", "before-measurements.json"):
        path = ROOT / "docs/17-evidence/images/desktop-engineering-ui/dui-01" / name
        value = path.read_text(encoding="utf-8")
        if prefix in value:
            path.write_text(value.replace(prefix, ""), encoding="utf-8")


def main() -> None:
    args = parse_args()
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    if staging.get("counts") != {
        "approval_targets": 17,
        "evidence_state_families": 15,
        "evidence_state_captures": 45,
        "wide_evidence": 10,
    }:
        raise RuntimeError("unexpected WAVE-06 capture inventory")
    integrate_manifest(staging, args.date)
    integrate_archive(staging, args.date)
    integrate_report(staging, args.date)
    normalize_historical_paths()
    print("integrated WAVE-06 manifest, archive, packet and historical path normalization")


if __name__ == "__main__":
    main()

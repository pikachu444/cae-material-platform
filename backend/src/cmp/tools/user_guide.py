"""Verify current documentation, navigation contracts, and screenshot evidence."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import re
import struct
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)#]+)(?:#[^)]+)?\)")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_NON_CURRENT_IMAGE = re.compile(r"docs/17-evidence/images/")
_CURRENT_IMAGE_PREFIX = "docs/user-guide/images/current/"
_EVIDENCE_IMAGE_PREFIX = "docs/17-evidence/images/"
_REPOSITORY_LITERAL = re.compile(
    r"`((?:apps|backend|contracts|deploy|docs|fixtures|plugins|scripts|tests)/"
    r"[^`\s]+\.(?:css|json|md|mjs|png|jpg|jpeg|py|tsx|yaml|yml))`",
    re.IGNORECASE,
)
_STRUCTURED_IMAGE_MANIFESTS: tuple[str, ...] = (
    "docs/17-evidence/images/issue-221-high-dpi-decision/measurements.json",
    "docs/17-evidence/images/issue-184-high-dpi-global-implementation/visual-evidence.json",
    "docs/17-evidence/images/issue-260-fe05-modeling-data/manifest.json",
    "docs/17-evidence/images/issue-261-fe06-m2-materials-css-ownership/manifest.json",
    "docs/17-evidence/images/issue-261-fe06-m3-governance-css-ownership/manifest.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-manifest.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-01.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-02.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-03.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-04.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-05.json",
    "docs/17-evidence/issue-261-b4-css-ownership-integration-duplicates-06.json",
    "docs/17-evidence/issue-261-m1e-modeling-ownership-integration-duplicates-01.json",
    "docs/17-evidence/issue-261-m1e2-modeling-core-shell-manifest.json",
    "docs/17-evidence/images/issue-261-m1e3-modeling-family-ownership/duplicate-image-groups.json",
    "docs/17-evidence/images/issue-261-m1e3-documentation-impact/manifest.json",
    "docs/17-evidence/images/issue-261-m1e4-modeling-core-stage-ownership/manifest.json",
)
_STRUCTURED_IMAGE_MANIFEST_GLOBS: tuple[str, ...] = ()
_STRUCTURED_IMAGE_YAML_MANIFESTS: tuple[str, ...] = (
    "docs/17-evidence/images/issue-161-shared-ui-foundation/visual-evidence.yaml",
    "docs/17-evidence/images/issue-206-curve-channel-metadata-and-deviation/visual-evidence.yaml",
    "docs/17-evidence/images/issue-208-schema-bundle-administration/visual-evidence.yaml",
    "docs/17-evidence/images/issue-209-dma-fld-governed-import/visual-evidence.yaml",
    "docs/17-evidence/images/issue-210-scalar-distribution-fitting/visual-evidence.yaml",
    "docs/17-evidence/images/issue-212-explicit-toe-compensation/visual-evidence.yaml",
    "docs/17-evidence/images/issue-246-source-v2-categories/visual-evidence.yaml",
)
_IMAGE_PATH_MANIFESTS: tuple[str, ...] = ()
_CURRENT_PRODUCT_EVIDENCE_MANIFEST = (
    "docs/17-evidence/images/issue-289-administration-database-workflow/visual-evidence.yaml"
)
_CURRENT_PRODUCT_EVIDENCE_KEY = "after_editor"
_CURRENT_PRODUCT_REFERENCE_TARGETS: dict[str, tuple[str, str, int, int, str]] = {
    "administration-database-normal-1920x1080": (
        "administration-database",
        "normal",
        1920,
        1080,
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-1920x1080.png",
    ),
    "administration-database-normal-2560x1440": (
        "administration-database",
        "normal",
        2560,
        1440,
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-2560x1440.png",
    ),
    "administration-database-normal-3840x2160": (
        "administration-database",
        "normal",
        3840,
        2160,
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-3840x2160.png",
    ),
}
_CURRENT_PRODUCT_REFERENCE_VIEWPORTS = (
    "1920x1080",
    "2560x1440",
    "3840x2160",
)
_STALE_CURRENT_PATTERNS = {
    "retired global navigation": re.compile(
        r"(?:전역|global)\s+\*\*(?:Dashboard|Models|Exports|Governance)\*\*", re.IGNORECASE
    ),
    "manual connection panel": re.compile(r"Connection\s+panel", re.IGNORECASE),
    "retired T-46 screenshot": re.compile(r"t46-[^)\s]+\.png", re.IGNORECASE),
}
_NUMBER_ONLY_ATX_HEADING = re.compile(
    r"^\s{0,3}#{1,6}[ \t]+(?:[A-Z][A-Z0-9]{0,7}-)?\d+(?:[.-]\d+)*[ \t]*#*[ \t]*$"
)
_NUMBER_ONLY_SETEXT_TITLE = re.compile(r"^\s{0,3}(?:[A-Z][A-Z0-9]{0,7}-)?\d+(?:[.-]\d+)*[ \t]*$")
_SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(?:=+|-+)[ \t]*$")
_DOCS_PORTAL_REQUIRED_MARKERS = (
    "## 저장소 지도",
    "### 루트에서 찾기",
    "### `docs/`에서 찾기",
    "| 제품 소개와 5분 실행 | [루트 README](../README.md) |",
    "| 저장소 작업 규칙 | [저장소 작업 지침](../AGENTS.md) |",
    "| 현재 구현 범위 | [현재 구현 상태](../IMPLEMENTATION_STATUS.md) |",
    "| 제품 사용과 운영 절차 | [사용자 가이드](user-guide/index.md) · "
    "[관리자 가이드](admin-guide/index.md) |",
    "| 작업 순서와 검증 | [현재 전달 backlog](13-delivery/backlog.md) · "
    "[테스트 전략](14-testing/test-strategy.md) |",
    "## 읽기 경로 세 가지",
    "### 제품을 사용하거나 현재 동작을 확인할 때",
    "### 일반 이슈를 구현할 때",
    "### contract나 fixture를 확인할 때",
    "## 권위가 충돌할 때",
    "[contract 안내](../contracts/README.md)",
    "[fixture 안내](../fixtures/README.md)",
)
_CLOSED_ISSUE_157_CURRENT_MARKER = "issues/157)에서 완료"
_STALE_ISSUE_157_GUIDANCE = re.compile(
    r"(?:"
    r"(?:#157|issues/157).{0,240}"
    r"(?:남아|미해결|열려|open\b|해결되지|완료되지|진행 중|수정 중|복구 중|"
    r"재현(?:·|/)?수정|실패(?:가|는|를|에서))"
    r"|"
    r"(?:남아|미해결|열려|open\b|해결되지|완료되지|진행 중|수정 중|복구 중|"
    r"재현(?:·|/)?수정|실패(?:가|는|를|에서)).{0,240}(?:#157|issues/157)"
    r")",
    re.DOTALL | re.IGNORECASE,
)
_FIXED_QUICK_TUNNEL_URL = re.compile(
    r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com",
    re.IGNORECASE,
)
_README_HEADINGS = (
    "## 이 플랫폼에서 하는 일",
    "## 역할별로 할 수 있는 일",
    "## 핵심 사용 흐름",
    "## 지금 가능한 일과 다음 화면",
    "## 5분 로컬 실행",
    "## 개발과 검증",
    "## 문서",
)
_PERMANENT_REFERENCE_SOURCE_IDS = frozenset(
    {
        "granta-mi-product",
        "granta-viewer-profile",
        "granta-advanced-search",
        "granta-datasheet",
        "granta-material-models",
        "granta-selector-product",
        "granta-gateway-filters",
        "granta-one-mi-custom-search",
        "granta-tabular-data",
        "granta-model-parameters",
        "granta-simulation-records",
        "granta-read-edit",
        "granta-selector-stages",
        "smdc-quick-search",
        "smdc-cae-download",
        "smdc-filters",
        "smdc-compare",
        "smdc-review",
        "smdc-version-control",
        "material-modeler-import",
        "material-modeler-prepare",
        "material-modeler-curve-fitting",
        "material-modeler-hyperelastic-edit",
        "simcenter-material-modeler-2026",
    }
)


class UserGuideContractError(RuntimeError):
    """Raised when current documentation or screenshot evidence is incomplete."""


@dataclass(frozen=True, slots=True)
class UserGuideReport:
    document_count: int
    capture_count: int
    navigation_count: int
    classified_markdown_count: int
    current_document_count: int
    local_link_count: int
    image_count: int
    orphan_image_count: int
    duplicate_image_group_count: int


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UserGuideContractError(f"{name} must be a mapping")
    return cast(dict[str, Any], value)


def _sequence(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise UserGuideContractError(f"{name} must be a list")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UserGuideContractError(f"{name} must be non-blank text")
    return value.strip()


def _inside(path: Path, parent: Path, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as error:
        raise UserGuideContractError(f"{name} escapes {parent}") from error
    return resolved


def _relative(path: Path, project: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def _glob_matches(path: str, pattern: str) -> bool:
    candidate = pattern
    while True:
        if fnmatch.fnmatchcase(path, candidate):
            return True
        if "/**/" not in candidate:
            return False
        candidate = candidate.replace("/**/", "/", 1)


def _tracked_markdown(project: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        path
        for line in result.stdout.splitlines()
        if line and (project / (path := line.strip().replace("\\", "/"))).is_file()
    )


def _documentation_classes(project: Path) -> dict[str, str]:
    manifest_path = project / "docs" / "documentation-manifest.yaml"
    manifest = _mapping(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        "documentation manifest",
    )
    rules = _sequence(manifest.get("rules"), "documentation manifest rules")
    classified: dict[str, str] = {}
    for path in _tracked_markdown(project):
        matches: list[str] = []
        for ordinal, raw_rule in enumerate(rules, start=1):
            rule = _mapping(raw_rule, f"documentation rule {ordinal}")
            status = _text(rule.get("status"), f"documentation rule {ordinal} status")
            if status not in {"current", "authoritative", "reference"}:
                raise UserGuideContractError(f"unsupported documentation status: {status}")
            patterns = _sequence(rule.get("include"), f"documentation rule {ordinal} include")
            exclude_patterns = _sequence(
                rule.get("exclude", []),
                f"documentation rule {ordinal} exclude",
            )
            included = any(
                _glob_matches(path, _text(pattern, "documentation include")) for pattern in patterns
            )
            excluded = any(
                _glob_matches(path, _text(pattern, "documentation exclude"))
                for pattern in exclude_patterns
            )
            if included and not excluded:
                matches.append(status)
        if len(matches) != 1:
            raise UserGuideContractError(
                f"tracked Markdown must match exactly one documentation rule: {path} ({matches})"
            )
        classified[path] = matches[0]
    return classified


def _image_dimensions(path: Path) -> tuple[int, int]:
    value = path.read_bytes()
    if len(value) >= 24 and value[:8] == _PNG_SIGNATURE and value[12:16] == b"IHDR":
        return cast(tuple[int, int], struct.unpack(">II", value[16:24]))
    if len(value) >= 4 and value[:3] == _JPEG_SIGNATURE:
        offset = 2
        start_of_frame = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while offset + 8 < len(value):
            if value[offset] != 0xFF:
                offset += 1
                continue
            marker = value[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(value):
                break
            segment_length = int.from_bytes(value[offset : offset + 2], "big")
            if marker in start_of_frame and offset + 7 <= len(value):
                height = int.from_bytes(value[offset + 3 : offset + 5], "big")
                width = int.from_bytes(value[offset + 5 : offset + 7], "big")
                return width, height
            if segment_length < 2:
                break
            offset += segment_length
    raise UserGuideContractError(f"screenshot has an unsupported image format: {path}")


def _verify_document_links(
    project: Path, classes: dict[str, str]
) -> tuple[set[str], set[str], int]:
    current_images: set[str] = set()
    referenced_images: set[str] = set()
    local_link_count = 0
    for relative_document, status in classes.items():
        document = project / relative_document
        content = document.read_text(encoding="utf-8")
        if status in {"current", "authoritative"}:
            fenced_marker: tuple[str, int] | None = None
            previous_line: tuple[int, str] | None = None
            for line_number, line in enumerate(content.splitlines(), start=1):
                fence = re.match(r"^\s*(`{3,}|~{3,})", line)
                if fence:
                    marker = fence.group(1)
                    if fenced_marker is None:
                        fenced_marker = (marker[0], len(marker))
                    elif marker[0] == fenced_marker[0] and len(marker) >= fenced_marker[1]:
                        fenced_marker = None
                    previous_line = None
                    continue
                if fenced_marker is not None:
                    previous_line = None
                    continue
                number_only_heading: tuple[int, str] | None = None
                if _NUMBER_ONLY_ATX_HEADING.fullmatch(line):
                    number_only_heading = (line_number, line)
                elif (
                    previous_line is not None
                    and _SETEXT_UNDERLINE.fullmatch(line)
                    and _NUMBER_ONLY_SETEXT_TITLE.fullmatch(previous_line[1])
                ):
                    number_only_heading = previous_line
                if number_only_heading is not None:
                    heading_line, heading = number_only_heading
                    raise UserGuideContractError(
                        f"{relative_document} contains a number-only Markdown heading "
                        f"on line {heading_line}: {heading.strip()}"
                    )
                previous_line = (line_number, line) if line.strip() else None
        if status == "current":
            for label, pattern in _STALE_CURRENT_PATTERNS.items():
                if pattern.search(content):
                    raise UserGuideContractError(f"{relative_document} contains {label}")
        for match in _MARKDOWN_LINK.finditer(content):
            target = match.group(1).strip().strip("<>")
            if re.match(r"^(?:https?://|mailto:)", target):
                continue
            local_link_count += 1
            linked = _inside(document.parent / target, project, f"link in {relative_document}")
            if not linked.exists():
                raise UserGuideContractError(
                    f"missing link target in {relative_document}: {target}"
                )
            if linked.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                relative_image = _relative(linked, project)
                referenced_images.add(relative_image)
                if status == "current":
                    if _NON_CURRENT_IMAGE.search(relative_image):
                        raise UserGuideContractError(
                            "current document uses a non-current reference image: "
                            f"{relative_document} -> {relative_image}"
                        )
                    current_images.add(relative_image)
        if status in {"current", "authoritative"}:
            for literal in _REPOSITORY_LITERAL.findall(content):
                if any(marker in literal for marker in ("*", "{", "}")):
                    continue
                candidates = (
                    _inside(project / literal, project, f"path in {relative_document}"),
                    _inside(document.parent / literal, project, f"path in {relative_document}"),
                )
                if not any(candidate.exists() for candidate in candidates):
                    raise UserGuideContractError(
                        f"missing repository path in {relative_document}: {literal}"
                    )
    return current_images, referenced_images, local_link_count


def _verify_repository_guidance(project: Path) -> None:
    portal = (project / "docs" / "README.md").read_text(encoding="utf-8")
    missing_markers = [marker for marker in _DOCS_PORTAL_REQUIRED_MARKERS if marker not in portal]
    if missing_markers:
        raise UserGuideContractError(
            f"docs/README.md is missing repository map guidance: {missing_markers}"
        )

    readme = (project / "README.md").read_text(encoding="utf-8")
    if _CLOSED_ISSUE_157_CURRENT_MARKER not in readme:
        raise UserGuideContractError("README.md is missing the closed #157 current guidance")
    if _STALE_ISSUE_157_GUIDANCE.search(readme):
        raise UserGuideContractError("README.md contains stale open-issue guidance for closed #157")
    fixed_tunnel = _FIXED_QUICK_TUNNEL_URL.search(readme)
    if fixed_tunnel:
        raise UserGuideContractError(
            f"README.md must not pin a temporary Quick Tunnel URL: {fixed_tunnel.group(0)}"
        )


def _verify_readme(project: Path, registered_images: set[str]) -> None:
    readme = (project / "README.md").read_text(encoding="utf-8")
    for heading in _README_HEADINGS:
        if heading not in readme:
            raise UserGuideContractError(f"README.md is missing required section: {heading}")
    for role in ("일반 사용자", "Reviewer", "Administrator"):
        if role not in readme:
            raise UserGuideContractError(f"README.md is missing the role/task entry: {role}")
    for workflow in (
        "재료 검색 → 결과 비교 → 재료 상세 → 솔버 카드 → 미리보기/다운로드",
        "모델링 Data → Process → Fit → Export → 재료 라이브러리 저장",
    ):
        if workflow not in readme:
            raise UserGuideContractError(f"README.md is missing the core workflow: {workflow}")
    if "현재 화면" not in readme or "승인된 구현 목표" not in readme:
        raise UserGuideContractError(
            "README.md must distinguish current screens from approved implementation targets"
        )
    if "docker compose -f deploy/compose/docker-compose.demo.yml up --build -d" not in readme:
        raise UserGuideContractError("README.md is missing the runnable Compose quickstart")
    readme_images = {
        _relative(_inside(project / match.group(1), project, "README image"), project)
        for match in _MARKDOWN_IMAGE.finditer(readme)
    }
    if len(readme_images & registered_images) < 2:
        raise UserGuideContractError("README.md must show at least two current registered screens")


def _verify_permanent_reference_catalog(project: Path) -> set[str]:
    catalog_path = project / "docs/00-research/product-reference-source-catalog.json"
    catalog = _mapping(
        json.loads(catalog_path.read_text(encoding="utf-8")), "reference source catalog"
    )
    sources = _sequence(catalog.get("sources"), "reference source catalog sources")
    source_ids: set[str] = set()
    for ordinal, raw_source in enumerate(sources, start=1):
        source = _mapping(raw_source, f"reference source {ordinal}")
        source_id = _text(source.get("id"), f"reference source {ordinal} id")
        if source_id in source_ids:
            raise UserGuideContractError(f"duplicate permanent reference source id: {source_id}")
        source_ids.add(source_id)
        for field in ("product", "version", "title", "publisher", "url", "evidence_type"):
            _text(source.get(field), f"reference source {source_id} {field}")
        if not _text(source.get("url"), f"reference source {source_id} url").startswith("https://"):
            raise UserGuideContractError(f"reference source URL must use https: {source_id}")
        _sequence(source.get("supports"), f"reference source {source_id} supports")
        _sequence(source.get("limitations"), f"reference source {source_id} limitations")
    if not _PERMANENT_REFERENCE_SOURCE_IDS <= source_ids:
        missing = sorted(_PERMANENT_REFERENCE_SOURCE_IDS - source_ids)
        raise UserGuideContractError(f"permanent reference source IDs drifted; missing={missing}")
    registered_images: set[str] = set()
    for relative_root, minimum_images in (
        ("docs/00-research/ux-reference-gallery/images", 5),
        ("docs/00-research/images/gui-reference", 20),
    ):
        image_root = project / relative_root
        if not image_root.is_dir():
            raise UserGuideContractError(
                f"permanent reference image root is missing: {relative_root}"
            )
        images = [
            path
            for path in image_root.iterdir()
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
        if len(images) < minimum_images:
            raise UserGuideContractError(
                f"permanent reference image root is incomplete: {relative_root}"
            )
        registered_images.update(_relative(image, project) for image in images)
    return registered_images


def _capture_script_outputs(script: Path) -> set[str]:
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "CURRENT_CAPTURE_OUTPUTS"
            for target in targets
        ):
            continue
        if node.value is None:
            break
        value = ast.literal_eval(node.value)
        if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
            break
        return cast(set[str], set(value))
    raise UserGuideContractError(
        "capture script must declare CURRENT_CAPTURE_OUTPUTS: "
        f"{_relative(script, script.parents[1])}"
    )


def _structured_manifest_images(project: Path) -> set[str]:
    images: set[str] = set()

    def resolve_image_ref(value: str, manifest: Path) -> str | None:
        normalized = value.replace("\\", "/")
        if Path(normalized).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            return None
        if any(character.isspace() for character in value):
            raise UserGuideContractError(
                f"image manifest path contains whitespace: {manifest} -> {value}"
            )
        candidate = Path(normalized)
        image = _inside(
            candidate if candidate.is_absolute() else project / candidate,
            project,
            f"image manifest {manifest}",
        )
        if not image.is_file():
            raise UserGuideContractError(
                f"image manifest target is missing: {manifest} -> {normalized}"
            )
        return _relative(image, project)

    def visit(value: object, manifest: Path) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"image", "file", "path"}:
                    if not isinstance(item, str):
                        raise UserGuideContractError(
                            f"image manifest reference must be text: {manifest} -> {key}"
                        )
                    if relative := resolve_image_ref(item, manifest):
                        images.add(relative)
                else:
                    visit(item, manifest)
        elif isinstance(value, list):
            for item in value:
                visit(item, manifest)

    for relative in _STRUCTURED_IMAGE_MANIFESTS:
        manifest = project / relative
        visit(json.loads(manifest.read_text(encoding="utf-8")), manifest)
    for pattern in _STRUCTURED_IMAGE_MANIFEST_GLOBS:
        for manifest in sorted(project.glob(pattern)):
            visit(json.loads(manifest.read_text(encoding="utf-8")), manifest)
    for relative in _STRUCTURED_IMAGE_YAML_MANIFESTS:
        manifest = project / relative
        visit(yaml.safe_load(manifest.read_text(encoding="utf-8")), manifest)
    for relative in _IMAGE_PATH_MANIFESTS:
        manifest = project / relative
        content = _mapping(
            yaml.safe_load(manifest.read_text(encoding="utf-8")),
            f"image path manifest {relative}",
        )
        for raw_image in _sequence(content.get("images"), f"image path manifest {relative}"):
            image_ref = _text(raw_image, f"image path manifest {relative} entry")
            image = _inside(project / image_ref, project, f"image path manifest {relative}")
            if not image.is_file():
                raise UserGuideContractError(
                    f"image path manifest target is missing: {relative} -> {image_ref}"
                )
            images.add(_relative(image, project))
    return images


def _verify_current_product_reference_evidence(
    project: Path,
    reference_id: str,
    reference: dict[str, Any],
    image: Path,
    viewport: dict[str, Any],
    expected_hash: str,
    evidence_root: Path,
) -> None:
    if "sources" in reference:
        raise UserGuideContractError(
            f"current product reference must not claim static sources: {reference_id}"
        )
    if "measurements" in reference:
        raise UserGuideContractError(
            f"current product reference must use visual evidence, not measurements: {reference_id}"
        )

    evidence_ref = _text(
        reference.get("evidence_manifest"),
        f"service reference {reference_id} evidence manifest",
    )
    evidence = _inside(
        project / evidence_ref,
        evidence_root,
        f"service reference {reference_id} evidence manifest",
    )
    if not evidence.is_file() or evidence.suffix.lower() not in {".yaml", ".yml"}:
        raise UserGuideContractError(
            f"current product reference evidence is missing or unsupported: {reference_id}"
        )
    evidence_manifest = _mapping(
        yaml.safe_load(evidence.read_text(encoding="utf-8")),
        f"service reference {reference_id} evidence manifest",
    )
    evidence_key = _text(
        reference.get("evidence_key"),
        f"service reference {reference_id} evidence key",
    )
    viewport_key = f"{viewport.get('width')}x{viewport.get('height')}"
    evidence_viewports = [
        _mapping(item, f"service reference {reference_id} evidence viewport")
        for item in _sequence(
            evidence_manifest.get("viewports"),
            f"service reference {reference_id} evidence viewports",
        )
    ]
    matching_viewports = [
        item for item in evidence_viewports if item.get("viewport") == viewport_key
    ]
    if len(matching_viewports) != 1:
        raise UserGuideContractError(
            f"current product reference evidence viewport is not unique: "
            f"{reference_id} {viewport_key}"
        )
    evidence_record = _mapping(
        matching_viewports[0].get(evidence_key),
        f"service reference {reference_id} evidence record",
    )
    evidence_image_ref = _text(
        evidence_record.get("path"),
        f"service reference {reference_id} evidence image",
    )
    evidence_image_path = Path(evidence_image_ref.replace("\\", "/"))
    if evidence_image_path.is_absolute():
        raise UserGuideContractError(
            f"current product reference evidence image must be portable: {reference_id}"
        )
    evidence_image = _inside(
        evidence.parent / evidence_image_path,
        evidence.parent,
        f"service reference {reference_id} evidence image",
    )
    if evidence_image != image:
        raise UserGuideContractError(
            f"current product reference image differs from visual evidence: {reference_id}"
        )
    if (evidence_record.get("width"), evidence_record.get("height")) != (
        viewport.get("width"),
        viewport.get("height"),
    ):
        raise UserGuideContractError(
            f"current product reference viewport differs from visual evidence: {reference_id}"
        )
    evidence_hash = _text(
        evidence_record.get("sha256"),
        f"service reference {reference_id} evidence hash",
    )
    if evidence_hash != expected_hash:
        raise UserGuideContractError(
            f"current product reference hash differs from visual evidence: {reference_id}"
        )


def _verify_service_reference_inventory(project: Path) -> None:
    inventory_path = project / "docs" / "01-product" / "service-reference-inventory.yaml"
    inventory = _mapping(
        yaml.safe_load(inventory_path.read_text(encoding="utf-8")),
        "service reference inventory",
    )
    if inventory.get("schema_version") != 3:
        raise UserGuideContractError("service reference inventory schema version drifted")
    policy = _mapping(inventory.get("policy"), "service reference inventory policy")
    if policy.get("default_lifecycle") != "static-bundle":
        raise UserGuideContractError("service reference inventory default lifecycle drifted")
    families = [
        _mapping(item, f"service reference inventory family {ordinal}")
        for ordinal, item in enumerate(
            _sequence(inventory.get("families"), "service reference inventory families"),
            start=1,
        )
    ]
    administration_database = [family for family in families if family.get("id") == "ADM-DB"]
    if len(administration_database) != 1:
        raise UserGuideContractError("service reference inventory must contain one ADM-DB family")
    family = administration_database[0]
    normal = _mapping(family.get("normal"), "service reference inventory ADM-DB normal")
    expected_fields = {
        "target_base": "administration-database-normal",
        "state": "normal",
        "lifecycle": "current-product-evidence",
        "images": 3,
    }
    if any(normal.get(key) != value for key, value in expected_fields.items()):
        raise UserGuideContractError(
            "service reference inventory ADM-DB lifecycle contract drifted"
        )
    approved_viewports = tuple(
        _text(item, "service reference inventory ADM-DB approved viewport")
        for item in _sequence(
            normal.get("approved_viewports"),
            "service reference inventory ADM-DB approved viewports",
        )
    )
    if approved_viewports != _CURRENT_PRODUCT_REFERENCE_VIEWPORTS:
        raise UserGuideContractError(
            "service reference inventory ADM-DB approved viewports drifted"
        )
    if family.get("image_count") != len(_CURRENT_PRODUCT_REFERENCE_TARGETS):
        raise UserGuideContractError("service reference inventory ADM-DB image count drifted")


def _verify_service_reference_manifest(project: Path) -> set[str]:
    _verify_service_reference_inventory(project)
    manifest_path = project / "docs" / "01-product" / "service-reference-manifest.yaml"
    manifest = _mapping(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        "service reference manifest",
    )
    if manifest.get("schema_version") != 3:
        raise UserGuideContractError("service reference manifest schema version drifted")
    if manifest.get("retention") != "approved-targets-only":
        raise UserGuideContractError("service reference retention policy drifted")
    if manifest.get("default_lifecycle") != "static-bundle":
        raise UserGuideContractError("service reference default lifecycle drifted")
    references = [
        _mapping(item, f"service reference {ordinal}")
        for ordinal, item in enumerate(
            _sequence(manifest.get("references"), "service references"), start=1
        )
    ]
    if len(references) != 72:
        raise UserGuideContractError("service reference manifest must contain 72 approved targets")

    reference_ids = [
        _text(reference.get("id"), f"service reference {ordinal} id")
        for ordinal, reference in enumerate(references, start=1)
    ]
    if len(set(reference_ids)) != len(reference_ids):
        duplicates = sorted(
            reference_id for reference_id, count in Counter(reference_ids).items() if count > 1
        )
        raise UserGuideContractError(f"duplicate service reference ids: {duplicates}")
    lifecycle_by_id = {
        reference_id: reference.get("lifecycle", manifest["default_lifecycle"])
        for reference_id, reference in zip(reference_ids, references, strict=True)
    }
    unsupported_lifecycles = {
        reference_id: lifecycle
        for reference_id, lifecycle in lifecycle_by_id.items()
        if lifecycle not in {"static-bundle", "current-product-evidence"}
    }
    if unsupported_lifecycles:
        raise UserGuideContractError(
            f"service reference lifecycles are unsupported: {unsupported_lifecycles}"
        )
    current_product_ids = {
        reference_id
        for reference_id, lifecycle in lifecycle_by_id.items()
        if lifecycle == "current-product-evidence"
    }
    expected_current_product_ids = set(_CURRENT_PRODUCT_REFERENCE_TARGETS)
    if current_product_ids != expected_current_product_ids:
        raise UserGuideContractError(
            "current product reference targets drifted: "
            f"actual={sorted(current_product_ids)}, "
            f"expected={sorted(expected_current_product_ids)}"
        )
    legacy_ids = {
        reference_id
        for reference_id, lifecycle in lifecycle_by_id.items()
        if lifecycle == "static-bundle"
    }
    if len(legacy_ids) != 69:
        raise UserGuideContractError(
            f"service reference manifest must contain 69 legacy targets: {len(legacy_ids)}"
        )

    source_root = project / "docs" / "00-research" / "ux-service-reference"
    reference_root = project / "docs" / "17-evidence" / "images" / "issue-167-service-reference"
    evidence_root = project / "docs" / "17-evidence" / "images"
    ids: set[str] = set()
    images: set[str] = set()
    expected_measurements: set[Path] = set()
    for ordinal, reference in enumerate(references, start=1):
        reference_id = reference_ids[ordinal - 1]
        ids.add(reference_id)
        if reference.get("status") != "approved":
            raise UserGuideContractError(f"service reference is not approved: {reference_id}")
        owner = _mapping(
            reference.get("product_owner_approval"),
            f"service reference {reference_id} owner approval",
        )
        if owner.get("status") != "approved":
            raise UserGuideContractError(f"service reference lacks owner approval: {reference_id}")

        lifecycle = reference.get("lifecycle", manifest["default_lifecycle"])
        image_ref = _text(reference.get("image"), f"service reference {reference_id} image")
        viewport = _mapping(reference.get("viewport"), f"service reference {reference_id} viewport")
        if lifecycle == "current-product-evidence":
            screen, state, width, height, expected_image_ref = _CURRENT_PRODUCT_REFERENCE_TARGETS[
                reference_id
            ]
            if (reference.get("screen"), reference.get("state")) != (screen, state):
                raise UserGuideContractError(
                    f"current product reference identity contract drifted: {reference_id}"
                )
            if (
                viewport.get("width"),
                viewport.get("height"),
                viewport.get("device_scale_factor"),
            ) != (width, height, 1):
                raise UserGuideContractError(
                    f"current product reference viewport contract drifted: {reference_id}"
                )
            if image_ref != expected_image_ref:
                raise UserGuideContractError(
                    f"current product reference image contract drifted: {reference_id}"
                )
            if reference.get("evidence_manifest") != _CURRENT_PRODUCT_EVIDENCE_MANIFEST:
                raise UserGuideContractError(
                    f"current product reference evidence declaration drifted: {reference_id}"
                )
            if reference.get("evidence_key") != _CURRENT_PRODUCT_EVIDENCE_KEY:
                raise UserGuideContractError(
                    f"current product reference evidence key drifted: {reference_id}"
                )
        image_parent = reference_root if lifecycle == "static-bundle" else evidence_root
        image = _inside(
            project / image_ref, image_parent, f"service reference {reference_id} image"
        )
        if not image.is_file() or image.suffix.lower() != ".png":
            raise UserGuideContractError(f"service reference image is missing: {reference_id}")
        if _image_dimensions(image) != (viewport.get("width"), viewport.get("height")):
            raise UserGuideContractError(f"service reference viewport drifted: {reference_id}")
        expected_hash = _text(
            reference.get("image_sha256"), f"service reference {reference_id} hash"
        )
        if hashlib.sha256(image.read_bytes()).hexdigest() != expected_hash:
            raise UserGuideContractError(f"service reference hash drifted: {reference_id}")

        if lifecycle == "static-bundle":
            if "evidence_manifest" in reference or "evidence_key" in reference:
                raise UserGuideContractError(
                    "static service reference must not use current product evidence: "
                    f"{reference_id}"
                )
            sources = _mapping(
                reference.get("sources"), f"service reference {reference_id} sources"
            )
            if not sources:
                raise UserGuideContractError(f"service reference has no source: {reference_id}")
            for source_name, raw_source in sources.items():
                source_ref = _text(raw_source, f"service reference {reference_id} {source_name}")
                source = _inside(
                    project / source_ref,
                    source_root,
                    f"service reference {reference_id} {source_name}",
                )
                if not source.is_file() or source.suffix.lower() not in {
                    ".html",
                    ".css",
                    ".js",
                }:
                    raise UserGuideContractError(
                        "service reference source is missing or unsupported: "
                        f"{reference_id} {source_ref}"
                    )
            measurement_ref = _text(
                reference.get("measurements"), f"service reference {reference_id} measurements"
            )
            measurement = _inside(
                project / measurement_ref,
                reference_root,
                f"service reference {reference_id} measurements",
            )
            if not measurement.is_file() or not measurement.name.endswith(".measurements.json"):
                raise UserGuideContractError(
                    f"service reference measurements are missing: {reference_id}"
                )
            json.loads(measurement.read_text(encoding="utf-8"))
            expected_measurements.add(measurement)
        else:
            if image.is_relative_to(reference_root.resolve()):
                raise UserGuideContractError(
                    f"current product reference must not use the static bundle: {reference_id}"
                )
            _verify_current_product_reference_evidence(
                project,
                reference_id,
                reference,
                image,
                viewport,
                expected_hash,
                evidence_root,
            )
        images.add(_relative(image, project))

    actual_measurements = {
        path.resolve()
        for path in reference_root.iterdir()
        if path.is_file() and path.name.endswith(".measurements.json")
    }
    if actual_measurements != expected_measurements:
        unexpected = sorted(
            _relative(path, project) for path in actual_measurements - expected_measurements
        )
        missing = sorted(
            _relative(path, project) for path in expected_measurements - actual_measurements
        )
        raise UserGuideContractError(
            f"static service reference measurements must match legacy targets: "
            f"unexpected={unexpected}, missing={missing}"
        )
    unsupported_files = sorted(
        _relative(path, project)
        for path in reference_root.iterdir()
        if path.is_file()
        and path.suffix.lower() != ".png"
        and not path.name.endswith(".measurements.json")
    )
    if unsupported_files:
        raise UserGuideContractError(
            f"static service reference directory contains unsupported files: {unsupported_files}"
        )
    return images


def _duplicate_allowances(project: Path, manifest: dict[str, Any]) -> set[frozenset[str]]:
    entries = _sequence(manifest.get("allowed_duplicate_groups", []), "duplicate allowances")
    allowances: set[frozenset[str]] = set()
    for ordinal, raw_entry in enumerate(entries, start=1):
        entry = _mapping(raw_entry, f"duplicate allowance {ordinal}")
        _text(entry.get("rationale"), f"duplicate allowance {ordinal} rationale")
        image_refs = _sequence(entry.get("images"), f"duplicate allowance {ordinal} images")
        if len(image_refs) < 2:
            raise UserGuideContractError(
                f"duplicate allowance {ordinal} must list at least two exact images"
            )
        paths: list[str] = []
        for image_ordinal, raw_image in enumerate(image_refs, start=1):
            image_ref = _text(raw_image, f"duplicate allowance {ordinal} image {image_ordinal}")
            if any(character.isspace() for character in image_ref) or any(
                character in image_ref for character in "*?[]{}"
            ):
                raise UserGuideContractError(
                    f"duplicate allowance {ordinal} image must be an exact path: {image_ref}"
                )
            image = _inside(
                project / image_ref,
                project,
                f"duplicate allowance {ordinal} image {image_ordinal}",
            )
            if not image.is_file() or image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                raise UserGuideContractError(f"duplicate allowance target is missing: {image_ref}")
            paths.append(_relative(image, project))
        group = frozenset(paths)
        if len(group) != len(paths):
            raise UserGuideContractError(f"duplicate allowance {ordinal} repeats an image path")
        if group in allowances:
            raise UserGuideContractError(f"duplicate image allowance is repeated: {sorted(group)}")
        lifecycle_counts = Counter(_image_lifecycle(path) for path in paths)
        if not _allowed_duplicate_lifecycles(lifecycle_counts):
            raise UserGuideContractError(
                f"duplicate allowance has an unsupported lifecycle mix: {dict(lifecycle_counts)}"
            )
        allowances.add(group)
    return allowances


def _image_lifecycle(relative: str) -> str:
    if relative.startswith(_CURRENT_IMAGE_PREFIX):
        return "current"
    if relative.startswith("docs/17-evidence/images/issue-167-service-reference/"):
        return "reference"
    if relative.startswith("docs/00-research/"):
        return "reference"
    if relative.startswith(_EVIDENCE_IMAGE_PREFIX):
        return "evidence"
    return "unclassified"


def _allowed_duplicate_lifecycles(lifecycle_counts: Counter[str]) -> bool:
    lifecycles = set(lifecycle_counts)
    if lifecycles == {"reference"} or lifecycles == {"evidence"}:
        return True
    return (
        lifecycles <= {"evidence", "current"}
        and lifecycle_counts["evidence"] >= 1
        and lifecycle_counts["current"] <= 1
    )


def _verify_image_inventory(
    project: Path,
    referenced_images: set[str],
    allowed_duplicate_groups: set[frozenset[str]],
) -> tuple[int, int, int]:
    roots = (
        project / "docs" / "00-research",
        project / "docs" / "17-evidence" / "images",
        project / "docs" / "user-guide" / "images",
    )
    images = sorted(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    inventory_paths = {_relative(path, project) for path in images}
    orphan_images = sorted(inventory_paths - referenced_images)
    if orphan_images:
        raise UserGuideContractError(
            f"unreferenced images require archive rationale or deletion: {orphan_images}"
        )

    hashes: dict[str, list[Path]] = {}
    for image in images:
        value = image.read_bytes()
        is_png = value.startswith(_PNG_SIGNATURE)
        is_jpeg = value.startswith(_JPEG_SIGNATURE)
        if (image.suffix.lower() == ".png" and not is_png) or (
            image.suffix.lower() in {".jpg", ".jpeg"} and not is_jpeg
        ):
            raise UserGuideContractError(
                f"image extension does not match bytes: {_relative(image, project)}"
            )
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        hashes.setdefault(digest, []).append(image)
    duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]
    actual_allowed_groups: set[frozenset[str]] = set()
    invalid_duplicate_groups: list[tuple[list[str], dict[str, int]]] = []
    for paths in duplicate_groups:
        relative_paths = sorted(_relative(path, project) for path in paths)
        lifecycle_counts = dict(Counter(_image_lifecycle(path) for path in relative_paths))
        group = frozenset(relative_paths)
        if group in allowed_duplicate_groups and _allowed_duplicate_lifecycles(
            Counter(_image_lifecycle(path) for path in relative_paths)
        ):
            actual_allowed_groups.add(group)
            continue
        invalid_duplicate_groups.append((relative_paths, lifecycle_counts))
    if invalid_duplicate_groups:
        raise UserGuideContractError(
            "duplicate image hashes require one explicit duplicate group: "
            f"{invalid_duplicate_groups}"
        )
    # A historical evidence manifest may record that its immutable original was
    # byte-identical to the then-current guide image. The current lifecycle path
    # is intentionally replaceable on a later visual issue, so that historical
    # evidence-to-current declaration expires without editing the old manifest.
    # Evidence-only duplicate declarations remain strict and must still match.
    stale_allowances = {
        group
        for group in allowed_duplicate_groups - actual_allowed_groups
        if not any(path.startswith(_CURRENT_IMAGE_PREFIX) for path in group)
        and not any(group < actual_group for actual_group in actual_allowed_groups)
    }
    if stale_allowances:
        raise UserGuideContractError(
            "duplicate image allowances no longer match equal bytes: "
            f"{[sorted(pair) for pair in stale_allowances]}"
        )
    return len(images), len(orphan_images), len(duplicate_groups)


def verify_user_guide(root: Path) -> UserGuideReport:
    project = root.resolve()
    guide_root = project / "docs" / "user-guide"
    image_root = guide_root / "images" / "current"
    documents = sorted(guide_root.glob("*.md"))
    if not documents:
        raise UserGuideContractError("no user-guide documents were found")

    classes = _documentation_classes(project)
    current_document_images, document_images, local_link_count = _verify_document_links(
        project, classes
    )

    manifest = _mapping(
        yaml.safe_load((guide_root / "screenshot-manifest.yaml").read_text(encoding="utf-8")),
        "screenshot manifest",
    )
    captures = _sequence(manifest.get("captures"), "screenshot manifest captures")
    capture_ids: set[str] = set()
    registered_images: set[str] = set()
    for ordinal, raw_capture in enumerate(captures, start=1):
        capture = _mapping(raw_capture, f"capture {ordinal}")
        capture_id = _text(capture.get("id"), f"capture {ordinal} id")
        if capture_id in capture_ids:
            raise UserGuideContractError(f"duplicate screenshot id: {capture_id}")
        capture_ids.add(capture_id)
        route = _text(capture.get("route"), f"capture {capture_id} route")
        _text(capture.get("workflow"), f"capture {capture_id} workflow")
        _text(capture.get("fixture"), f"capture {capture_id} fixture")
        if not route.startswith("/"):
            raise UserGuideContractError(f"capture route must be absolute: {capture_id}")
        relative_image = _text(capture.get("image"), f"capture {capture_id} image")
        image = _inside(guide_root / relative_image, image_root, f"capture {capture_id} image")
        if not image.is_file() or image.suffix.lower() != ".png" or image.stat().st_size < 10_000:
            raise UserGuideContractError(f"capture is missing or implausibly small: {capture_id}")
        width, height = _image_dimensions(image)
        if width < 800 or height < 700:
            raise UserGuideContractError(
                f"capture is below the minimum evidence viewport: {capture_id}"
            )
        if capture.get("width") != width or capture.get("height") != height:
            raise UserGuideContractError(f"capture viewport drifted: {capture_id}")
        project_image = _relative(image, project)
        if project_image in registered_images:
            raise UserGuideContractError(
                f"screenshot image is registered more than once: {project_image}"
            )
        registered_images.add(project_image)

    capture_script_ref = _text(manifest.get("capture_script"), "screenshot capture script")
    capture_script = _inside(
        guide_root / capture_script_ref,
        project,
        "screenshot capture script",
    )
    if not capture_script.is_file():
        raise UserGuideContractError(f"capture script is missing: {capture_script_ref}")
    scripted_images = {
        f"{_CURRENT_IMAGE_PREFIX}{name}" for name in _capture_script_outputs(capture_script)
    }
    if scripted_images != registered_images:
        raise UserGuideContractError(
            "capture script outputs drifted from the current manifest: "
            f"missing={sorted(registered_images - scripted_images)}, "
            f"unexpected={sorted(scripted_images - registered_images)}"
        )

    missing_registration = current_document_images - registered_images
    unused_registration = registered_images - current_document_images
    if missing_registration:
        raise UserGuideContractError(
            f"current document images are absent from the manifest: {sorted(missing_registration)}"
        )
    if unused_registration:
        raise UserGuideContractError(
            "current manifest images are unused by current documents: "
            f"{sorted(unused_registration)}"
        )
    _verify_repository_guidance(project)
    _verify_readme(project, registered_images)
    permanent_reference_images = _verify_permanent_reference_catalog(project)

    navigation = _mapping(
        yaml.safe_load((guide_root / "navigation-contract.yaml").read_text(encoding="utf-8")),
        "navigation contract",
    )
    items = _sequence(navigation.get("items"), "navigation contract items")
    navigation_sources = (
        project / "apps" / "web" / "src" / "app.tsx",
        project / "apps" / "web" / "src" / "design" / "application-shell.tsx",
    )
    app_source = "\n".join(
        source.read_text(encoding="utf-8") for source in navigation_sources if source.is_file()
    )
    index_source = (guide_root / "index.md").read_text(encoding="utf-8")
    labels: set[str] = set()
    routes: set[str] = set()
    for ordinal, raw_item in enumerate(items, start=1):
        item = _mapping(raw_item, f"navigation item {ordinal}")
        label = _text(item.get("label"), f"navigation item {ordinal} label")
        route = _text(item.get("route"), f"navigation item {ordinal} route")
        guide_name = _text(item.get("guide"), f"navigation item {ordinal} guide")
        if label in labels or route in routes:
            raise UserGuideContractError(f"duplicate navigation label or route: {label} {route}")
        labels.add(label)
        routes.add(route)
        if f'label: "{label}"' not in app_source or f'target: "{route}"' not in app_source:
            raise UserGuideContractError(
                f"navigation contract drifted from web navigation: {label}"
            )
        guide = _inside(guide_root / guide_name, guide_root, f"navigation guide for {label}")
        if not guide.is_file() or f"({guide_name})" not in index_source:
            raise UserGuideContractError(f"navigation guide is missing from the index: {label}")

    structured_manifest_images = _structured_manifest_images(project)
    service_reference_images = _verify_service_reference_manifest(project)
    referenced_images = (
        document_images
        | registered_images
        | scripted_images
        | structured_manifest_images
        | permanent_reference_images
        | service_reference_images
    )
    duplicate_manifest = _mapping(
        yaml.safe_load(
            (project / "docs" / "01-product" / "service-reference-duplicates.yaml").read_text(
                encoding="utf-8"
            )
        ),
        "service reference duplicate manifest",
    )
    allowed_duplicate_groups = _duplicate_allowances(
        project, duplicate_manifest
    ) | _duplicate_allowances(project, manifest)
    for relative in _STRUCTURED_IMAGE_MANIFESTS:
        structured_manifest = _mapping(
            json.loads((project / relative).read_text(encoding="utf-8")),
            f"structured image manifest {relative}",
        )
        allowed_duplicate_groups |= _duplicate_allowances(project, structured_manifest)
    for relative in _STRUCTURED_IMAGE_YAML_MANIFESTS:
        structured_manifest = _mapping(
            yaml.safe_load((project / relative).read_text(encoding="utf-8")),
            f"structured image manifest {relative}",
        )
        allowed_duplicate_groups |= _duplicate_allowances(project, structured_manifest)
    image_count, orphan_image_count, duplicate_image_group_count = _verify_image_inventory(
        project, referenced_images, allowed_duplicate_groups
    )

    return UserGuideReport(
        document_count=len(documents),
        capture_count=len(captures),
        navigation_count=len(items),
        classified_markdown_count=len(classes),
        current_document_count=sum(status == "current" for status in classes.values()),
        local_link_count=local_link_count,
        image_count=image_count,
        orphan_image_count=orphan_image_count,
        duplicate_image_group_count=duplicate_image_group_count,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = verify_user_guide(args.root)
    except (OSError, subprocess.CalledProcessError, UserGuideContractError) as error:
        parser.exit(1, f"user-guide check failed: {error}\n")
    print(
        "user-guide check passed: "
        f"{report.document_count} guide documents, {report.capture_count} current captures, "
        f"{report.navigation_count} navigation items, "
        f"{report.classified_markdown_count} classified Markdown files, "
        f"{report.local_link_count} local links, {report.image_count} images"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reject user-visible changes that omit their current documentation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml

ImpactMode = Literal["staged", "range", "worktree"]

_GUIDE_PREFIX = "docs/user-guide/"
_SCREENSHOT_MANIFEST = "docs/user-guide/screenshot-manifest.yaml"
_NAVIGATION_CONTRACT = "docs/user-guide/navigation-contract.yaml"
_FRONTEND_GUARD_BASELINE = "apps/web/frontend-guard-baseline.json"
_EXCEPTION_PREFIX = "docs/testing/documentation-impact-exceptions/"
_EXCEPTION_SCHEMA = "cmp.documentation-impact-exception.v1"
_NON_USER_VISIBLE_CLASSIFICATION = "non-user-visible-foundation"
_NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION = "non-user-visible-structural-extraction"
_NON_USER_VISIBLE_COMPOSITION_CLASSIFICATION = "non-user-visible-composition-attestation"
_FRONTEND_GUARD_SOURCE_SHA_SENTINEL = b"0" * 40
_DOCUMENTATION_MANIFEST = "docs/documentation-manifest.yaml"
_VISUAL_EVIDENCE_LIFECYCLES = frozenset({"current", "frozen", "transient"})
_CURRENT_FIVE_VIEWPORTS = frozenset(
    {"1366x768", "1440x900", "1920x1080", "2560x1440", "3840x2160"}
)
_ISSUE_167_EXCEPTION_FILES = frozenset(
    {
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-1920x1080.png",
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-2560x1440.png",
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-3840x2160.png",
    }
)
_ISSUE_167_DEPENDENCIES = frozenset(
    {
        "docs/product/service-reference-manifest.yaml",
        "docs/17-evidence/images/issue-289-administration-database-workflow/visual-evidence.yaml",
    }
)
# This is a semantic, one-time retirement policy for the legacy Materials
# reference bundle. Values are SHA-256 digests of raw Git blob bytes at the
# merge base (not decoded or newline-normalized worktree text).
_RETIRED_STATIC_MATERIALS_REFERENCE_ROOT = (
    "docs/17-evidence/images/issue-167-service-reference"
)
_RETIRED_STATIC_MATERIALS_REFERENCE_SHA256: dict[str, str] = {
    f"{_RETIRED_STATIC_MATERIALS_REFERENCE_ROOT}/{name}": digest
    for name, digest in (
        ("materials-search-normal-1440x900.png",
         "7f96a68d0ff03eb20b95abf831354e6a1052e34f0246871c9318ede0cce367a0"),
        ("materials-search-normal-1440x900.measurements.json",
         "8309dc5d310536fa4d0a0f2f892a4e6c64210e8708a9a6dc68a7b427bffe05d3"),
        ("materials-search-normal-1366x768.png",
         "bd400b2f913a0d2c8c1e5dba6565c05b12055118ffbbaac1b9e5845cf6bfff89"),
        ("materials-search-normal-1366x768.measurements.json",
         "483fc26b3820c081711d2ace7521d009a4827951b53f49d201a0b36a04c0e373"),
        ("materials-search-normal-1920x1080.png",
         "57f136268f52386c99cb13970f694cf40a30bdb57a6bc3badcab0b70a24ed3ae"),
        ("materials-search-normal-1920x1080.measurements.json",
         "5a5129499769d80b3226b6d2eb6450e8febc0b588ab283e291ab1fd4a37f5e8c"),
        ("materials-datasheet-overview-normal-1440x900.png",
         "c12ab49d173016db7119f0fc8a898cb66495f0424f3b5629480cd91185c3876b"),
        ("materials-datasheet-overview-normal-1440x900.measurements.json",
         "b2daf32cef06e643f2f2e02ff90b1452b175b8da78e727099dcc13d506fef33a"),
        ("materials-datasheet-overview-normal-1366x768.png",
         "d7b0ff64903b655882987ce4feefb9beb456e6cf5709ff8726ec8e293de9f43d"),
        ("materials-datasheet-overview-normal-1366x768.measurements.json",
         "fd6898dd1d69e756a5476551d1bc6b7ff90e2b88865b66a9bbfe9eb6cae74c5c"),
        ("materials-datasheet-overview-normal-1920x1080.png",
         "8ac1d48195a233d385743d3d9d936bcea8047f25967a63f0cff9a8a984ab06f0"),
        ("materials-datasheet-overview-normal-1920x1080.measurements.json",
         "7a4ea2345f6fbd3f355f2669845d6bd5097ebc6cc0b40f2121d278ea0844096f"),
        ("materials-datasheet-related-long-1440x900.png",
         "810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6"),
        ("materials-datasheet-related-long-1440x900.measurements.json",
         "a1c6d34bc178393b4c91e4651e33e39ce26edf278a72ce562583cd84358f6794"),
        ("materials-datasheet-empty-1440x900.png",
         "8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6"),
        ("materials-datasheet-empty-1440x900.measurements.json",
         "15aba5de7033c0d8a9b6d2fa4dcd96b205534fc209f3010925a728b28cf56692"),
        ("materials-card-preview-normal-1366x768.png",
         "b4f38c0117c13f50b9cefbccf833d389b7a91c8c719961c66b9d2226cf3950a3"),
        ("materials-card-preview-normal-1366x768.measurements.json",
         "3c4f770657f3229cdb03d53fe37a191b0d220d5fa535a09f4081d5878d97f0b1"),
        ("materials-search-long-1440x900.png",
         "43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484"),
        ("materials-search-long-1440x900.measurements.json",
         "f3ca0dffc71c404ee0fdbd6515cebc56917db16f9ea1798e14b21014b2f64a9d"),
        ("materials-search-empty-1440x900.png",
         "d9e4fed1d8c17ca86b7c14dfe57909591b44ff8ec300286bb49f3a940fb5e1b1"),
        ("materials-search-empty-1440x900.measurements.json",
         "06f4afae598ca967bf5c1a3f5ca81f7d11a1d05a5921211885d7534a3bdac5b3"),
        ("materials-card-preview-normal-1440x900.png",
         "05b327f3741f27962bb6dc7ee961071ab3dedb2b840fedc5c94799ea6076c8db"),
        ("materials-card-preview-normal-1440x900.measurements.json",
         "8b340eef0664941287d0974e5f08f5a4f797ecfa77683500db740db01063df1f"),
        ("materials-card-preview-normal-1920x1080.png",
         "963ac2613b244caadde2e9f576c9078ebbf6f6138177b8c25c30018797d77fb4"),
        ("materials-card-preview-normal-1920x1080.measurements.json",
         "90449452c55577608223f176af17a9884f0ebd57713be7460f2907fc433308d8"),
        ("materials-card-approximation-blocked-1440x900.png",
         "6cfe99b8f20b4609c0fc509e79c8013ef13d764ba55166a617cc9b08c2402ec8"),
        ("materials-card-approximation-blocked-1440x900.measurements.json",
         "8ea9f5c1baa6918ac279d0e985df348dee225612ff3fd5d17e7650d79bdf0674"),
        ("materials-card-unsupported-blocked-1440x900.png",
         "8eba256b6a59e6c9d61a7a3b6574e4878952dd62e690703ce25a88764fd1afc6"),
        ("materials-card-unsupported-blocked-1440x900.measurements.json",
         "c21c345ec800923a0a01a97512df43ba3928cd27c4594592419427f15274ddc8"),
    )
}
_ISSUE_184_VISUAL_EVIDENCE = (
    "docs/17-evidence/images/issue-184-high-dpi-global-implementation/visual-evidence.json"
)
_ISSUE_184_ROOT = "docs/17-evidence/images/issue-184-high-dpi-global-implementation"
# The approved #184 policy snapshot is immutable.  Tests may replace this named
# constant with a temporary fixture commit; production must keep this SHA.
_ISSUE_184_POLICY_BASE = "94d8a1cdefa104fb41865171093b0657966b159f"
_ISSUE_223_PREFIX = "docs/17-evidence/images/issue-223-"
_ISSUE_351_RETIRED_EVIDENCE_ROOTS = frozenset(
    f"docs/17-evidence/images/{name}"
    for name in (
        "issue-160-activity-density",
        "issue-160-review-publication",
        "issue-161-administration-button-semantics",
        "issue-261-b4-css-ownership-publication",
        "issue-261-fe06-m1a0-data-same-selector-overlap",
        "issue-261-fe06-m1a1-data-source-tabs",
        "issue-261-fe06-m1a2-data-source-advanced",
        "issue-261-fe06-m1a3-data-import-diagnostics",
        "issue-261-fe06-m1a4-data-raw-source-preview",
        "issue-261-fe06-m1a5-data-library-source-list",
        "issue-261-fe06-m1a6-data-curve-row-label",
        "issue-261-fe06-m1a7-data-mapping-heading",
        "issue-261-fe06-m1a8-data-optional-channel",
        "issue-261-fe06-m1a9-data-mapping-table",
        "issue-261-fe06-m1a10-data-split-frame",
        "issue-261-fe06-m1a11-data-file-details",
        "issue-261-fe06-m1a12-data-mapping-change-actions",
        "issue-261-fe06-m1a13-data-local-scrollport",
        "issue-261-fe06-m1a14-data-mapping-blocker",
        "issue-261-fe06-m1a15-data-intake-surface",
        "issue-261-fe06-m1a16-data-local-import-controls",
        "issue-261-fe06-m1a17-data-mapping-attention",
        "issue-261-fe06-m1a18-data-mapping-resolved",
        "issue-261-fe06-m1a19-data-intake-field-rows",
        "issue-261-fe06-m1a20-data-mapping-decision-frame",
        "issue-298-frontend-guard-297-correction",
    )
)
_SHARED_DESIGN_PREFIX = "apps/web/src/design/"
_PRESERVED_FOUNDATION_FILES = {
    "apps/web/src/design/primitives.css",
    "apps/web/src/design/tokens.css",
    "apps/web/src/design/typography.css",
}
_OPENAPI_CONTRACTS = {
    "contracts/http/openapi.yaml",
    "contracts/http/openapi.baseline.yaml",
}


class DocumentationImpactError(RuntimeError):
    """Raised when changed files do not include required current documentation."""


@dataclass(frozen=True, slots=True)
class DocumentationImpactReport:
    changed_files: tuple[str, ...]
    visual_files: tuple[str, ...]
    exempted_visual_files: tuple[str, ...]
    exception_issue: str | None
    requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentationImpactException:
    path: str
    issue: str
    source_sha: str
    classification: str
    reason: str
    visual_files: tuple[str, ...]
    unconsumed_modules: tuple[str, ...]
    preserved_computed_value_files: tuple[str, ...]
    import_only_files: tuple[str, ...] = ()
    relocations: tuple[_Relocation, ...] = ()
    composition_targets: tuple[str, ...] = ()
    characterization_tests: tuple[str, ...] = ()
    navigation_contract: str | None = None
    visual_patch_sha256: str | None = None
    attested_patch_sha256: str | None = None
    independent_audit: str | None = None
    product_owner_disposition: str | None = None


@dataclass(frozen=True, slots=True)
class _Relocation:
    source: str
    target: str
    declarations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedDocumentationImpactException:
    exception: DocumentationImpactException
    derived_selectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _VisualEvidenceException:
    lifecycle: str
    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _VisualEvidenceConfig:
    raster_extensions: frozenset[str]
    roots: tuple[tuple[str, str], ...]
    exceptions: tuple[_VisualEvidenceException, ...]


@dataclass(frozen=True, slots=True)
class _CssRule:
    context: tuple[str, ...]
    selector: str
    declarations: tuple[tuple[str, str], ...]


def _normalize(paths: Iterable[str]) -> set[str]:
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


def _git_lines(project: Path, arguments: list[str], *, allow_failure: bool = False) -> set[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=not allow_failure,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return _normalize(result.stdout.splitlines())


def _parse_name_status_entries(value: bytes) -> dict[str, bool]:
    tokens = [token for token in value.split(b"\0") if token]
    entries: dict[str, bool] = {}
    index = 0
    while index < len(tokens):
        status = tokens[index].decode("ascii", errors="strict")
        index += 1
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count > len(tokens):
            raise DocumentationImpactError("git name-status output is malformed")
        paths = [
            token.decode("utf-8", errors="strict").replace("\\", "/")
            for token in tokens[index : index + path_count]
        ]
        if path_count == 2:
            entries[paths[0]] = entries.get(paths[0], False)
            exception_relocation = (
                status == "R100"
                and paths[1].startswith(_EXCEPTION_PREFIX)
            )
            # A byte-identical exception relocation is still part of the changed
            # set, but it must not be interpreted as a newly changed waiver. Any
            # content change or later exception edit remains evidence and keeps
            # the one-exception fail-closed rule.
            entries[paths[1]] = not exception_relocation
        else:
            entries[paths[0]] = entries.get(paths[0], False) or not status.startswith("D")
        index += path_count
    return entries


def _parse_name_status(value: bytes) -> set[str]:
    return set(_parse_name_status_entries(value))


def git_changed_entries(
    project: Path,
    arguments: list[str],
    *,
    allow_failure: bool = False,
) -> dict[str, bool]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            "--diff-filter=ACMRTD",
            *arguments,
        ],
        cwd=project,
        check=not allow_failure,
        capture_output=True,
    )
    if result.returncode != 0:
        return {}
    return _parse_name_status_entries(result.stdout)


def git_changed_paths(
    project: Path,
    arguments: list[str],
    *,
    allow_failure: bool = False,
) -> set[str]:
    return set(git_changed_entries(project, arguments, allow_failure=allow_failure))


def _merge_entries(target: dict[str, bool], source: Mapping[str, bool]) -> None:
    for path, can_supply_evidence in source.items():
        target[path] = target.get(path, False) or can_supply_evidence


def changed_entries(project: Path, mode: ImpactMode) -> dict[str, bool]:
    if mode == "staged":
        return git_changed_entries(project, ["--cached"])
    if mode == "range":
        return git_changed_entries(project, ["origin/main...HEAD"], allow_failure=True)
    changed: dict[str, bool] = {}
    _merge_entries(changed, git_changed_entries(project, []))
    _merge_entries(changed, git_changed_entries(project, ["--cached"]))
    _merge_entries(
        changed,
        {
            path: True
            for path in _git_lines(project, ["ls-files", "--others", "--exclude-standard"])
        },
    )
    _merge_entries(
        changed,
        git_changed_entries(project, ["origin/main...HEAD"], allow_failure=True),
    )
    return changed


def changed_files(project: Path, mode: ImpactMode) -> set[str]:
    return set(changed_entries(project, mode))


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    return (
        "tests" in pure.parts
        or "__tests__" in pure.parts
        or ".test." in name
        or ".spec." in name
        or ".stories." in name
        or path.startswith("apps/web/e2e/")
        or path.startswith("apps/web/.storybook/")
    )


def _is_visual_source(path: str) -> bool:
    return (
        path.startswith("apps/web/")
        and PurePosixPath(path).suffix.lower() in {".tsx", ".css"}
        and not _is_test_path(path)
    )


_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_LITERAL_RE = re.compile(
    r"(?:0[xX][0-9A-Fa-f_]+n?|0[bB][01_]+n?|0[oO][0-7_]+n?|"
    r"(?:\d[\d_]*(?:\.[\d_]*)?|\.[\d_]+)(?:[eE][+-]?[\d_]+)?n?)"
)
_OPTIONAL_PROPERTY_IMPORT_TYPE_RE = re.compile(
    r'^(?P<prefix>\s*[A-Za-z_$][A-Za-z0-9_$]*\s*\?\s*:\s*)'
    r'import\(\s*["\'](?:\.{1,2}/)[^"\']+["\']\s*\)\s*\.\s*'
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)",
    flags=re.MULTILINE,
)


def _canonical_repo_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty canonical path")
    if value != value.strip():
        raise DocumentationImpactError(f"{field} must be a canonical path")
    if "\\" in value or any(character in value for character in "*?[]{}"):
        raise DocumentationImpactError(f"{field} must use canonical POSIX paths")
    if value.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", value):
        raise DocumentationImpactError(f"{field} must be repository-relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DocumentationImpactError(f"{field} contains ambiguous path segments")
    normalized = PurePosixPath(value).as_posix()
    if normalized != value:
        raise DocumentationImpactError(f"{field} must be canonical")
    if not value.startswith("apps/web/src/"):
        raise DocumentationImpactError(f"{field} must be under apps/web/src")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise DocumentationImpactError(f"{field} entries must be non-empty strings")
        normalized = item.strip().replace("\\", "/")
        if any(character in normalized for character in "*?[]{}"):
            raise DocumentationImpactError(f"{field} does not allow wildcard paths")
        items.append(normalized)
    if len(set(items)) != len(items):
        raise DocumentationImpactError(f"{field} contains duplicate entries")
    return tuple(sorted(items))


def _path_list(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise DocumentationImpactError(
            f"{field} must be {'an empty or non-empty' if allow_empty else 'a non-empty'} list"
        )
    items = tuple(_canonical_repo_path(item, f"{field} entry") for item in value)
    if len(set(items)) != len(items):
        raise DocumentationImpactError(f"{field} contains duplicate entries")
    return tuple(sorted(items))


def _artifact_path_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty list")
    items = tuple(
        _canonical_artifact_path(item, f"{field} entry") for item in value
    )
    if len(set(items)) != len(items):
        raise DocumentationImpactError(f"{field} contains duplicate entries")
    return tuple(sorted(items))


def _canonical_artifact_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty canonical path")
    if value != value.strip() or "\\" in value or any(character in value for character in "*?[]{}"):
        raise DocumentationImpactError(f"{field} must be a canonical exact path")
    if value.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", value):
        raise DocumentationImpactError(f"{field} must be repository-relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DocumentationImpactError(f"{field} contains ambiguous path segments")
    if PurePosixPath(value).as_posix() != value:
        raise DocumentationImpactError(f"{field} must be canonical")
    return value


def _unique_json_mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DocumentationImpactError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json_mapping(path: Path, field: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_mapping)
    except (OSError, UnicodeError, json.JSONDecodeError, DocumentationImpactError) as error:
        raise DocumentationImpactError(f"cannot read {field}: {error}") from error
    return _mapping(raw, field)


class _UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate keys at every mapping depth."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise DocumentationImpactError("documentation-impact YAML keys must be strings")
        if key in mapping:
            raise DocumentationImpactError(f"duplicate YAML key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DocumentationImpactError(f"{field} must be a mapping")
    return value


def _path_is_under(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def _exception_path_matches(path: str, configured: str) -> bool:
    # Configured file exceptions are exact paths; only directory exceptions
    # authorize descendants.  A trailing slash is not canonical, so normal
    # directory nesting is unambiguous.
    if PurePosixPath(configured).suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return path == configured
    return _path_is_under(path, configured)


def _parse_visual_evidence_config(raw: object, field: str) -> _VisualEvidenceConfig:
    manifest = _mapping(raw, field)
    if manifest.get("version") != 3:
        raise DocumentationImpactError(f"{field} must use version 3")
    data = _mapping(manifest.get("visual_evidence"), f"{field} visual_evidence")
    expected_keys = {"raster_extensions", "roots", "exceptions"}
    if set(data) != expected_keys:
        raise DocumentationImpactError(
            f"{field} visual_evidence keys must be exactly {', '.join(sorted(expected_keys))}"
        )

    extensions = data["raster_extensions"]
    if not isinstance(extensions, list) or not extensions:
        raise DocumentationImpactError(
            f"{field} visual_evidence.raster_extensions must be a non-empty list"
        )
    if any(not isinstance(item, str) for item in extensions):
        raise DocumentationImpactError(
            f"{field} visual_evidence.raster_extensions entries must be strings"
        )
    normalized_extensions = tuple(item.lower() for item in extensions)
    expected_extensions = (".jpeg", ".jpg", ".png")
    if tuple(sorted(normalized_extensions)) != expected_extensions:
        raise DocumentationImpactError(
            f"{field} visual_evidence.raster_extensions must be exactly "
            ".png, .jpg, .jpeg"
        )
    if len(set(normalized_extensions)) != len(normalized_extensions):
        raise DocumentationImpactError(
            f"{field} visual_evidence.raster_extensions contains duplicate entries"
        )

    raw_roots = _mapping(data["roots"], f"{field} visual_evidence.roots")
    if set(raw_roots) != _VISUAL_EVIDENCE_LIFECYCLES:
        raise DocumentationImpactError(
            f"{field} visual_evidence.roots must define current, frozen, and transient"
        )
    roots: dict[str, str] = {}
    for lifecycle in ("current", "frozen", "transient"):
        roots[lifecycle] = _canonical_artifact_path(
            raw_roots[lifecycle], f"{field} visual_evidence.roots.{lifecycle}"
        )
    if len(set(roots.values())) != len(roots):
        raise DocumentationImpactError(
            f"{field} visual_evidence lifecycle roots must be distinct"
        )
    root_items = tuple(roots.items())
    for index, (left_name, left_root) in enumerate(root_items):
        for right_name, right_root in root_items[index + 1 :]:
            if _path_is_under(left_root, right_root) or _path_is_under(right_root, left_root):
                raise DocumentationImpactError(
                    f"{field} visual_evidence lifecycle roots overlap: "
                    f"{left_name}={left_root}, {right_name}={right_root}"
                )

    raw_exceptions = data["exceptions"]
    if not isinstance(raw_exceptions, list):
        raise DocumentationImpactError(
            f"{field} visual_evidence.exceptions must be a list"
        )
    exceptions: list[_VisualEvidenceException] = []
    exception_paths: list[str] = []
    for index, raw_exception in enumerate(raw_exceptions):
        item = _mapping(raw_exception, f"{field} visual_evidence.exceptions[{index}]")
        if set(item) != {"lifecycle", "paths"}:
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}] keys must be exactly "
                "lifecycle, paths"
            )
        lifecycle = item["lifecycle"]
        if lifecycle not in _VISUAL_EVIDENCE_LIFECYCLES:
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}] has an unknown lifecycle"
            )
        if lifecycle == "transient":
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}] cannot make transient evidence usable"
            )
        raw_paths = item["paths"]
        if not isinstance(raw_paths, list) or not raw_paths:
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}].paths must be a non-empty list"
            )
        paths = tuple(
            _canonical_artifact_path(
                path,
                f"{field} visual_evidence.exceptions[{index}].paths[{path_index}]",
            )
            for path_index, path in enumerate(raw_paths)
        )
        if len(set(paths)) != len(paths):
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}].paths contains duplicate entries"
            )
        if any(not _path_is_under(path, roots["frozen"]) for path in paths):
            raise DocumentationImpactError(
                f"{field} visual_evidence.exceptions[{index}] may only nest the frozen root"
            )
        exceptions.append(_VisualEvidenceException(lifecycle=lifecycle, paths=paths))
        exception_paths.extend(paths)

    if len(set(exception_paths)) != len(exception_paths):
        raise DocumentationImpactError(
            f"{field} visual_evidence.exceptions contains duplicate paths"
        )
    for index, left in enumerate(exception_paths):
        for right in exception_paths[index + 1 :]:
            if _path_is_under(left, right) or _path_is_under(right, left):
                raise DocumentationImpactError(
                    f"{field} visual_evidence.exceptions have ambiguous overlap: "
                    f"{left}, {right}"
                )

    expected_exceptions = {
        "current": frozenset(_ISSUE_167_EXCEPTION_FILES),
        "frozen": frozenset({_ISSUE_184_ROOT}),
    }
    actual_exceptions = {
        item.lifecycle: frozenset(item.paths) for item in exceptions
    }
    if (
        len(exceptions) != len(expected_exceptions)
        or actual_exceptions != expected_exceptions
    ):
        raise DocumentationImpactError(
            f"{field} visual_evidence.exceptions must exactly match the approved current and "
            "frozen exception policy"
        )
    return _VisualEvidenceConfig(
        raster_extensions=frozenset(normalized_extensions),
        roots=root_items,
        exceptions=tuple(exceptions),
    )


_DEFAULT_VISUAL_EVIDENCE_CONFIG = _VisualEvidenceConfig(
    raster_extensions=frozenset({".png", ".jpg", ".jpeg"}),
    roots=(
        ("current", "docs/user-guide/images/current"),
        ("frozen", "docs/17-evidence/images"),
        ("transient", ".artifacts"),
    ),
    exceptions=(
        _VisualEvidenceException(
            lifecycle="current",
            paths=tuple(sorted(_ISSUE_167_EXCEPTION_FILES)),
        ),
        _VisualEvidenceException(lifecycle="frozen", paths=(_ISSUE_184_ROOT,)),
    ),
)


def _load_visual_evidence_config(project: Path) -> _VisualEvidenceConfig:
    path = project / _DOCUMENTATION_MANIFEST
    if not path.exists():
        # Small contract fixtures predate the repository manifest and exercise
        # only source classification.  The real checkout always carries the
        # manifest; missing fixture metadata uses the same strict defaults.
        return _DEFAULT_VISUAL_EVIDENCE_CONFIG
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, DocumentationImpactError) as error:
        raise DocumentationImpactError(f"cannot read {_DOCUMENTATION_MANIFEST}: {error}") from error
    return _parse_visual_evidence_config(raw, _DOCUMENTATION_MANIFEST)


def _visual_evidence_lifecycle(
    path: str,
    config: _VisualEvidenceConfig,
) -> str | None:
    for exception in config.exceptions:
        if any(_exception_path_matches(path, configured) for configured in exception.paths):
            return exception.lifecycle
    for lifecycle, root in config.roots:
        if _path_is_under(path, root):
            return lifecycle
    return None


def _parse_exception(path: str, raw: object) -> DocumentationImpactException:
    data = _mapping(raw, path)
    expected_keys = {
        "schemaVersion",
        "issue",
        "sourceSha",
        "classification",
        "reason",
        "visualFiles",
        "verification",
    }
    if set(data) != expected_keys:
        raise DocumentationImpactError(
            f"{path} keys must be exactly {', '.join(sorted(expected_keys))}"
        )
    if data["schemaVersion"] != _EXCEPTION_SCHEMA:
        raise DocumentationImpactError(f"{path} has an unsupported schemaVersion")
    issue = data["issue"]
    if not isinstance(issue, str) or not re.fullmatch(r"#[1-9][0-9]*", issue):
        raise DocumentationImpactError(f"{path} issue must be a GitHub issue reference")
    expected_paths = {
        f"{_EXCEPTION_PREFIX}issue-{issue[1:]}.yaml",
        f"{_EXCEPTION_PREFIX}issue-{issue[1:]}.yml",
    }
    if path not in expected_paths:
        raise DocumentationImpactError(f"{path} filename must match issue {issue}")
    source_sha = data["sourceSha"]
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise DocumentationImpactError(f"{path} sourceSha must be a lowercase 40-character SHA")
    classification = data["classification"]
    if classification not in {
        _NON_USER_VISIBLE_CLASSIFICATION,
        _NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION,
        _NON_USER_VISIBLE_COMPOSITION_CLASSIFICATION,
    }:
        raise DocumentationImpactError(f"{path} classification is not allowed")
    reason = data["reason"]
    if not isinstance(reason, str) or len(reason.strip()) < 20:
        raise DocumentationImpactError(f"{path} reason must explain the non-user-visible boundary")

    verification = _mapping(data["verification"], f"{path} verification")
    parsed_relocations: list[_Relocation] = []
    composition_targets: tuple[str, ...] = ()
    characterization_tests: tuple[str, ...] = ()
    navigation_contract: str | None = None
    visual_patch_sha256: str | None = None
    attested_patch_sha256: str | None = None
    independent_audit: str | None = None
    product_owner_disposition: str | None = None
    if classification == _NON_USER_VISIBLE_CLASSIFICATION:
        verification_keys = {
            "unconsumedModules",
            "preservedComputedValueFiles",
        }
        if set(verification) != verification_keys:
            raise DocumentationImpactError(
                f"{path} verification keys must be exactly {', '.join(sorted(verification_keys))}"
            )
        unconsumed_modules = _string_list(
            verification["unconsumedModules"],
            f"{path} verification.unconsumedModules",
        )
        preserved_computed_value_files = _string_list(
            verification["preservedComputedValueFiles"],
            f"{path} verification.preservedComputedValueFiles",
        )
        import_only_files: tuple[str, ...] = ()
    elif classification == _NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION:
        verification_keys = {"importOnlyFiles", "relocations"}
        if set(verification) != verification_keys:
            raise DocumentationImpactError(
                f"{path} verification keys must be exactly {', '.join(sorted(verification_keys))}"
            )
        import_only_files = _path_list(
            verification["importOnlyFiles"],
            f"{path} verification.importOnlyFiles",
            allow_empty=True,
        )
        raw_relocations = verification["relocations"]
        if not isinstance(raw_relocations, list) or not raw_relocations:
            raise DocumentationImpactError(
                f"{path} verification.relocations must be a non-empty list"
            )
        for index, raw_relocation in enumerate(raw_relocations):
            relocation = _mapping(raw_relocation, f"{path} verification.relocations[{index}]")
            if set(relocation) != {"source", "target", "declarations"}:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] keys must be exactly "
                    "declarations, source, target"
                )
            source = _canonical_repo_path(
                relocation["source"],
                f"{path} verification.relocations[{index}].source",
            )
            target = _canonical_repo_path(
                relocation["target"],
                f"{path} verification.relocations[{index}].target",
            )
            if source == target:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] source and target must differ"
                )
            declarations = relocation["declarations"]
            if not isinstance(declarations, list) or not declarations:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}].declarations must be non-empty"
                )
            names: list[str] = []
            for name in declarations:
                if not isinstance(name, str) or _IDENTIFIER_RE.fullmatch(name) is None:
                    raise DocumentationImpactError(
                        f"{path} verification.relocations[{index}] has an invalid declaration name"
                    )
                names.append(name)
            if len(set(names)) != len(names):
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] has duplicate declarations"
                )
            parsed_relocations.append(
                _Relocation(source=source, target=target, declarations=tuple(names))
            )
        sources = [item.source for item in parsed_relocations]
        targets = [item.target for item in parsed_relocations]
        names = [name for item in parsed_relocations for name in item.declarations]
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            raise DocumentationImpactError(
                f"{path} verification.relocations contains duplicate source or target"
            )
        if len(set(names)) != len(names):
            raise DocumentationImpactError(
                f"{path} verification.relocations contains duplicate declaration names"
            )
        if set(sources) & set(import_only_files) or set(targets) & set(import_only_files):
            raise DocumentationImpactError(f"{path} verification paths overlap")
        unconsumed_modules = ()
        preserved_computed_value_files = ()
    else:
        verification_keys = {
            "attestedPatchSha256",
            "characterizationTests",
            "compositionTargets",
            "independentAudit",
            "navigationContract",
            "productOwnerDisposition",
            "visualPatchSha256",
        }
        if set(verification) != verification_keys:
            raise DocumentationImpactError(
                f"{path} verification keys must be exactly "
                f"{', '.join(sorted(verification_keys))}"
            )
        composition_targets = _path_list(
            verification["compositionTargets"],
            f"{path} verification.compositionTargets",
        )
        characterization_tests = _artifact_path_list(
            verification["characterizationTests"],
            f"{path} verification.characterizationTests",
        )
        navigation_contract = _canonical_artifact_path(
            verification["navigationContract"],
            f"{path} verification.navigationContract",
        )
        visual_patch_sha256 = verification["visualPatchSha256"]
        attested_patch_sha256 = verification["attestedPatchSha256"]
        for field, digest in (
            ("visualPatchSha256", visual_patch_sha256),
            ("attestedPatchSha256", attested_patch_sha256),
        ):
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise DocumentationImpactError(
                    f"{path} verification.{field} must be a lowercase SHA-256"
                )
        independent_audit = verification["independentAudit"]
        product_owner_disposition = verification["productOwnerDisposition"]
        if independent_audit != "APPROVE":
            raise DocumentationImpactError(
                f"{path} verification.independentAudit must be APPROVE"
            )
        if product_owner_disposition != "no-visible-change":
            raise DocumentationImpactError(
                f"{path} verification.productOwnerDisposition must be no-visible-change"
            )
        unconsumed_modules = ()
        preserved_computed_value_files = ()
        import_only_files = ()
    return DocumentationImpactException(
        path=path,
        issue=issue,
        source_sha=source_sha,
        classification=classification,
        reason=reason.strip(),
        visual_files=_string_list(data["visualFiles"], f"{path} visualFiles"),
        unconsumed_modules=unconsumed_modules,
        preserved_computed_value_files=preserved_computed_value_files,
        import_only_files=import_only_files,
        relocations=tuple(parsed_relocations),
        composition_targets=composition_targets,
        characterization_tests=characterization_tests,
        navigation_contract=navigation_contract,
        visual_patch_sha256=visual_patch_sha256,
        attested_patch_sha256=attested_patch_sha256,
        independent_audit=independent_audit,
        product_owner_disposition=product_owner_disposition,
    )


def _load_changed_exception(
    project: Path,
    evidence: set[str],
) -> DocumentationImpactException | None:
    candidates = sorted(
        path
        for path in evidence
        if path.startswith(_EXCEPTION_PREFIX) and path.endswith((".yaml", ".yml"))
    )
    if not candidates:
        return None
    if len(candidates) != 1:
        raise DocumentationImpactError("exactly one documentation-impact exception may change")
    path = candidates[0]
    try:
        raw = yaml.load((project / path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError, DocumentationImpactError) as error:
        raise DocumentationImpactError(f"cannot read {path}: {error}") from error
    return _parse_exception(path, raw)


def _load_range_composition_attestation(
    project: Path,
    merge_base: str,
    visual_files: set[str],
) -> DocumentationImpactException | None:
    candidates: list[DocumentationImpactException] = []
    paths = sorted(
        path
        for path in _git_lines(
            project,
            ["ls-tree", "-r", "--name-only", "origin/main", "--", _EXCEPTION_PREFIX],
        )
        if path.endswith((".yaml", ".yml"))
    )
    for path in paths:
        result = subprocess.run(
            ["git", "show", f"origin/main:{path}"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            raw = yaml.load(result.stdout, Loader=_UniqueKeyLoader)
        except (yaml.YAMLError, DocumentationImpactError) as error:
            raise DocumentationImpactError(f"cannot read origin/main:{path}: {error}") from error
        data = _mapping(raw, f"origin/main:{path}")
        if data.get("classification") != _NON_USER_VISIBLE_COMPOSITION_CLASSIFICATION:
            continue
        exception = _parse_exception(path, data)
        if set(exception.visual_files) == visual_files and _is_ancestor(
            project, exception.source_sha, merge_base
        ):
            candidates.append(exception)
    if len(candidates) > 1:
        raise DocumentationImpactError(
            "origin/main contains multiple composition attestations for this exact diff"
        )
    return candidates[0] if candidates else None


def _patch_bytes(project: Path, source_sha: str, paths: Iterable[str]) -> bytes:
    selected = sorted(set(paths))
    if not selected:
        raise DocumentationImpactError("cannot fingerprint an empty documentation-impact patch")
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--no-ext-diff",
                "--binary",
                "--full-index",
                f"{source_sha}...HEAD",
                "--",
                *selected,
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError("cannot fingerprint the attested Git patch") from error
    return result.stdout


def _patch_sha256(project: Path, source_sha: str, paths: Iterable[str]) -> str:
    return hashlib.sha256(_patch_bytes(project, source_sha, paths)).hexdigest()


def _git_blob_bytes(project: Path, revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=project,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise DocumentationImpactError(f"cannot read {path} at {revision}")
    return result.stdout


def _canonical_frontend_guard_bytes(value: bytes, field: str) -> bytes:
    pattern = re.compile(
        rb'(?m)^(  "sourceSha"[ \t]*:[ \t]*")([0-9a-f]{40})(",\r?)$'
    )
    matches = tuple(pattern.finditer(value))
    if len(matches) != 1:
        raise DocumentationImpactError(
            f"{field} must contain exactly one canonical top-level sourceSha line"
        )
    return pattern.sub(
        lambda match: match.group(1)
        + _FRONTEND_GUARD_SOURCE_SHA_SENTINEL
        + match.group(3),
        value,
        count=1,
    )


def _attested_patch_sha256(project: Path, source_sha: str, paths: Iterable[str]) -> str:
    selected = set(paths)
    if _FRONTEND_GUARD_BASELINE not in selected:
        raise DocumentationImpactError(
            f"attested patch must include {_FRONTEND_GUARD_BASELINE}"
        )
    other_patch = _patch_bytes(
        project,
        source_sha,
        selected - {_FRONTEND_GUARD_BASELINE},
    )
    base_guard = _canonical_frontend_guard_bytes(
        _git_blob_bytes(project, source_sha, _FRONTEND_GUARD_BASELINE),
        f"{_FRONTEND_GUARD_BASELINE} at {source_sha}",
    )
    current_guard = _canonical_frontend_guard_bytes(
        _git_blob_bytes(project, "HEAD", _FRONTEND_GUARD_BASELINE),
        f"{_FRONTEND_GUARD_BASELINE} at HEAD",
    )
    canonical_guard = b"".join(
        (
            b"cmp.frontend-guard-attested-patch.v1\0",
            len(base_guard).to_bytes(8, "big"),
            base_guard,
            len(current_guard).to_bytes(8, "big"),
            current_guard,
        )
    )
    return hashlib.sha256(other_patch + canonical_guard).hexdigest()


def _is_ancestor(project: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=project,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _production_source_paths(project: Path) -> Iterable[Path]:
    source = project / "apps/web/src"
    if not source.exists():
        return ()
    return (
        path
        for path in source.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".css", ".ts", ".tsx"}
        and not _is_test_path(path.relative_to(project).as_posix())
    )


def _normalize_css(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _closing_brace(text: str, opening: int, source: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    raise DocumentationImpactError(f"cannot parse unmatched CSS block in {source}")


def _css_declarations(body: str, source: str, selector: str) -> tuple[tuple[str, str], ...]:
    declarations: list[tuple[str, str]] = []
    for raw_declaration in body.split(";"):
        declaration = raw_declaration.strip()
        if not declaration:
            continue
        if ":" not in declaration:
            raise DocumentationImpactError(
                f"cannot prove CSS declaration {declaration!r} in {source} ({selector})"
            )
        property_name, value = declaration.split(":", 1)
        normalized_property = property_name.strip()
        normalized_value = _normalize_css(value)
        if not normalized_property or not normalized_value:
            raise DocumentationImpactError(
                f"cannot prove empty CSS declaration in {source} ({selector})"
            )
        declarations.append((normalized_property, normalized_value))
    if len({name for name, _value in declarations}) != len(declarations):
        raise DocumentationImpactError(
            f"cannot prove duplicate CSS declarations in {source} ({selector})"
        )
    return tuple(declarations)


def _css_rules(
    text: str,
    source: str,
    context: tuple[str, ...] = (),
) -> tuple[_CssRule, ...]:
    without_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    rules: list[_CssRule] = []
    cursor = 0
    while True:
        opening = without_comments.find("{", cursor)
        if opening < 0:
            if without_comments[cursor:].strip().strip(";"):
                raise DocumentationImpactError(f"cannot parse trailing CSS in {source}")
            break
        header = without_comments[cursor:opening].strip()
        if ";" in header:
            header = header.rsplit(";", 1)[1].strip()
        if not header:
            raise DocumentationImpactError(f"cannot parse empty CSS selector in {source}")
        closing = _closing_brace(without_comments, opening, source)
        body = without_comments[opening + 1 : closing]
        normalized_header = _normalize_css(header)
        if normalized_header.startswith(("@media ", "@supports ", "@container ", "@layer ")):
            rules.extend(_css_rules(body, source, (*context, normalized_header)))
        elif normalized_header.startswith("@"):
            raise DocumentationImpactError(
                f"cannot prove CSS at-rule {normalized_header!r} in {source}"
            )
        else:
            rules.append(
                _CssRule(
                    context=context,
                    selector=normalized_header,
                    declarations=_css_declarations(body, source, normalized_header),
                )
            )
        cursor = closing + 1
    return tuple(rules)


def _css_rule_map(
    rules: tuple[_CssRule, ...],
    source: str,
) -> dict[tuple[tuple[str, ...], str], _CssRule]:
    mapped: dict[tuple[tuple[str, ...], str], _CssRule] = {}
    for rule in rules:
        key = (rule.context, rule.selector)
        if key in mapped:
            raise DocumentationImpactError(
                f"cannot prove repeated CSS selector {rule.selector!r} in {source}"
            )
        mapped[key] = rule
    return mapped


def _base_file_text(project: Path, source_sha: str, path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "show", f"{source_sha}:{path}"],
            cwd=project,
            check=True,
            capture_output=True,
        )
        return result.stdout.decode("utf-8", errors="strict")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise DocumentationImpactError(
            f"cannot read {path} at exception sourceSha {source_sha}"
        ) from error


def _class_selectors(selector: str) -> set[str]:
    return set(re.findall(r"\.(-?[_a-zA-Z][_a-zA-Z0-9-]*)", selector))


def _required_positive_classes(selector: str, source: str) -> set[str]:
    without_attributes = re.sub(r"\[[^\]]*\]", "", selector)
    if "[" in without_attributes or "]" in without_attributes or ":" in without_attributes:
        raise DocumentationImpactError(
            f"cannot prove new CSS selector {selector!r} in {source} requires "
            "a positive isolated class"
        )
    return _class_selectors(without_attributes)


def _prove_preserved_css(
    project: Path,
    exception: DocumentationImpactException,
    *,
    base_files: Mapping[str, str] | None = None,
) -> tuple[set[str], set[str]]:
    rule_map = dict[tuple[tuple[str, ...], str], _CssRule]
    parsed: dict[str, tuple[rule_map, rule_map]] = {}
    all_base_classes: set[str] = set()
    new_variables: dict[str, str] = {}
    replacements: list[tuple[str, str, str, str]] = []

    for path in exception.preserved_computed_value_files:
        current_path = project / path
        try:
            current_text = current_path.read_text(encoding="utf-8")
        except OSError as error:
            raise DocumentationImpactError(f"cannot read changed CSS {path}: {error}") from error
        if base_files is None:
            base_text = _base_file_text(project, exception.source_sha, path)
        else:
            try:
                base_text = base_files[path]
            except KeyError as error:
                raise DocumentationImpactError(
                    f"test base content is missing for {path}"
                ) from error
        base_rules = _css_rule_map(_css_rules(base_text, path), path)
        current_rules = _css_rule_map(_css_rules(current_text, path), path)
        parsed[path] = (base_rules, current_rules)
        all_base_classes.update(
            class_name
            for rule in base_rules.values()
            for class_name in _class_selectors(rule.selector)
        )

        missing_rules = set(base_rules) - set(current_rules)
        if missing_rules:
            raise DocumentationImpactError(
                f"{exception.path} cannot prove unchanged appearance: {path} removes CSS rules"
            )
        for key, base_rule in base_rules.items():
            current_rule = current_rules[key]
            base_declarations = dict(base_rule.declarations)
            current_declarations = dict(current_rule.declarations)
            missing_declarations = set(base_declarations) - set(current_declarations)
            if missing_declarations:
                raise DocumentationImpactError(
                    f"{exception.path} cannot prove unchanged appearance: {path} removes "
                    f"declarations from {base_rule.selector}"
                )
            for property_name, current_value in current_declarations.items():
                if property_name not in base_declarations:
                    if (
                        not base_rule.context
                        and base_rule.selector == ":root"
                        and property_name.startswith("--")
                    ):
                        if property_name in new_variables:
                            raise DocumentationImpactError(
                                f"{exception.path} defines new CSS variable "
                                f"{property_name} more than once"
                            )
                        new_variables[property_name] = current_value
                        continue
                    raise DocumentationImpactError(
                        f"{exception.path} cannot prove unchanged appearance: {path} adds "
                        f"a declaration to existing selector {base_rule.selector}"
                    )
                base_value = base_declarations[property_name]
                if current_value != base_value:
                    replacements.append(
                        (path, f"{base_rule.selector} {property_name}", base_value, current_value)
                    )

    variable_reference = re.compile(r"var\((--[-_a-zA-Z0-9]+)\)")
    for path, declaration, base_value, current_value in replacements:
        match = variable_reference.fullmatch(current_value)
        if match is None or new_variables.get(match.group(1)) != base_value:
            raise DocumentationImpactError(
                f"{exception.path} cannot prove unchanged appearance: {path} changes "
                f"{declaration} from {base_value!r} to {current_value!r}"
            )

    derived_selectors: set[str] = set()
    for path, (base_rules, current_rules) in parsed.items():
        for key in set(current_rules) - set(base_rules):
            selector = current_rules[key].selector
            branches = [branch.strip() for branch in selector.split(",")]
            for branch in branches:
                novel_classes = _required_positive_classes(branch, path) - all_base_classes
                if not novel_classes:
                    raise DocumentationImpactError(
                        f"{exception.path} cannot prove new CSS selector {branch!r} in {path} "
                        "is isolated from existing product markup"
                    )
                derived_selectors.update(novel_classes)
    if not derived_selectors:
        raise DocumentationImpactError(
            f"{exception.path} must add an automatically derivable isolated CSS selector"
        )
    return derived_selectors, set(new_variables)


@dataclass(frozen=True, slots=True)
class _TsToken:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Declaration:
    name: str
    kind: Literal["type", "value"]
    start: int
    end: int
    export: bool
    defining_start: int
    defining_end: int


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    imported: str
    local: str
    kind: Literal["type", "value"]
    raw: str


@dataclass(frozen=True, slots=True)
class _StaticImport:
    start: int
    end: int
    text: str
    module: str
    module_quote: str
    module_start: int
    module_end: int
    bindings: tuple[_ImportBinding, ...]
    form: str
    type_only: bool
    has_default_or_namespace: bool
    side_effect: bool


def _line_start(text: str, offset: int) -> int:
    return text.rfind("\n", 0, offset) + 1


def _scan_ts(text: str, *, include_template_expressions: bool = False) -> tuple[_TsToken, ...]:
    """Scan enough TypeScript lexical structure to fail closed on ambiguous source."""
    tokens: list[_TsToken] = []
    i = 0
    previous: _TsToken | None = None

    def add(kind: str, start: int, end: int) -> None:
        nonlocal previous
        token = _TsToken(kind=kind, text=text[start:end], start=start, end=end)
        tokens.append(token)
        previous = token

    def regex_allowed() -> bool:
        if previous is None:
            return True
        if previous.kind in {"literal", "template", "regex"}:
            return False
        if previous.kind == "identifier" and previous.text not in {
            "return",
            "throw",
            "case",
            "delete",
            "void",
            "typeof",
            "instanceof",
            "in",
            "of",
            "yield",
            "await",
        }:
            return False
        return previous.text not in {
            ")",
            "]",
            "}",
            "<",
            "++",
            "--",
        }

    def skip_string(start: int, quote: str) -> int:
        index = start + 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == quote:
                return index + 1
            if char in "\r\n":
                raise DocumentationImpactError("unterminated string literal")
            index += 1
        raise DocumentationImpactError("unterminated string literal")

    def skip_regex(start: int) -> int:
        index = start + 1
        in_class = False
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                index += 1
                while index < len(text) and (text[index].isalpha() or text[index].isdigit()):
                    index += 1
                return index
            elif char in "\r\n":
                raise DocumentationImpactError("unterminated regular expression literal")
            index += 1
        raise DocumentationImpactError("unterminated regular expression literal")

    def skip_template(start: int) -> int:
        index = start + 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "`":
                return index + 1
            if (
                char == "$"
                and index + 1 < len(text)
                and text[index + 1] == "{"
                and include_template_expressions
            ):
                # Scan the expression in place, retaining its identifier tokens.  A
                # nested scanner is intentionally conservative and requires balanced
                # braces before returning to the template text.
                depth = 1
                index += 2
                expression_start = index
                quote: str | None = None
                escaped = False
                while index < len(text) and depth:
                    current = text[index]
                    if quote is not None:
                        if escaped:
                            escaped = False
                        elif current == "\\":
                            escaped = True
                        elif current == quote:
                            quote = None
                        index += 1
                        continue
                    if current in {"'", '"'}:
                        quote = current
                    elif current == "`":
                        # Nested templates are accepted only when they close.
                        nested_end = skip_template(index)
                        index = nested_end
                        continue
                    elif current == "{":
                        depth += 1
                    elif current == "}":
                        depth -= 1
                    index += 1
                if depth:
                    raise DocumentationImpactError("unterminated template expression")
                nested = _scan_ts(
                    text[expression_start : index - 1],
                    include_template_expressions=True,
                )
                for token in nested:
                    tokens.append(
                        _TsToken(
                            token.kind,
                            token.text,
                            token.start + expression_start,
                            token.end + expression_start,
                        )
                    )
                index += 0
                continue
            index += 1
        raise DocumentationImpactError("unterminated template literal")

    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i + 2)
            i = len(text) if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise DocumentationImpactError("unterminated block comment")
            i = end + 2
            continue
        if (
            char == "'"
            and previous is not None
            and previous.kind == "identifier"
            and previous.end == i
        ):
            add("punctuation", i, i + 1)
            i += 1
            continue
        if char in {'"', "'"}:
            end = skip_string(i, char)
            add("literal", i, end)
            i = end
            continue
        if char == "`":
            end = skip_template(i)
            add("template", i, end)
            i = end
            continue
        if char == "/" and regex_allowed() and not text.startswith("/=", i):
            end = skip_regex(i)
            add("regex", i, end)
            i = end
            continue
        match = _IDENTIFIER_RE.match(text, i)
        if match:
            add("identifier", i, match.end())
            i = match.end()
            continue
        number_match = _NUMBER_LITERAL_RE.match(text, i)
        if number_match:
            add("literal", i, number_match.end())
            i = number_match.end()
            continue
        # Keep multi-character operators together only where this affects parsing.
        operator = next(
            (
                candidate
                for candidate in (
                    "=>",
                    "===",
                    "!==",
                    "==",
                    "!=",
                    "<=",
                    ">=",
                    "&&",
                    "||",
                    "??",
                    "++",
                    "--",
                    "?.",
                    "...",
                    "**",
                )
                if text.startswith(candidate, i)
            ),
            char,
        )
        add("punctuation", i, i + len(operator))
        i += len(operator)
    return tuple(sorted(tokens, key=lambda token: (token.start, token.end)))


def _matching_token(tokens: tuple[_TsToken, ...], index: int, opening: str, closing: str) -> int:
    depth = 0
    for cursor in range(index, len(tokens)):
        token = tokens[cursor].text
        if token == opening:
            depth += 1
        elif token == closing:
            depth -= 1
            if depth == 0:
                return cursor
    raise DocumentationImpactError("unbalanced TypeScript declaration")


def _validate_function_return_annotation(
    tokens: tuple[_TsToken, ...], start: int, end: int
) -> None:
    if start >= end or tokens[start].text != ":":
        return
    parts = tokens[start + 1 : end]
    if not parts or not any(token.kind == "identifier" for token in parts):
        raise DocumentationImpactError("function return annotation must contain an identifier")
    angle = square = 0
    for token in parts:
        if token.kind in {"literal", "template", "regex"}:
            raise DocumentationImpactError("function return annotation contains a literal")
        if token.text in {"{", "}", "(", ")", "=", "=>", ";"}:
            raise DocumentationImpactError("unsupported function return annotation")
        if token.text == "<":
            angle += 1
        elif token.text == ">":
            angle -= 1
            if angle < 0:
                raise DocumentationImpactError("unbalanced function return annotation")
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
            if square < 0:
                raise DocumentationImpactError("unbalanced function return annotation")
        elif token.kind == "punctuation" and token.text not in {
            ".",
            ",",
            "|",
            "&",
            "?",
            "<",
            ">",
            "[",
            "]",
        }:
            raise DocumentationImpactError("unsupported function return annotation")
    if angle or square:
        raise DocumentationImpactError("unbalanced function return annotation")


def _find_declarations(
    text: str,
    *,
    required_names: set[str] | None = None,
) -> tuple[_Declaration, ...]:
    tokens = _scan_ts(text)
    declarations: list[_Declaration] = []
    found_names: set[str] = set()

    def record(declaration: _Declaration) -> bool:
        declarations.append(declaration)
        found_names.add(declaration.name)
        if not required_names:
            return False
        return required_names <= found_names

    brace = paren = square = 0
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if token.text == "{":
            brace += 1
            cursor += 1
            continue
        if token.text == "}":
            brace -= 1
            if brace < 0:
                raise DocumentationImpactError("unbalanced TypeScript braces")
            cursor += 1
            continue
        if token.text == "(":
            paren += 1
            cursor += 1
            continue
        if token.text == ")":
            paren -= 1
            if paren < 0:
                raise DocumentationImpactError("unbalanced TypeScript parentheses")
            cursor += 1
            continue
        if token.text == "[":
            square += 1
            cursor += 1
            continue
        if token.text == "]":
            square -= 1
            if square < 0:
                raise DocumentationImpactError("unbalanced TypeScript brackets")
            cursor += 1
            continue
        if brace or paren or square:
            cursor += 1
            continue
        export = token.text == "export"
        keyword_index = cursor + 1 if export else cursor
        if keyword_index >= len(tokens) or _line_start(text, token.start) != token.start:
            cursor += 1
            continue
        keyword = tokens[keyword_index].text
        if keyword not in {"type", "const", "function"}:
            cursor += 1
            continue
        keyword_token = tokens[keyword_index]
        if export and keyword_token.start != token.end + 1:
            raise DocumentationImpactError("export declaration must use a single ASCII space")
        if keyword_index + 1 >= len(tokens):
            raise DocumentationImpactError("declaration is missing its name")
        name_token = tokens[keyword_index + 1]
        if name_token.kind != "identifier":
            raise DocumentationImpactError("declaration name must be an identifier")
        name = name_token.text
        if keyword == "type":
            if keyword_index + 2 >= len(tokens) or tokens[keyword_index + 2].text != "=":
                raise DocumentationImpactError("only simple type declarations are supported")
            depth = 0
            end_index: int | None = None
            for probe in range(keyword_index + 3, len(tokens)):
                value = tokens[probe].text
                if value in {"{", "(", "[", "<"}:
                    depth += 1
                elif value in {"}", ")", "]", ">"}:
                    depth -= 1
                    if depth < 0:
                        raise DocumentationImpactError("unbalanced type declaration")
                elif value == ";" and depth == 0:
                    end_index = probe
                    break
            if end_index is None:
                raise DocumentationImpactError("type declaration requires a semicolon")
            if record(
                _Declaration(
                    name=name,
                    kind="type",
                    start=token.start,
                    end=tokens[end_index].end,
                    export=export,
                    defining_start=name_token.start,
                    defining_end=name_token.end,
                )
            ):
                return tuple(declarations)
            cursor = end_index + 1
            continue
        if keyword == "const":
            equal_index: int | None = None
            for probe in range(keyword_index + 2, len(tokens)):
                if tokens[probe].text == "=":
                    equal_index = probe
                    break
                if tokens[probe].text in {";", "const", "function", "type"}:
                    break
            if equal_index is None:
                raise DocumentationImpactError("const declaration requires an initializer")
            if equal_index == keyword_index + 2 and tokens[equal_index - 1].text != name:
                raise DocumentationImpactError("const declaration name is invalid")
            depth = 0
            end_index = None
            for probe in range(equal_index + 1, len(tokens)):
                value = tokens[probe].text
                if value in {"{", "(", "[", "<"}:
                    depth += 1
                elif value in {"}", ")", "]", ">"}:
                    depth -= 1
                    if depth < 0:
                        raise DocumentationImpactError("unbalanced const declaration")
                elif value == ";" and depth == 0:
                    end_index = probe
                    break
            if end_index is None:
                raise DocumentationImpactError("const declaration requires a semicolon")
            if record(
                _Declaration(
                    name=name,
                    kind="value",
                    start=token.start,
                    end=tokens[end_index].end,
                    export=export,
                    defining_start=name_token.start,
                    defining_end=name_token.end,
                )
            ):
                return tuple(declarations)
            cursor = end_index + 1
            continue
        # function
        open_index = keyword_index + 2
        if open_index >= len(tokens) or tokens[open_index].text != "(":
            raise DocumentationImpactError("only non-generic function declarations are supported")
        close_index = _matching_token(tokens, open_index, "(", ")")
        body_index = close_index + 1
        if body_index < len(tokens) and tokens[body_index].text == ":":
            body_index += 1
            while body_index < len(tokens) and tokens[body_index].text != "{":
                body_index += 1
        _validate_function_return_annotation(tokens, close_index + 1, body_index)
        if body_index >= len(tokens) or tokens[body_index].text != "{":
            raise DocumentationImpactError("function declaration requires a body")
        body_end = _matching_token(tokens, body_index, "{", "}")
        if record(
            _Declaration(
                name=name,
                kind="value",
                start=token.start,
                end=tokens[body_end].end,
                export=export,
                defining_start=name_token.start,
                defining_end=name_token.end,
            )
        ):
            return tuple(declarations)
        cursor = body_end + 1
    if brace or paren or square:
        raise DocumentationImpactError("unbalanced TypeScript source")
    return tuple(declarations)


def _static_imports(text: str) -> tuple[_StaticImport, ...]:
    """Parse top-level static import statements, retaining exact source spans."""
    tokens = _scan_ts(text)
    imports: list[_StaticImport] = []
    i = 0
    brace = paren = square = 0
    while i < len(tokens):
        token = tokens[i]
        if token.text == "{":
            brace += 1
        elif token.text == "}":
            brace -= 1
        elif token.text == "(":
            paren += 1
        elif token.text == ")":
            paren -= 1
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
        if brace or paren or square or token.text != "import":
            i += 1
            continue
        # Dynamic import(...) is residual code, never a static import.
        if i + 1 < len(tokens) and tokens[i + 1].text == "(":
            i += 1
            continue
        statement_end = None
        import_brace = import_paren = import_square = 0
        for probe in range(i + 1, len(tokens)):
            probe_token = tokens[probe]
            if probe_token.text == ";":
                statement_end = probe
                break
            if (
                not (import_brace or import_paren or import_square)
                and "\n" in text[tokens[probe - 1].end : probe_token.start]
                and probe_token.text not in {"from", "as", "type"}
            ):
                # Bare import declarations may omit semicolons only at their own
                # risk; fail closed rather than treating ASI as a relocation.
                break
            if probe_token.text == "{":
                import_brace += 1
            elif probe_token.text == "}":
                import_brace -= 1
            elif probe_token.text == "(":
                import_paren += 1
            elif probe_token.text == ")":
                import_paren -= 1
            elif probe_token.text == "[":
                import_square += 1
            elif probe_token.text == "]":
                import_square -= 1
        if statement_end is None:
            raise DocumentationImpactError("static import requires a semicolon")
        end = tokens[statement_end].end
        start = token.start
        statement = text[start:end]
        module_match = list(re.finditer(r"(['\"])([^'\"]*)\1", statement))
        if not module_match:
            raise DocumentationImpactError("static import requires a quoted module literal")
        module_match_item = module_match[-1]
        module = module_match_item.group(2)
        module_quote = module_match_item.group(1)
        module_start = start + module_match_item.start(2)
        module_end = start + module_match_item.end(2)
        prefix = statement[: module_match_item.start()]
        type_only = bool(re.match(r"import\s+type(?:\s|\{)", prefix))
        side_effect = bool(re.match(r"import\s*['\"]", statement))
        has_default_or_namespace = False
        bindings: list[_ImportBinding] = []
        brace_match = re.search(r"\{(?P<body>.*)\}", prefix, flags=re.DOTALL)
        if brace_match:
            body = brace_match.group("body")
            for raw_item in body.split(","):
                item = raw_item.strip()
                if not item:
                    continue
                item_type: Literal["type", "value"] = (
                    "type" if type_only or re.match(r"type\s+", item) else "value"
                )
                if item_type == "type":
                    item = re.sub(r"^type\s+", "", item)
                alias_parts = re.split(r"\s+as\s+", item)
                if len(alias_parts) > 2:
                    raise DocumentationImpactError("malformed named import alias")
                imported = alias_parts[0].strip()
                local = alias_parts[-1].strip()
                if (
                    _IDENTIFIER_RE.fullmatch(imported) is None
                    or _IDENTIFIER_RE.fullmatch(local) is None
                ):
                    raise DocumentationImpactError("named imports must use identifiers")
                bindings.append(_ImportBinding(imported, local, item_type, raw_item))
        before_brace = prefix.split("{", 1)[0]
        before_brace = re.sub(r"^import\s+type\s*", "", before_brace)
        before_brace = re.sub(r"\s+from\s*$", "", before_brace).rstrip()
        if before_brace.strip():
            default_part = before_brace.replace("import", "", 1).strip().rstrip(",").strip()
            if default_part:
                has_default_or_namespace = True
                if default_part.startswith("*"):
                    namespace_match = re.search(
                        r"\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)", default_part
                    )
                    if namespace_match:
                        bindings.append(
                            _ImportBinding(
                                "*",
                                namespace_match.group(1),
                                "type" if type_only else "value",
                                default_part,
                            )
                        )
                    else:
                        raise DocumentationImpactError("malformed namespace import")
                elif _IDENTIFIER_RE.fullmatch(default_part):
                    bindings.append(
                        _ImportBinding(
                            "default", default_part, "type" if type_only else "value", default_part
                        )
                    )
                elif default_part:
                    raise DocumentationImpactError("malformed default import")
        form = "side-effect" if side_effect else ("type" if type_only else "named")
        imports.append(
            _StaticImport(
                start=start,
                end=end,
                text=statement,
                module=module,
                module_quote=module_quote,
                module_start=module_start,
                module_end=module_end,
                bindings=tuple(bindings),
                form=form,
                type_only=type_only,
                has_default_or_namespace=has_default_or_namespace,
                side_effect=side_effect,
            )
        )
        i = statement_end + 1
    return tuple(imports)


def _remove_spans(text: str, spans: Iterable[tuple[int, int]]) -> str:
    result = text
    for start, end in sorted(spans, reverse=True):
        # Whole-line declarations/imports remove their newline as well.  This
        # keeps the residual comparison byte-stable after an extraction.
        left = start
        right = end
        if _line_start(result, start) == start:
            if right < len(result) and result[right : right + 2] == "\r\n":
                right += 2
            elif right < len(result) and result[right] == "\n":
                right += 1
        result = result[:left] + result[right:]
    return result


def _nonblank_lines(text: str) -> str:
    """Compare residual source by exact nonblank lines, ignoring extraction gaps."""
    return "\n".join(line for line in text.split("\n") if line.strip())


def _identifier_occurrences(
    text: str, *, excluded: Iterable[tuple[int, int]] = ()
) -> tuple[str, ...]:
    excluded_spans = tuple(excluded)
    tokens = _scan_ts(text, include_template_expressions=True)
    occurrences: list[str] = []
    for token in tokens:
        if token.kind != "identifier":
            continue
        if any(start <= token.start < end for start, end in excluded_spans):
            continue
        occurrences.append(token.text)
    return tuple(occurrences)


def _git_blob_paths(project: Path, source_sha: str) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "-z", source_sha, "--", "apps/web/src"],
            cwd=project,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError("cannot enumerate merge-base source files") from error
    paths: set[str] = set()
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        header, path_bytes = entry.split(b"\t", 1)
        mode, object_type, _sha = header.decode("ascii").split()
        path = path_bytes.decode("utf-8").replace("\\", "/")
        if object_type != "blob" or mode == "120000":
            continue
        paths.add(path)
    return paths


def _current_source_paths(project: Path, entries: Mapping[str, bool]) -> set[str]:
    tracked = _git_lines(project, ["ls-files"])
    candidates = {path for path in tracked if path.startswith("apps/web/src/")}
    candidates.update(
        path for path, supplied in entries.items() if supplied and path.startswith("apps/web/src/")
    )
    result: set[str] = set()
    for path in candidates:
        candidate = project / Path(*path.split("/"))
        try:
            if candidate.is_file() and not candidate.is_symlink():
                result.add(path)
        except OSError:
            continue
    return result


def _read_current(project: Path, path: str) -> str:
    candidate = project / Path(*path.split("/"))
    if candidate.is_symlink() or not candidate.is_file():
        raise DocumentationImpactError(f"{path} must be a current regular file")
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError as error:
        raise DocumentationImpactError(f"cannot read current source {path}: {error}") from error


def _read_base(
    project: Path, source_sha: str, path: str, base_files: Mapping[str, str] | None
) -> str:
    if base_files is not None and path in base_files:
        return base_files[path]
    return _base_file_text(project, source_sha, path)


def _resolve_relative_module(
    importer: str,
    specifier: str,
    universe: set[str],
    *,
    project: Path | None = None,
) -> str:
    if not specifier or "\\" in specifier or not specifier.startswith(("./", "../")):
        raise DocumentationImpactError(f"unsupported relative import {specifier!r} in {importer}")
    if any(value in specifier for value in ("?", "#")) or specifier.endswith("/"):
        raise DocumentationImpactError(f"ambiguous import specifier {specifier!r}")
    parent = PurePosixPath(importer).parent
    joined = PurePosixPath(parent, specifier)
    parts: list[str] = []
    for part in joined.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise DocumentationImpactError(f"import escapes apps/web/src: {specifier!r}")
            parts.pop()
        else:
            parts.append(part)
    resolved_base = "/".join(parts)
    if not resolved_base.startswith("apps/web/src/"):
        raise DocumentationImpactError(f"import escapes apps/web/src: {specifier!r}")
    suffix = PurePosixPath(resolved_base).suffix
    candidates: list[str]
    if suffix:
        if suffix not in {".ts", ".tsx"}:
            raise DocumentationImpactError(f"unsupported import suffix {specifier!r}")
        candidates = [resolved_base]
    else:
        candidates = [
            f"{resolved_base}.ts",
            f"{resolved_base}.tsx",
            f"{resolved_base}/index.ts",
            f"{resolved_base}/index.tsx",
        ]
    existing: list[str] = []
    for candidate in candidates:
        if candidate not in universe:
            continue
        if project is not None:
            path = project / Path(*candidate.split("/"))
            if path.is_symlink() or not path.is_file():
                continue
        existing.append(candidate)
    if len(existing) != 1:
        raise DocumentationImpactError(
            f"import {specifier!r} from {importer} resolves to {len(existing)} candidates"
        )
    return existing[0]


def _binding_tuple(import_item: _StaticImport) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (binding.imported, binding.local, binding.kind) for binding in import_item.bindings
    )


_EXPORT_STAR_PATTERN = re.compile(
    r"^[ \t]*export[ \t]+\*[ \t]+from[ \t]+(?P<quote>['\"])"
    r"(?P<module>[^'\"\r\n]+)(?P=quote)[ \t]*;[ \t]*$",
    re.MULTILINE,
)
_EXPORT_NAMED_PATTERN = re.compile(
    r"^[ \t]*export[ \t]*\{(?P<body>.*?)\}[ \t]*from[ \t]+(?P<quote>['\"])"
    r"(?P<module>[^'\"\r\n]+)(?P=quote)[ \t]*;[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
_EXPORT_LOCAL_NAMED_PATTERN = re.compile(
    r"^[ \t]*export[ \t]*\{(?P<body>.*?)\}[ \t]*;[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class _RuntimeDeclarationFingerprint:
    exported: bool
    declaration_kind: Literal["class", "const", "function"]
    tokens: tuple[tuple[str, str], ...]
    identifiers: tuple[str, ...]


def _export_star_modules(text: str) -> tuple[str, ...]:
    return tuple(match.group("module") for match in _EXPORT_STAR_PATTERN.finditer(text))


def _named_runtime_reexports(text: str) -> tuple[tuple[str, str, str], ...]:
    result: list[tuple[str, str, str]] = []
    for match in _EXPORT_NAMED_PATTERN.finditer(text):
        module = match.group("module")
        for raw_binding in match.group("body").split(","):
            binding = raw_binding.strip()
            if not binding or binding.startswith("type "):
                continue
            names = re.split(r"\s+as\s+", binding)
            if len(names) == 1:
                imported = exported = names[0]
            elif len(names) == 2:
                imported, exported = names
            else:
                return ()
            if not all(re.fullmatch(r"[A-Za-z_$][\w$]*", name) for name in names):
                return ()
            result.append((imported, exported, module))
    return tuple(result)


def _named_local_runtime_exports(text: str) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for match in _EXPORT_LOCAL_NAMED_PATTERN.finditer(text):
        for raw_binding in match.group("body").split(","):
            binding = raw_binding.strip()
            if not binding or binding.startswith("type "):
                continue
            names = re.split(r"\s+as\s+", binding)
            if len(names) == 1:
                local = exported = names[0]
            elif len(names) == 2:
                local, exported = names
            else:
                return ()
            if not all(re.fullmatch(r"[A-Za-z_$][\w$]*", name) for name in names):
                return ()
            result.append((local, exported))
    return tuple(result)


def _runtime_parameter_fingerprint(
    tokens: tuple[_TsToken, ...], start: int, end: int
) -> tuple[tuple[str, str], ...]:
    result: list[_TsToken] = []
    brace = paren = square = angle = 0
    skipping_type = False
    in_default = False
    for token in tokens[start:end]:
        value = token.text
        at_top = not (brace or paren or square or angle)
        if skipping_type:
            if at_top and value in {",", "="}:
                skipping_type = False
                if value == "=":
                    in_default = True
                    result.append(token)
                else:
                    in_default = False
                    result.append(token)
                continue
        elif at_top and not in_default and value == ":":
            skipping_type = True
            continue
        elif at_top and not in_default and value == "?":
            continue
        elif at_top and value == ",":
            in_default = False
            result.append(token)
            continue

        if not skipping_type:
            result.append(token)
        if value == "{":
            brace += 1
        elif value == "}":
            brace -= 1
        elif value == "(":
            paren += 1
        elif value == ")":
            paren -= 1
        elif value == "[":
            square += 1
        elif value == "]":
            square -= 1
        elif value == "<":
            angle += 1
        elif value == ">" and angle:
            angle -= 1
    return tuple((token.kind, token.text) for token in result)


def _class_instance_runtime_tokens(
    tokens: tuple[_TsToken, ...], keyword_index: int, body_index: int, end_index: int
) -> tuple[_TsToken, ...] | None:
    """Return class tokens without static members resolved through explicit property access."""
    result = list(tokens[keyword_index : body_index + 1])
    cursor = body_index + 1
    brace = paren = square = 0
    while cursor < end_index:
        token = tokens[cursor]
        if not (brace or paren or square) and token.text == "static":
            static_brace = static_paren = static_square = 0
            cursor += 1
            while cursor < end_index:
                value = tokens[cursor].text
                if value == "{":
                    static_brace += 1
                elif value == "}":
                    static_brace -= 1
                elif value == "(":
                    static_paren += 1
                elif value == ")":
                    static_paren -= 1
                elif value == "[":
                    static_square += 1
                elif value == "]":
                    static_square -= 1
                elif value == ";" and not (static_brace or static_paren or static_square):
                    cursor += 1
                    break
                if min(static_brace, static_paren, static_square) < 0:
                    return None
                cursor += 1
            else:
                return None
            continue
        result.append(token)
        if token.text == "{":
            brace += 1
        elif token.text == "}":
            brace -= 1
        elif token.text == "(":
            paren += 1
        elif token.text == ")":
            paren -= 1
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
        if min(brace, paren, square) < 0:
            return None
        cursor += 1
    if brace or paren or square:
        return None
    result.append(tokens[end_index])
    return tuple(result)


def _direct_runtime_declarations(
    text: str,
) -> dict[str, _RuntimeDeclarationFingerprint] | None:
    """Return conservative fingerprints for top-level runtime declarations."""
    tokens = _scan_ts(text, include_template_expressions=True)
    matches: dict[str, _RuntimeDeclarationFingerprint] = {}
    brace = paren = square = 0
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if token.text == "{":
            brace += 1
            cursor += 1
            continue
        if token.text == "}":
            brace -= 1
            if brace < 0:
                return None
            cursor += 1
            continue
        if token.text == "(":
            paren += 1
            cursor += 1
            continue
        if token.text == ")":
            paren -= 1
            if paren < 0:
                return None
            cursor += 1
            continue
        if token.text == "[":
            square += 1
            cursor += 1
            continue
        if token.text == "]":
            square -= 1
            if square < 0:
                return None
            cursor += 1
            continue
        if brace or paren or square or text[_line_start(text, token.start) : token.start].strip():
            cursor += 1
            continue

        declaration_start = cursor
        exported = token.text == "export"
        keyword_index = cursor + 1 if exported else cursor
        if keyword_index < len(tokens) and tokens[keyword_index].text == "async":
            keyword_index += 1
        if (
            keyword_index >= len(tokens)
            or tokens[keyword_index].text not in {"class", "const", "function"}
            or keyword_index + 1 >= len(tokens)
            or tokens[keyword_index + 1].kind != "identifier"
        ):
            cursor += 1
            continue
        declaration_kind: Literal["class", "const", "function"]
        if tokens[keyword_index].text == "class":
            declaration_kind = "class"
        elif tokens[keyword_index].text == "const":
            declaration_kind = "const"
        else:
            declaration_kind = "function"
        name = tokens[keyword_index + 1].text
        runtime_tokens: tuple[_TsToken, ...]
        end_index: int | None = None

        body_index: int | None = None
        if declaration_kind == "const":
            nested_brace = nested_paren = nested_square = angle = 0
            equal_index: int | None = None
            for probe in range(keyword_index + 2, len(tokens)):
                value = tokens[probe].text
                if value == "=" and not (nested_brace or nested_paren or nested_square or angle):
                    equal_index = probe
                    break
                if value == "{":
                    nested_brace += 1
                elif value == "}":
                    nested_brace -= 1
                elif value == "(":
                    nested_paren += 1
                elif value == ")":
                    nested_paren -= 1
                elif value == "[":
                    nested_square += 1
                elif value == "]":
                    nested_square -= 1
                elif value == "<":
                    angle += 1
                elif value == ">" and angle:
                    angle -= 1
                if min(nested_brace, nested_paren, nested_square, angle) < 0:
                    return None
            if equal_index is None:
                return None
            nested_brace = nested_paren = nested_square = angle = 0
            for probe in range(equal_index + 1, len(tokens)):
                value = tokens[probe].text
                if value == "{":
                    nested_brace += 1
                elif value == "}":
                    nested_brace -= 1
                elif value == "(":
                    nested_paren += 1
                elif value == ")":
                    nested_paren -= 1
                elif value == "[":
                    nested_square += 1
                elif value == "]":
                    nested_square -= 1
                elif value == "<":
                    angle += 1
                elif value == ">" and angle:
                    angle -= 1
                elif value == ";" and not (nested_brace or nested_paren or nested_square or angle):
                    end_index = probe
                    break
                if min(nested_brace, nested_paren, nested_square, angle) < 0:
                    return None
            if end_index is None:
                return None
            runtime_tokens = (
                tokens[keyword_index : keyword_index + 2] + tokens[equal_index : end_index + 1]
            )
        elif declaration_kind == "class":
            body_index = next(
                (
                    probe
                    for probe in range(keyword_index + 2, len(tokens))
                    if tokens[probe].text == "{"
                ),
                None,
            )
            if body_index is None:
                return None
            try:
                end_index = _matching_token(tokens, body_index, "{", "}")
            except DocumentationImpactError:
                return None
            class_tokens = _class_instance_runtime_tokens(
                tokens, keyword_index, body_index, end_index
            )
            if class_tokens is None:
                return None
            runtime_tokens = class_tokens
        else:
            angle = 0
            parameter_open: int | None = None
            for probe in range(keyword_index + 2, len(tokens)):
                value = tokens[probe].text
                if value == "<":
                    angle += 1
                elif value == ">" and angle:
                    angle -= 1
                elif value == "(" and not angle:
                    parameter_open = probe
                    break
            if parameter_open is None:
                return None
            try:
                parameter_close = _matching_token(tokens, parameter_open, "(", ")")
            except DocumentationImpactError:
                return None
            return_angle = return_paren = return_square = 0
            for probe in range(parameter_close + 1, len(tokens)):
                value = tokens[probe].text
                if value == "<":
                    return_angle += 1
                elif value == ">" and return_angle:
                    return_angle -= 1
                elif value == "(":
                    return_paren += 1
                elif value == ")" and return_paren:
                    return_paren -= 1
                elif value == "[":
                    return_square += 1
                elif value == "]" and return_square:
                    return_square -= 1
                elif value == "{" and not (return_angle or return_paren or return_square):
                    body_index = probe
                    break
                elif value == ";" and not (return_angle or return_paren or return_square):
                    return None
            if body_index is None:
                return None
            try:
                end_index = _matching_token(tokens, body_index, "{", "}")
            except DocumentationImpactError:
                return None
            prefix_start = (
                keyword_index - 1
                if keyword_index > declaration_start and tokens[keyword_index - 1].text == "async"
                else keyword_index
            )
            fingerprint = tuple(
                (item.kind, item.text) for item in tokens[prefix_start : keyword_index + 2]
            )
            fingerprint += (("punctuation", "("),)
            fingerprint += _runtime_parameter_fingerprint(
                tokens, parameter_open + 1, parameter_close
            )
            fingerprint += (("punctuation", ")"),)
            fingerprint += tuple(
                (item.kind, item.text) for item in tokens[body_index : end_index + 1]
            )
            runtime_tokens = ()

        if declaration_kind != "function":
            fingerprint = tuple((item.kind, item.text) for item in runtime_tokens)
        if name in matches:
            return None
        matches[name] = _RuntimeDeclarationFingerprint(
            exported=exported,
            declaration_kind=declaration_kind,
            tokens=fingerprint,
            identifiers=tuple(value for kind, value in fingerprint if kind == "identifier"),
        )
        cursor = (end_index or declaration_start) + 1
    if brace or paren or square:
        return None
    return matches


def _runtime_import_map(
    text: str,
) -> dict[str, tuple[str, str]] | None:
    result: dict[str, tuple[str, str]] = {}
    try:
        imports = _static_imports(text)
    except DocumentationImpactError:
        return None
    for import_item in imports:
        if import_item.side_effect:
            return None
        for binding in import_item.bindings:
            if binding.kind != "value":
                continue
            if binding.local in result:
                return None
            result[binding.local] = (import_item.module, binding.imported)
    return result


def _simple_object_bindings(
    tokens: tuple[_TsToken, ...], start: int, end: int
) -> dict[str, str] | None:
    result: dict[str, str] = {}
    segment_start = start
    brace = paren = square = 0
    segments: list[tuple[_TsToken, ...]] = []
    for cursor in range(start, end + 1):
        at_end = cursor == end
        token = tokens[cursor] if not at_end else None
        if token is not None and token.text == "{":
            brace += 1
        elif token is not None and token.text == "}":
            brace -= 1
        elif token is not None and token.text == "(":
            paren += 1
        elif token is not None and token.text == ")":
            paren -= 1
        elif token is not None and token.text == "[":
            square += 1
        elif token is not None and token.text == "]":
            square -= 1
        if min(brace, paren, square) < 0:
            return None
        if at_end or (token is not None and token.text == "," and not (brace or paren or square)):
            segment = tokens[segment_start:cursor]
            if segment:
                segments.append(segment)
            segment_start = cursor + 1
    if brace or paren or square:
        return None
    for segment in segments:
        if len(segment) == 1 and segment[0].kind == "identifier":
            source = local = segment[0].text
        elif (
            len(segment) == 3
            and segment[0].kind == "identifier"
            and segment[1].text == ":"
            and segment[2].kind == "identifier"
        ):
            source = segment[0].text
            local = segment[2].text
        else:
            return None
        if local in result:
            return None
        result[local] = source
    return result


def _runtime_destructured_aliases(
    text: str,
) -> dict[str, tuple[str, tuple[str, ...]]] | None:
    tokens = _scan_ts(text, include_template_expressions=True)
    result: dict[str, tuple[str, tuple[str, ...]]] = {}
    brace = paren = square = 0
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if (
            not (brace or paren or square)
            and token.text == "const"
            and text[_line_start(text, token.start) : token.start].strip() == ""
            and cursor + 1 < len(tokens)
            and tokens[cursor + 1].text == "{"
        ):
            try:
                binding_end = _matching_token(tokens, cursor + 1, "{", "}")
            except DocumentationImpactError:
                return None
            bindings = _simple_object_bindings(tokens, cursor + 2, binding_end)
            if bindings is None or binding_end + 2 >= len(tokens):
                return None
            if tokens[binding_end + 1].text != "=" or tokens[binding_end + 2].kind != "identifier":
                return None
            base = tokens[binding_end + 2].text
            path: list[str] = []
            probe = binding_end + 3
            while (
                probe + 1 < len(tokens)
                and tokens[probe].text == "."
                and tokens[probe + 1].kind == "identifier"
            ):
                path.append(tokens[probe + 1].text)
                probe += 2
            if not path or probe >= len(tokens) or tokens[probe].text != ";":
                return None
            for local, source in bindings.items():
                if local in result:
                    return None
                result[local] = (base, (*path, source))
            cursor = probe + 1
            continue
        if token.text == "{":
            brace += 1
        elif token.text == "}":
            brace -= 1
        elif token.text == "(":
            paren += 1
        elif token.text == ")":
            paren -= 1
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
        if min(brace, paren, square) < 0:
            return None
        cursor += 1
    if brace or paren or square:
        return None
    return result


def _class_static_object_member(
    text: str, class_name: str, container_name: str, member_name: str
) -> str | None:
    tokens = _scan_ts(text, include_template_expressions=True)
    brace = paren = square = 0
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if (
            not (brace or paren or square)
            and text[_line_start(text, token.start) : token.start].strip() == ""
        ):
            keyword_index = cursor + 1 if token.text == "export" else cursor
            if (
                keyword_index + 1 < len(tokens)
                and tokens[keyword_index].text == "class"
                and tokens[keyword_index + 1].text == class_name
            ):
                body_index = next(
                    (
                        probe
                        for probe in range(keyword_index + 2, len(tokens))
                        if tokens[probe].text == "{"
                    ),
                    None,
                )
                if body_index is None:
                    return None
                try:
                    body_end = _matching_token(tokens, body_index, "{", "}")
                except DocumentationImpactError:
                    return None
                member_cursor = body_index + 1
                member_brace = member_paren = member_square = 0
                while member_cursor < body_end:
                    member_token = tokens[member_cursor]
                    if (
                        not (member_brace or member_paren or member_square)
                        and member_token.text == "static"
                    ):
                        probe = member_cursor + 1
                        if probe < body_end and tokens[probe].text == "readonly":
                            probe += 1
                        if probe < body_end and tokens[probe].text == container_name:
                            if (
                                probe + 2 >= body_end
                                or tokens[probe + 1].text != "="
                                or tokens[probe + 2].text != "{"
                            ):
                                return None
                            try:
                                object_end = _matching_token(tokens, probe + 2, "{", "}")
                            except DocumentationImpactError:
                                return None
                            bindings = _simple_object_bindings(tokens, probe + 3, object_end)
                            if bindings is None:
                                return None
                            return next(
                                (
                                    local
                                    for local, source in bindings.items()
                                    if source == member_name
                                ),
                                None,
                            )
                    if member_token.text == "{":
                        member_brace += 1
                    elif member_token.text == "}":
                        member_brace -= 1
                    elif member_token.text == "(":
                        member_paren += 1
                    elif member_token.text == ")":
                        member_paren -= 1
                    elif member_token.text == "[":
                        member_square += 1
                    elif member_token.text == "]":
                        member_square -= 1
                    if min(member_brace, member_paren, member_square) < 0:
                        return None
                    member_cursor += 1
                return None
        if token.text == "{":
            brace += 1
        elif token.text == "}":
            brace -= 1
        elif token.text == "(":
            paren += 1
        elif token.text == ")":
            paren -= 1
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
        if min(brace, paren, square) < 0:
            return None
        cursor += 1
    return None


def _dependency_fingerprint(
    name: str, fingerprint: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    return (
        ("dependency", name),
        ("dependency", "{"),
        *fingerprint,
        ("dependency", "}"),
    )


def _runtime_export_property_fingerprint(
    project: Path,
    source_sha: str,
    module_path: str,
    export_name: str,
    property_path: tuple[str, ...],
    universe: set[str],
    *,
    current: bool,
    visited: frozenset[tuple[str, str]],
) -> tuple[tuple[str, str], ...] | None:
    property_key = f"{export_name}.{'.'.join(property_path)}"
    key = (module_path, property_key)
    if key in visited:
        return (("cycle", property_key),)
    if len(property_path) != 2:
        return None
    try:
        text = (
            _read_current(project, module_path)
            if current
            else _read_base(project, source_sha, module_path, None)
        )
    except DocumentationImpactError:
        return None
    declarations = _direct_runtime_declarations(text)
    if declarations is None:
        return None
    declaration = declarations.get(export_name)
    if declaration is None or not declaration.exported or declaration.declaration_kind != "class":
        return None
    local = _class_static_object_member(text, export_name, property_path[0], property_path[1])
    if local is None:
        return None
    return _runtime_local_symbol_fingerprint(
        project,
        source_sha,
        module_path,
        local,
        universe,
        current=current,
        visited=visited | {key},
    )


def _runtime_alias_fingerprint(
    project: Path,
    source_sha: str,
    module_path: str,
    alias: tuple[str, tuple[str, ...]],
    imports: Mapping[str, tuple[str, str]],
    universe: set[str],
    *,
    current: bool,
    visited: frozenset[tuple[str, str]],
) -> tuple[tuple[str, str], ...] | None:
    base, property_path = alias
    binding = imports.get(base)
    if binding is None:
        return None
    specifier, imported = binding
    if not specifier.startswith(("./", "../")) or imported in {"default", "*"}:
        return None
    try:
        target = _resolve_relative_module(
            module_path,
            specifier,
            universe,
            project=project if current else None,
        )
    except DocumentationImpactError:
        return None
    return _runtime_export_property_fingerprint(
        project,
        source_sha,
        target,
        imported,
        property_path,
        universe,
        current=current,
        visited=visited,
    )


def _runtime_export_fingerprint(
    project: Path,
    source_sha: str,
    module_path: str,
    export_name: str,
    universe: set[str],
    *,
    current: bool,
    visited: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[tuple[str, str], ...] | None:
    key = (module_path, export_name)
    if key in visited:
        return (("cycle", export_name),)
    try:
        text = (
            _read_current(project, module_path)
            if current
            else _read_base(project, source_sha, module_path, None)
        )
    except DocumentationImpactError:
        return None
    next_visited = visited | {key}
    declarations = _direct_runtime_declarations(text)
    imports = _runtime_import_map(text)
    aliases = _runtime_destructured_aliases(text)
    if declarations is None or imports is None or aliases is None:
        return None
    direct = declarations.get(export_name)
    if direct is not None and direct.exported:
        result = direct.tokens
        for dependency_name in sorted(set(direct.identifiers)):
            if dependency_name == export_name:
                continue
            dependency: tuple[tuple[str, str], ...] | None = None
            if dependency_name in declarations:
                dependency = _runtime_local_symbol_fingerprint(
                    project,
                    source_sha,
                    module_path,
                    dependency_name,
                    universe,
                    current=current,
                    visited=next_visited,
                )
            elif dependency_name in imports:
                dependency = _runtime_import_fingerprint(
                    project,
                    source_sha,
                    module_path,
                    imports[dependency_name],
                    universe,
                    current=current,
                    visited=next_visited,
                )
            elif dependency_name in aliases:
                dependency = _runtime_alias_fingerprint(
                    project,
                    source_sha,
                    module_path,
                    aliases[dependency_name],
                    imports,
                    universe,
                    current=current,
                    visited=next_visited,
                )
            if dependency is not None:
                result += _dependency_fingerprint(dependency_name, dependency)
            elif (
                dependency_name in declarations
                or dependency_name in imports
                or dependency_name in aliases
            ):
                return None
        return result

    local_candidates: list[tuple[tuple[str, str], ...]] = []
    for local, exported in _named_local_runtime_exports(text):
        if exported != export_name:
            continue
        candidate = _runtime_local_symbol_fingerprint(
            project,
            source_sha,
            module_path,
            local,
            universe,
            current=current,
            visited=next_visited,
        )
        if candidate is not None:
            local_candidates.append(candidate)
    if local_candidates:
        return local_candidates[0] if len(local_candidates) == 1 else None

    named_candidates: list[tuple[tuple[str, str], ...]] = []
    for imported, exported, specifier in _named_runtime_reexports(text):
        if exported != export_name:
            continue
        try:
            target = _resolve_relative_module(
                module_path,
                specifier,
                universe,
                project=project if current else None,
            )
        except DocumentationImpactError:
            return None
        candidate = _runtime_export_fingerprint(
            project,
            source_sha,
            target,
            imported,
            universe,
            current=current,
            visited=next_visited,
        )
        if candidate is not None:
            named_candidates.append(candidate)
    if named_candidates:
        return named_candidates[0] if len(named_candidates) == 1 else None

    candidates: list[tuple[tuple[str, str], ...]] = []
    for specifier in _export_star_modules(text):
        try:
            target = _resolve_relative_module(
                module_path,
                specifier,
                universe,
                project=project if current else None,
            )
        except DocumentationImpactError:
            return None
        candidate = _runtime_export_fingerprint(
            project,
            source_sha,
            target,
            export_name,
            universe,
            current=current,
            visited=next_visited,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _runtime_import_fingerprint(
    project: Path,
    source_sha: str,
    importer: str,
    binding: tuple[str, str],
    universe: set[str],
    *,
    current: bool,
    visited: frozenset[tuple[str, str]],
) -> tuple[tuple[str, str], ...] | None:
    specifier, imported = binding
    if not specifier.startswith(("./", "../")):
        return (("package", specifier), ("package-export", imported))
    if imported in {"default", "*"}:
        return None
    try:
        target = _resolve_relative_module(
            importer,
            specifier,
            universe,
            project=project if current else None,
        )
    except DocumentationImpactError:
        return None
    return _runtime_export_fingerprint(
        project,
        source_sha,
        target,
        imported,
        universe,
        current=current,
        visited=visited,
    )


def _runtime_local_symbol_fingerprint(
    project: Path,
    source_sha: str,
    module_path: str,
    symbol_name: str,
    universe: set[str],
    *,
    current: bool,
    visited: frozenset[tuple[str, str]],
) -> tuple[tuple[str, str], ...] | None:
    key = (module_path, symbol_name)
    if key in visited:
        return (("cycle", symbol_name),)
    try:
        text = (
            _read_current(project, module_path)
            if current
            else _read_base(project, source_sha, module_path, None)
        )
    except DocumentationImpactError:
        return None
    declarations = _direct_runtime_declarations(text)
    imports = _runtime_import_map(text)
    aliases = _runtime_destructured_aliases(text)
    if declarations is None or imports is None or aliases is None:
        return None
    direct = declarations.get(symbol_name)
    if direct is None:
        binding = imports.get(symbol_name)
        if binding is not None:
            return _runtime_import_fingerprint(
                project,
                source_sha,
                module_path,
                binding,
                universe,
                current=current,
                visited=visited | {key},
            )
        alias = aliases.get(symbol_name)
        if alias is None:
            return None
        return _runtime_alias_fingerprint(
            project,
            source_sha,
            module_path,
            alias,
            imports,
            universe,
            current=current,
            visited=visited | {key},
        )

    result = direct.tokens
    next_visited = visited | {key}
    for dependency_name in sorted(set(direct.identifiers)):
        if dependency_name == symbol_name:
            continue
        dependency: tuple[tuple[str, str], ...] | None = None
        if dependency_name in declarations:
            dependency = _runtime_local_symbol_fingerprint(
                project,
                source_sha,
                module_path,
                dependency_name,
                universe,
                current=current,
                visited=next_visited,
            )
        elif dependency_name in imports:
            dependency = _runtime_import_fingerprint(
                project,
                source_sha,
                module_path,
                imports[dependency_name],
                universe,
                current=current,
                visited=next_visited,
            )
        elif dependency_name in aliases:
            dependency = _runtime_alias_fingerprint(
                project,
                source_sha,
                module_path,
                aliases[dependency_name],
                imports,
                universe,
                current=current,
                visited=next_visited,
            )
        if dependency is not None:
            result += _dependency_fingerprint(dependency_name, dependency)
        elif (
            dependency_name in declarations
            or dependency_name in imports
            or dependency_name in aliases
        ):
            return None
    return result


def _is_import_only_visual_change(
    project: Path,
    source_sha: str,
    path: str,
    *,
    base_universe: set[str] | None = None,
    current_universe: set[str] | None = None,
) -> bool:
    """Return true only when a TSX change rewires imports without changing render code.

    Relative named imports may be regrouped across local ownership modules, but
    their imported/local/type bindings must remain identical. A runtime binding
    may change modules only when its exported declaration has the same token
    fingerprint (including through a local export-star barrel). Existing package,
    default, namespace, and side-effect imports stay byte-identical and ordered.
    New relative CSS side-effect imports are allowed only when the imported CSS is
    itself a current change, so its visual impact remains covered as CSS. All
    non-import source bytes stay identical apart from blank extraction gaps.
    """
    if PurePosixPath(path).suffix.lower() != ".tsx":
        return False
    try:
        base_text = _read_base(project, source_sha, path, None)
        current_text = _read_current(project, path)
        base_imports = _static_imports(base_text)
        current_imports = _static_imports(current_text)
    except DocumentationImpactError:
        return False

    base_remaining = _remove_spans(
        base_text, ((item.start, item.end) for item in base_imports)
    ).replace("\r\n", "\n")
    current_remaining = _remove_spans(
        current_text, ((item.start, item.end) for item in current_imports)
    ).replace("\r\n", "\n")
    base_remaining = _OPTIONAL_PROPERTY_IMPORT_TYPE_RE.sub(
        r"\g<prefix>import(\"<type-owner>\").\g<name>", base_remaining
    )
    current_remaining = _OPTIONAL_PROPERTY_IMPORT_TYPE_RE.sub(
        r"\g<prefix>import(\"<type-owner>\").\g<name>", current_remaining
    )
    if _nonblank_lines(base_remaining) != _nonblank_lines(current_remaining):
        return False

    def import_shape(
        imports: Iterable[_StaticImport],
    ) -> tuple[dict[tuple[str, str, str], str], tuple[_StaticImport, ...]] | None:
        local_named: dict[tuple[str, str, str], str] = {}
        protected: list[_StaticImport] = []
        for import_item in imports:
            if (
                import_item.module.startswith(("./", "../"))
                and not import_item.side_effect
                and not import_item.has_default_or_namespace
                and import_item.bindings
            ):
                for binding in _binding_tuple(import_item):
                    if binding in local_named:
                        return None
                    local_named[binding] = import_item.module
            else:
                protected.append(import_item)
        return local_named, tuple(protected)

    base_shape = import_shape(base_imports)
    current_shape = import_shape(current_imports)
    if base_shape is None or current_shape is None:
        return False
    base_named, base_protected = base_shape
    current_named, current_protected = current_shape
    if set(base_named) != set(current_named):
        return False

    base_paths = base_universe or _git_blob_paths(project, source_sha)
    current_paths = current_universe or _current_source_paths(
        project, changed_entries(project, "worktree")
    )
    current_changes = changed_entries(project, "worktree")
    base_index = 0
    for import_item in current_protected:
        if (
            base_index < len(base_protected)
            and import_item.text == base_protected[base_index].text
        ):
            base_index += 1
            continue
        if (
            not import_item.side_effect
            or not import_item.module.startswith(("./", "../"))
            or PurePosixPath(import_item.module).suffix.lower() != ".css"
        ):
            return False
        imported_path = posixpath.normpath(
            f"{PurePosixPath(path).parent.as_posix()}/{import_item.module}"
        )
        if imported_path not in current_paths or not current_changes.get(imported_path, False):
            return False
    if base_index != len(base_protected):
        return False

    for binding, base_module in base_named.items():
        current_module = current_named[binding]
        if base_module == current_module:
            continue
        try:
            base_target = _resolve_relative_module(path, base_module, base_paths)
            current_target = _resolve_relative_module(
                path, current_module, current_paths, project=project
            )
        except DocumentationImpactError:
            return False
        if binding[2] == "type" or base_target == current_target:
            continue
        base_fingerprint = _runtime_export_fingerprint(
            project,
            source_sha,
            base_target,
            binding[0],
            base_paths,
            current=False,
        )
        current_fingerprint = _runtime_export_fingerprint(
            project,
            source_sha,
            current_target,
            binding[0],
            current_paths,
            current=True,
        )
        if base_fingerprint is None or base_fingerprint != current_fingerprint:
            return False
    return True


def _remove_named_bindings(statement: _StaticImport, removed: set[str]) -> str:
    if not removed:
        return statement.text
    opening = statement.text.find("{")
    closing = statement.text.rfind("}")
    if opening < 0 or closing < opening:
        raise DocumentationImpactError("cannot remove bindings from a non-named import")
    body = statement.text[opening + 1 : closing]
    chunks = body.split(",")
    kept: list[str] = []
    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        binding_name = re.split(r"\s+as\s+", re.sub(r"^type\s+", "", stripped))[-1].strip()
        if binding_name not in removed:
            kept.append(chunk)
    return statement.text[: opening + 1] + ",".join(kept) + statement.text[closing:]


def _decl_map(
    text: str,
    source: str,
    *,
    required_names: set[str] | None = None,
) -> dict[str, _Declaration]:
    try:
        declarations = _find_declarations(text, required_names=required_names)
    except DocumentationImpactError as error:
        raise DocumentationImpactError(f"cannot parse declarations in {source}: {error}") from error
    mapped: dict[str, _Declaration] = {}
    for declaration in declarations:
        if declaration.name in mapped:
            raise DocumentationImpactError(
                f"declaration {declaration.name} appears more than once in {source}"
            )
        mapped[declaration.name] = declaration
    return mapped


def _validate_source_imports(
    *,
    source: str,
    base_text: str,
    current_text: str,
    base_imports: tuple[_StaticImport, ...],
    current_imports: tuple[_StaticImport, ...],
    added_target_index: int | None,
    removable: Mapping[str, set[str]],
    import_only_rewrite: Mapping[int, str] | None = None,
) -> None:
    expected_current = len(base_imports) + (1 if added_target_index is not None else 0)
    if len(current_imports) != expected_current:
        raise DocumentationImpactError(f"{source} changes the number of static imports")
    current_without_target = [
        item for index, item in enumerate(current_imports) if index != added_target_index
    ]
    if len(current_without_target) != len(base_imports):
        raise DocumentationImpactError(f"{source} splits, merges, or moves imports")
    for ordinal, (base_item, current_item) in enumerate(
        zip(base_imports, current_without_target, strict=True)
    ):
        removed = removable.get(str(ordinal), set())
        if current_item.form != base_item.form or current_item.type_only != base_item.type_only:
            raise DocumentationImpactError(f"{source} changes import form at ordinal {ordinal}")
        if (
            current_item.has_default_or_namespace != base_item.has_default_or_namespace
            or current_item.side_effect != base_item.side_effect
        ):
            raise DocumentationImpactError(
                f"{source} changes default, namespace, or side-effect imports"
            )
        if current_item.module != base_item.module and (
            import_only_rewrite is None or ordinal not in import_only_rewrite
        ):
            raise DocumentationImpactError(f"{source} changes an existing import module")
        if import_only_rewrite is not None and ordinal in import_only_rewrite:
            if current_item.module != import_only_rewrite[ordinal]:
                raise DocumentationImpactError(
                    f"{source} rewrites the wrong type-only import module"
                )
            if not any(binding.kind == "type" for binding in base_item.bindings):
                raise DocumentationImpactError(f"{source} rewrites a runtime import module")
        expected_bindings = tuple(
            binding for binding in base_item.bindings if binding.local not in removed
        )
        if _binding_tuple(current_item) != _binding_tuple_for(expected_bindings):
            raise DocumentationImpactError(f"{source} changes import bindings at ordinal {ordinal}")
        if (
            not removed
            and current_item.text != base_item.text
            and (import_only_rewrite is None or ordinal not in import_only_rewrite)
        ):
            raise DocumentationImpactError(f"{source} changes import formatting or attributes")
        if removed and current_item.text != _remove_named_bindings(base_item, removed):
            raise DocumentationImpactError(f"{source} changes retained import bytes")


def _binding_tuple_for(bindings: Iterable[_ImportBinding]) -> tuple[tuple[str, str, str], ...]:
    return tuple((binding.imported, binding.local, binding.kind) for binding in bindings)


def _target_import_name_set(import_item: _StaticImport) -> set[tuple[str, str, str]]:
    if import_item.side_effect or import_item.has_default_or_namespace or not import_item.bindings:
        raise DocumentationImpactError("target imports must be non-empty named imports")
    return set(_binding_tuple(import_item))


def _validate_binding_order(
    import_item: _StaticImport,
    source: str,
    *,
    target_dependency: bool = False,
) -> None:
    bindings = import_item.bindings
    seen_type = False
    for binding in bindings:
        if binding.kind == "type":
            seen_type = True
        elif seen_type:
            raise DocumentationImpactError(
                f"{source} import bindings must list values before inline types"
            )
    value_names = [binding.local for binding in bindings if binding.kind == "value"]
    type_names = [binding.local for binding in bindings if binding.kind == "type"]
    if value_names != sorted(value_names) or type_names != sorted(type_names):
        raise DocumentationImpactError(
            f"{source} import bindings are not lexicographically ordered"
        )
    if target_dependency:
        if not value_names and not import_item.type_only:
            raise DocumentationImpactError(f"{source} all-type import must use import type")
        if value_names and import_item.type_only:
            raise DocumentationImpactError(f"{source} mixed import must use named import")


def _validate_structural_exception(
    project: Path,
    exception: DocumentationImpactException,
    visual_files: set[str],
    merge_base: str,
    *,
    changed: Mapping[str, bool] | None = None,
    base_files: Mapping[str, str] | None = None,
) -> _ValidatedDocumentationImpactException:
    if exception.source_sha != merge_base:
        raise DocumentationImpactError(
            f"{exception.path} sourceSha {exception.source_sha} does not match "
            f"origin/main merge-base {merge_base}"
        )
    changed_entries_map: Mapping[str, bool] = changed or {path: True for path in visual_files}
    changed_paths = set(changed_entries_map)
    relocations = exception.relocations
    sources = {item.source for item in relocations}
    targets = {item.target for item in relocations}
    import_only = set(exception.import_only_files)
    declared_visual = sources | import_only
    if visual_files != declared_visual:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must exactly match relocation sources "
            "and importOnlyFiles"
        )
    if any(
        _canonical_repo_path(path, exception.path) != path for path in declared_visual | targets
    ):
        raise DocumentationImpactError(f"{exception.path} contains non-canonical paths")
    if not declared_visual <= changed_paths or not targets <= changed_paths:
        raise DocumentationImpactError(
            f"{exception.path} paths must all be in the complete changed set"
        )
    if any(not changed_entries_map.get(path, False) for path in declared_visual | targets):
        raise DocumentationImpactError(
            f"{exception.path} source, import-only, and target paths must be current changes"
        )
    if any(PurePosixPath(path).suffix.lower() != ".tsx" for path in declared_visual):
        raise DocumentationImpactError(f"{exception.path} sources must be production .tsx files")
    if any(PurePosixPath(path).suffix.lower() != ".ts" or _is_test_path(path) for path in targets):
        raise DocumentationImpactError(
            f"{exception.path} targets must be production non-test .ts files"
        )
    changed_visual = {path for path in changed_paths if _is_visual_source(path)}
    if changed_visual != declared_visual:
        raise DocumentationImpactError(
            f"{exception.path} changed visual sources must be declared exactly"
        )

    base_universe = (
        set(base_files or {})
        if base_files is not None
        else _git_blob_paths(project, exception.source_sha)
    )
    current_universe = _current_source_paths(project, changed_entries_map)
    if base_files is not None:
        current_universe.update(
            path
            for path in changed_paths
            if path.startswith("apps/web/src/") and (project / Path(*path.split("/"))).is_file()
        )
    for path in sources | import_only:
        if path not in base_universe:
            raise DocumentationImpactError(
                f"{exception.path} source {path} is absent at merge base"
            )
        if path not in current_universe:
            raise DocumentationImpactError(
                f"{exception.path} source {path} is absent in current worktree"
            )
    for path in targets:
        if path in base_universe:
            raise DocumentationImpactError(
                f"{exception.path} target {path} already exists at merge base"
            )
        if path not in current_universe:
            raise DocumentationImpactError(
                f"{exception.path} target {path} is absent in current worktree"
            )

    target_by_source: dict[str, list[_Relocation]] = {}
    for relocation in relocations:
        target_by_source.setdefault(relocation.source, []).append(relocation)
    global_names = {name for item in relocations for name in item.declarations}
    for source, source_relocations in target_by_source.items():
        moved_names = {name for item in source_relocations for name in item.declarations}
        base_text = _read_base(project, exception.source_sha, source, base_files)
        current_text = _read_current(project, source)
        base_declarations = _decl_map(base_text, source, required_names=moved_names)
        base_imports = _static_imports(base_text)
        current_imports = _static_imports(current_text)
        if any(name not in base_declarations for name in moved_names):
            raise DocumentationImpactError(
                f"{source} relocation declaration is not present at merge base"
            )
        # A declaration must be top-level and each relocation name is globally unique.
        if moved_names - global_names:
            raise DocumentationImpactError(f"{source} has undeclared moved declarations")
        base_decl_spans = [
            (base_declarations[name].start, base_declarations[name].end) for name in moved_names
        ]

        base_remaining = _remove_spans(
            base_text,
            [
                *(item for item in ((item.start, item.end) for item in base_imports)),
                *base_decl_spans,
            ],
        ).replace("\r\n", "\n")
        current_remaining = _remove_spans(
            current_text,
            [(item.start, item.end) for item in current_imports],
        ).replace("\r\n", "\n")
        if _nonblank_lines(base_remaining) != _nonblank_lines(current_remaining):
            raise DocumentationImpactError(f"{source} changes residual source bytes")

        moved_regions: list[str] = []
        expected_target_names: set[str] = set()
        target_paths = {item.target for item in source_relocations}
        if len(target_paths) != 1:
            raise DocumentationImpactError(f"{source} must use one target import statement")
        target_path = next(iter(target_paths))
        for relocation in source_relocations:
            target_text = _read_current(project, relocation.target)
            target_declarations = _decl_map(target_text, relocation.target)
            base_declaration_names = set(relocation.declarations)
            for name in base_declaration_names:
                base_declaration = base_declarations[name]
                target_declaration = target_declarations.get(name)
                if target_declaration is None:
                    raise DocumentationImpactError(
                        f"{relocation.target} is missing declaration {name}"
                    )
                expected_target_names.add(name)
                base_decl_text = base_text[base_declaration.start : base_declaration.end]
                target_decl_text = target_text[target_declaration.start : target_declaration.end]
                if target_decl_text != base_decl_text and not (
                    not base_declaration.export and target_decl_text == "export " + base_decl_text
                ):
                    raise DocumentationImpactError(
                        f"{name} declaration bytes changed during extraction"
                    )
                moved_regions.append(
                    _remove_spans(
                        target_decl_text,
                        [
                            (
                                target_declaration.defining_start - target_declaration.start,
                                target_declaration.defining_end - target_declaration.start,
                            )
                        ],
                    )
                )
            target_imports = _static_imports(target_text)
            target_spans = [(item.start, item.end) for item in target_imports]
            remaining_target = _remove_spans(
                target_text,
                [
                    *target_spans,
                    *(
                        (declaration.start, declaration.end)
                        for name, declaration in target_declarations.items()
                        if name in expected_target_names
                    ),
                ],
            )
            if remaining_target.strip():
                raise DocumentationImpactError(
                    f"{relocation.target} contains residual code or standalone comments"
                )

        moved_occurrences = set(_identifier_occurrences("\n".join(moved_regions)))
        remaining_occurrences = set(_identifier_occurrences(current_remaining))
        reference_names = {name for name in moved_names if name in remaining_occurrences}
        removable_by_ordinal: dict[str, set[str]] = {}
        base_bindings: dict[tuple[str, str], tuple[int, _ImportBinding, str]] = {}
        runtime_module_order: list[str] = []
        for ordinal, import_item in enumerate(base_imports):
            if not import_item.module.startswith(("./", "../")):
                if any(binding.local in moved_occurrences for binding in import_item.bindings):
                    raise DocumentationImpactError(
                        f"{source} moved declarations use unsupported package import "
                        f"{import_item.module!r}"
                    )
                continue
            resolved = _resolve_relative_module(source, import_item.module, base_universe)
            if (
                any(binding.kind == "value" for binding in import_item.bindings)
                and resolved not in runtime_module_order
            ):
                runtime_module_order.append(resolved)
            for binding in import_item.bindings:
                base_bindings[(binding.local, str(ordinal))] = (ordinal, binding, resolved)
        expected_target_dependencies: dict[str, list[_ImportBinding]] = {}
        for (_local, _ordinal), (ordinal, binding, resolved) in base_bindings.items():
            if binding.local in moved_occurrences:
                expected_target_dependencies.setdefault(resolved, []).append(binding)
                if binding.local not in remaining_occurrences:
                    removable_by_ordinal.setdefault(str(ordinal), set()).add(binding.local)

        target_imports = _static_imports(_read_current(project, target_path))
        target_universe = current_universe
        target_groups: list[tuple[str, _StaticImport]] = []
        target_group_paths: set[str] = set()
        for target_import in target_imports:
            resolved = _resolve_relative_module(
                target_path, target_import.module, target_universe, project=project
            )
            if resolved in target_group_paths:
                raise DocumentationImpactError(
                    f"{target_path} has duplicate import groups for {resolved}"
                )
            _target_import_name_set(target_import)
            _validate_binding_order(target_import, target_path, target_dependency=True)
            target_group_paths.add(resolved)
            target_groups.append((resolved, target_import))
        expected_modules = set(expected_target_dependencies)
        if {resolved for resolved, _ in target_groups} != expected_modules:
            raise DocumentationImpactError(f"{target_path} imports unused or missing dependencies")
        for resolved, target_import in target_groups:
            actual = _target_import_name_set(target_import)
            expected = {
                (binding.imported, binding.local, binding.kind)
                for binding in expected_target_dependencies[resolved]
            }
            if actual != expected:
                raise DocumentationImpactError(f"{target_path} changes dependency bindings")
            if not all(binding.local in moved_occurrences for binding in target_import.bindings):
                raise DocumentationImpactError(f"{target_path} imports an unreferenced dependency")
        type_groups = [
            resolved
            for resolved, item in target_groups
            if all(binding.kind == "type" for binding in item.bindings)
        ]
        runtime_groups = [
            resolved for resolved, item in target_groups if resolved not in type_groups
        ]
        if type_groups != sorted(type_groups):
            raise DocumentationImpactError(
                f"{target_path} type-only dependency groups are not sorted"
            )
        expected_runtime_order = [
            resolved for resolved in runtime_module_order if resolved in runtime_groups
        ]
        if runtime_groups != expected_runtime_order:
            raise DocumentationImpactError(f"{target_path} runtime dependency groups are reordered")

        added_target_import_indices = [
            index
            for index, item in enumerate(current_imports)
            if index >= len(base_imports)
            and _resolve_relative_module(source, item.module, current_universe, project=project)
            == target_path
        ]
        expected_source_bindings: set[tuple[str, str, str]] = set()
        for name in reference_names:
            declaration = base_declarations[name]
            expected_source_bindings.add(
                (name, name, "type" if declaration.kind == "type" else "value")
            )
        if expected_source_bindings:
            if len(added_target_import_indices) != 1:
                raise DocumentationImpactError(f"{source} must add exactly one target import")
            added = current_imports[added_target_import_indices[0]]
            _target_import_name_set(added)
            _validate_binding_order(added, source)
            if _target_import_name_set(added) != expected_source_bindings:
                raise DocumentationImpactError(f"{source} target import bindings are not exact")
            if added_target_import_indices[0] != len(current_imports) - 1:
                raise DocumentationImpactError(
                    f"{source} target import is not after pre-existing imports"
                )
        elif added_target_import_indices:
            raise DocumentationImpactError(f"{source} adds an unnecessary target import")
        _validate_source_imports(
            source=source,
            base_text=base_text,
            current_text=current_text,
            base_imports=base_imports,
            current_imports=current_imports,
            added_target_index=added_target_import_indices[0]
            if added_target_import_indices
            else None,
            removable=removable_by_ordinal,
        )

    for path in import_only:
        base_text = _read_base(project, exception.source_sha, path, base_files)
        current_text = _read_current(project, path)
        base_imports = _static_imports(base_text)
        current_imports = _static_imports(current_text)
        if len(base_imports) != len(current_imports):
            raise DocumentationImpactError(f"{path} changes type-only import statement count")
        base_residual = _remove_spans(
            base_text, [(item.start, item.end) for item in base_imports]
        ).replace("\r\n", "\n")
        current_residual = _remove_spans(
            current_text, [(item.start, item.end) for item in current_imports]
        ).replace("\r\n", "\n")
        if _nonblank_lines(base_residual) != _nonblank_lines(current_residual):
            raise DocumentationImpactError(f"{path} changes residual source bytes")
        rewrites: dict[int, str] = {}
        exact_rewrites = 0
        for index, (base_item, current_item) in enumerate(
            zip(base_imports, current_imports, strict=True)
        ):
            if (
                _binding_tuple(base_item) != _binding_tuple(current_item)
                or base_item.text == current_item.text
            ):
                if base_item.text != current_item.text and _binding_tuple(
                    base_item
                ) != _binding_tuple(current_item):
                    raise DocumentationImpactError(f"{path} changes type-only import bindings")
                continue
            type_bindings = [binding for binding in base_item.bindings if binding.kind == "type"]
            if not type_bindings or any(binding.kind != "type" for binding in base_item.bindings):
                raise DocumentationImpactError(f"{path} rewrites a runtime import")
            if any(binding.local not in global_names for binding in type_bindings):
                raise DocumentationImpactError(f"{path} rewrites an undeclared type binding")
            for binding in type_bindings:
                matching_sources = {
                    relocation.source
                    for relocation in exception.relocations
                    if binding.local in relocation.declarations
                }
                if len(matching_sources) != 1:
                    raise DocumentationImpactError(
                        f"{path} rewrites a type binding with no unique relocation source"
                    )
                base_source = _resolve_relative_module(
                    path, base_item.module, base_universe, project=project
                )
                expected_source = next(iter(matching_sources))
                if base_source != expected_source:
                    raise DocumentationImpactError(
                        f"{path} rewrites a type binding from {base_source}, "
                        f"expected relocation source {expected_source}"
                    )
            resolved_current = _resolve_relative_module(
                path, current_item.module, current_universe, project=project
            )
            matching_targets = {
                relocation.target
                for relocation in exception.relocations
                if any(binding.local in relocation.declarations for binding in type_bindings)
            }
            if len(matching_targets) != 1 or resolved_current not in matching_targets:
                raise DocumentationImpactError(
                    f"{path} rewrites to an undeclared relocation target"
                )
            if any(
                not any(
                    binding.local in relocation.declarations
                    and relocation.target == resolved_current
                    for relocation in exception.relocations
                )
                for binding in type_bindings
            ):
                raise DocumentationImpactError(f"{path} rewrites unrelated type bindings")
            rewrites[index] = current_item.module
            exact_rewrites += 1
        if exact_rewrites == 0:
            raise DocumentationImpactError(f"{path} has no exact relocated type import rewrite")
        _validate_source_imports(
            source=path,
            base_text=base_text,
            current_text=current_text,
            base_imports=base_imports,
            current_imports=current_imports,
            added_target_index=None,
            removable={},
            import_only_rewrite=rewrites,
        )
    return _ValidatedDocumentationImpactException(exception=exception, derived_selectors=())


def _validate_composition_attestation(
    project: Path,
    exception: DocumentationImpactException,
    entries: Mapping[str, bool],
    merge_base: str,
    mode: ImpactMode | None,
) -> _ValidatedDocumentationImpactException:
    if mode != "range":
        raise DocumentationImpactError(
            f"{exception.path} composition attestation is valid only for a committed range"
        )
    visual_files = {path for path in entries if _is_visual_source(path)}
    if not _is_ancestor(project, exception.source_sha, merge_base):
        raise DocumentationImpactError(
            f"{exception.path} sourceSha {exception.source_sha} is not an ancestor of "
            f"origin/main merge-base {merge_base}"
        )
    baseline_ui_drift = git_changed_paths(
        project,
        [
            f"{exception.source_sha}..{merge_base}",
            "--",
            "apps/web",
            _NAVIGATION_CONTRACT,
        ],
    )
    baseline_path_drift = git_changed_paths(
        project,
        [f"{exception.source_sha}..{merge_base}", "--", *sorted(entries)],
    )
    if baseline_ui_drift or baseline_path_drift:
        raise DocumentationImpactError(
            f"{exception.path} sourceSha-to-merge-base state changed the attested baseline"
        )
    if set(exception.visual_files) != visual_files or not visual_files:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must exactly match the changed visual sources"
        )
    if "apps/web/src/app.tsx" not in visual_files or any(
        path != "apps/web/src/app.tsx" and not path.startswith("apps/web/src/app/")
        for path in visual_files
    ):
        raise DocumentationImpactError(
            f"{exception.path} may cover only app.tsx composition sources"
        )

    targets = set(exception.composition_targets)
    inferred_targets = {
        path
        for path, current in entries.items()
        if current
        and path.startswith("apps/web/src/app/")
        and PurePosixPath(path).suffix.lower() in {".ts", ".tsx"}
        and not _is_test_path(path)
        and not _git_path_exists(project, merge_base, path)
    }
    if targets != inferred_targets or not targets:
        raise DocumentationImpactError(
            f"{exception.path} compositionTargets must exactly match new app composition modules"
        )
    if any(
        not entries.get(path, False) or not _git_path_exists(project, "HEAD", path)
        for path in targets
    ):
        raise DocumentationImpactError(
            f"{exception.path} compositionTargets must be changed files present at HEAD"
        )
    target_visuals = {path for path in targets if _is_visual_source(path)}
    if target_visuals != visual_files - {"apps/web/src/app.tsx"}:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must cover every new TSX composition target"
        )

    tests = set(exception.characterization_tests)
    inferred_tests = {
        path
        for path, current in entries.items()
        if current
        and (path.startswith("apps/web/src/app/") or path.startswith("apps/web/e2e/"))
        and PurePosixPath(path).suffix.lower() in {".ts", ".tsx"}
        and _is_test_path(path)
        and not _git_path_exists(project, merge_base, path)
    }
    if tests != inferred_tests or not tests:
        raise DocumentationImpactError(
            f"{exception.path} characterizationTests must exactly match new app routing tests"
        )
    if any(
        not entries.get(path, False) or not _git_path_exists(project, "HEAD", path)
        for path in tests
    ):
        raise DocumentationImpactError(
            f"{exception.path} characterizationTests must be changed files present at HEAD"
        )
    if exception.navigation_contract != _NAVIGATION_CONTRACT or not entries.get(
        _NAVIGATION_CONTRACT, False
    ):
        raise DocumentationImpactError(
            f"{exception.path} must bind the changed {_NAVIGATION_CONTRACT}"
        )
    if not entries.get(_FRONTEND_GUARD_BASELINE, False):
        raise DocumentationImpactError(
            f"{exception.path} must bind the changed {_FRONTEND_GUARD_BASELINE}"
        )
    guard_baseline = _read_git_json_mapping(project, "HEAD", _FRONTEND_GUARD_BASELINE)
    if guard_baseline.get("sourceSha") != merge_base:
        raise DocumentationImpactError(
            f"{_FRONTEND_GUARD_BASELINE} sourceSha must exactly match merge-base {merge_base}"
        )

    actual_visual_digest = _patch_sha256(project, merge_base, visual_files)
    if exception.visual_patch_sha256 != actual_visual_digest:
        raise DocumentationImpactError(
            f"{exception.path} visualPatchSha256 does not match the exact visual patch"
        )
    attested_paths = set(entries) - {exception.path}
    actual_attested_digest = _attested_patch_sha256(
        project,
        merge_base,
        attested_paths,
    )
    if exception.attested_patch_sha256 != actual_attested_digest:
        raise DocumentationImpactError(
            f"{exception.path} attestedPatchSha256 does not match the exact changed patch"
        )
    return _ValidatedDocumentationImpactException(exception=exception, derived_selectors=())


def _validate_exception(
    project: Path,
    exception: DocumentationImpactException,
    visual_files: set[str] | Mapping[str, bool],
    merge_base: str,
    *,
    base_files: Mapping[str, str] | None = None,
    changed: Mapping[str, bool] | None = None,
    mode: ImpactMode | None = None,
) -> _ValidatedDocumentationImpactException:
    if exception.classification == _NON_USER_VISIBLE_COMPOSITION_CLASSIFICATION:
        complete_changed = changed
        if complete_changed is None and isinstance(visual_files, Mapping):
            complete_changed = visual_files
        if complete_changed is None:
            raise DocumentationImpactError(
                f"{exception.path} composition attestation requires the complete changed path set"
            )
        return _validate_composition_attestation(
            project,
            exception,
            complete_changed,
            merge_base,
            mode,
        )
    if exception.classification == _NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION:
        complete_changed = changed
        if complete_changed is None and isinstance(visual_files, Mapping):
            complete_changed = visual_files
        visual_set = (
            {path for path in visual_files if _is_visual_source(path)}
            if isinstance(visual_files, Mapping)
            else set(visual_files)
        )
        return _validate_structural_exception(
            project,
            exception,
            visual_set,
            merge_base,
            changed=complete_changed,
            base_files=base_files,
        )
    if isinstance(visual_files, Mapping):
        visual_files = {path for path in visual_files if _is_visual_source(path)}
    if exception.source_sha != merge_base:
        raise DocumentationImpactError(
            f"{exception.path} sourceSha {exception.source_sha} does not match "
            f"origin/main merge-base {merge_base}"
        )
    if set(exception.visual_files) != visual_files:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must exactly match the changed visual sources"
        )
    if not visual_files:
        raise DocumentationImpactError(
            f"{exception.path} is stale because no visual source changed"
        )
    if any(not path.startswith(_SHARED_DESIGN_PREFIX) for path in visual_files):
        raise DocumentationImpactError(
            f"{exception.path} can cover only files under {_SHARED_DESIGN_PREFIX}"
        )
    covered = set(exception.unconsumed_modules) | set(exception.preserved_computed_value_files)
    if covered != visual_files:
        raise DocumentationImpactError(
            f"{exception.path} verification files must exactly cover visualFiles"
        )
    if any(path not in visual_files for path in exception.unconsumed_modules):
        raise DocumentationImpactError(
            f"{exception.path} unconsumedModules must be changed visual sources"
        )
    if any(
        PurePosixPath(path).suffix.lower() not in {".ts", ".tsx"}
        for path in exception.unconsumed_modules
    ):
        raise DocumentationImpactError(
            f"{exception.path} unconsumedModules allows only TypeScript modules"
        )
    if not set(exception.preserved_computed_value_files).issubset(_PRESERVED_FOUNDATION_FILES):
        raise DocumentationImpactError(
            f"{exception.path} preservedComputedValueFiles can include only shared "
            "tokens, typography, and primitives"
        )

    derived_selectors, new_variables = _prove_preserved_css(
        project,
        exception,
        base_files=base_files,
    )
    ignored_sources = set(exception.unconsumed_modules) | set(
        exception.preserved_computed_value_files
    )
    for source_path in _production_source_paths(project):
        relative = source_path.relative_to(project).as_posix()
        if relative in ignored_sources:
            continue
        text = source_path.read_text(encoding="utf-8")
        for module in exception.unconsumed_modules:
            module_name = PurePosixPath(module).stem
            if module_name in text:
                raise DocumentationImpactError(
                    f"{exception.path} module {module} is referenced by product source {relative}"
                )
        for selector in derived_selectors:
            if re.search(rf"(?<![-_a-zA-Z0-9]){re.escape(selector)}(?![-_a-zA-Z0-9])", text):
                raise DocumentationImpactError(
                    f"{exception.path} selector {selector} is used by product source {relative}"
                )
        for variable in new_variables:
            if variable in text:
                raise DocumentationImpactError(
                    f"{exception.path} CSS variable {variable} is used by product source {relative}"
                )
    return _ValidatedDocumentationImpactException(
        exception=exception,
        derived_selectors=tuple(sorted(derived_selectors)),
    )


def _merge_base(project: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "merge-base", "origin/main", "HEAD"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError("cannot resolve origin/main merge-base") from error
    merge_base = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", merge_base):
        raise DocumentationImpactError("origin/main merge-base is not a full Git SHA")
    return merge_base


def _read_git_json_mapping(project: Path, revision: str, path: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "show", f"{revision}:{path}"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, UnicodeError) as error:
        raise DocumentationImpactError(f"cannot read {path} at base {revision}: {error}") from error
    if result.returncode != 0:
        raise DocumentationImpactError(f"cannot read {path} at base {revision}")
    try:
        raw = json.loads(result.stdout, object_pairs_hook=_unique_json_mapping)
    except (json.JSONDecodeError, DocumentationImpactError) as error:
        raise DocumentationImpactError(f"cannot read {path} at base {revision}: {error}") from error
    return _mapping(raw, path)


def _git_path_exists(project: Path, revision: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{path}"],
        cwd=project,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _issue_184_add_only_allowlist(project: Path | None, merge_base: str | None) -> set[str]:
    if project is None or merge_base is None:
        return set()
    # The dynamic PR merge-base is intentionally not policy authority.  It is
    # used below only to reject modifications and validate read-back deltas.
    manifest = _read_git_json_mapping(project, _ISSUE_184_POLICY_BASE, _ISSUE_184_VISUAL_EVIDENCE)
    completeness = _mapping(
        manifest.get("full_screen_density_completeness"),
        f"{_ISSUE_184_VISUAL_EVIDENCE} full_screen_density_completeness",
    )
    allowed: set[str] = set()
    for density in ("compact", "standard", "large"):
        item = _mapping(
            completeness.get(density),
            f"{_ISSUE_184_VISUAL_EVIDENCE} full_screen_density_completeness.{density}",
        )
        missing = item.get("missing")
        if not isinstance(missing, list) or len(missing) != 10:
            raise DocumentationImpactError(
                f"{_ISSUE_184_VISUAL_EVIDENCE} base {density} missing list must contain "
                "exactly 10 names"
            )
        for index, name in enumerate(missing):
            if (
                not isinstance(name, str)
                or PurePosixPath(name).name != name
                or "\\" in name
                or PurePosixPath(name).suffix.lower() != ".png"
            ):
                raise DocumentationImpactError(
                    f"{_ISSUE_184_VISUAL_EVIDENCE} base {density} missing[{index}] "
                    "must be a PNG filename"
                )
            allowed.add(f"{_ISSUE_184_ROOT}/after/{density}/{name}")
    if len(allowed) != 30:
        raise DocumentationImpactError(
            f"{_ISSUE_184_VISUAL_EVIDENCE} base missing lists must derive exactly 30 paths"
        )
    return allowed


def _issue_184_manifest_missing(
    project: Path,
    added_paths: set[str],
    merge_base: str | None,
) -> None:
    path = project / _ISSUE_184_VISUAL_EVIDENCE
    if not path.is_file():
        raise DocumentationImpactError(
            f"{_ISSUE_184_VISUAL_EVIDENCE} must remain readable after an allowed addition"
        )
    manifest = _read_json_mapping(path, _ISSUE_184_VISUAL_EVIDENCE)
    completeness = _mapping(
        manifest.get("full_screen_density_completeness"),
        f"{_ISSUE_184_VISUAL_EVIDENCE} full_screen_density_completeness",
    )
    for added in sorted(added_paths):
        match = re.fullmatch(
            rf"{re.escape(_ISSUE_184_ROOT)}/after/(compact|standard|large)/([^/]+\.png)",
            added,
            re.IGNORECASE,
        )
        if match is None:
            continue
        density, name = match.group(1), match.group(2)
        target = project / Path(*added.split("/"))
        if not target.is_file() or target.is_symlink():
            raise DocumentationImpactError(f"{added} must be present after an allowed addition")
        item = _mapping(
            completeness.get(density),
            f"{_ISSUE_184_VISUAL_EVIDENCE} full_screen_density_completeness.{density}",
        )
        missing = item.get("missing")
        if not isinstance(missing, list):
            raise DocumentationImpactError(
                f"{_ISSUE_184_VISUAL_EVIDENCE} {density} missing state must be a list"
            )
        if name in missing:
            raise DocumentationImpactError(
                f"{added} remains listed as missing in {_ISSUE_184_VISUAL_EVIDENCE}"
            )

    if merge_base is None:
        return
    base_manifest = _read_git_json_mapping(project, merge_base, _ISSUE_184_VISUAL_EVIDENCE)
    base_completeness = _mapping(
        base_manifest.get("full_screen_density_completeness"),
        f"{_ISSUE_184_VISUAL_EVIDENCE} base full_screen_density_completeness",
    )
    additions_by_density = {density: 0 for density in ("compact", "standard", "large")}
    for added in sorted(added_paths):
        match = re.fullmatch(
            rf"{re.escape(_ISSUE_184_ROOT)}/after/(compact|standard|large)/([^/]+\.png)",
            added,
            re.IGNORECASE,
        )
        if match is not None:
            additions_by_density[match.group(1)] += 1
    for density, addition_count in additions_by_density.items():
        if not addition_count:
            continue
        current_item = _mapping(
            completeness.get(density),
            f"{_ISSUE_184_VISUAL_EVIDENCE} full_screen_density_completeness.{density}",
        )
        base_item = _mapping(
            base_completeness.get(density),
            f"{_ISSUE_184_VISUAL_EVIDENCE} base full_screen_density_completeness.{density}",
        )
        current_present = current_item.get("present")
        base_present = base_item.get("present")
        if not isinstance(current_present, int) or isinstance(current_present, bool):
            raise DocumentationImpactError(
                f"{_ISSUE_184_VISUAL_EVIDENCE} {density} present count is unreadable"
            )
        if not isinstance(base_present, int) or isinstance(base_present, bool):
            raise DocumentationImpactError(
                f"{_ISSUE_184_VISUAL_EVIDENCE} base {density} present count is unreadable"
            )
        expected_present = base_present + addition_count
        if current_present != expected_present:
            raise DocumentationImpactError(
                f"{_ISSUE_184_VISUAL_EVIDENCE} {density} present count must read back "
                f"as {expected_present} after additions"
            )


def _issue_223_root(path: str) -> str | None:
    if not path.startswith(_ISSUE_223_PREFIX):
        return None
    remainder = path.removeprefix(_ISSUE_223_PREFIX)
    issue_root_name = remainder.split("/", 1)[0]
    if not issue_root_name:
        return None
    return f"{_ISSUE_223_PREFIX}{issue_root_name}"


def _issue_351_retired_root(path: str) -> str | None:
    return next(
        (root for root in _ISSUE_351_RETIRED_EVIDENCE_ROOTS if _path_is_under(path, root)),
        None,
    )


def _git_blob_bytes(project: Path, revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", f"{revision}:{path}"],
        cwd=project,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise DocumentationImpactError(
            f"retired Materials reference is unavailable at merge base: {path}"
        )
    return result.stdout


def _validate_retired_materials_reference_changes(
    entries: Mapping[str, bool],
    *,
    project: Path | None,
    merge_base: str | None,
) -> None:
    changed = set(entries)
    root_paths = {
        path
        for path in changed
        if _path_is_under(path, _RETIRED_STATIC_MATERIALS_REFERENCE_ROOT)
    }
    if not root_paths:
        return
    retired_paths = set(_RETIRED_STATIC_MATERIALS_REFERENCE_SHA256)
    adjacent = sorted(root_paths - retired_paths)
    if adjacent:
        raise DocumentationImpactError(
            "retired Materials reference deletion cannot include adjacent assets: "
            f"{adjacent}"
        )
    if root_paths != retired_paths or any(entries[path] for path in retired_paths):
        raise DocumentationImpactError(
            "retired Materials references require one complete delete-only PNG/measurement set"
        )
    if project is None or merge_base is None:
        raise DocumentationImpactError(
            "retired Materials references require a repository merge base"
        )
    for path, expected_sha256 in _RETIRED_STATIC_MATERIALS_REFERENCE_SHA256.items():
        if not _git_path_exists(project, merge_base, path):
            raise DocumentationImpactError(
                "retired Materials reference set is unavailable at this merge base: "
                f"{path}"
            )
        actual_sha256 = hashlib.sha256(_git_blob_bytes(project, merge_base, path)).hexdigest()
        if actual_sha256 != expected_sha256:
            raise DocumentationImpactError(
                "retired Materials reference merge-base blob hash drifted: "
                f"{path}"
            )
        worktree_path = project.joinpath(*PurePosixPath(path).parts)
        if worktree_path.exists():
            raise DocumentationImpactError(
                "retired Materials reference must be absent from the worktree: "
                f"{path}"
            )
    required_docs = {
        "docs/product/service-reference-manifest.yaml",
        _SCREENSHOT_MANIFEST,
    }
    if not required_docs.issubset(changed):
        raise DocumentationImpactError(
            "retired Materials references require the service and screenshot manifests"
        )
    if not any(
        path.startswith(_GUIDE_PREFIX) and path.endswith(".md") for path in changed
    ):
        raise DocumentationImpactError(
            "retired Materials references require a changed current user guide"
        )


def _validate_visual_evidence_changes(
    entries: Mapping[str, bool],
    config: _VisualEvidenceConfig,
    *,
    project: Path | None = None,
    merge_base: str | None = None,
) -> None:
    changed = set(entries)
    _validate_retired_materials_reference_changes(
        entries,
        project=project,
        merge_base=merge_base,
    )
    issue_184_paths = {
        path
        for path in changed
        if _path_is_under(path, _ISSUE_184_ROOT)
        and PurePosixPath(path).suffix.lower() in config.raster_extensions
    }
    issue_184_allowlist = (
        _issue_184_add_only_allowlist(project, merge_base) if issue_184_paths else set()
    )
    issue_351_roots = {
        retired_root
        for path in changed
        if PurePosixPath(path).suffix.lower() in config.raster_extensions
        if (retired_root := _issue_351_retired_root(path)) is not None
    }
    if issue_351_roots:
        if project is None or merge_base is None:
            raise DocumentationImpactError(
                "issue-351 retired evidence deletion requires a repository merge base"
            )
        for retired_root in issue_351_roots:
            if not _git_path_exists(project, merge_base, retired_root):
                raise DocumentationImpactError(
                    f"issue-351 retired evidence root is absent from the merge base: {retired_root}"
                )
            root_path = project.joinpath(*PurePosixPath(retired_root).parts)
            if root_path.exists():
                raise DocumentationImpactError(
                    f"issue-351 cleanup must delete the complete approved root: {retired_root}"
                )
    issue_184_additions: set[str] = set()
    for raw_path, current in entries.items():
        path = raw_path.strip().replace("\\", "/")
        if PurePosixPath(path).suffix.lower() not in config.raster_extensions:
            continue
        # The exact legacy Materials set is handled by the semantic, complete-set
        # retirement policy above.  Do not let the generic frozen-root rule
        # reclassify those approved delete-only members after that validation.
        if _path_is_under(path, _RETIRED_STATIC_MATERIALS_REFERENCE_ROOT):
            continue
        lifecycle = _visual_evidence_lifecycle(path, config)
        if lifecycle is None or lifecycle == "transient":
            continue
        if _issue_351_retired_root(path) is not None:
            if current:
                raise DocumentationImpactError(
                    f"issue-351 retired evidence roots permit deletion only: {path}"
                )
            continue
        if path in _ISSUE_167_EXCEPTION_FILES:
            if not all(entries.get(dependency, False) for dependency in _ISSUE_167_DEPENDENCIES):
                raise DocumentationImpactError(
                    f"current-product evidence exception requires both coupling manifests: {path}"
                )
            continue

        if _path_is_under(path, _ISSUE_184_ROOT):
            if current and path in issue_184_allowlist:
                if (
                    project is not None
                    and merge_base is not None
                    and _git_path_exists(project, merge_base, path)
                ):
                    raise DocumentationImpactError(
                        f"issue-184 visual evidence permits additions only: {path}"
                    )
                issue_184_additions.add(path)
                continue
            if not current:
                raise DocumentationImpactError(
                    f"issue-184 frozen visual evidence permits additions only: {path}"
                )
            raise DocumentationImpactError(
                "issue-184 visual evidence path is not in the base-derived 30 add-only "
                f"allowlist: {path}"
            )

        issue_223_root = _issue_223_root(path)
        if issue_223_root is not None:
            if not current:
                raise DocumentationImpactError(
                    f"actual-device #223 visual evidence does not permit delete or rename: {path}"
                )
            coupling = {
                f"{issue_223_root}/manifest.json",
                f"{issue_223_root}/visual-evidence.yaml",
            }
            if not any(entries.get(path, False) for path in coupling):
                raise DocumentationImpactError(
                    "actual-device #223 visual evidence requires a same-root manifest "
                    f"change: {path}"
                )
            continue

        if lifecycle == "frozen":
            raise DocumentationImpactError(f"frozen visual evidence is immutable: {path}")

    if issue_184_additions:
        if _ISSUE_184_VISUAL_EVIDENCE not in changed:
            path = sorted(issue_184_additions)[0]
            raise DocumentationImpactError(
                f"issue-184 allowed additions require {_ISSUE_184_VISUAL_EVIDENCE}: {path}"
            )
        if project is not None:
            _issue_184_manifest_missing(project, issue_184_additions, merge_base)


def _current_changed_pngs(
    entries: Mapping[str, bool],
    config: _VisualEvidenceConfig,
) -> set[str]:
    roots = dict(config.roots)
    current_root = roots["current"]
    return {
        path
        for path, current in entries.items()
        if current
        and _path_is_under(path, current_root)
        and PurePosixPath(path).suffix.lower() == ".png"
    }


def _has_current_five_viewport_family(paths: Iterable[str]) -> bool:
    groups: dict[str, set[str]] = {}
    pattern = re.compile(
        r"^(?P<stem>.+?)[-_](?P<viewport>1366x768|1440x900|1920x1080|2560x1440|3840x2160)\.png$",
        re.IGNORECASE,
    )
    for path in paths:
        pure_path = PurePosixPath(path)
        name = pure_path.name
        match = pattern.fullmatch(name)
        if match is not None:
            key = f"{pure_path.parent}/{match.group('stem')}"
            groups.setdefault(key, set()).add(match.group("viewport"))
    return any(_CURRENT_FIVE_VIEWPORTS <= viewports for viewports in groups.values())


def _current_family_paths(paths: Iterable[str]) -> dict[str, dict[str, str]]:
    pattern = re.compile(
        r"^(?P<stem>.+?)[-_](?P<viewport>1366x768|1440x900|1920x1080|2560x1440|3840x2160)\.png$",
        re.IGNORECASE,
    )
    groups: dict[str, dict[str, str]] = {}
    for path in paths:
        pure_path = PurePosixPath(path)
        match = pattern.fullmatch(pure_path.name)
        if match is None:
            continue
        key = f"{pure_path.parent}/{match.group('stem')}"
        groups.setdefault(key, {})[match.group("viewport")] = path
    return groups


def _path_is_referenced_by_changed_documentation(
    project: Path, path: str, changed: set[str]
) -> bool:
    """Require the exact image path in both changed documentation surfaces.

    A five-viewport family may omit an unchanged member only when the changed
    screenshot manifest and a changed current guide both continue to name that
    exact file.  Looking for either surface would let a guide-only or manifest-
    only edit accidentally make an unrelated same-stem image satisfy the gate.
    """
    references = {path, PurePosixPath(path).name, path.removeprefix("docs/user-guide/")}
    seen_manifest = False
    seen_guide = False
    for relative in changed:
        is_manifest = relative == _SCREENSHOT_MANIFEST
        is_guide = relative.startswith(_GUIDE_PREFIX) and relative.endswith(".md")
        if not (is_manifest or is_guide):
            continue
        candidate = project / Path(*PurePosixPath(relative).parts)
        if not candidate.is_file():
            continue
        content = candidate.read_text(encoding="utf-8")
        if any(reference in content for reference in references):
            if is_manifest:
                seen_manifest = True
            if is_guide:
                seen_guide = True
    return seen_manifest and seen_guide


def _can_use_unchanged_current_family(
    project: Path | None,
    merge_base: str | None,
    changed: set[str],
    current_pngs: set[str],
) -> bool:
    if project is None or merge_base is None or not current_pngs:
        return False
    for members in _current_family_paths(current_pngs).values():
        if not members:
            continue
        missing = _CURRENT_FIVE_VIEWPORTS - set(members)
        if not missing:
            return True
        # Derive the exact same-stem path for each missing viewport.  A family
        # is usable only when every omitted member is byte-identical to the
        # merge-base blob and both current docs surfaces mention that member.
        sample = next(iter(members.values()))
        sample_path = PurePosixPath(sample)
        stem_match = re.match(
            r"^(?P<stem>.+?)[-_](?:1366x768|1440x900|1920x1080|2560x1440|3840x2160)\.png$",
            sample_path.name,
            flags=re.IGNORECASE,
        )
        if stem_match is None:
            continue
        for viewport in missing:
            candidate = (
                sample_path.parent
                / f"{stem_match.group('stem')}-{viewport}.png"
            ).as_posix()
            candidate_path = project / Path(*PurePosixPath(candidate).parts)
            if not candidate_path.is_file() or not _git_path_exists(project, merge_base, candidate):
                break
            if candidate_path.read_bytes() != _git_blob_bytes(project, merge_base, candidate):
                break
            if not _path_is_referenced_by_changed_documentation(project, candidate, changed):
                break
        else:
            return True
    return False


def evaluate_documentation_impact(
    paths: Iterable[str] | Mapping[str, bool],
    *,
    exception: _ValidatedDocumentationImpactException | None = None,
    ignored_visual_files: Iterable[str] = (),
    visual_evidence: _VisualEvidenceConfig | None = None,
    project: Path | None = None,
    merge_base: str | None = None,
) -> DocumentationImpactReport:
    if exception is not None and not isinstance(exception, _ValidatedDocumentationImpactException):
        raise DocumentationImpactError(
            "documentation-impact exceptions must pass repository validation"
        )
    if isinstance(paths, Mapping):
        normalized_entries = {
            path.strip().replace("\\", "/"): bool(can_supply_evidence)
            for path, can_supply_evidence in paths.items()
            if isinstance(path, str) and path.strip()
        }
        changed = set(normalized_entries)
        evidence = {
            path for path, can_supply_evidence in normalized_entries.items() if can_supply_evidence
        }
    else:
        changed = _normalize(paths)
        normalized_entries = {path: True for path in changed}
        evidence = set(changed)

    config = visual_evidence or _DEFAULT_VISUAL_EVIDENCE_CONFIG
    _validate_visual_evidence_changes(
        normalized_entries,
        config,
        project=project,
        merge_base=merge_base,
    )
    evidence = {
        path
        for path in evidence
        if _visual_evidence_lifecycle(path, config) != "transient"
    }
    ignored_visual = _normalize(ignored_visual_files)
    if ignored_visual - changed or any(not _is_visual_source(path) for path in ignored_visual):
        raise DocumentationImpactError(
            "ignored documentation-impact paths must be changed visual sources"
        )
    visual = sorted(
        path for path in changed if _is_visual_source(path) and path not in ignored_visual
    )
    exempted_visual = set(exception.exception.visual_files) if exception else set()
    if exempted_visual - set(visual):
        raise DocumentationImpactError(
            "documentation-impact exception lists a path that is not a changed visual source"
        )
    visual_requiring_documentation = sorted(set(visual) - exempted_visual)
    guide_changed = any(
        path.startswith(_GUIDE_PREFIX) and path.endswith(".md") for path in evidence
    )
    manifest_changed = _SCREENSHOT_MANIFEST in evidence
    current_pngs = _current_changed_pngs(normalized_entries, config)
    requirements: list[str] = []

    if visual_requiring_documentation:
        if not guide_changed:
            requirements.append("update a current docs/user-guide/*.md workflow")
        if not manifest_changed:
            requirements.append("update docs/user-guide/screenshot-manifest.yaml")
        if not current_pngs:
            requirements.append("add or update a current user-guide PNG")
        elif not (
            _has_current_five_viewport_family(current_pngs)
            or _can_use_unchanged_current_family(
                project,
                merge_base,
                changed,
                current_pngs,
            )
        ):
            requirements.append(
                "add or update one complete current user-guide PNG family at "
                "1366x768, 1440x900, 1920x1080, 2560x1440, and 3840x2160"
            )

    app_changed = "apps/web/src/app.tsx" in changed
    if app_changed and _NAVIGATION_CONTRACT not in evidence:
        requirements.append("update docs/user-guide/navigation-contract.yaml for app.tsx")

    workflow_contract_changed = bool(changed & _OPENAPI_CONTRACTS)
    if workflow_contract_changed and not guide_changed:
        requirements.append("update a current user guide for the OpenAPI workflow change")

    if requirements:
        visual_note = f"; visual sources: {', '.join(visual)}" if visual else ""
        raise DocumentationImpactError("; ".join(requirements) + visual_note)

    return DocumentationImpactReport(
        changed_files=tuple(sorted(changed)),
        visual_files=tuple(visual),
        exempted_visual_files=tuple(sorted(exempted_visual)),
        exception_issue=exception.exception.issue if exception else None,
        requirements=(),
    )


def verify_documentation_impact(root: Path, mode: ImpactMode) -> DocumentationImpactReport:
    project = root.resolve()
    entries = changed_entries(project, mode)
    merge_base = _merge_base(project)
    config = _load_visual_evidence_config(project)
    _validate_visual_evidence_changes(
        entries,
        config,
        project=project,
        merge_base=merge_base,
    )
    evidence = {
        path
        for path, can_supply_evidence in entries.items()
        if can_supply_evidence and _visual_evidence_lifecycle(path, config) != "transient"
    }
    visual_entries = {path for path in entries if _is_visual_source(path)}
    exception = _load_changed_exception(project, evidence)
    if (
        exception is not None
        and exception.classification == _NON_USER_VISIBLE_COMPOSITION_CLASSIFICATION
    ):
        if visual_entries:
            raise DocumentationImpactError(
                f"{exception.path} must be approved on origin/main before the visual diff"
            )
        exception = None
    if exception is None and mode == "range" and visual_entries:
        exception = _load_range_composition_attestation(
            project,
            merge_base,
            visual_entries,
        )
    base_source_paths = _git_blob_paths(project, merge_base)
    current_source_paths = _current_source_paths(project, entries)
    declared_exception_visual = set(exception.visual_files) if exception is not None else set()
    import_only_visual = {
        path
        for path, current in entries.items()
        if current
        and path not in declared_exception_visual
        and _is_visual_source(path)
        and _is_import_only_visual_change(
            project,
            merge_base,
            path,
            base_universe=base_source_paths,
            current_universe=current_source_paths,
        )
    }
    validation_entries = {
        path: current for path, current in entries.items() if path not in import_only_visual
    }
    validated_exception = None
    if exception is not None:
        validated_exception = _validate_exception(
            project,
            exception,
            validation_entries,
            merge_base,
            changed=validation_entries,
            mode=mode,
        )
    return evaluate_documentation_impact(
        entries,
        exception=validated_exception,
        visual_evidence=config,
        project=project,
        merge_base=merge_base,
        ignored_visual_files=import_only_visual,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("staged", "range", "worktree"), default="staged")
    args = parser.parse_args()
    try:
        report = verify_documentation_impact(args.root, args.mode)
    except (OSError, subprocess.CalledProcessError, DocumentationImpactError) as error:
        parser.exit(1, f"documentation impact check failed: {error}\n")
    exception_note = (
        f", {len(report.exempted_visual_files)} documented N/A by {report.exception_issue}"
        if report.exception_issue
        else ""
    )
    print(
        "documentation impact check passed: "
        f"{len(report.changed_files)} changed files, {len(report.visual_files)} visual sources"
        f"{exception_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

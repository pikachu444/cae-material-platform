from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest
import yaml
from cmp.tools.user_guide import (
    UserGuideContractError,
    _documentation_classes,
    _glob_matches,
    _verify_document_links,
)

ROOT = Path(__file__).parents[2]
ADR_NAME = re.compile(r"^\d{4}-.+\.md$")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST = frozenset(
    {
        "docs/17-evidence/issue-184-high-dpi-global-implementation.md",
        "docs/17-evidence/issue-184-to-223-windows-4k-handoff.md",
        "docs/17-evidence/issue-221-high-dpi-decision.md",
        "docs/17-evidence/issue-260-modeling-data-visual-normalization.md",
        "docs/17-evidence/issue-261-b1-modeling-stage-css-ownership.md",
        "docs/17-evidence/issue-261-b4-css-ownership-integration.md",
        "docs/17-evidence/issue-261-css-inventory-and-migration-plan.md",
        "docs/17-evidence/issue-261-fe06-residual-owner-boundary-consolidation.md",
        "docs/17-evidence/issue-261-m1e-modeling-ownership-integration.md",
        "docs/17-evidence/issue-261-m1e3-modeling-family-ownership.md",
        "docs/17-evidence/issue-261-m1e5-producer-routed-residual.md",
        "docs/17-evidence/issue-261-m2-materials-css-ownership.md",
        "docs/17-evidence/issue-261-m6-zero-consumer-audit-and-removal.md",
        "docs/17-evidence/issue-262-fe07a-materials-architecture-ui.md",
        "docs/17-evidence/issue-289-administration-database-workflow.md",
        "docs/17-evidence/issue-309-modeling-data-axis-overlap.md",
        "docs/17-evidence/issue-342-task1b-frontend-design-packet.md",
        "docs/17-evidence/issue-342-task1b-json-record-registration.md",
    }
)


def _adr_files(root: Path) -> set[str]:
    return {
        path.name
        for path in (root / "adr").glob("*.md")
        if ADR_NAME.fullmatch(path.name)
    }


def _verify_adr_index(root: Path) -> None:
    index = root / "adr" / "README.md"
    assert index.is_file(), "adr/README.md is missing"
    targets = [
        match.group(1)
        for match in MARKDOWN_LINK.finditer(index.read_text(encoding="utf-8"))
        if ADR_NAME.fullmatch(Path(match.group(1)).name)
    ]
    for target in targets:
        assert (index.parent / target).is_file(), f"ADR index target is missing: {target}"

    counts = Counter(Path(target).name for target in targets)
    expected = _adr_files(root)
    assert set(counts) == expected, (
        "ADR index drift: "
        f"missing={sorted(expected - set(counts))}, "
        f"unexpected={sorted(set(counts) - expected)}"
    )
    assert all(count == 1 for count in counts.values()), (
        "ADR index entries must occur exactly once: "
        f"{sorted(name for name, count in counts.items() if count != 1)}"
    )


def _copy_documentation_manifest(root: Path) -> Path:
    target = root / "docs" / "documentation-manifest.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "docs" / "documentation-manifest.yaml", target)
    return target


def _init_git_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _verify_top_level_evidence_allowlist(root: Path) -> None:
    manifest = yaml.safe_load(
        (root / "docs" / "documentation-manifest.yaml").read_text(encoding="utf-8")
    )
    include_patterns = {
        pattern
        for rule in manifest["rules"]
        for pattern in rule["include"]
        if isinstance(pattern, str)
    }
    probe = "docs/17-evidence/__task4_unapproved_probe__.md"
    broad_patterns = sorted(
        pattern for pattern in include_patterns if _glob_matches(probe, pattern)
    )
    assert not broad_patterns, (
        "top-level evidence Markdown must use exact allowlist entries: "
        f"{broad_patterns}"
    )

    manifest_paths = {
        pattern
        for pattern in include_patterns
        if Path(pattern).parent.as_posix() == "docs/17-evidence"
        and pattern.endswith(".md")
    }
    assert manifest_paths == TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST, (
        "manifest top-level evidence allowlist drift: "
        f"missing={sorted(TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST - manifest_paths)}, "
        f"unapproved={sorted(manifest_paths - TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST)}"
    )

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in (root / "docs" / "17-evidence").glob("*.md")
    }
    assert actual_paths == TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST, (
        "top-level evidence Markdown allowlist drift: "
        f"missing={sorted(TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST - actual_paths)}, "
        f"unapproved={sorted(actual_paths - TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST)}"
    )


def test_every_adr_is_indexed_once_and_links_resolve() -> None:
    _verify_adr_index(ROOT)


def test_missing_adr_index_entry_fails_and_restoration_passes(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "adr", tmp_path / "adr")
    index = tmp_path / "adr" / "README.md"
    original = index.read_text(encoding="utf-8")
    removed_entry = "- [ADR-0001 Modular monolith](0001-modular-monolith.md)\n"
    assert original.count(removed_entry) == 1
    index.write_text(original.replace(removed_entry, ""), encoding="utf-8")

    with pytest.raises(AssertionError, match="ADR index drift: missing"):
        _verify_adr_index(tmp_path)

    index.write_text(original, encoding="utf-8")
    _verify_adr_index(tmp_path)


def test_duplicate_adr_index_entry_fails(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "adr", tmp_path / "adr")
    index = tmp_path / "adr" / "README.md"
    duplicate_entry = "- [ADR-0001 Modular monolith](0001-modular-monolith.md)\n"
    original = index.read_text(encoding="utf-8")
    assert original.count(duplicate_entry) == 1
    index.write_text(f"{original}\n{duplicate_entry}", encoding="utf-8")

    with pytest.raises(AssertionError, match="ADR index entries must occur exactly once"):
        _verify_adr_index(tmp_path)


def test_docs_portal_and_agent_guidance_route_to_the_adr_index() -> None:
    assert "[ADR 색인](../adr/README.md)" in (ROOT / "docs" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "adr/README.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_all_tracked_markdown_is_classified_and_local_links_resolve() -> None:
    classes = _documentation_classes(ROOT)
    _verify_document_links(ROOT, classes)


def test_unregistered_docs_markdown_fails_classification(tmp_path: Path) -> None:
    _copy_documentation_manifest(tmp_path)
    unregistered = tmp_path / "docs" / "unregistered-task4-probe.md"
    unregistered.write_text("# Unregistered Task 4 probe\n", encoding="utf-8")
    _init_git_repository(tmp_path)

    with pytest.raises(
        UserGuideContractError,
        match=re.escape(
            "tracked Markdown must match exactly one documentation rule: "
            "docs/unregistered-task4-probe.md ([])"
        ),
    ):
        _documentation_classes(tmp_path)


def test_broken_repository_relative_link_fails(tmp_path: Path) -> None:
    document = tmp_path / "docs" / "broken-link-task4-probe.md"
    document.parent.mkdir(parents=True)
    document.write_text("[missing](missing-target.md)\n", encoding="utf-8")

    with pytest.raises(
        UserGuideContractError,
        match=re.escape(
            "missing link target in docs/broken-link-task4-probe.md: missing-target.md"
        ),
    ):
        _verify_document_links(
            tmp_path,
            {"docs/broken-link-task4-probe.md": "authoritative"},
        )


def test_top_level_evidence_markdown_matches_approved_allowlist() -> None:
    _verify_top_level_evidence_allowlist(ROOT)


def test_unapproved_top_level_evidence_markdown_fails_even_when_registered(
    tmp_path: Path,
) -> None:
    manifest = _copy_documentation_manifest(tmp_path)
    evidence_root = tmp_path / "docs" / "17-evidence"
    evidence_root.mkdir(parents=True)
    for relative in TOP_LEVEL_EVIDENCE_MARKDOWN_ALLOWLIST:
        (tmp_path / relative).write_text("# Approved\n", encoding="utf-8")

    unapproved = "docs/17-evidence/unapproved-task4-probe.md"
    (tmp_path / unapproved).write_text("# Unapproved\n", encoding="utf-8")
    content = manifest.read_text(encoding="utf-8")
    anchor = '      - "docs/17-evidence/issue-342-task1b-json-record-registration.md"'
    assert content.count(anchor) == 1
    manifest.write_text(
        content.replace(anchor, f'{anchor}\n      - "{unapproved}"'),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="manifest top-level evidence allowlist drift"):
        _verify_top_level_evidence_allowlist(tmp_path)

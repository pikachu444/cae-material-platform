from __future__ import annotations

import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
from cmp.tools.user_guide import _documentation_classes, _verify_document_links

ROOT = Path(__file__).parents[2]
ADR_NAME = re.compile(r"^\d{4}-.+\.md$")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")


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


def test_docs_portal_and_agent_guidance_route_to_the_adr_index() -> None:
    assert "[ADR 색인](../adr/README.md)" in (ROOT / "docs" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "adr/README.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_all_tracked_markdown_is_classified_and_local_links_resolve() -> None:
    classes = _documentation_classes(ROOT)
    _verify_document_links(ROOT, classes)

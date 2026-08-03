from __future__ import annotations

import re
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
_SCRIPT = runpy.run_path(str(_PROJECT_ROOT / "scripts/capture_current_product.py"))
CURRENT_CAPTURE_OUTPUTS = cast(tuple[str, ...], _SCRIPT["CURRENT_CAPTURE_OUTPUTS"])
REVISION_LABEL_PATTERN = cast(re.Pattern[str], _SCRIPT["REVISION_LABEL_PATTERN"])
_capture_to_empty_directory = cast(
    Callable[[Path, Callable[[Path], None]], int],
    _SCRIPT["_capture_to_empty_directory"],
)
_storybook_script = runpy.run_path(
    str(_PROJECT_ROOT / "scripts/capture_storybook_foundation.py")
)
default_storybook_output_path = cast(
    Callable[[str], Path], _storybook_script["default_output_path"]
)


def test_incomplete_capture_cannot_reuse_files_from_previous_output(
    tmp_path: Path,
) -> None:
    target = tmp_path / "docs/user-guide/images/current"
    target.mkdir(parents=True)
    for name in CURRENT_CAPTURE_OUTPUTS:
        (target / name).write_bytes(b"previous-capture")
    missing = CURRENT_CAPTURE_OUTPUTS[0]

    def incomplete_capture(staged: Path) -> None:
        for name in CURRENT_CAPTURE_OUTPUTS[1:]:
            (staged / name).write_bytes(b"new-capture")

    with pytest.raises(RuntimeError, match=missing):
        _capture_to_empty_directory(target, incomplete_capture)

    assert {path.name for path in target.iterdir()} == set(CURRENT_CAPTURE_OUTPUTS)
    assert all(
        (target / name).read_bytes() == b"previous-capture"
        for name in CURRENT_CAPTURE_OUTPUTS
    )
    assert not list(target.parent.glob(".current-capture-*"))


def test_current_capture_contract_contains_product_routes_only() -> None:
    assert len(CURRENT_CAPTURE_OUTPUTS) == 43
    assert all(not name.startswith("storybook-") for name in CURRENT_CAPTURE_OUTPUTS)


@pytest.mark.parametrize("label", ["r1", "r2", "r37"])
def test_current_capture_accepts_any_persisted_revision_number(label: str) -> None:
    assert REVISION_LABEL_PATTERN.fullmatch(label)


@pytest.mark.parametrize("label", ["r0", "r", "3", "draft"])
def test_current_capture_rejects_invalid_or_internal_revision_labels(label: str) -> None:
    assert REVISION_LABEL_PATTERN.fullmatch(label) is None


def test_storybook_default_captures_are_untracked_local_artifacts() -> None:
    expected = {
        "foundation": Path(".artifacts/storybook/storybook-foundation-1440x900.png"),
        "governed": Path(".artifacts/storybook/storybook-governed-workflow-1440x900.png"),
    }

    for scope, path in expected.items():
        assert default_storybook_output_path(scope) == path
        assert "docs/user-guide/images/current" not in path.as_posix()
        assert "docs/17-evidence" not in path.as_posix()

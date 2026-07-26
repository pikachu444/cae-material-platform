from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
_SCRIPT = runpy.run_path(str(_PROJECT_ROOT / "scripts/capture_current_product.py"))
CURRENT_CAPTURE_OUTPUTS = cast(tuple[str, ...], _SCRIPT["CURRENT_CAPTURE_OUTPUTS"])
_capture_to_empty_directory = cast(
    Callable[[Path, Callable[[Path], None]], int],
    _SCRIPT["_capture_to_empty_directory"],
)
_preserve_external_captures = cast(
    Callable[[Path, Path], None],
    _SCRIPT["_preserve_external_captures"],
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


def test_full_capture_preserves_separately_captured_storybook_evidence(
    tmp_path: Path,
) -> None:
    target = tmp_path / "current"
    staged = tmp_path / "staged"
    target.mkdir()
    staged.mkdir()
    storybook = target / "storybook-foundation-1440x900.png"
    storybook.write_bytes(b"separately-captured-storybook")

    _preserve_external_captures(target, staged)

    assert (staged / storybook.name).read_bytes() == storybook.read_bytes()

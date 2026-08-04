from __future__ import annotations

import ast
import re
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
_CAPTURE_SOURCE = (_PROJECT_ROOT / "scripts/capture_current_product.py").read_text(
    encoding="utf-8"
)
_SCRIPT = runpy.run_path(str(_PROJECT_ROOT / "scripts/capture_current_product.py"))
CURRENT_CAPTURE_OUTPUTS = cast(tuple[str, ...], _SCRIPT["CURRENT_CAPTURE_OUTPUTS"])
MODELING_DATA_SESSION_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DATA_SESSION_OUTPUTS"]
)
MODELING_PROCESS_OUTPUTS = cast(tuple[str, ...], _SCRIPT["MODELING_PROCESS_OUTPUTS"])
PROCESS_NO_PREVIEW_SAVED_INSTRUCTION = cast(
    str, _SCRIPT["PROCESS_NO_PREVIEW_SAVED_INSTRUCTION"]
)
REVISION_LABEL_PATTERN = cast(re.Pattern[str], _SCRIPT["REVISION_LABEL_PATTERN"])
_assert_modeling_process_saved_rows = cast(
    Callable[[object], list[str]], _SCRIPT["_assert_modeling_process_saved_rows"]
)
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


class _FakeRows:
    def __init__(self, row_text: list[str]) -> None:
        self.row_text = row_text
        self.index_waits: list[int] = []
        self.scalar_waits: list[str] = []

    def nth(self, index: int) -> "_FakeRowsWait":
        return _FakeRowsWait(self, index=index)

    def filter(self, *, has_text: str) -> "_FakeRowsWait":
        return _FakeRowsWait(self, scalar=has_text)

    def all_inner_texts(self) -> list[str]:
        return list(self.row_text)


class _FakeRowsWait:
    def __init__(
        self,
        rows: _FakeRows,
        *,
        index: int | None = None,
        scalar: str | None = None,
    ) -> None:
        self.rows = rows
        self.index = index
        self.scalar = scalar

    @property
    def first(self) -> "_FakeRowsWait":
        return self

    def wait_for(self, **_: object) -> None:
        if self.index is not None:
            self.rows.index_waits.append(self.index)
            if self.index >= len(self.rows.row_text):
                raise TimeoutError(f"row index {self.index} is missing")
        if self.scalar is not None:
            self.rows.scalar_waits.append(self.scalar)
            if not any(self.scalar in text for text in self.rows.row_text):
                raise TimeoutError(f"row scalar {self.scalar!r} is missing")


class _FakeSavedResults:
    def __init__(self, rows: _FakeRows) -> None:
        self.rows = rows

    def wait_for(self, **_: object) -> None:
        return None

    def get_attribute(self, name: str) -> str | None:
        assert name == "open"
        return "open"

    def locator(self, selector: str) -> _FakeRows:
        assert selector == ".process-comparison-row"
        return self.rows


class _FakePage:
    def __init__(self, row_text: list[str]) -> None:
        self.rows = _FakeRows(row_text)
        self.saved_results = _FakeSavedResults(self.rows)

    def locator(self, selector: str) -> _FakeSavedResults:
        assert selector == "details.process-saved-results"
        return self.saved_results


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
    assert len(CURRENT_CAPTURE_OUTPUTS) == 58
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_DATA_SESSION_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_PROCESS_OUTPUTS)
    assert {
        "modeling-data-2560x1440.png",
        "modeling-data-3840x2160.png",
        "modeling-data-empty-1440x900.png",
        "modeling-data-invalid-1440x900.png",
    } <= set(CURRENT_CAPTURE_OUTPUTS)
    assert all(not name.startswith("storybook-") for name in CURRENT_CAPTURE_OUTPUTS)


def test_default_capture_producer_runs_process_only_after_generic_modeling() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    producer = next(
        node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "produce"
    )
    calls = sorted(
        (
            node.lineno,
            node.func.id,
        )
        for node in ast.walk(producer)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    )
    call_names = [name for _, name in calls]
    assert call_names.index("_capture_modeling") < call_names.index(
        "_capture_modeling_process_only"
    ) < call_names.index("_capture_modeling_data_viewports")


def test_modeling_process_capture_contract_covers_wide_and_settled_states() -> None:
    assert len(MODELING_PROCESS_OUTPUTS) == 7
    assert {
        "modeling-process-1366x768.png",
        "modeling-process-1440x900.png",
        "modeling-process-1920x1080.png",
        "modeling-process-2560x1440.png",
        "modeling-process-3840x2160.png",
        "modeling-process-blocked-1440x900.png",
        "modeling-process-siblings-1440x900.png",
    } == set(MODELING_PROCESS_OUTPUTS)


def test_saved_process_rows_wait_on_embedded_scalars_and_reject_drift() -> None:
    row_text = [
        "Robust elastic · Specimen 01 · r1 · robust_huber · 0.0002–0.002 · 210.0 GPa · output r1 · history",
        "Chord elastic · Specimen 01 · r1 · chord · 0.001–0.003 · 120.0 GPa · output r1 · current",
    ]
    page = _FakePage(row_text)

    assert (
        _assert_modeling_process_saved_rows(page, require_current_and_history=True)
        == row_text
    )
    assert page.rows.index_waits == [1]
    assert page.rows.scalar_waits == ["210.0 GPa", "120.0 GPa"]

    missing_scalar = _FakePage(
        [row_text[0], row_text[1].replace("120.0 GPa", "119.0 GPa")]
    )
    with pytest.raises(TimeoutError, match=r"120\.0 GPa"):
        _assert_modeling_process_saved_rows(missing_scalar)

    swapped_scalar = _FakePage(
        [
            row_text[0].replace("210.0 GPa", "120.0 GPa"),
            row_text[1].replace("120.0 GPa", "210.0 GPa"),
        ]
    )
    with pytest.raises(RuntimeError, match="Robust elastic"):
        _assert_modeling_process_saved_rows(swapped_scalar)


def test_saved_process_capture_rejects_graph_hit_test_occlusion() -> None:
    reachability_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_saved_rows_reachable", 1
    )[1].split("\ndef _patch_capture_processing_output_pointer", 1)[0]

    assert "elementFromPoint" in reachability_assertion
    assert "process-comparison-row" in reachability_assertion
    assert 'check.get("actionLabel") != "Use settings"' in reachability_assertion
    assert "actionTopmost" in reachability_assertion
    assert 'plotUseful' in reachability_assertion
    assert 'plotHeadingVisible' in reachability_assertion
    assert 'plotHeadingTopmost' in reachability_assertion
    assert 'plotToolbarExists' in reachability_assertion
    assert 'plotEmptyVisible' in reachability_assertion
    assert 'plotEmptyTopmost' in reachability_assertion
    assert 'plotEmptyContained' in reachability_assertion
    assert 'The graph stays here while you prepare the curves.' in reachability_assertion
    assert "PROCESS_NO_PREVIEW_SAVED_INSTRUCTION" in reachability_assertion
    assert PROCESS_NO_PREVIEW_SAVED_INSTRUCTION == (
        "No Process preview is active. Choose Use settings for a saved result, then select "
        "Preview changes to preview the draft."
    )
    assert "Choose a saved Test Data revision. The graph compares real curves without changing saved data." not in reachability_assertion
    assert 'if layout.get("plotToolbarExists")' in reachability_assertion
    assert "_assert_modeling_process_saved_rows_reachable(siblings)" in _CAPTURE_SOURCE


def test_blocked_process_waits_for_hidden_registry_attachment_and_visible_rail() -> None:
    blocked_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_blocked", 1
    )[1].split("\ndef _capture_modeling_process_fit", 1)[0]

    assert 'method_buttons.first.wait_for(state="attached", timeout=30_000)' in blocked_assertion
    assert 'method_buttons.first.wait_for(timeout=30_000)' not in blocked_assertion
    assert 'rail_buttons = page.locator(".configured-step-list button:visible")' in blocked_assertion
    assert 'rail_buttons.first.wait_for(timeout=30_000)' in blocked_assertion


def test_blocked_process_fixture_seeds_the_destination_document_before_navigation() -> None:
    blocked_flow = _CAPTURE_SOURCE.split(
        "    blocked = _new_page", 1
    )[1].split("    siblings = _new_page", 1)[0]

    init_script = blocked_flow.split("blocked.add_init_script(", 1)[1].split(
        "    blocked.goto(", 1
    )[0]
    assert "blocked.evaluate(" not in blocked_flow
    assert "session.testData = null" not in init_script
    assert "delete session.testData" in init_script
    assert "selectedTestDataRefs: []" in init_script
    assert "selectedDocumentIds: []" in init_script
    assert "visibleTestDataKeys: []" in init_script
    assert "(() => {" in init_script
    assert "})();" in init_script
    assert "() => {" not in init_script.replace("(() => {", "")
    assert blocked_flow.index("blocked.add_init_script(") < blocked_flow.index(
        "blocked.goto("
    )
    assert "_wait_for_modeling_process_destination_state(blocked)" in blocked_flow
    assert blocked_flow.index("blocked.goto(") < blocked_flow.index(
        "_wait_for_modeling_process_destination_state(blocked)"
    ) < blocked_flow.index("_assert_modeling_process_blocked(blocked)")


def test_process_capture_waits_for_destination_state_and_responsive_plot_geometry() -> None:
    destination_wait = _CAPTURE_SOURCE.split(
        "def _wait_for_modeling_process_destination_state", 1
    )[1].split("def _wait_for_modeling_process_plot_size", 1)[0]
    assert "testData === null" not in destination_wait
    assert "testData === undefined" in destination_wait
    for field in (
        "selectedTestDataRefs",
        "selectedDocumentIds",
        "visibleTestDataKeys",
    ):
        assert f"Array.isArray(workspace.{field})" in destination_wait
        assert f"workspace.{field}.length === 0" in destination_wait

    plot_wait = _CAPTURE_SOURCE.split(
        "def _wait_for_modeling_process_plot_size", 1
    )[1].split("def _assert_modeling_process_preview", 1)[0]
    assert "svg.viewBox.baseVal" in plot_wait
    assert "svg.getBoundingClientRect()" in plot_wait
    assert "Math.abs(viewBox.width - rendered.width) < 1" in plot_wait
    assert "Math.abs(viewBox.height - rendered.height) < 1" in plot_wait

    preview_flow = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_preview", 1
    )[1].split("def _assert_modeling_process_geometry", 1)[0]
    assert preview_flow.index("_wait_for_modeling_process_plot_size(page)") < preview_flow.index(
        "panel = page.locator"
    )

    blocked_flow = _CAPTURE_SOURCE.split(
        "    blocked = _new_page", 1
    )[1].split("    siblings = _new_page", 1)[0]
    assert "before_screenshot=lambda: _assert_modeling_process_capture_ready(blocked)" in blocked_flow
    assert blocked_flow.index("before_screenshot=lambda: _assert_modeling_process_capture_ready(blocked)") > blocked_flow.index(
        "_assert_modeling_process_blocked(blocked)"
    )


def test_fresh_process_saves_wait_for_success_before_listing_outputs() -> None:
    fresh_branch = _CAPTURE_SOURCE.split(
        "    else:\n        _assert_modeling_process_preview(siblings)", 1
    )[1].split("    if siblings.locator", 1)[0]
    success_wait = (
        'siblings.get_by_text("Processed result saved and current", exact=False)'
        '.wait_for(timeout=30_000)'
    )

    assert fresh_branch.count(success_wait) == 2
    assert fresh_branch.index(success_wait) < fresh_branch.index(
        "saved_outputs = _matching_process_outputs"
    )


def test_process_capture_path_parameter_is_not_shadowed_by_resume_locals() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    capture_function = next(
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_capture_modeling_process_only"
    )
    output_parameters = [
        argument
        for argument in (*capture_function.args.posonlyargs, *capture_function.args.args)
        if argument.arg == "output"
    ]
    assert len(output_parameters) == 1
    assert isinstance(output_parameters[0].annotation, ast.Name)
    assert output_parameters[0].annotation.id == "Path"

    class _FunctionScopeStores(ast.NodeVisitor):
        def __init__(self) -> None:
            self.output_stores: list[ast.Name] = []

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == "output" and isinstance(node.ctx, ast.Store):
                self.output_stores.append(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            # Comprehension iteration variables live in their implicit scope;
            # still inspect the iterable and filters for assignment expressions.
            self.visit(node.iter)
            for condition in node.ifs:
                self.visit(condition)

    stores = _FunctionScopeStores()
    for statement in capture_function.body:
        stores.visit(statement)

    output_stores = stores.output_stores
    assert output_stores == [], "the capture output Path parameter must never be rebound"


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

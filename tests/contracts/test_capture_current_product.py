from __future__ import annotations

import ast
import re
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

# Embedded Playwright snippets and exact UI labels intentionally exceed Ruff's
# line length and preserve typographic punctuation for source-contract checks.
# ruff: noqa: E501, RUF001

_PROJECT_ROOT = Path(__file__).parents[2]
_CAPTURE_SOURCE = (_PROJECT_ROOT / "scripts/capture_current_product.py").read_text(
    encoding="utf-8"
)
_SCRIPT = runpy.run_path(str(_PROJECT_ROOT / "scripts/capture_current_product.py"))
CURRENT_CAPTURE_OUTPUTS = cast(tuple[str, ...], _SCRIPT["CURRENT_CAPTURE_OUTPUTS"])
DISPLAY_DENSITIES = cast(tuple[str, ...], _SCRIPT["DISPLAY_DENSITIES"])
_display_density_scope = cast(Callable[[str], str], _SCRIPT["_display_density_scope"])
PRODUCT_ACCESS_OUTPUTS = cast(tuple[str, ...], _SCRIPT["PRODUCT_ACCESS_OUTPUTS"])
ADMINISTRATION_DATABASE_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["ADMINISTRATION_DATABASE_OUTPUTS"]
)
MATERIAL_CURVE_OUTPUTS = cast(tuple[str, ...], _SCRIPT["MATERIAL_CURVE_OUTPUTS"])
ACTIVITY_OUTPUTS = cast(tuple[str, ...], _SCRIPT["ACTIVITY_OUTPUTS"])
MODELING_EXPORT_OUTPUTS = cast(tuple[str, ...], _SCRIPT["MODELING_EXPORT_OUTPUTS"])
MODELING_DATA_SESSION_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DATA_SESSION_OUTPUTS"]
)
MODELING_DATA_DOCUMENT_KEYS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DATA_DOCUMENT_KEYS"]
)
MODELING_PROCESS_OUTPUTS = cast(tuple[str, ...], _SCRIPT["MODELING_PROCESS_OUTPUTS"])
MODELING_DISTRIBUTION_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DISTRIBUTION_OUTPUTS"]
)
MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS"]
)
MODELING_DISTRIBUTION_DETAIL_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_DISTRIBUTION_DETAIL_OUTPUTS"]
)
MODELING_PROCESS_FIT_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_PROCESS_FIT_OUTPUTS"]
)
MODELING_FIT_STATE_OUTPUTS = cast(
    tuple[str, ...], _SCRIPT["MODELING_FIT_STATE_OUTPUTS"]
)
_assert_modeling_process_exact_read_failed = cast(
    Callable[[object, int | None], None], _SCRIPT["_assert_modeling_process_exact_read_failed"]
)
_select_warned_fit_candidate = cast(
    Callable[[object], None], _SCRIPT["_select_warned_fit_candidate"]
)
PROCESS_NO_PREVIEW_SAVED_INSTRUCTION = cast(
    str, _SCRIPT["PROCESS_NO_PREVIEW_SAVED_INSTRUCTION"]
)
REVISION_LABEL_PATTERN = cast(re.Pattern[str], _SCRIPT["REVISION_LABEL_PATTERN"])
_assert_modeling_process_saved_rows = cast(
    Callable[..., list[str]], _SCRIPT["_assert_modeling_process_saved_rows"]
)
_assert_modeling_process_saved_rows_three = cast(
    Callable[..., list[str]], _SCRIPT["_assert_modeling_process_saved_rows_three"]
)
_wait_for_modeling_process_saved_rows_refresh = cast(
    Callable[..., None], _SCRIPT["_wait_for_modeling_process_saved_rows_refresh"]
)
_assert_resumable_modeling_process_outputs = cast(
    Callable[[list[dict[str, object]], dict[str, object], dict[str, object]], dict[str, dict[str, object]]],
    _SCRIPT["_assert_resumable_modeling_process_outputs"],
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

    def nth(self, index: int) -> _FakeRowsWait:
        return _FakeRowsWait(self, index=index)

    def filter(self, *, has_text: str) -> _FakeRowsWait:
        return _FakeRowsWait(self, scalar=has_text)

    def all_inner_texts(self) -> list[str]:
        return list(self.row_text)


class _FakeCandidateCell:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self) -> str:
        return self.text


class _FakeCandidateCells:
    def __init__(self, cells: list[str]) -> None:
        self.cells = cells

    @property
    def last(self) -> _FakeCandidateCell:
        return _FakeCandidateCell(self.cells[-1])


class _FakeCandidateButton:
    def __init__(self, table: _FakeCandidateTable, index: int, *, matches: bool = True) -> None:
        self.table = table
        self.index = index
        self.matches = matches

    def count(self) -> int:
        return int(self.matches)

    def click(self) -> None:
        assert self.matches
        self.table.selected_index = self.index


class _FakeCandidateRow:
    def __init__(self, table: _FakeCandidateTable, index: int, cells: list[str]) -> None:
        self.table = table
        self.index = index
        self.cells = cells

    @property
    def text(self) -> str:
        return " ".join(self.cells)

    def locator(self, selector: str) -> _FakeCandidateCells:
        assert selector == "td"
        return _FakeCandidateCells(self.cells)

    def get_by_role(self, role: str, **options: object) -> _FakeCandidateButton:
        assert role == "button"
        name = options.get("name")
        matches = True
        if isinstance(name, re.Pattern):
            selected = self.table.selected_index == self.index
            label = (
                f"{self.cells[1]} candidate selected"
                if selected
                else f"Select {self.cells[1]} candidate"
            )
            matches = name.search(label) is not None
        return _FakeCandidateButton(self.table, self.index, matches=matches)


class _FakeCandidateButtons:
    def __init__(self, table: _FakeCandidateTable, rows: list[_FakeCandidateRow]) -> None:
        self.table = table
        self.rows = rows

    def count(self) -> int:
        return len(self.rows)

    @property
    def first(self) -> _FakeCandidateButton:
        return self.rows[0].get_by_role("button")

    @property
    def last(self) -> _FakeCandidateButton:
        return self.rows[-1].get_by_role("button")


class _FakeCandidateRows:
    def __init__(self, table: _FakeCandidateTable, rows: list[_FakeCandidateRow]) -> None:
        self.table = table
        self.rows = rows

    def count(self) -> int:
        return len(self.rows)

    def nth(self, index: int) -> _FakeCandidateRow:
        return self.rows[index]

    def filter(self, *, has_text: re.Pattern[str]) -> _FakeCandidateRows:
        return type(self)(self.table, [row for row in self.rows if has_text.search(row.text)])

    def get_by_role(self, role: str, **_: object) -> _FakeCandidateButtons:
        assert role == "button"
        return _FakeCandidateButtons(self.table, self.rows)


class _FakeCandidateTable:
    def __init__(self, rows: list[list[str]]) -> None:
        self.selected_index: int | None = None
        candidate_rows = [
            _FakeCandidateRow(self, index, cells) for index, cells in enumerate(rows)
        ]
        self.rows = _FakeCandidateRows(self, candidate_rows)

    def locator(self, selector: str) -> _FakeCandidateRows:
        assert selector == "tbody tr"
        return self.rows

    def get_by_role(self, role: str, **_: object) -> _FakeCandidateButtons:
        assert role == "button"
        return _FakeCandidateButtons(self, self.rows.rows)


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
    def first(self) -> _FakeRowsWait:
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


class _SettlingFakeRows(_FakeRows):
    def __init__(self, row_text: list[str], events: list[str]) -> None:
        super().__init__(row_text)
        self.events = events

    def all_inner_texts(self) -> list[str]:
        self.events.append("all_inner_texts")
        return super().all_inner_texts()


class _SettlingFakePage:
    def __init__(self, initial_rows: list[str], settled_rows: list[str]) -> None:
        self.events: list[str] = []
        self.rows = _SettlingFakeRows(initial_rows, self.events)
        self.saved_results = _FakeSavedResults(self.rows)
        self.settled_rows = settled_rows
        self.wait_expression: str | None = None
        self.wait_timeout: int | None = None

    def locator(self, selector: str) -> _FakeSavedResults:
        assert selector == "details.process-saved-results"
        return self.saved_results

    def wait_for_function(self, expression: str, *, timeout: int) -> None:
        self.events.append("wait_for_function")
        self.wait_expression = expression
        self.wait_timeout = timeout
        self.rows.row_text = list(self.settled_rows)
        if len(self.rows.row_text) != 3 or any(
            "Loading saved result…" in text for text in self.rows.row_text
        ):
            raise TimeoutError("saved Process rows did not settle")


class _FakeRequest:
    def __init__(self, url: str) -> None:
        self.url = url
        self.method = "GET"


class _FakeResponse:
    def __init__(self, url: str, *, ok: bool = True) -> None:
        self.url = url
        self.request = _FakeRequest(url)
        self.ok = ok
        self.status = 200 if ok else 500


class _RefreshingFakeSummary:
    def __init__(self, page: _RefreshingFakePage) -> None:
        self.page = page

    def click(self) -> None:
        self.page.events.append("summary.click")
        self.page.open = True
        self.page.rows.row_text = list(self.page.loading_rows)
        self.page.emit_response(self.page.pending_responses.pop(0))


class _RefreshingFakeDetails:
    def __init__(self, page: _RefreshingFakePage) -> None:
        self.page = page
        self.summary = _RefreshingFakeSummary(page)

    def wait_for(self, **_: object) -> None:
        return None

    def get_attribute(self, name: str) -> str | None:
        assert name == "open"
        return "open" if self.page.open else None

    def locator(self, selector: str) -> object:
        if selector == ":scope > summary":
            return self.summary
        assert selector == ".process-comparison-row"
        return self.page.rows


class _RefreshingExpectation:
    def __init__(self, page: _RefreshingFakePage, predicate: Callable[[object], bool]) -> None:
        self.page = page
        self.predicate = predicate
        self.value: object | None = None

    def __enter__(self) -> _RefreshingExpectation:
        self.page.expectation = self
        return self

    def __exit__(self, *_: object) -> None:
        self.page.expectation = None
        if self.value is None:
            raise TimeoutError("saved Process refresh did not start")


class _RefreshingFakePage:
    def __init__(self, loading_rows: list[str], settled_rows: list[str]) -> None:
        self.events: list[str] = []
        self.open = False
        self.loading_rows = loading_rows
        self.settled_rows = settled_rows
        self.rows = _FakeRows(list(loading_rows))
        self.details = _RefreshingFakeDetails(self)
        self.pending_responses = [
            _FakeResponse(
                f"https://demo.test/api/v1/processing-outputs/out-{index}/content"
            )
            for index in range(1, 4)
        ]
        self.response_listeners: list[Callable[[object], None]] = []
        self.expectation: _RefreshingExpectation | None = None
        self.wait_expressions: list[str] = []

    def locator(self, selector: str) -> _RefreshingFakeDetails:
        assert selector == "details.process-saved-results"
        return self.details

    def on(self, event: str, callback: Callable[[object], None]) -> None:
        assert event == "response"
        self.response_listeners.append(callback)

    def remove_listener(self, event: str, callback: Callable[[object], None]) -> None:
        assert event == "response"
        self.response_listeners.remove(callback)

    def expect_response(
        self,
        predicate: Callable[[object], bool],
        *,
        timeout: int,
    ) -> _RefreshingExpectation:
        assert timeout == 30_000
        return _RefreshingExpectation(self, predicate)

    def emit_response(self, response: _FakeResponse) -> None:
        for callback in list(self.response_listeners):
            callback(response)
        if self.expectation is not None and self.expectation.predicate(response):
            self.expectation.value = response
        if not self.pending_responses:
            self.rows.row_text = list(self.settled_rows)

    def wait_for_function(self, expression: str, *, timeout: int) -> None:
        assert timeout == 30_000
        self.wait_expressions.append(expression)
        if "Loading saved result…" in expression:
            self.events.append("no-loading-gate")
            # The first expect_response above only releases one response.  A
            # DOM wait pumps the event loop, so the remaining two responses
            # reach the listener before the source validates its count.
            while self.pending_responses:
                self.emit_response(self.pending_responses.pop(0))
            if self.rows.row_text != self.settled_rows:
                raise TimeoutError("saved Process rows did not settle")
        else:
            self.events.append("render-gate")

    def evaluate(self, _expression: str) -> None:
        self.events.append("render-frame")


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
    assert len(CURRENT_CAPTURE_OUTPUTS) == 124
    assert "administration-schema-bundle-1440x900.png" in CURRENT_CAPTURE_OUTPUTS
    assert "material-database-categories-1440x900.png" in CURRENT_CAPTURE_OUTPUTS
    assert "material-database-linked-test-1440x900.png" in CURRENT_CAPTURE_OUTPUTS
    assert PRODUCT_ACCESS_OUTPUTS == (
        "administration-access-1366x768.png",
        "administration-access-1440x900.png",
        "administration-access-1920x1080.png",
        "administration-access-2560x1440.png",
        "administration-access-3840x2160.png",
        "administration-access-role-control-1366x768.png",
    )
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in PRODUCT_ACCESS_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in ADMINISTRATION_DATABASE_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MATERIAL_CURVE_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_DATA_SESSION_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_PROCESS_OUTPUTS)
    assert all(
        name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS
    )
    assert set(MODELING_DISTRIBUTION_DETAIL_OUTPUTS).isdisjoint(CURRENT_CAPTURE_OUTPUTS)
    assert len(MODELING_DISTRIBUTION_OUTPUTS) == 20
    assert set(MODELING_DISTRIBUTION_OUTPUTS) == {
        *MODELING_DISTRIBUTION_VIEWPORT_OUTPUTS,
        *MODELING_DISTRIBUTION_DETAIL_OUTPUTS,
    }
    assert {
        "modeling-data-2560x1440.png",
        "modeling-data-3840x2160.png",
        "modeling-data-empty-1440x900.png",
        "modeling-data-invalid-1440x900.png",
        "modeling-data-invalid-scrolled-1440x900.png",
        "modeling-process-exact-read-failed-1440x900.png",
    } <= set(CURRENT_CAPTURE_OUTPUTS)
    assert all(not name.startswith("storybook-") for name in CURRENT_CAPTURE_OUTPUTS)


def test_current_capture_installs_the_scoped_density_preference_before_first_paint() -> None:
    new_page = _CAPTURE_SOURCE.split("def _new_page", 1)[1].split(
        "def _bounding_box_edges", 1
    )[0]

    assert DISPLAY_DENSITIES == ("compact", "standard", "large")
    assert _display_density_scope("not-a-jwt") == (
        "%2Fapi%2Fv1|local-organization|local-workspace|anonymous"
    )
    assert '"--density"' in _CAPTURE_SOURCE
    assert "'cmp.material-platform.client-preferences.v1'" in new_page
    assert '"displayDensityByScope"' in new_page
    assert "CAPTURE_DISPLAY_DENSITY" in new_page
    assert new_page.index("context.add_init_script") < new_page.index(
        "page = context.new_page()"
    )


def test_modeling_data_ribbon_capture_uses_the_shared_density_formula() -> None:
    helper = _CAPTURE_SOURCE.split("def _modeling_data_ribbon_height", 1)[1].split(
        "def _assert_modeling_data_surface", 1
    )[0]

    for token in (
        "--ux-navigator-row-block-size",
        "--ux-splitter-inline-size",
        "--ux-pane-padding",
    ):
        assert token in helper
    assert "--ux-interactive-min-block-size" not in helper
    assert "--ux-control-min-block-size" not in helper
    assert "expected_height = _modeling_data_ribbon_height(page)" in helper
    assert "arg=expected_height" in helper
    assert "NORMAL_COMPACT_DATA_RIBBON_HEIGHT" not in _CAPTURE_SOURCE


def test_invalid_mapping_plot_reset_uses_the_density_aware_initial_allocation() -> None:
    helper = _CAPTURE_SOURCE.split("def _capture_modeling_data_exceptions", 1)[1].split(
        "def _capture_administration_database", 1
    )[0]

    assert 'after_plot["height"] < 240' in helper
    assert 'after_ribbon["height"] <= before_ribbon["height"]' in helper
    assert 'after_plot["height"] >= before_plot["height"]' in helper
    assert 'abs(reset_ribbon["height"] - before_ribbon["height"]) > 1' in helper
    assert 'abs(reset_plot["height"] - before_plot["height"]) > 1' in helper
    assert 'scroll_metrics["scrollHeight"] <= scroll_metrics["clientHeight"] + 1' in helper
    assert 'local_region.press("PageDown")' in helper
    assert ">=296px" not in helper


def test_activity_capture_contract_is_role_correct_for_requesters_and_reviewers() -> None:
    new_page = _CAPTURE_SOURCE.split("def _new_page", 1)[1].split(
        "def _bounding_box_edges", 1
    )[0]
    solver_flow = _CAPTURE_SOURCE.split("def _capture_solver_delivery", 1)[1].split(
        "def _capture_activity", 1
    )[0]
    activity_wait = _CAPTURE_SOURCE.split("def _wait_for_activity_queue", 1)[1].split(
        "def _ensure_activity_review_fixture", 1
    )[0]

    assert '_wait_for_activity_queue(page, expect_review_action=False, expected_view="in-progress")' in solver_flow
    assert 'solver_review.get_by_text("Waiting for review", exact=True).wait_for' in solver_flow
    assert "requester Activity row must not expose the Reviewer action" in solver_flow
    assert "expect_review_action: bool = True" in activity_wait
    assert 'expected_view: str | None = None' in activity_wait
    assert 'page.get_by_role("tab", name=view_label, exact=True).click()' in activity_wait
    assert "review_button.first.wait_for" in activity_wait
    assert ACTIVITY_OUTPUTS == (
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
    )
    assert 'if not has_overflow' in _CAPTURE_SOURCE
    assert 'rail_visible != has_overflow' in _CAPTURE_SOURCE
    assert "_seed_activity_delivery_history(page)" in _CAPTURE_SOURCE
    assert "_seed_activity_recovery_history(page, base_url)" in _CAPTURE_SOURCE
    assert "Array.from({ length: 20 }" in _CAPTURE_SOURCE
    assert "cmp.activity.recovery.v1:" in _CAPTURE_SOURCE
    assert "Activity decision error did not retain the review reason" in _CAPTURE_SOURCE
    assert "_assert_activity_shared_density(page, width)" in _CAPTURE_SOURCE
    assert "data: token('--ux-data-font-size')" in _CAPTURE_SOURCE
    assert "metadata: token('--ux-metadata-font-size')" in _CAPTURE_SOURCE
    assert '"data": measurements["tokens"]["data"]' in _CAPTURE_SOURCE
    assert '"metadata": measurements["tokens"]["metadata"]' in _CAPTURE_SOURCE
    assert "if viewport_width == 3840:" in _CAPTURE_SOURCE
    assert 'name="Recovery needed"' in _CAPTURE_SOURCE
    assert 'expect_review_action=False' in _CAPTURE_SOURCE
    assert "context.add_init_script" in new_page
    assert "json.dumps" in new_page
    assert "page.evaluate" not in new_page
    assert new_page.index("context.add_init_script") < new_page.index("page = context.new_page()")
    assert new_page.index("page = context.new_page()") < new_page.index("page.goto(base_url)")
    assert "No review actions are assigned to this role." not in _CAPTURE_SOURCE


def test_current_capture_rejects_fixed_width_islands_in_shared_workspaces() -> None:
    capture_source = _CAPTURE_SOURCE.split("def _assert_shared_workspace_geometry", 1)[1].split(
        "def _assert_export_action_visible", 1
    )[0]

    assert "shell_box[\"width\"] < width * 0.97" in capture_source
    assert "workspace[\"width\"] < width * 0.8" in capture_source
    assert '".modeling-workspace-shell"' in capture_source
    assert '".materials-page"' in capture_source
    assert '".materials-workspace"' in capture_source
    assert '".material-detail-shell"' not in capture_source
    assert '".export-workspace"' in capture_source
    assert '".activity-shell"' in capture_source
    assert '".administration-workspace"' in capture_source
    assert '".administration-record-workbench"' in capture_source
    assert '".material-database-page"' not in capture_source
    assert '".governed-import-route"' in capture_source
    assert "_assert_shared_workspace_geometry(page, width, path.name)" in capture_source
    assert "_assert_wide_material_cluster" not in _CAPTURE_SOURCE
    assert "bounded left cluster" not in _CAPTURE_SOURCE


def test_administration_capture_checks_bounded_balanced_workgroups() -> None:
    geometry_source = _CAPTURE_SOURCE.split(
        "def _assert_semantic_three_pane_geometry", 1
    )[1].split("def _capture", 1)[0]

    assert "--ux-navigator-default-inline-size" in geometry_source
    assert "--ux-readable-form-max-inline-size" in geometry_source
    assert 'geometry["viewportWidth"] >= 2560 and group["width"] <= 1920' in geometry_source
    assert 'group["width"] < container["width"] * 0.9' in geometry_source
    assert 'geometry["navigator"]["width"] > geometry["navigatorDefault"] + 1' in geometry_source
    assert 'abs(left_margin - right_margin) > 2' in geometry_source
    assert 'form["width"] > geometry["readableFormMaximum"] + 1' in geometry_source
    assert 'group_selector=".schema-editor-grid"' in _CAPTURE_SOURCE
    assert 'form_selector=".schema-property-editor .property-sheet"' in _CAPTURE_SOURCE
    assert 'group_selector=".catalog-record-grid"' in _CAPTURE_SOURCE
    assert 'form_selector=".catalog-datasheet > form"' in _CAPTURE_SOURCE


def test_modeling_fit_capture_contract_covers_five_viewports_and_recovery_states() -> None:
    fit_viewports = tuple(
        f"modeling-fit-{width}x{height}.png"
        for width, height in ((1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160))
    )
    assert MODELING_FIT_STATE_OUTPUTS == (
        "modeling-fit-candidate-parameters-long-1440x900.png",
        "modeling-fit-candidate-evidence-scrolled-1440x900.png",
        "modeling-fit-calculation-failed-1920x1080.png",
        "modeling-fit-save-failed-1920x1080.png",
        "modeling-fit-exact-source-blocked-1920x1080.png",
        "modeling-fit-exact-read-failed-1920x1080.png",
        "modeling-fit-restored-1920x1080.png",
    )
    assert MODELING_PROCESS_FIT_OUTPUTS == (
        tuple(
            f"modeling-process-{width}x{height}.png"
            for width, height in (
                (1366, 768),
                (1440, 900),
                (1920, 1080),
                (2560, 1440),
                (3840, 2160),
            )
        )
        + fit_viewports
        + MODELING_FIT_STATE_OUTPUTS
    )
    assert all(
        name in CURRENT_CAPTURE_OUTPUTS
        for name in fit_viewports + MODELING_FIT_STATE_OUTPUTS
    )
    assert 'name=re.compile(r"^Preview .+\\/.+ blend$")' in _CAPTURE_SOURCE
    assert 'name=re.compile(r"^Selected · .+$")' in _CAPTURE_SOURCE
    assert "fitted domain$" not in _CAPTURE_SOURCE
    warned_selection = _CAPTURE_SOURCE.split(
        "def _select_warned_fit_candidate", 1
    )[1].split("def _select_exact_fit_candidate", 1)[0]
    assert 'name=re.compile(r"^.+ candidate selected$")' in warned_selection
    assert 'name=re.compile(r"^Select .+ candidate$")' in warned_selection
    measurement_gate = _CAPTURE_SOURCE.split(
        "def _measure_process_fit", 1
    )[1].split("def _assert_modeling_process_saved_rows", 1)[0]
    assert "def _assert_elastic_stage_workspace" in measurement_gate
    assert '_assert_elastic_stage_workspace("process", "Process")' in measurement_gate
    assert '_assert_elastic_stage_workspace("fit", "Fit")' in measurement_gate
    assert 'measurement["workspaceWidth"]' in measurement_gate
    assert 'measurement["workspaceHeight"]' in measurement_gate
    assert "1920 + 1" not in measurement_gate
    assert "> 879" not in measurement_gate


def test_modeling_export_capture_contract_uses_declared_preview_and_atomic_create_flow() -> None:
    export_viewports = tuple(
        f"modeling-export-{width}x{height}.png"
        for width, height in (
            (1366, 768),
            (1440, 900),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        )
    )
    assert MODELING_EXPORT_OUTPUTS == (
        *export_viewports,
        "modeling-export-source-blocked-1440x900.png",
        "modeling-export-approximation-blocked-1440x900.png",
        "modeling-export-delivered-1440x900.png",
    )
    assert set(MODELING_EXPORT_OUTPUTS) <= set(CURRENT_CAPTURE_OUTPUTS)
    recovery_helper = _CAPTURE_SOURCE.split(
        "def _prepare_exact_metal_source_if_needed", 1
    )[1].split("def _prepare_exact_target_preview", 1)[0]
    assert 'get_by_role(\n        "heading", name="Prepare selected model", exact=True' in recovery_helper
    assert 'get_by_role(\n        "checkbox",\n        name="I reviewed the extrapolated range used by this model.",' in recovery_helper
    assert 'get_by_role("textbox", name="Reason for preparing model", exact=True)' in recovery_helper
    assert 'get_by_role(\n        "button", name="Prepare selected model", exact=True' in recovery_helper
    assert "EXPORT_RECOVERY_REASON" in recovery_helper
    assert "Retry preparation" in recovery_helper
    assert 'page.on("dialog", reject_dialog)' in recovery_helper
    assert "dialog.dismiss()" in recovery_helper
    assert "page.remove_listener(\"dialog\", reject_dialog)" in recovery_helper
    assert "section.modeling-target-preview.export-workspace .export-workspace-grid" in recovery_helper
    assert recovery_helper.index("if not recovery_heading.count()") < recovery_helper.index(
        "acknowledgement.wait_for"
    )
    assert recovery_helper.index("reason.fill(EXPORT_RECOVERY_REASON)") < recovery_helper.index(
        "prepare.click()"
    )
    assert recovery_helper.index("prepare.click()") < recovery_helper.index(
        "page.wait_for_function(", recovery_helper.index("prepare.click()")
    )

    module = ast.parse(_CAPTURE_SOURCE)
    fit_export_helper = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == "_prepare_fit_for_export"
    )
    fit_export_helper_source = ast.get_source_segment(_CAPTURE_SOURCE, fit_export_helper)
    assert fit_export_helper_source is not None
    assert "_prepare_fit_from_saved_process(" in fit_export_helper_source
    assert "require_material_record=True" in fit_export_helper_source
    assert "_click_modeling_fit_preview_and_wait(page)" in fit_export_helper_source
    assert fit_export_helper_source.index(
        "_prepare_fit_from_saved_process("
    ) < fit_export_helper_source.index("_click_modeling_fit_preview_and_wait(page)")

    fit_source_helper = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_prepare_fit_from_saved_process"
    )
    fit_source_helper_source = ast.get_source_segment(_CAPTURE_SOURCE, fit_source_helper)
    assert fit_source_helper_source is not None
    assert "if require_material_record:" in fit_source_helper_source
    assert fit_source_helper_source.index(
        "_resolve_exact_material_record(page, base_url)"
    ) < fit_source_helper_source.index("_save_process_output_for_fit(")

    export_capture = _CAPTURE_SOURCE.split(
        "def _capture_modeling_export_only", 1
    )[1].split("def _capture_modeling(", 1)[0]
    assert export_capture.count("_prepare_fit_for_export(") == 4
    assert export_capture.count("_save_exact_fit_selection(") == 4
    normal_flow = export_capture.split("    for width, height", 1)[1].split(
        "    source_blocked_page =", 1
    )[0]
    approximation_flow = export_capture.split("    approximation =", 1)[1].split(
        "    delivered =", 1
    )[0]
    delivered_flow = export_capture.split("    delivered =", 1)[1]
    source_blocked_flow = export_capture.split("    source_blocked_page =", 1)[1].split(
        "    approximation =", 1
    )[0]
    normal_fit_prepare = normal_flow.index("_prepare_fit_for_export(")
    normal_fit_save = normal_flow.index(
        '_save_exact_fit_selection(page, candidate_key="swift+voce", require_warning=False)'
    )
    normal_open = normal_flow.index('_open_modeling_stage(page, "export")')
    normal_recovery = normal_flow.index("_prepare_exact_metal_source_if_needed(page)")
    normal_preview = normal_flow.index("_prepare_exact_target_preview(page)")
    assert normal_fit_prepare < normal_fit_save < normal_open < normal_recovery < normal_preview
    assert "_ensure_neutral_material_record_binding(" not in normal_flow
    assert 'if page.get_by_role("button", name="Create solver card", exact=True).count()' not in normal_flow
    source_fit_prepare = source_blocked_flow.index("_prepare_fit_for_export(")
    source_fit_save = source_blocked_flow.index(
        '_save_exact_fit_selection(source_blocked_page, candidate_key="swift+voce", require_warning=False)'
    )
    source_open = source_blocked_flow.index('_open_modeling_stage(source_blocked_page, "export")')
    source_heading = source_blocked_flow.index(
        'source_blocked_page.get_by_role("heading", name="Prepare selected model", exact=True)'
    )
    source_capture = source_blocked_flow.index("_capture(source_blocked_page")
    assert source_fit_prepare < source_fit_save < source_open < source_heading < source_capture
    approximation_open = approximation_flow.index('_open_modeling_stage(approximation, "export")')
    approximation_recovery = approximation_flow.index(
        "_prepare_exact_metal_source_if_needed(approximation)"
    )
    approximation_preview = approximation_flow.index("_prepare_exact_target_preview(")
    assert approximation_flow.index("_prepare_fit_for_export(") < approximation_flow.index(
        '_save_exact_fit_selection(approximation, candidate_key="swift+voce", require_warning=False)'
    ) < approximation_open < approximation_recovery < approximation_preview
    assert "_ensure_neutral_material_record_binding(" not in approximation_flow
    delivered_open = delivered_flow.index('_open_modeling_stage(delivered, "export")')
    delivered_recovery = delivered_flow.index("_prepare_exact_metal_source_if_needed(delivered)")
    delivered_binding = delivered_flow.index(
        "_ensure_neutral_material_record_binding(delivered, base_url)"
    )
    delivered_preview = delivered_flow.index("_prepare_exact_target_preview(delivered")
    assert delivered_flow.index("_prepare_fit_for_export(") < delivered_flow.index(
        '_save_exact_fit_selection(delivered, candidate_key="swift+voce", require_warning=False)'
    ) < delivered_open < delivered_recovery < delivered_binding < delivered_preview
    assert export_capture.count("_ensure_neutral_material_record_binding(") == 1
    assert "_prepare_exact_metal_source_if_needed" not in source_blocked_flow

    binding_helper = _CAPTURE_SOURCE.split(
        "def _ensure_neutral_material_record_binding", 1
    )[1].split("def _prepare_exact_target_preview", 1)[0]
    assert "/api/v1/catalog/domain-bindings:resolve" in binding_helper
    assert "material_record = _resolve_exact_material_record(page, base_url)" in binding_helper
    assert "published_only=true" not in binding_helper
    assert "published Material workflow has no Neutral Material Record" not in binding_helper
    assert "/domain-binding`" in binding_helper
    assert 'kind: "neutral_material"' in binding_helper
    assert 'status: "created"' in binding_helper
    assert 'status: "reused"' in binding_helper

    export_flow = _CAPTURE_SOURCE.split(
        "def _prepare_exact_target_preview", 1
    )[1].split("def _capture_modeling_export_only", 1)[0]
    assert 'page.get_by_role("heading", name=STAGE_HEADINGS["export"], exact=True)' not in export_flow
    assert 'export_region = page.locator("section.modeling-target-preview.export-workspace")' in export_flow
    assert 'export_grid = export_region.locator(":scope > .export-workspace-grid")' in export_flow
    assert 'export_region.wait_for(state="visible", timeout=30_000)' in export_flow
    assert 'export_grid.wait_for(state="visible", timeout=30_000)' in export_flow
    assert 'target = export_grid.get_by_role("combobox", name="Solver target", exact=True)' in export_flow
    region_wait = export_flow.index('export_region.wait_for(state="visible", timeout=30_000)')
    grid_locator = export_flow.index('export_grid = export_region.locator(":scope > .export-workspace-grid")')
    grid_wait = export_flow.index('export_grid.wait_for(state="visible", timeout=30_000)')
    target_locator = export_flow.index('target = export_grid.get_by_role("combobox", name="Solver target", exact=True)')
    assert region_wait < grid_locator < grid_wait < target_locator
    assert 'get_by_role("combobox", name="Solver target", exact=True)' in export_flow
    assert 'select_option("abaqus/2025/kg_m_s")' in export_flow
    assert 'page.locator("details.export-advanced-input")' in export_flow
    assert 'advanced.locator(":scope > summary")' in export_flow
    assert 'summary.inner_text().strip() != "Native card options"' in export_flow
    assert 'advanced.get_attribute("open") is None' in export_flow
    assert 'summary.click()' in export_flow
    assert 'native_name.wait_for(state="visible", timeout=30_000)' in export_flow
    assert 'native_name.fill("DP780_C1_REFERENCE")' in export_flow
    target_selection = export_flow.index("target.select_option")
    disclosure_open = export_flow.index("summary.click()")
    native_name_fill = export_flow.index('native_name.fill("DP780_C1_REFERENCE")')
    assert target_selection < disclosure_open < native_name_fill
    assert ".fill(\"DP780_C1_REFERENCE\", force=True)" not in export_flow
    assert "evaluate(\"" not in export_flow
    assert 'get_by_label("Native preview", exact=True).locator("pre").wait_for' in export_flow
    assert 'document.querySelector(\'[aria-label="Native preview"] pre\')\n          ||' not in export_flow
    assert 'document.querySelectorAll(\n            \'.export-main .export-preview-state\'\n          )' in export_flow
    assert 'document.querySelectorAll(\'[role="heading"]\')' not in export_flow
    assert 'heading.textContent?.trim() === "Not created"' in export_flow
    assert 'document.querySelector(\'[role="alert"]\')' in export_flow
    assert 'get_by_role("button", name="Run Export check", exact=True)' in export_flow
    assert 'create_button.count() != 1' in export_flow
    assert 'expected_status = "Ready to create" if acknowledge else "Review required"' in export_flow
    assert "should_be_disabled = not acknowledge" in export_flow
    assert "Current Export task must expose exactly one visible primary action" in export_flow
    assert "Export task must expose exactly one visible primary action before C1" in export_flow
    run_check = export_flow.index(
        'get_by_role("button", name="Run Export check", exact=True)'
    )
    terminal_wait = export_flow.index('terminalHeading || visibleAlert')
    native_preview_wait = export_flow.index(
        'get_by_label("Native preview", exact=True).locator("pre").wait_for',
        terminal_wait,
    )
    assert run_check < terminal_wait < native_preview_wait
    assert "preview_only Export must not expose a delivered success status" in export_flow
    assert "preview_only Export must not expose a delivery receipt" in export_flow
    assert "preview_only Export must not expose an Open solver card pointer" in export_flow
    assert 'details.export-delivery-details' in export_flow
    assert 'for resource in ("solver_card", "preview", "download", "receipt")' in export_flow
    assert 'get_by_role("button", name="Open solver card", exact=True)' in export_flow
    assert "delivery_error.all_inner_texts()" in export_flow
    assert "after_animation: Callable[[], object] | None = None" in _CAPTURE_SOURCE
    assert "def _assert_export_capture_shell(page: Page)" in _CAPTURE_SOURCE
    assert "application-workspace" in _CAPTURE_SOURCE
    assert "outerScrollZero" in _CAPTURE_SOURCE
    assert "shellVisible" in _CAPTURE_SOURCE
    assert "shellStacked" in _CAPTURE_SOURCE
    assert "workspace: workspace.scrollTop" in _CAPTURE_SOURCE
    assert "workbench: workbench.scrollTop" in _CAPTURE_SOURCE
    assert "exportRegion: exportRegion.scrollTop" in _CAPTURE_SOURCE
    assert "#modeling-export-native-preview-viewport" in _CAPTURE_SOURCE
    assert "#modeling-export-mapping-viewport" in _CAPTURE_SOURCE
    assert "exportLocalScrollOrigins" in _CAPTURE_SOURCE
    assert "exportLocalScrollZero" in _CAPTURE_SOURCE
    capture_helper = _CAPTURE_SOURCE.split("def _capture(", 1)[1].split(
        "def _assert_export_action_visible", 1
    )[0]
    assert capture_helper.index("await new Promise(requestAnimationFrame)") < capture_helper.index(
        "if after_animation is not None:"
    ) < capture_helper.index("page.screenshot")
    assert "def _assert_export_action_visible(page: Page, label: str)" in _CAPTURE_SOURCE
    assert 'page.get_by_role("button", name=label, exact=True)' in _CAPTURE_SOURCE
    assert 'page.evaluate("() => window.scrollY")' in _CAPTURE_SOURCE
    assert 'details.export-advanced-input' in _CAPTURE_SOURCE
    assert "def _assert_export_recovery_capture(page: Page)" in _CAPTURE_SOURCE
    assert "pane.scrollTop =" in _CAPTURE_SOURCE
    assert "paneScrollTop: pane.scrollTop" in _CAPTURE_SOURCE
    assert "details.export-prerequisite-evidence" in _CAPTURE_SOURCE
    assert "evidenceClosed: evidence.getAttribute('open') === null && !evidence.open" in _CAPTURE_SOURCE
    assert "localOverflow: pane.scrollHeight > pane.clientHeight" in _CAPTURE_SOURCE
    assert "visibleRecoveryClipped" in _CAPTURE_SOURCE
    assert 'metrics["visibleRecoveryClipped"]' in _CAPTURE_SOURCE
    assert 'metrics["paneScrollTop"] <= 0' not in _CAPTURE_SOURCE
    recovery_capture = _CAPTURE_SOURCE.split(
        "def _assert_export_recovery_capture", 1
    )[1].split("def _open_materials_search", 1)[0]
    assert recovery_capture.index("const evidence =") < recovery_capture.index(
        "const visibleRecoveryNodes ="
    ) < recovery_capture.index("visibleRecoveryClipped") < recovery_capture.index(
        'metrics["visibleRecoveryClipped"]'
    )
    assert "before_screenshot=lambda page=page: _assert_export_action_visible(page, \"Create solver card\")" in _CAPTURE_SOURCE
    assert "after_animation=lambda page=page: _assert_export_capture_shell(page)" in _CAPTURE_SOURCE
    assert "before_screenshot=lambda: _assert_export_recovery_capture(source_blocked_page)" in _CAPTURE_SOURCE
    assert "before_screenshot=lambda: _assert_export_action_visible(approximation, \"Create solver card\")" in _CAPTURE_SOURCE
    assert "after_animation=lambda: _assert_export_capture_shell(approximation)" in _CAPTURE_SOURCE
    assert "before_screenshot=lambda: _assert_export_action_visible(delivered, \"Open solver card\")" in _CAPTURE_SOURCE
    assert "after_animation=lambda: _assert_export_capture_shell(delivered)" in _CAPTURE_SOURCE
    assert 'get_by_role("heading", name="Prepare selected model", exact=True)' in _CAPTURE_SOURCE
    assert 'target_value="openradioss/2025/kg_m_s"' in _CAPTURE_SOURCE
    assert 'modeling-export-source-blocked-1440x900.png' in _CAPTURE_SOURCE
    assert 'modeling-export-approximation-blocked-1440x900.png' in _CAPTURE_SOURCE
    assert 'modeling-export-delivered-1440x900.png' in _CAPTURE_SOURCE
    assert 'open_card.click()' in _CAPTURE_SOURCE
    assert 'get_by_role("button", name="Deliver native card", exact=True)' not in export_flow
    assert 'get_by_role("button", name="Change solver target", exact=True)' not in export_flow
    assert '".export-properties"' in _CAPTURE_SOURCE
    assert '".export-main"' in _CAPTURE_SOURCE
    assert '".export-result"' in _CAPTURE_SOURCE
    assert '".export-native-preview-shell > .native-preview"' not in _CAPTURE_SOURCE
    assert '".mapping-scroll"' in _CAPTURE_SOURCE


def test_capture_contract_rejects_positional_wait_for_function_arguments() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    wait_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "wait_for_function"
    ]
    assert wait_calls
    assert [node.lineno for node in wait_calls if len(node.args) > 1] == []

    target_preview_call = next(
        node
        for node in wait_calls
        if any(
            keyword.arg == "arg"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "expected_status"
            for keyword in node.keywords
        )
    )
    assert len(target_preview_call.args) == 1


def test_modeling_fit_capture_saves_exact_process_source_and_scrolls_evidence_locally() -> None:
    assert "_save_process_output_for_fit(" in _CAPTURE_SOURCE
    assert "_prepare_modeling_process(page, base_url, verify_data_reload=False)" in _CAPTURE_SOURCE
    assert "processingOutput" in _CAPTURE_SOURCE
    assert "metal-fit-runs" in _CAPTURE_SOURCE
    assert 'get_by_role("button", name="Candidate parameters", exact=True)' in _CAPTURE_SOURCE
    assert 'fit-evidence-drawer#fit-evidence-dock' in _CAPTURE_SOURCE
    assert 'drawer.locator(".fit-evidence-body")' in _CAPTURE_SOURCE
    assert 'get_by_role("button", name="Close", exact=True)' in _CAPTURE_SOURCE
    assert "scrollbar gutter" in _CAPTURE_SOURCE
    scroll_fn_start = _CAPTURE_SOURCE.index("def _scroll_fit_evidence_locally")
    scroll_fn_end = _CAPTURE_SOURCE.index(
        "\ndef _assert_modeling_process_preview", scroll_fn_start
    )
    scroll_fn_source = _CAPTURE_SOURCE[scroll_fn_start:scroll_fn_end]
    assert "12 <= gutter <= 16" in scroll_fn_source
    assert "12-16 px inclusive" in scroll_fn_source
    reset_index = scroll_fn_source.index("el.scrollTop = 0;")
    reset_left_index = scroll_fn_source.index("el.scrollLeft = 0;", reset_index)
    focus_index = scroll_fn_source.index(
        "el.focus({ preventScroll: true });", reset_left_index
    )
    metrics_index = scroll_fn_source.index("metrics = body.evaluate", focus_index)
    page_down_index = scroll_fn_source.index(
        'body.press("PageDown")', metrics_index
    )
    assert (
        reset_index < reset_left_index < focus_index < metrics_index < page_down_index
    )
    assert "native-thumb drag" in _CAPTURE_SOURCE
    assert "page.mouse.down()" in _CAPTURE_SOURCE
    assert "window.scrollY" in _CAPTURE_SOURCE
    assert 'body.press("PageDown")' in _CAPTURE_SOURCE
    assert "page.keyboard.press(\"Escape\")" in _CAPTURE_SOURCE
    assert "Candidate selection reason" in _CAPTURE_SOURCE
    assert "Acknowledge selected candidate warning" in _CAPTURE_SOURCE


def test_modeling_fit_scrolled_capture_positions_the_local_decision_surface() -> None:
    assert "def _position_fit_evidence_decision_surface" in _CAPTURE_SOURCE
    position_start = _CAPTURE_SOURCE.index("def _position_fit_evidence_decision_surface")
    position_end = _CAPTURE_SOURCE.index(
        "\ndef _assert_modeling_process_preview", position_start
    )
    position_source = _CAPTURE_SOURCE[position_start:position_end]
    assert 'table[aria-label="Selected candidate parameters and bounds"]' in position_source
    assert 'Candidate selection reason' in position_source
    assert 'Acknowledge selected candidate warning' in position_source
    assert "window.scrollY" in position_source
    assert "const meaningfulVisiblePx = 12;" in position_source
    assert "const intersectionBounds" in position_source
    assert "const tableBottomBounds" in position_source
    assert "const warningTextSurface" in position_source
    assert "document.createRange()" in position_source
    assert "range.getClientRects()" in position_source
    assert "Fit warning text range has no rendered text rects" in position_source
    assert "const acknowledgementInputSurface" in position_source
    assert "const acknowledgementInputIntersection" in position_source
    assert "const feasibleLower = Math.max" in position_source
    assert "const feasibleUpper = Math.min" in position_source
    assert "const integerLower = Math.ceil(feasibleLower);" in position_source
    assert "const integerUpper = Math.floor(feasibleUpper);" in position_source
    assert "const hasFeasibleInteger = integerLower <= integerUpper;" in position_source
    assert "const targetScrollTop = hasFeasibleInteger" in position_source
    assert "if (targetScrollTop !== null)" in position_source
    assert "el.scrollTop = targetScrollTop" in position_source
    assert "const visibleRange = (rangeSurface)" in position_source
    assert "warningText: visibleRange(warningTextSurface)" in position_source
    assert "acknowledgementInput: visible(acknowledgement)" in position_source
    assert "intersection," in position_source
    assert "intersects: intersection >= meaningfulVisiblePx" in position_source
    assert 'metrics["targetScrollTop"] is None' in position_source
    assert "no feasible local scroll interval" in position_source
    assert 'metrics[key]["intersection"] < metrics["meaningfulVisiblePx"]' in position_source
    assert position_source.index("const feasibleLower = Math.max") < position_source.index(
        "const targetScrollTop = hasFeasibleInteger"
    )
    assert position_source.index("const targetScrollTop = hasFeasibleInteger") < position_source.index(
        "el.scrollTop = targetScrollTop"
    )
    assert position_source.index('metrics["targetScrollTop"] is None') < position_source.index(
        'metrics["scrollTop"] <= 0'
    )
    callback_start = _CAPTURE_SOURCE.index("def prepare_scrolled_capture")
    callback_end = _CAPTURE_SOURCE.index("\n\n    _capture(", callback_start)
    callback_source = _CAPTURE_SOURCE[callback_start:callback_end]
    assert callback_source.index("_scroll_fit_evidence_locally") < callback_source.index(
        "_position_fit_evidence_decision_surface"
    )


def test_modeling_fit_capture_enforces_elastic_shell_rows_scale_and_collision_geometry() -> None:
    assert "_assert_fit_display_scale" in _CAPTURE_SOURCE
    assert ".modeling-workspace-stage-fit" in _CAPTURE_SOURCE
    assert "fitInput" in _CAPTURE_SOURCE
    assert "fitStepCount" in _CAPTURE_SOURCE
    assert "fitGroups" in _CAPTURE_SOURCE
    assert "fitRemoveStep" in _CAPTURE_SOURCE
    assert "fitEvidenceTrigger" in _CAPTURE_SOURCE
    assert "fitTopActions" in _CAPTURE_SOURCE
    for style_key in (
        "borderRadius",
        "fontSize",
        "fontWeight",
        "backgroundColor",
        "borderColor",
        "color",
    ):
        assert style_key in _CAPTURE_SOURCE
    assert 'style_key in ("borderRadius", "fontSize", "fontWeight")' in _CAPTURE_SOURCE
    assert 'style_key in ("backgroundColor", "borderColor", "color")' in _CAPTURE_SOURCE
    assert "Fit Advanced/Preview secondary" in _CAPTURE_SOURCE
    assert "Ghosh exceeds chart scale" in _CAPTURE_SOURCE
    assert "extrapolation-annotation-layer text" in _CAPTURE_SOURCE
    assert "extrapolation-region rect" in _CAPTURE_SOURCE
    assert "typeof node.getBBox !== 'function'" in _CAPTURE_SOURCE
    assert "label_geometry.get(\"bottom\")" in _CAPTURE_SOURCE
    assert "shade_geometry.get(\"top\")" in _CAPTURE_SOURCE
    assert "escaped the SVG/plot bounds" in _CAPTURE_SOURCE
    assert 're.fullmatch(r"Tensile test \\d{4}"' in _CAPTURE_SOURCE
    assert 'minimum_rail_width = _css_token_px(page, "--ux-navigator-min-inline-size")' in _CAPTURE_SOURCE
    assert 'default_rail_width = _css_token_px(page, "--ux-navigator-default-inline-size")' in _CAPTURE_SOURCE
    assert 'minimum_rail_width - 1 <= measurement["railWidth"] <= default_rail_width + 1' in _CAPTURE_SOURCE
    assert 'expected_ribbon_height = _css_token_px(page, "--ux-workbench-ribbon-block-size")' in _CAPTURE_SOURCE
    assert 'abs(measurement["ribbonHeight"] - expected_ribbon_height) > 1' in _CAPTURE_SOURCE
    assert "segmentIntersectsRect" in _CAPTURE_SOURCE
    assert "legendCurveSegmentOverlap" in _CAPTURE_SOURCE
    assert "legendExtrapolationBoundaryOverlap" in _CAPTURE_SOURCE
    assert "legendExtrapolationLabelOverlap" in _CAPTURE_SOURCE
    assert "legendStateOverlayOverlap" in _CAPTURE_SOURCE
    assert "lastXTickWithinSvg" in _CAPTURE_SOURCE
    assert "xTicksWithinSvg" in _CAPTURE_SOURCE
    assert "legendOutsideSvg" in _CAPTURE_SOURCE


def test_modeling_fit_capture_resolves_hardening_clip_path_and_curve_containment() -> None:
    assert "hardening-series-clip" in _CAPTURE_SOURCE
    assert "const hardeningGroup = svg.querySelector('.hardening-series-clip')" in _CAPTURE_SOURCE
    assert "const clipPathUrl = hardeningGroup?.getAttribute('clip-path') || ''" in _CAPTURE_SOURCE
    assert "const clipPathMatch = clipPathUrl.match" in _CAPTURE_SOURCE
    assert "const clipPathId = clipPathMatch?.[1] || ''" in _CAPTURE_SOURCE
    assert "svg.ownerDocument?.getElementById(clipPathId)" in _CAPTURE_SOURCE
    assert "const clipRect = attributeBox(clipPath?.querySelector('rect'))" in _CAPTURE_SOURCE
    assert "curveLines.every(line => hardeningGroup.contains(line))" in _CAPTURE_SOURCE
    assert "curveLinesContained" in _CAPTURE_SOURCE
    assert "hardeningClip" in _CAPTURE_SOURCE
    assert "hardening_clip_rect" in _CAPTURE_SOURCE
    assert "hardening_clip_geometry.get(\"curveLinesContained\") is not True" in _CAPTURE_SOURCE
    assert "hardening_clip_rect.get(\"top\")" in _CAPTURE_SOURCE
    assert "shade_geometry.get(\"top\")" in _CAPTURE_SOURCE
    assert "label_geometry.get(\"bottom\")" in _CAPTURE_SOURCE
    assert "hardening curves are not contained by a resolved clipPath" in _CAPTURE_SOURCE


def test_modeling_fit_capture_states_route_calculation_save_and_exact_read_failures() -> None:
    for path in MODELING_FIT_STATE_OUTPUTS:
        assert f'output / "{path}"' in _CAPTURE_SOURCE
    assert '"**/api/v1/metal-fit-runs"' in _CAPTURE_SOURCE
    assert '"**/api/v1/processing-outputs"' in _CAPTURE_SOURCE
    assert '"**/api/v1/processing-outputs/*/content"' in _CAPTURE_SOURCE
    assert "deterministic Fit calculation failure" in _CAPTURE_SOURCE
    assert "deterministic Fit save failure" in _CAPTURE_SOURCE
    assert "deterministic saved Fit exact-read failure" in _CAPTURE_SOURCE
    assert "Retry exact saved Fit" in _CAPTURE_SOURCE
    assert '"Saved Fit result unavailable", exact=False' in _CAPTURE_SOURCE
    assert (
        "No saved Process Output is bound. Save Process before calculating Fit."
        in _CAPTURE_SOURCE
    )
    assert 'get_by_role("button", name="Back to Process", exact=True)' in _CAPTURE_SOURCE
    assert "blocked_history" in _CAPTURE_SOURCE
    assert "blocked_requests" in _CAPTURE_SOURCE
    assert "Restored Fit output lost its selected candidate/reason evidence" in _CAPTURE_SOURCE


def test_fit_exact_source_blocker_uses_visible_anchored_process_stage_name() -> None:
    blocker_flow = _CAPTURE_SOURCE.split(
        "    fit_blocked = _new_page", 1
    )[1].split("    exact_read_failed = _new_page", 1)[0]

    assert 'get_by_role("button", name=re.compile(r"^Process\\b"))' in blocker_flow
    assert "process_stage.count() != 1" in blocker_flow
    assert "process_stage.is_visible()" in blocker_flow
    assert 'get_by_role("button", name="Process", exact=True)' not in blocker_flow


def test_fit_exact_source_blocker_scopes_duplicate_copy_to_plot_overlay() -> None:
    blocker_flow = _CAPTURE_SOURCE.split(
        "    fit_blocked = _new_page", 1
    )[1].split("    exact_read_failed = _new_page", 1)[0]

    assert 'fit_plot_overlay = fit_blocked.locator(\n        "#modeling-fit .engineering-curve-plot-empty-overlay"\n    )' in blocker_flow
    assert 'fit_plot_overlay.get_by_text(\n        fit_blocker_message,\n        exact=True,\n    )' in blocker_flow
    assert 'fit_source_binding = fit_blocked.locator(".fit-context-source")' in blocker_flow
    assert 'fit_source_binding.inner_text().strip() != "No saved Process Output"' in blocker_flow
    assert "fit_blocked.get_by_text(" not in blocker_flow
    assert ".first" not in blocker_flow


def test_fit_exact_source_recovery_assertion_starts_after_blocked_screenshot() -> None:
    blocker_flow = _CAPTURE_SOURCE.split(
        "    fit_blocked = _new_page", 1
    )[1].split("    exact_read_failed = _new_page", 1)[0]
    screenshot = blocker_flow.index(
        'output / "modeling-fit-exact-source-blocked-1920x1080.png"'
    )
    evidence_reset = blocker_flow.index("blocked_requests: list[str] = []")
    listener = blocker_flow.index(
        'fit_blocked.on("request", record_blocked_recovery_request)'
    )
    recovery_click = blocker_flow.index(
        'fit_blocked.get_by_role("button", name="Back to Process", exact=True).click()'
    )
    listener_cleanup = blocker_flow.index(
        'fit_blocked.remove_listener("request", record_blocked_recovery_request)'
    )
    recovered_history = blocker_flow.index("recovered_history = {")
    non_get_check = blocker_flow.index("allowed_preview_path = \"/api/v1/processing:preview\"")

    assert (
        screenshot
        < evidence_reset
        < listener
        < recovery_click
        < recovered_history
        < non_get_check
        < listener_cleanup
    )
    assert "method = str(getattr(request, \"method\", \"\")).upper()" in blocker_flow
    assert "url = str(getattr(request, \"url\", \"\"))" in blocker_flow
    assert 'blocked_requests.append(f"{method} {url}")' in blocker_flow
    assert 'request.startswith("POST ")' in blocker_flow
    assert 'urlsplit(request.split(" ", 1)[1]).path == allowed_preview_path' in blocker_flow
    assert "blocked_requests: list[str] = []\n    fit_blocked.on(\"request\", lambda" not in blocker_flow


def test_fit_save_stays_on_fit_and_explicitly_navigates_export_only_at_callers() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    save_node = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_save_exact_fit_selection"
    )
    save_source = ast.get_source_segment(_CAPTURE_SOURCE, save_node)
    assert save_source is not None
    assert 'get_by_text(\n        "Saved current", exact=True' in save_source
    assert 'parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]' in save_source
    assert "processingOutput" in save_source
    assert 'pointer.get(key)' in save_source
    assert "_prepare_exact_target_preview" not in save_source
    assert "stage=export" not in save_source

    export_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_export_only", 1
    )[1].split("def _capture_modeling(", 1)[0]
    assert export_only.index(
        '_save_exact_fit_selection(page, candidate_key="swift+voce", require_warning=False)'
    ) < export_only.index(
        '_open_modeling_stage(page, "export")'
    ) < export_only.index("_prepare_exact_target_preview(page)")

    generic = _CAPTURE_SOURCE.split(
        "def _capture_modeling(", 1
    )[1].split("def _measure_process_fit", 1)[0]
    assert "for stage, heading in STAGE_HEADINGS.items()" in generic
    assert '_open_modeling_stage(page, stage)' in generic
    assert "_save_exact_fit_selection(page)" in generic
    assert (
        'page.get_by_role("button", name="Save fit & continue", exact=True).click()'
        not in generic
    )

    consistency = _CAPTURE_SOURCE.split(
        "def _capture_modeling_consistency", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    assert "comparison_open=True" in consistency
    comparison_open = consistency.index("comparison_open=True")
    comparison_close = consistency.index(
        'page.get_by_role("button", name="Close comparison", exact=True).click()'
    )
    normal_capture = consistency.index(
        '_capture(page, output / f"modeling-data-{width}x{height}.png"'
    )
    assert comparison_open < comparison_close < normal_capture
    assert "comparison_open=False" in consistency[comparison_close:normal_capture]
    assert 'minimum_rail_width = _css_token_px(' in consistency
    assert '"--ux-navigator-min-inline-size"' in consistency
    assert '"--ux-navigator-default-inline-size"' in consistency
    assert 'curve rail escaped the shared readable range' in consistency
    process_source = consistency.index("_save_process_output_for_fit(")
    fit_preview = consistency.index("_click_modeling_fit_preview_and_wait(page)")
    fit_save = consistency.index("_save_exact_fit_selection(page)")
    assert process_source < fit_preview < fit_save
    open_export = consistency.index('_open_modeling_stage(page, "export")')
    recover_source = consistency.index("_prepare_exact_metal_source_if_needed(page)")
    prepare_target = consistency.index("_prepare_exact_target_preview(page)")
    assert fit_save < open_export < recover_source < prepare_target
    export_assertion = consistency.index("_assert_export_exact_source_surface(page)")
    export_capture = consistency.index('"surface": "exact-target-preview"')
    export_continue = consistency.index("                continue", export_capture)
    plot_geometry = consistency.index("_measure_process_fit(", export_continue)
    assert prepare_target < export_assertion < export_capture < export_continue < plot_geometry
    assert '_assert_export_action_visible(\n                        page, "Create solver card"' in consistency
    assert "after_animation=lambda page=page: _assert_export_capture_shell(page)" in consistency


def test_fit_save_allows_only_the_expected_exact_restore_error_after_commit_proof() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    save_node = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_save_exact_fit_selection"
    )
    save_source = ast.get_source_segment(_CAPTURE_SOURCE, save_node)
    assert save_source is not None
    assert "allow_expected_exact_restore_failure: bool = False" in save_source
    assert "EXPECTED_EXACT_FIT_RESTORE_ERROR" in save_source
    assert "not allow_expected_exact_restore_failure or not error_text.startswith(" in save_source
    assert 'get_by_text(\n        "Saved current", exact=True' in save_source
    assert save_source.index('get_by_text(\n        "Saved current", exact=True') < save_source.rindex(
        'parse_qs(urlsplit(page.url).query).get("stage") != ["fit"]'
    )
    assert save_source.index('pointer.get(key)') < save_source.index('error_banner = page.locator(".error-banner")')

    exact_read_failed_flow = _CAPTURE_SOURCE.split(
        "    exact_read_failed = prepared_fit", 1
    )[1].split("    restored = prepared_fit", 1)[0]
    assert (
        "_save_exact_fit_selection(\n"
        "        exact_read_failed,\n"
        "        allow_expected_exact_restore_failure=True,\n"
        "    )"
    ) in exact_read_failed_flow


def test_restored_fit_counts_only_the_exact_processing_output_content_read() -> None:
    restored_flow = _CAPTURE_SOURCE.split(
        "    restored = prepared_fit", 1
    )[1].split("def _capture_modeling_process_fit", 1)[0]

    assert 'r"/api/v1/processing-outputs/[^/]+/content"' in restored_flow
    assert "urlsplit(url).path" in restored_flow
    assert "expected_restore_url" in restored_flow

    for caller in (
        "_capture_modeling_export_only",
        "_capture_modeling(",
        "_capture_modeling_consistency",
    ):
        caller_source = _CAPTURE_SOURCE.split(f"def {caller}", 1)[1]
        if caller == "_capture_modeling(":
            caller_source = caller_source.split("def _measure_process_fit", 1)[0]
        elif caller == "_capture_modeling_export_only":
            caller_source = caller_source.split("def _capture_modeling(", 1)[0]
        else:
            caller_source = caller_source.split("def _capture_modeling_data_viewports", 1)[0]
        assert "allow_expected_exact_restore_failure=True" not in caller_source


def test_warned_fit_candidate_selection_uses_warning_cell_not_stability_text() -> None:
    table = _FakeCandidateTable(
        [
            [
                "Select candidate",
                "Voce",
                "Recommended",
                "RMSE",
                "strain range",
                "Converged · active bound none",
                "Identifiable · active bound none",
                "None",
            ],
            [
                "Select candidate",
                "Ghosh",
                "—",
                "RMSE",
                "strain range",
                "Converged · active bound none",
                "Structurally identifiable combination",
                "Ghosh n and p are not separately identifiable",
            ],
        ]
    )

    _select_warned_fit_candidate(table)

    assert table.selected_index == 1


def test_warned_fit_candidate_selection_rejects_rows_without_warning() -> None:
    table = _FakeCandidateTable(
        [
            [
                "Select candidate",
                "Voce",
                "Recommended",
                "RMSE",
                "strain range",
                "Converged · active bound none",
                "Identifiable · active bound none",
                "None",
            ],
            [
                "Select candidate",
                "Swift",
                "—",
                "RMSE",
                "strain range",
                "Converged · active bound none",
                "Identifiable · active bound none",
                "None",
            ],
        ]
    )

    with pytest.raises(RuntimeError, match="did not expose a warned candidate"):
        _select_warned_fit_candidate(table)

    assert table.selected_index is None


def test_exact_fit_export_candidate_selector_is_anchored_case_insensitive_and_unique() -> None:
    helper = _CAPTURE_SOURCE.split("def _select_exact_fit_candidate", 1)[1].split(
        "def _assert_fit_selected_evidence", 1
    )[0]

    assert 're.compile(\n            r"^Select swift \\+ voce 50[/]50 candidate$",\n            re.IGNORECASE,\n        )' in helper
    assert '50/50 candidate$' not in helper
    assert 'table.get_by_role("button", name=label)' in helper
    assert "candidate.count() != 1" in helper
    assert "_select_warned_fit_candidate" not in helper
    assert ".first" not in helper
    assert ".last" not in helper
    assert "exact=True" not in helper


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
    assert call_names.index("_capture_modeling_process_only") < call_names.index(
        "_capture_modeling_fit_states"
    ) < call_names.index("_capture_modeling_data_viewports")


def test_fit_viewport_capture_routes_all_states_for_targeted_and_default_producers() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    process_fit = next(
        node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_capture_modeling_process_fit"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_capture_modeling_fit_states"
        for node in ast.walk(process_fit)
    )
    producer = next(
        node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "produce"
    )
    producer_calls = {
        node.func.id
        for node in ast.walk(producer)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_capture_modeling_fit_states" in producer_calls
    assert set(MODELING_FIT_STATE_OUTPUTS).issubset(set(CURRENT_CAPTURE_OUTPUTS))
    assert "include_process_normals=False" in _CAPTURE_SOURCE


def test_modeling_process_capture_contract_covers_wide_and_settled_states() -> None:
    assert len(MODELING_PROCESS_OUTPUTS) == 10
    assert MODELING_PROCESS_OUTPUTS == (
        "modeling-process-1366x768.png",
        "modeling-process-1440x900.png",
        "modeling-process-1920x1080.png",
        "modeling-process-2560x1440.png",
        "modeling-process-3840x2160.png",
        "modeling-process-linear-regression-1366x768.png",
        "modeling-process-manual-1366x768.png",
        "modeling-process-blocked-1440x900.png",
        "modeling-process-exact-read-failed-1440x900.png",
        "modeling-process-siblings-1440x900.png",
    )


def test_open_modeling_stage_targets_one_visible_strong_title_not_aria_name() -> None:
    helper = _CAPTURE_SOURCE.split("def _open_modeling_stage", 1)[1].split(
        "def _wait_for_modeling_data_surface", 1
    )[0]

    assert 'page.locator(".modeling-stage-shell button:visible")' in helper
    assert 'has=page.locator("strong").filter(' in helper
    assert 'has_text=re.compile(rf"^{re.escape(stage_title)}$")' in helper
    assert 'stage_button.wait_for(state="visible", timeout=30_000)' in helper
    assert "stage_button.count() != 1" in helper
    assert ".get_by_role(" not in helper
    assert ".get_by_text(" not in helper
    assert "exact=False" not in helper


def test_process_geometry_contract_rejects_identity_clipping_chart_collisions_and_bad_control_gap() -> None:
    geometry = _CAPTURE_SOURCE.split("def _measure_process_fit", 1)[1].split(
        "def _wait_modeling_process_panel", 1
    )[0]

    assert "full-plot geometry received a blocked plot" in geometry
    assert "use the dedicated blocked-state assertion instead" in geometry
    assert geometry.index("blocked_plot.count()") < geometry.index("measurement = cast(")
    assert "page.mouse.move(width // 2, max(1, height - 2))" in geometry
    assert geometry.index("page.mouse.move(") < geometry.index("measurement = cast(")
    assert 're.fullmatch(r"Tensile test \\d{4}"' in geometry
    assert 'if measurement.get("processRowClipped"):' in geometry
    assert "processRowClipped" in geometry
    for overlap_key in (
        "legendTickOverlap",
        "legendAxisLabelOverlap",
        "legendAxisOverlap",
        "legendCurveSegmentOverlap",
        "legendExtrapolationBoundaryOverlap",
        "legendExtrapolationLabelOverlap",
        "legendStateOverlayOverlap",
    ):
        assert overlap_key in geometry
    assert 'min(_css_token_px(page, "--ux-plot-min-block-size"), height * 0.42)' in geometry
    assert '_css_token_px(page, "--ux-interactive-min-block-size")' in geometry
    assert 'shared_right_reservation = (' in geometry
    assert '_css_token_px(page, "--ux-navigator-min-inline-size")' in geometry
    assert '24 if stage == "data" else shared_right_reservation' in geometry
    assert 'else 180 if stage == "data" else default_minimum' in geometry
    assert 'abs(_as_float(horizontal_axis.get("width")) - expected_drawable_width) > 2' in geometry
    assert 'maximum_control_gap = _css_token_px(page, "--ux-space-4") + 2' in geometry
    assert 'method_range_gap > maximum_control_gap' in geometry
    assert "methodRangeGap" in geometry
    for field in ("processControls", "topActions", "processRibbon", "processPanel", "saveBand"):
        assert field in geometry
    for label in (
        "Evaluation method",
        "Elastic range start",
        "Elastic range end",
        "Manual Young's modulus",
        "Manual Young's modulus unit",
        "Manual Young's modulus reason",
        "Process result name",
        "Reason for saving Process result",
        "Save Process result",
    ):
        assert label in geometry
    assert 'expected_input_height = _css_token_px(page, "--ux-input-min-block-size")' in geometry
    assert "abs(height_px - expected_input_height) > 1" in geometry
    assert 'control.get("whiteSpace") != "nowrap"' in geometry
    assert "scrollHeight" in geometry
    assert "_aligned(normal_row)" in geometry
    assert "manual_row" in geometry
    for label in (
        "Manual Young's modulus",
        "Manual Young's modulus unit",
        "Manual Young's modulus reason",
    ):
        assert f'processRoot?.querySelector(`[aria-label="{label}"]`)' in geometry
    assert '.modeling-context-actions > .modeling-advanced-menu > summary' in geometry
    assert '.modeling-context-actions > button.button.secondary' in geometry
    assert '.modeling-context-actions button[aria-label="Preview changes"], .modeling-context-actions button' not in geometry
    assert 'expected_top_action_labels = ["Advanced", "Distribution analysis", "Preview changes"]' in geometry
    assert "actual_top_action_labels" in geometry
    assert "if not _aligned(top_actions):" in geometry
    assert "Process top action baselines drifted" in geometry
    assert 'float(box.get("width", 0)) <= 0' in geometry


def test_modeling_data_exception_uses_current_quantity_specific_mapping_names() -> None:
    exception_flow = _CAPTURE_SOURCE.split(
        "def _capture_modeling_data_exceptions", 1
    )[1].split("def _capture_modeling_session_shell", 1)[0]

    assert 'name="Engineering strain source column"' in exception_flow
    assert 'name="Engineering stress source column"' in exception_flow
    assert 'name="Engineering stress original unit"' in exception_flow
    assert "Use a different source column for each required channel." in exception_flow
    assert 'name="Independent source column"' not in exception_flow
    assert 'name="Dependent source column"' not in exception_flow
    assert 'name="Dependent original unit"' not in exception_flow
    assert "Use different source columns for Independent and Dependent." not in exception_flow


def test_process_capture_runs_manual_surface_after_initial_preview_before_1366_capture() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    preview = process_only.index("_assert_modeling_process_preview(page)")
    manual = process_only.index("_assert_modeling_process_manual_surface(")
    capture = process_only.index("_capture(", manual)

    assert preview < manual < capture
    assert "if width == 1366:" in process_only


def test_process_preparation_selects_exact_data_identity_before_opening_process() -> None:
    process_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling_process(", 1
    )[1].split("def _list_processing_outputs", 1)[0]

    data_stage = process_flow.index("_prepare_modeling(")
    data_selector = process_flow.index(
        "_modeling_data_library_row(page, PROCESS_SOURCE_DOCUMENT_KEY)"
    )
    primary_assertion = process_flow.index("if primary_button.count() != 1")
    session_assertion = process_flow.index("session = _modeling_session(page)")
    exact_ref_assertion = process_flow.index("if focused_ref is None")
    open_process = process_flow.index('_open_modeling_stage(page, "process")')

    assert (
        data_stage
        < data_selector
        < primary_assertion
        < session_assertion
        < exact_ref_assertion
        < open_process
    )
    assert '.modeling-data-record-button[aria-current="true"]' in process_flow
    assert 'focused.get("label") != PROCESS_SOURCE_DOCUMENT_KEY' in process_flow
    assert 'focused.get("revisionNo") != 1' in process_flow
    assert 'len(refs) != 3' in process_flow
    assert 'len(workspace.get("selectedDocumentIds", [])) != 1' in process_flow
    assert 'len(workspace.get("visibleTestDataKeys", [])) != 3' in process_flow
    assert "retain_comparisons=True" in process_flow


def test_process_manual_surface_contract_uses_real_pointer_and_restores_server_result() -> None:
    helper = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_manual_surface", 1
    )[1].split("def _assert_modeling_process_geometry", 1)[0]

    assert 'manual.select_option("manual")' in helper
    assert 'control.wait_for(state="visible", timeout=30_000)' in helper
    assert "panel_box = _bounding_box_edges(panel.bounding_box())" in helper
    assert "control_box = _bounding_box_edges(control.bounding_box())" in helper
    assert "panel_box = panel.bounding_box()" not in helper
    assert "control_box = control.bounding_box()" not in helper
    assert 'control_box["left"] < panel_box["left"]' in helper
    assert 'control_box["right"] > panel_box["right"]' in helper
    assert 'control_box["top"] < panel_box["top"]' in helper
    assert 'control_box["bottom"] > panel_box["bottom"]' in helper
    assert "elementFromPoint" in helper
    assert "own: Boolean(node && hit && (hit === node || node.contains(hit)))" in helper
    assert "scrollWidth" in helper
    assert "clientWidth" in helper
    assert 'value.focus()' in helper
    assert helper.count('page.keyboard.press("Tab")') == 2
    assert '"Manual Young\'s modulus unit"' in helper
    assert '"Manual Young\'s modulus reason"' in helper
    assert 'plot_box["height"] < 280' in helper
    assert 'svg_box["height"] < 230' in helper
    assert 'auto.select_option("robust_huber")' in helper
    assert helper.index('auto.select_option("robust_huber")') < helper.index(
        "_click_modeling_process_preview_and_wait(page)"
    )
    assert '_click_modeling_process_preview_and_wait(page)' in helper
    assert 'get_by_text("210.0 GPa", exact=True)' in helper


def test_process_manual_fit_override_preserves_normal_svg_threshold() -> None:
    module = ast.parse(_CAPTURE_SOURCE)
    measure = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == "_measure_process_fit"
    )
    manual = next(
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_assert_modeling_process_manual_surface"
    )
    measure_source = ast.get_source_segment(_CAPTURE_SOURCE, measure)
    assert measure_source is not None
    assert "minimum_svg_height: int | None = None" in measure_source
    assert 'min(_css_token_px(page, "--ux-plot-min-block-size"), height * 0.42)' in measure_source
    assert '- _css_token_px(page, "--ux-interactive-min-block-size")' in measure_source
    assert 'else 180 if stage == "data" else default_minimum' in measure_source

    measure_calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_measure_process_fit"
    ]
    override_calls = [
        node
        for node in measure_calls
        if any(keyword.arg == "minimum_svg_height" for keyword in node.keywords)
    ]
    assert len(override_calls) == 1
    override = override_calls[0]
    override_keyword = next(
        keyword for keyword in override.keywords if keyword.arg == "minimum_svg_height"
    )
    assert isinstance(override_keyword.value, ast.Constant)
    assert override_keyword.value.value == 230
    assert manual.end_lineno is not None
    assert manual.lineno < override.lineno <= manual.end_lineno


def test_process_preview_capture_covers_every_native_method_option_and_direct_result_surface() -> None:
    preview = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_preview", 1
    )[1].split("def _assert_modeling_process_manual_surface", 1)[0]

    for value, label in (
        ("robust_huber", "Auto robust"),
        ("linear_regression", "Linear regression"),
        ("chord", "Chord"),
        ("secant", "Secant"),
        ("manual", "Manual slope"),
    ):
        assert f'("{value}", "{label}")' in preview
    assert 'method.locator("option").all_inner_texts()' in preview
    assert 'method.select_option(value)' in preview
    assert 'method.press("Home")' in preview
    assert 'method.press("ArrowDown")' in preview
    assert 'heading.locator("h2")' in preview
    assert 'method.select_option(method_by_label[method_label])' in preview
    assert '_click_modeling_process_preview_and_wait(page)' in preview


def test_process_preview_capture_waits_for_the_actual_preview_post_and_idle_button() -> None:
    helper = _CAPTURE_SOURCE.split(
        "def _click_modeling_process_preview_and_wait", 1
    )[1].split("def _assert_modeling_process_preview", 1)[0]
    assert "page.expect_response(" in helper
    assert 'response.request.method == "POST"' in helper
    assert 'path.endswith("/processing:preview")' in helper
    assert 'response.ok' in helper
    assert "!preview.disabled" in helper
    assert "Updating…" in helper


def test_process_capture_keeps_stage_round_trip_and_failure_preservation_paths() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    assert 'output / "modeling-process-exact-read-failed-1440x900.png"' in process_only
    assert 'output / "modeling-process-siblings-1440x900.png"' in process_only
    assert "_assert_modeling_process_exact_read_failed" in process_only
    assert "Retry exact source" in process_only
    assert "exactly three outputs" in process_only
    assert "roundtrip = _new_page" not in process_only
    assert "Elastic window 0.0005-0.0025" in process_only
    assert "Baseline elastic evaluation for DP780 review" in process_only
    assert 'primary_method.select_option("robust_huber")' in process_only
    assert 'primary_start.fill("0.0005")' in process_only
    assert 'primary_end.fill("0.0025")' in process_only
    assert 'history_row = details.locator(".process-comparison-row").filter(has_text="Chord elastic")' in process_only
    assert "expected_current_output=final_output" in process_only
    assert 'history_panel.get_by_role("combobox", name="Evaluation method", exact=True).input_value() != "chord"' in process_only
    assert 'history_panel.get_by_role("spinbutton", name="Elastic range start", exact=True).input_value() != "0.001"' in process_only
    assert 'history_panel.get_by_role("spinbutton", name="Elastic range end", exact=True).input_value() != "0.003"' in process_only
    assert "history_rows = _assert_modeling_process_saved_rows_three" in process_only
    assert 'sum("current" in row for row in history_rows) != 1' in process_only
    resume_branch = process_only.split("if resumed_existing_primary:", 1)[1].split(
        "if not resumed_existing_primary:", 1
    )[0]
    assert 'resume_current_row = resume_details.locator(".process-comparison-row").filter(' in resume_branch
    assert 'resume_current_row.get_by_role("button", name="Use settings", exact=True).click()' in resume_branch
    assert resume_branch.index('resume_current_row.get_by_role("button", name="Use settings", exact=True).click()') < resume_branch.index(
        "_click_modeling_process_preview_and_wait(siblings)"
    )
    assert "resume_method.select_option" not in resume_branch
    assert "resume_start.fill" not in resume_branch
    assert "resume_end.fill" not in resume_branch
    assert "_assert_capture_processing_output_pointer(siblings, elastic_output)" in resume_branch
    assert "siblings.wait_for_timeout(350)" in resume_branch
    assert "resume_preview_posts" in resume_branch
    assert "resume_output_posts" in resume_branch
    assert '"210.0 GPa", exact=True' in resume_branch
    assert "history_preview_posts" in process_only
    assert "siblings.wait_for_timeout(350)" in process_only
    assert 'history_panel.locator(".process-band-result").get_by_text("210.0 GPa", exact=True)' in process_only
    roundtrip = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_stage_round_trip", 1
    )[1].split("def _assert_modeling_process_blocked", 1)[0]
    assert 'for stage in ("data", "fit", "export", "process")' in roundtrip
    assert '_open_modeling_stage(page, stage)' in roundtrip
    assert "processing-outputs" in roundtrip
    assert "mutation_tokens = (\"processing-outputs\", \"selection\", \"export\")" in roundtrip
    assert 'preview_path = "/processing:preview"' in roundtrip
    assert "data_preview_requests" in roundtrip
    assert "forbidden_preview_requests" in roundtrip
    assert "post_data_json" in roundtrip
    assert 'active_stage == "data" and steps == []' in roundtrip
    assert "if forbidden_preview_requests" in roundtrip
    assert "rerender_rows = _assert_modeling_process_saved_rows_three" in roundtrip
    assert "expected_current_output" in roundtrip
    assert roundtrip.count("_assert_capture_processing_output_pointer(page, expected_current_output)") == 2
    assert "graph_label = graph.get_attribute(\"aria-label\")" in roundtrip
    assert "returned_graph.get_attribute(\"aria-label\") != graph_label" in roundtrip
    assert '_assert_modeling_process_stage_round_trip(' in process_only


def test_resume_pointer_and_preview_contract_has_no_direct_control_mutations() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    resume_branch = process_only.split("if resumed_existing_primary:", 1)[1].split(
        "if not resumed_existing_primary:", 1
    )[0]
    use_settings = 'resume_current_row.get_by_role("button", name="Use settings", exact=True).click()'
    explicit_preview = "_click_modeling_process_preview_and_wait(siblings)"
    assert use_settings in resume_branch
    assert resume_branch.index(use_settings) < resume_branch.index(explicit_preview)
    assert resume_branch.count(
        "_assert_capture_processing_output_pointer(siblings, elastic_output)"
    ) == 2
    assert "resume_method.select_option" not in resume_branch
    assert "resume_start.fill" not in resume_branch
    assert "resume_end.fill" not in resume_branch
    assert "siblings.wait_for_timeout(350)" in resume_branch
    assert "resume_preview_posts" in resume_branch
    assert "resume_output_posts" in resume_branch
    assert 'resume_method.input_value() != "robust_huber"' in resume_branch
    assert 'resume_start.input_value() != "0.0005"' in resume_branch
    assert 'resume_end.input_value() != "0.0025"' in resume_branch
    assert 'name="Save Process result", exact=True' in resume_branch


def test_roundtrip_preview_monitor_allows_only_data_empty_steps_and_no_persistent_mutations() -> None:
    roundtrip = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_stage_round_trip", 1
    )[1].split("def _assert_modeling_process_blocked", 1)[0]
    assert 'mutation_tokens = ("processing-outputs", "selection", "export")' in roundtrip
    assert 'method_name not in {"GET", "HEAD", "OPTIONS"}' in roundtrip
    assert 'preview_path = "/processing:preview"' in roundtrip
    assert "post_data_json" in roundtrip
    assert "steps = payload.get(\"steps\")" in roundtrip
    assert 'if active_stage == "data" and steps == []:' in roundtrip
    assert "data_preview_requests.append" in roundtrip
    assert "forbidden_preview_requests.append" in roundtrip
    assert "if forbidden_preview_requests:" in roundtrip
    assert "mutation_requests.append" in roundtrip
    assert "if mutation_requests:" in roundtrip


def test_only_modeling_process_cli_help_and_output_contract_stay_at_nine() -> None:
    parser_fragment = _CAPTURE_SOURCE.split(
        '        "--only-modeling-process",', 1
    )[1].split("    parser.add_argument(", 1)[0]
    assert "ten Modeling Process viewports" in parser_fragment
    assert len(MODELING_PROCESS_OUTPUTS) == 10
    main_source = _CAPTURE_SOURCE.split("def main()", 1)[1]
    assert "selected_output_names: Sequence[str] = CURRENT_CAPTURE_OUTPUTS" in main_source
    assert 'name.endswith(f"-{width}x{height}.png")' in _CAPTURE_SOURCE


def test_distribution_detail_crops_are_explicit_issue_evidence_only() -> None:
    main_source = _CAPTURE_SOURCE.split("def main()", 1)[1]
    assert "--include-distribution-detail-crops" in main_source
    assert (
        '"--include-distribution-detail-crops requires --only-modeling-distribution"'
        in main_source
    )
    assert "include_detail_crops=args.include_distribution_detail_crops" in main_source


def test_exact_document_success_wait_replaces_removed_notice_for_data_and_process() -> None:
    assert "Loaded saved dataset revision" not in _CAPTURE_SOURCE

    helper = _CAPTURE_SOURCE.split(
        "def _wait_for_exact_document_load_settled", 1
    )[1].split("def _wait_for_data_plot", 1)[0]
    for fragment in (
        '.modeling-data-record-button[aria-current="true"]',
        ".curve-line.data-observed",
        "!document.querySelector('.error-banner')",
    ):
        assert fragment in helper
    assert 'select[aria-label="Test Data revision"]' not in helper
    assert "Load exact JSON" not in helper

    generic_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling(", 1
    )[1].split("def _prepare_modeling_process", 1)[0]
    assert MODELING_DATA_DOCUMENT_KEYS == (
        "CMP-DEMO-DP780-TEST-JSON",
        "CMP-DEMO-DP780-TEST-JSON-02",
        "CMP-DEMO-DP780-TEST-JSON-03",
    )
    assert "primary_row = _modeling_data_library_row(page, PROCESS_SOURCE_DOCUMENT_KEY)" in generic_flow
    assert "for count, document_key in enumerate(MODELING_DATA_DOCUMENT_KEYS[1:], start=2):" in generic_flow
    assert "_modeling_data_library_row(page, document_key)" in generic_flow
    assert "library_rows.count() != 3" not in generic_flow
    assert "library_rows.nth" not in generic_flow
    assert "checkboxes.nth" not in generic_flow
    assert "visibility.nth" not in generic_flow
    assert generic_flow.count("_wait_for_exact_document_load_settled(page)") == 3
    assert generic_flow.index("primary_button.click()") < generic_flow.index(
        "_wait_for_exact_document_load_settled(page)"
    ) < generic_flow.index("_wait_for_data_session_counts")

    surface_flow = _CAPTURE_SOURCE.split(
        "def _assert_modeling_data_surface(", 1
    )[1].split("def _assert_import_file_control", 1)[0]
    assert "for document_key in MODELING_DATA_DOCUMENT_KEYS:" in surface_flow
    assert "curve_rows.count() != 3" not in surface_flow
    assert ".modeling-data-record-button" in surface_flow
    assert 're.fullmatch(r"3 exact revisions?' not in surface_flow
    assert "Modeling Data result columns drifted" in surface_flow
    assert "two optional comparisons" in surface_flow
    assert "optional comparison action drifted from the Modeling action color" in surface_flow
    assert "Modeling Data Browser and Related data headings are not aligned" in surface_flow
    assert "row = _modeling_data_library_row(page, document_key)" in surface_flow
    assert 'library.locator(".data-library-row").nth' not in surface_flow

    process_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling_process(", 1
    )[1].split("def _list_processing_outputs", 1)[0]
    assert process_flow.count("_wait_for_exact_document_load_settled(page)") == 0
    assert "_prepare_modeling(" in process_flow
    assert "verify_reload=verify_data_reload" in process_flow
    assert "retain_comparisons=True" in process_flow
    for fragment in (
        "selectedTestDataRefs",
        "selectedDocumentIds",
        "visibleTestDataKeys",
        "_wait_modeling_process_panel(page)",
        "PROCESS_SOURCE_VISIBLE_IDENTITY",
        'name="Preview changes"',
        "preview.is_disabled()",
    ):
        assert fragment in process_flow

    failed_flow = _CAPTURE_SOURCE.split(
        "    failed = _new_page", 1
    )[1].split("    siblings = _new_page", 1)[0]
    assert "_wait_for_exact_document_load_settled(failed)" not in failed_flow
    assert "failed.reload()" in failed_flow


def test_capture_settles_focus_and_paint_after_before_screenshot_callback() -> None:
    capture = _CAPTURE_SOURCE.split("def _capture(", 1)[1].split(
        "def _open_materials_search", 1
    )[0]
    post_callback = capture.split("    if before_screenshot is not None:", 1)[1].split(
        "    page.screenshot", 1
    )[0]

    assert post_callback.index("before_screenshot()") < post_callback.index("page.evaluate(")
    assert post_callback.count("document.activeElement instanceof HTMLElement") == 1
    assert post_callback.count("document.activeElement.blur()") == 1
    assert post_callback.count("await new Promise(requestAnimationFrame);") == 2
    assert post_callback.index("document.activeElement.blur()") < post_callback.index(
        "await new Promise(requestAnimationFrame);"
    )
    assert capture.index("page.evaluate(", capture.index("before_screenshot()")) < capture.index(
        "page.screenshot"
    )


def test_saved_process_rows_wait_on_embedded_scalars_and_reject_drift() -> None:
    row_text = [
        "Robust elastic Auto robust 0.0002–0.002 210.0 GPa r1 history",
        "Chord elastic Chord 0.001–0.003 120.0 GPa r1 current",
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


def test_saved_process_three_rows_wait_for_exact_settled_rows_before_text_assertions() -> None:
    loading_rows = [
        "Robust elastic Loading saved result…",
        "Chord elastic Loading saved result…",
        "Elastic window 0.0005-0.0025 Loading saved result…",
    ]
    settled_rows = [
        "Robust elastic Auto robust 0.0002–0.002 210.0 GPa r1 history",
        "Chord elastic Chord 0.001–0.003 120.0 GPa r1 history",
        "Elastic window 0.0005-0.0025 Auto robust 0.0005–0.0025 210.0 GPa r1 current",
    ]
    page = _SettlingFakePage(loading_rows, settled_rows)

    assert (
        _assert_modeling_process_saved_rows_three(
            page,
            current_label="Elastic window 0.0005-0.0025",
        )
        == settled_rows
    )
    assert page.wait_timeout == 30_000
    assert page.wait_expression is not None
    assert "rows.length === 3" in page.wait_expression
    assert "Loading saved result…" in page.wait_expression
    assert page.events == ["wait_for_function", "all_inner_texts"]

    wrong_count = _SettlingFakePage(loading_rows[:2], settled_rows[:2])
    with pytest.raises(TimeoutError, match="did not settle"):
        _assert_modeling_process_saved_rows_three(
            wrong_count,
            current_label="Elastic window 0.0005-0.0025",
        )

    still_loading = _SettlingFakePage(loading_rows, loading_rows)
    with pytest.raises(TimeoutError, match="did not settle"):
        _assert_modeling_process_saved_rows_three(
            still_loading,
            current_label="Elastic window 0.0005-0.0025",
        )

    missing_scalar = _SettlingFakePage(
        loading_rows,
        [settled_rows[0], settled_rows[1].replace("120.0 GPa", "119.0 GPa"), settled_rows[2]],
    )
    with pytest.raises(RuntimeError, match="Chord elastic"):
        _assert_modeling_process_saved_rows_three(
            missing_scalar,
            current_label="Elastic window 0.0005-0.0025",
        )

    pointer_drift = _SettlingFakePage(
        loading_rows,
        [settled_rows[0].replace("history", "current"), settled_rows[1], settled_rows[2]],
    )
    with pytest.raises(RuntimeError, match="current pointer drifted"):
        _assert_modeling_process_saved_rows_three(
            pointer_drift,
            current_label="Elastic window 0.0005-0.0025",
        )


def test_saved_process_opening_refresh_gate_precedes_final_no_loading_check() -> None:
    loading_rows = [
        "Robust elastic Loading saved result…",
        "Chord elastic Loading saved result…",
        "Elastic window 0.0005-0.0025 Loading saved result…",
    ]
    settled_rows = [
        "Robust elastic Auto robust 0.0002–0.002 210.0 GPa r1 history",
        "Chord elastic Chord 0.001–0.003 120.0 GPa r1 history",
        "Elastic window 0.0005-0.0025 Auto robust 0.0005–0.0025 210.0 GPa r1 current",
    ]
    page = _RefreshingFakePage(loading_rows, settled_rows)

    assert _assert_modeling_process_saved_rows_three(
        page,
        current_label="Elastic window 0.0005-0.0025",
    ) == settled_rows
    assert page.events == [
        "summary.click",
        "no-loading-gate",
        "render-frame",
    ]
    assert len(page.wait_expressions) == 1
    assert page.wait_expressions[0].find("rows.length === 3") >= 0
    assert page.wait_expressions[0].find("Loading saved result…") >= 0


def test_saved_process_refresh_uses_dom_barrier_before_response_validation() -> None:
    helper = _CAPTURE_SOURCE.split(
        "def _wait_for_modeling_process_saved_rows_refresh", 1
    )[1].split("def _assert_modeling_process_saved_rows_three", 1)[0]

    assert 'page.on("response", record_response)' in helper
    assert 'page.wait_for_event("response"' not in helper
    assert "networkidle" not in helper
    assert "rows.length === 3" in helper
    assert "Loading saved result…" in helper
    barrier = helper.index("page.wait_for_function(")
    count_guard = helper.index("if len(content_responses) != 3")
    response_snapshot = helper.index("responses = list(content_responses.values())")
    status_guard = helper.index("failed = []")
    frame_barrier = helper.index("page.evaluate(")
    assert helper.index('page.on("response", record_response)') < helper.index("summary.click()")
    assert helper.index("first_response = first_response_info.value") < barrier
    assert barrier < count_guard < response_snapshot < status_guard < frame_barrier


def test_saved_process_siblings_capture_rechecks_rows_in_before_screenshot_hook() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    capture = process_only.split(
        'output / "modeling-process-siblings-1440x900.png"', 1
    )[0]
    hook = process_only.split(
        'output / "modeling-process-siblings-1440x900.png"', 1
    )[1].split("siblings.context.close()", 1)[0]

    assert "before_screenshot=lambda: _assert_modeling_process_saved_rows_three(" in hook
    assert 'current_label="Elastic window 0.0005-0.0025"' in hook
    assert capture.index("_assert_modeling_process_stage_round_trip(") < process_only.index(
        'output / "modeling-process-siblings-1440x900.png"'
    )


def test_saved_process_capture_rejects_graph_hit_test_occlusion() -> None:
    reachability_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_saved_rows_reachable", 1
    )[1].split("\ndef _patch_capture_processing_output_pointer", 1)[0]

    assert "elementFromPoint" in reachability_assertion
    assert "process-comparison-row" in reachability_assertion
    assert 'actions.all_inner_texts() != ["Use settings"] * 3' in reachability_assertion
    assert "document.activeElement === node" in reachability_assertion
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
    table_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_table_geometry", 1
    )[1].split("def _assert_modeling_process_saved_rows_reachable", 1)[0]
    assert "process-comparison-table" in table_assertion
    assert "thead th" in table_assertion
    assert "headers" in table_assertion
    assert "horizontalOrder" in table_assertion
    assert "actionTopmost" in table_assertion
    assert "_assert_modeling_process_table_geometry(page)" in _CAPTURE_SOURCE


def test_saved_process_reachability_supports_bounded_local_vertical_scroll() -> None:
    reachability_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_saved_rows_reachable", 1
    )[1].split("\ndef _patch_capture_processing_output_pointer", 1)[0]

    assert "len(checks) != 4" in reachability_assertion
    assert 'layout.get("rowCount") != 3' in reachability_assertion
    assert 'layout.get("localScrollReady")' in reachability_assertion
    assert "scroll_into_view_if_needed" in reachability_assertion
    assert "ribbon.clientWidth >= ribbon.scrollWidth - 1" in reachability_assertion


def test_modeling_process_resume_flag_is_scoped_and_full_capture_reuses_exact_three() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    assert "resume_modeling_process: bool = False" in process_only
    assert "elif len(initial_outputs) not in (0, 2)" in process_only
    assert "if resume_modeling_process and len(initial_outputs) != 3" in process_only
    assert "if len(initial_outputs) == 3" in process_only
    assert 'siblings.unroute_all(behavior="wait")' in process_only

    parser = _CAPTURE_SOURCE.split('    parser.add_argument(\n        "--resume-modeling-process"', 1)[1]
    assert "requires --only-modeling-process" in parser
    assert "if args.resume_modeling_process and not args.only_modeling_process:" in _CAPTURE_SOURCE
    assert 'parser.error("--resume-modeling-process requires --only-modeling-process")' in _CAPTURE_SOURCE
    assert "cannot be combined with another capture selector" in _CAPTURE_SOURCE


def _resume_output(
    *,
    output_id: str,
    revision_id: str,
    label: str,
    method: str,
    minimum: float,
    maximum: float,
) -> dict[str, object]:
    return {
        "processing_output_id": output_id,
        "current_revision": {"id": revision_id, "revision_no": 1},
        "source_document": {"aggregate_id": "source-1", "revision_id": "source-r1"},
        "mapping_profile": {"aggregate_id": "profile-1", "revision_id": "profile-r1"},
        "fit_decision": None,
        "label": label,
        "steps": [
            {
                "method_id": "metal.elastic_modulus",
                "method_version": "1.0.0",
                "options": {
                    "method": method,
                    "minimum_strain": minimum,
                    "maximum_strain": maximum,
                },
            }
        ],
    }


def test_resume_validation_requires_unique_ids_labels_and_all_three_exact_configurations() -> None:
    source: dict[str, object] = {"id": "source-1", "revisionId": "source-r1"}
    profile: dict[str, object] = {"id": "profile-1", "revisionId": "profile-r1"}
    outputs = [
        _resume_output(
            output_id="out-robust",
            revision_id="rev-robust",
            label="Robust elastic",
            method="robust_huber",
            minimum=0.0002,
            maximum=0.002,
        ),
        _resume_output(
            output_id="out-chord",
            revision_id="rev-chord",
            label="Chord elastic",
            method="chord",
            minimum=0.001,
            maximum=0.003,
        ),
        _resume_output(
            output_id="out-window",
            revision_id="rev-window",
            label="Elastic window 0.0005-0.0025",
            method="robust_huber",
            minimum=0.0005,
            maximum=0.0025,
        ),
    ]

    by_label = _assert_resumable_modeling_process_outputs(outputs, source, profile)
    assert set(by_label) == {
        "Robust elastic",
        "Chord elastic",
        "Elastic window 0.0005-0.0025",
    }

    invalid = [dict(item) for item in outputs]
    invalid[2] = _resume_output(
        output_id="out-window",
        revision_id="rev-window",
        label="Elastic window 0.0005-0.0025",
        method="chord",
        minimum=0.0005,
        maximum=0.0025,
    )
    with pytest.raises(RuntimeError, match=r"range drifted|method drifted"):
        _assert_resumable_modeling_process_outputs(invalid, source, profile)


def test_resume_restores_elastic_window_pointer_and_skips_save_post() -> None:
    pointer_helper = _CAPTURE_SOURCE.split(
        "def _patch_capture_processing_output_pointer", 1
    )[1].split("def _save_exact_fit_selection", 1)[0]
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]

    assert "session.processingOutput = pointer" in pointer_helper
    assert "def _assert_capture_processing_output_pointer" in _CAPTURE_SOURCE
    assert "elastic_output = resumed_by_label[\"Elastic window 0.0005-0.0025\"]" in process_only
    assert "_patch_capture_processing_output_pointer(siblings, elastic_output)" in process_only
    assert "_assert_capture_processing_output_pointer(siblings, elastic_output)" in process_only
    assert 'current_label="Elastic window 0.0005-0.0025"' in process_only
    assert "record_resume_output_post" in process_only
    assert "resume_output_posts" in process_only
    assert 'endswith("/processing-outputs")' in process_only
    assert "siblings.remove_listener(\"request\", record_resume_output_post)" in process_only
    assert "resumed_existing_primary = True" in process_only
    assert "if not resumed_existing_primary:" in process_only


def test_blocked_process_waits_for_hidden_registry_attachment_and_visible_rail() -> None:
    blocked_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_blocked", 1
    )[1].split("\ndef _capture_modeling_process_fit", 1)[0]

    assert 'method_buttons.first.wait_for(state="attached", timeout=30_000)' in blocked_assertion
    assert 'method_buttons.first.wait_for(timeout=30_000)' not in blocked_assertion
    assert '".configured-step-list > button:not(.configured-step-add):visible"' in blocked_assertion
    assert '".configured-step-list > button.configured-step-add:visible"' in blocked_assertion
    assert 'configured_step_buttons.first.wait_for(timeout=30_000)' in blocked_assertion
    assert 'toe_add_button.wait_for(timeout=30_000)' in blocked_assertion
    assert "configured_step_buttons.count() != 5" in blocked_assertion
    assert "any(not button.is_disabled() for button in configured_step_buttons.all())" in blocked_assertion
    assert "toe_add_button.count() != 1" in blocked_assertion
    assert "not toe_add_button.is_disabled()" in blocked_assertion


def test_exact_read_failure_capture_asserts_settled_retry_and_no_fallback() -> None:
    failure_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_exact_read_failed", 1
    )[1].split("def _assert_modeling_process_capture_ready", 1)[0]
    for fragment in (
        "Retry exact source",
        "Back to Data",
        "Preview changes",
        "Save Process result",
        "210\\.0",
        "120\\.0",
        "content_gets != 1",
        "data-plot-state=\"blocked\"",
    ):
        assert fragment in failure_assertion
    failed_flow = _CAPTURE_SOURCE.split(
        "    failed = _new_page", 1
    )[1].split("    siblings = _new_page", 1)[0]
    assert "failed.route(" in failed_flow
    assert "failed_content_gets" in failed_flow
    assert "failed_content_gets)" in failed_flow
    assert "modeling-process-exact-read-failed-1440x900.png" in failed_flow


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

    assert fresh_branch.count(success_wait) == 3
    assert fresh_branch.index(success_wait) < fresh_branch.index(
        "saved_outputs = _matching_capture_process_outputs"
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

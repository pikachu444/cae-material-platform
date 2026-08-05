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
_assert_modeling_process_exact_read_failed = cast(
    Callable[[object, int | None], None], _SCRIPT["_assert_modeling_process_exact_read_failed"]
)
PROCESS_NO_PREVIEW_SAVED_INSTRUCTION = cast(
    str, _SCRIPT["PROCESS_NO_PREVIEW_SAVED_INSTRUCTION"]
)
REVISION_LABEL_PATTERN = cast(re.Pattern[str], _SCRIPT["REVISION_LABEL_PATTERN"])
_assert_modeling_process_saved_rows = cast(
    Callable[[object], list[str]], _SCRIPT["_assert_modeling_process_saved_rows"]
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
    def __init__(self, page: "_RefreshingFakePage") -> None:
        self.page = page

    def click(self) -> None:
        self.page.events.append("summary.click")
        self.page.open = True
        self.page.rows.row_text = list(self.page.loading_rows)
        self.page.emit_response(self.page.pending_responses.pop(0))


class _RefreshingFakeDetails:
    def __init__(self, page: "_RefreshingFakePage") -> None:
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
    def __init__(self, page: "_RefreshingFakePage", predicate: Callable[[object], bool]) -> None:
        self.page = page
        self.predicate = predicate
        self.value: object | None = None

    def __enter__(self) -> "_RefreshingExpectation":
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
    assert len(CURRENT_CAPTURE_OUTPUTS) == 60
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_DATA_SESSION_OUTPUTS)
    assert all(name in CURRENT_CAPTURE_OUTPUTS for name in MODELING_PROCESS_OUTPUTS)
    assert {
        "modeling-data-2560x1440.png",
        "modeling-data-3840x2160.png",
        "modeling-data-empty-1440x900.png",
        "modeling-data-invalid-1440x900.png",
        "modeling-process-exact-read-failed-1440x900.png",
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
    assert len(MODELING_PROCESS_OUTPUTS) == 9
    assert MODELING_PROCESS_OUTPUTS == (
        "modeling-process-1366x768.png",
        "modeling-process-1440x900.png",
        "modeling-process-1920x1080.png",
        "modeling-process-2560x1440.png",
        "modeling-process-3840x2160.png",
        "modeling-process-linear-regression-1366x768.png",
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

    assert 're.fullmatch(r"Specimen \\d{2} · r[1-9]\\d*"' in geometry
    assert 'if measurement.get("processRowClipped"):' in geometry
    assert "processRowClipped" in geometry
    assert 'if measurement.get("legendTickOverlap") or measurement.get("legendAxisLabelOverlap") or measurement.get("legendAxisOverlap"):' in geometry
    for overlap_key in ("legendTickOverlap", "legendAxisLabelOverlap", "legendAxisOverlap"):
        assert overlap_key in geometry
    assert 'if not isinstance(method_range_gap, (int, float)) or method_range_gap < 0 or method_range_gap > 20:' in geometry
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
        "Processed curve label",
        "Save reason",
        "Save processed curves",
    ):
        assert label in geometry
    assert "abs(height_px - 28) > 1" in geometry
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
    assert 'expected_top_action_labels = ["Advanced", "Preview changes"]' in geometry
    assert "actual_top_action_labels" in geometry
    assert "if not _aligned(top_actions):" in geometry
    assert "Process top action baselines drifted" in geometry
    assert 'float(box.get("width", 0)) <= 0' in geometry


def test_process_capture_runs_manual_surface_after_initial_preview_before_1366_capture() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    preview = process_only.index("_assert_modeling_process_preview(page)")
    manual = process_only.index("_assert_modeling_process_manual_surface(page)")
    capture = process_only.index("_capture(", manual)

    assert preview < manual < capture
    assert "if width == 1366:" in process_only


def test_process_preparation_selects_exact_data_identity_before_opening_process() -> None:
    process_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling_process(page: Page, base_url: str) -> None:", 1
    )[1].split("def _list_processing_outputs", 1)[0]

    data_stage = process_flow.index("_prepare_modeling(page, base_url)")
    data_selector = process_flow.index(
        '".modeling-data-workspace-bounded .modeling-data-curve-tree"'
    )
    identity_filters = process_flow.index('has_text="Specimen 01"')
    revision_filter = process_flow.index('has_text="Session revision r1"')
    identity_assertion = process_flow.index("data_identity = exact_row.evaluate")
    click = process_flow.index("exact_row.click()")
    open_process = process_flow.index('_open_modeling_stage(page, "process")')

    assert data_stage < data_selector < identity_filters < revision_filter < identity_assertion < click < open_process
    assert 'data_rows = data_rail.locator(".curve-row-label")' in process_flow
    assert ".curve-secondary-identity" in process_flow
    assert 'data_identity.get("primary") != "Specimen 01"' in process_flow
    assert 'data_identity.get("secondary") != "Session revision r1"' in process_flow
    assert 'data_identity.get("primaryVisible") is not True' in process_flow
    assert 'data_identity.get("secondaryVisible") is not True' in process_flow


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
    assert "default_minimum = 330 if height == 768 else 430" in measure_source
    assert "minimum = minimum_svg_height if minimum_svg_height is not None else default_minimum" in measure_source

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
    assert 'heading.get_by_text("Curve response", exact=True)' in preview
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
    assert 'name="Save processed curves", exact=True' in resume_branch


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
    assert "nine Modeling Process viewports" in parser_fragment
    assert len(MODELING_PROCESS_OUTPUTS) == 9


def test_exact_document_success_wait_replaces_removed_notice_for_data_and_process() -> None:
    assert "Loaded saved dataset revision" not in _CAPTURE_SOURCE

    helper = _CAPTURE_SOURCE.split(
        "def _wait_for_exact_document_load_settled", 1
    )[1].split("def _wait_for_data_plot", 1)[0]
    for fragment in (
        'select[aria-label="Test Data revision"]',
        "selection.value",
        "selected.value === selection.value",
        "Load exact JSON",
        "!load.disabled",
        "!document.querySelector('.error-banner')",
    ):
        assert fragment in helper

    generic_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling(page: Page, base_url: str) -> None:", 1
    )[1].split("def _prepare_modeling_process", 1)[0]
    assert "for index in range(3):" in generic_flow
    assert generic_flow.count("_wait_for_exact_document_load_settled(page)") == 1
    assert generic_flow.index("library_rows.nth(index).click()") < generic_flow.index(
        "_wait_for_exact_document_load_settled(page)"
    ) < generic_flow.index("_wait_for_data_session_counts")

    process_flow = _CAPTURE_SOURCE.split(
        "def _prepare_modeling_process(page: Page, base_url: str) -> None:", 1
    )[1].split("def _list_processing_outputs", 1)[0]
    assert process_flow.count("_wait_for_exact_document_load_settled(page)") == 1
    assert process_flow.index("exact_row.click()") < process_flow.index(
        "_wait_for_exact_document_load_settled(page)"
    ) < process_flow.index("page.wait_for_function")
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
    table_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_table_geometry", 1
    )[1].split("def _assert_modeling_process_saved_rows_reachable", 1)[0]
    assert "process-comparison-table" in table_assertion
    assert "thead th" in table_assertion
    assert "headers" in table_assertion
    assert "horizontalOrder" in table_assertion
    assert "actionTopmost" in table_assertion
    assert "_assert_modeling_process_table_geometry(page)" in _CAPTURE_SOURCE


def test_saved_process_reachability_requires_three_rows_plus_layout_without_scroll() -> None:
    reachability_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_saved_rows_reachable", 1
    )[1].split("\ndef _patch_capture_processing_output_pointer", 1)[0]

    assert "len(checks) != 4" in reachability_assertion
    assert 'layout.get("rowCount") != 3' in reachability_assertion
    assert 'layout.get("rowsWithoutScroll")' in reachability_assertion
    assert "twoRowsWithoutScroll" not in reachability_assertion


def test_modeling_process_resume_flag_is_scoped_and_default_guard_stays_zero_or_two() -> None:
    process_only = _CAPTURE_SOURCE.split(
        "def _capture_modeling_process_only", 1
    )[1].split("def _capture_modeling_data_viewports", 1)[0]
    assert "resume_modeling_process: bool = False" in process_only
    assert "elif len(initial_outputs) not in (0, 2)" in process_only
    assert "if resume_modeling_process:" in process_only
    assert "if len(initial_outputs) != 3" in process_only

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
    source = {"id": "source-1", "revisionId": "source-r1"}
    profile = {"id": "profile-1", "revisionId": "profile-r1"}
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
    with pytest.raises(RuntimeError, match="range drifted|method drifted"):
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
    assert 'rail_buttons = page.locator(".configured-step-list button:visible")' in blocked_assertion
    assert 'rail_buttons.first.wait_for(timeout=30_000)' in blocked_assertion


def test_exact_read_failure_capture_asserts_settled_retry_and_no_fallback() -> None:
    failure_assertion = _CAPTURE_SOURCE.split(
        "def _assert_modeling_process_exact_read_failed", 1
    )[1].split("def _assert_modeling_process_capture_ready", 1)[0]
    for fragment in (
        "Retry exact source",
        "Back to Data",
        "Preview changes",
        "Save processed curves",
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

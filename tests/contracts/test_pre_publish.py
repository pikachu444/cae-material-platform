from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cmp.tools import pre_publish as pre_publish_module
from cmp.tools.pre_publish import (
    ChangeSet,
    CodexExecRunner,
    PrePublishError,
    PublicationTarget,
    ReviewRequest,
    _base_images,
    _default_whitespace_check,
    _fingerprint,
    _fingerprint_inputs,
    _is_ui_impact,
    _prompt,
    classify_command,
    collect_change_set,
    pre_push_publication_target,
    resolve_publication_target,
    run_pre_publish_pipeline,
    validate_pre_push_input,
)

_ROOT = Path(__file__).parents[2]


def _code_review_diff_arguments(change: ChangeSet) -> tuple[str, ...]:
    return (
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--unified=0",
        f"{change.base_ref}...HEAD",
        "--",
        ".",
        ":(exclude)**/*.md",
        ":(exclude)**/*.png",
        ":(exclude)**/*.jpg",
        ":(exclude)**/*.jpeg",
        ":(exclude)tests/**",
        ":(exclude)backend/tests/**",
        ":(exclude)contracts/examples/**",
        ":(exclude)generated/**",
        ":(exclude)scripts/capture*.py",
        ":(exclude)scripts/seed_full_demo.py",
        ":(exclude)**/*.test.ts",
        ":(exclude)**/*.test.tsx",
        ":(exclude)**/*.spec.ts",
        ":(exclude)**/*.spec.tsx",
    )


def _synthetic_review_diff(change: ChangeSet) -> bytes:
    return "".join(
        (
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            "@@ -1 +1 @@\n"
            "+synthetic review fixture\n"
        )
        for path in change.changed_files
    ).encode("utf-8")


@contextmanager
def _isolated_review_diff(change: ChangeSet) -> Iterator[None]:
    original_git_bytes = pre_publish_module._git_bytes

    def git_bytes(project: Path, arguments: Sequence[str]) -> bytes:
        if tuple(arguments) == _code_review_diff_arguments(change):
            return _synthetic_review_diff(change)
        return original_git_bytes(project, arguments)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pre_publish_module, "_git_bytes", git_bytes)
        yield


def _criteria() -> list[dict[str, object]]:
    return [
        {"id": f"V-{index:02d}", "score": 2, "evidence": "verified evidence"}
        for index in range(1, 17)
    ]


def _code_result(verdict: str = "PASS") -> dict[str, Any]:
    findings: list[dict[str, object]] = []
    if verdict == "NEEDS_CHANGES":
        findings.append(
            {
                "severity": "blocking",
                "category": "correctness",
                "summary": "broken gate",
                "evidence": {
                    "path": "backend/src/cmp/tools/pre_publish.py",
                    "line": 1,
                    "detail": "concrete evidence",
                },
                "required_action": "fix it",
            }
        )
    return {"verdict": verdict, "summary": "reviewed", "findings": findings}


def _visual_result(verdict: str = "PASS") -> dict[str, Any]:
    violations: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    hard_gate_pass = verdict == "PASS"
    if verdict == "NEEDS_CHANGES":
        violations.append(
            {
                "criterion": "V-10",
                "screen": "Materials",
                "evidence": "nested card",
                "required_action": "remove nested card",
            }
        )
    return {
        "verdict": verdict,
        "summary": "visual review complete",
        "screens": [
            {
                "route": "/materials",
                "image": "docs/user-guide/images/current/materials-search-1440x900.png",
                "viewport": {"width": 1440, "height": 900},
                "total_score": 32 if hard_gate_pass else 30,
                "hard_gate_pass": hard_gate_pass,
                "criteria": _criteria(),
            }
        ],
        "hard_gate_violations": violations,
        "findings": findings,
    }


class FakeReviewer:
    def __init__(self, results: list[object], events: list[str] | None = None) -> None:
        self.results = results
        self.requests: list[ReviewRequest] = []
        self.events = events

    @property
    def settings(self) -> Mapping[str, object]:
        return {
            "cli_sha256": "fake-cli",
            "ephemeral": True,
            "hooks": False,
            "sandbox": "read-only",
        }

    def run(self, request: ReviewRequest) -> None:
        self.requests.append(request)
        if self.events is not None:
            self.events.append(request.kind)
        value = self.results.pop(0)
        request.log_path.parent.mkdir(parents=True, exist_ok=True)
        request.log_path.write_text("fake reviewer\n", encoding="utf-8")
        if isinstance(value, Exception):
            raise value
        if isinstance(value, str):
            request.result_path.write_text(value, encoding="utf-8")
        else:
            request.result_path.write_text(json.dumps(value), encoding="utf-8")


def _change(*, visual: bool = False, diff_hash: str = "diff-a") -> ChangeSet:
    current = _ROOT / "docs/user-guide/images/current/materials-search-1440x900.png"
    return ChangeSet(
        base_ref="origin/main",
        base_sha="a" * 40,
        merge_base_sha="b" * 40,
        head_sha="c" * 40,
        diff_hash=diff_hash,
        changed_files=("backend/src/cmp/tools/pre_publish.py",),
        ui_impact_files=("apps/web/src/app.tsx",) if visual else (),
        current_images=(current,) if visual else (),
        deleted_current_images=(),
        image_hashes={current.relative_to(_ROOT).as_posix(): "image-a"} if visual else {},
        reference_images=(),
        reference_image_hashes={},
    )


def _run(
    tmp_path: Path,
    reviewer: FakeReviewer,
    change: ChangeSet,
    *,
    events: list[str] | None = None,
    worktree_reader: Any = lambda _project: b"clean",
    change_revalidator: Any = None,
    publication_target: PublicationTarget | None = None,
    asset_root: Path = _ROOT,
    independent_reviews: bool = True,
) -> str:
    def documentation(_project: Path) -> None:
        if events is not None:
            events.append("documentation")

    def whitespace(_project: Path, _change: ChangeSet) -> None:
        if events is not None:
            events.append("whitespace")

    def collect(_project: Path) -> ChangeSet:
        if events is not None:
            events.append("diff")
        return change

    def deterministic(_project: Path, _change: ChangeSet) -> None:
        if events is not None:
            events.append("deterministic")

    with _isolated_review_diff(change):
        return run_pre_publish_pipeline(
            _ROOT,
            independent_reviews=independent_reviews,
            runner=reviewer,
            cache_root=tmp_path / "cache",
            asset_root=asset_root,
            documentation_check=documentation,
            whitespace_check=whitespace,
            deterministic_check=deterministic,
            change_collector=collect,
            change_revalidator=change_revalidator or (lambda _project: change),
            worktree_reader=worktree_reader,
            emit=lambda _message: None,
            publication_target=publication_target,
        )


def test_default_whitespace_check_uses_change_base_ref_and_read_only_git_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")
    calls: list[tuple[Path, tuple[str, ...], dict[str, object]]] = []

    def git(
        project: Path,
        arguments: tuple[str, ...],
        *,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((project, arguments, {"text": text, "check": check}))
        return subprocess.CompletedProcess(["git", *arguments], 0, "", "")

    monkeypatch.setattr("cmp.tools.pre_publish._git", git)
    change = replace(_change(), base_ref="refs/heads/release")
    _default_whitespace_check(tmp_path, change)

    assert calls == [
        (
            tmp_path,
            ("diff", "--check", "refs/heads/release...HEAD"),
            {"text": True, "check": False},
        )
    ]
    assert marker.read_text(encoding="utf-8") == "unchanged\n"


def test_default_whitespace_check_preserves_git_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics = "backend/src/example.py:7: trailing whitespace.\n+bad"

    def git(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git"], 2, diagnostics, "ignored stderr")

    monkeypatch.setattr("cmp.tools.pre_publish._git", git)

    with pytest.raises(PrePublishError) as raised:
        _default_whitespace_check(_ROOT, _change())

    assert str(raised.value) == f"git diff --check failed: {diagnostics}"


def test_default_whitespace_check_fails_closed_on_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def git_command_failure(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("git executable unavailable")

    monkeypatch.setattr("cmp.tools.pre_publish.subprocess.run", git_command_failure)

    with pytest.raises(PrePublishError, match=r"git diff --check origin/main\.\.\.HEAD failed"):
        _default_whitespace_check(_ROOT, _change())


def test_whitespace_failure_is_fail_fast_and_has_no_later_activity(tmp_path: Path) -> None:
    events: list[str] = []
    emitted: list[str] = []
    reviewer = FakeReviewer([_code_result()], events)
    change = _change()

    def collect(_project: Path) -> ChangeSet:
        events.append("collect")
        return change

    def whitespace(_project: Path, _change: ChangeSet) -> None:
        events.append("whitespace")
        raise PrePublishError("whitespace gate failed")

    def revalidate(_project: Path) -> ChangeSet:
        events.append("revalidate")
        return change

    with pytest.raises(PrePublishError, match="whitespace gate failed"):
        run_pre_publish_pipeline(
            _ROOT,
            independent_reviews=True,
            runner=reviewer,
            cache_root=tmp_path / "cache",
            asset_root=_ROOT,
            documentation_check=lambda _project: events.append("documentation"),
            whitespace_check=whitespace,
            deterministic_check=lambda _project, _change: events.append("deterministic"),
            change_collector=collect,
            change_revalidator=revalidate,
            emit=emitted.append,
        )

    assert events == ["collect", "whitespace"]
    assert reviewer.requests == []
    assert not (tmp_path / "cache").exists()
    assert not any("PASS" in message for message in emitted)


def test_publication_target_validation_precedes_whitespace_gate(tmp_path: Path) -> None:
    change = _change()
    activity: list[str] = []
    target = PublicationTarget(
        action="ready",
        selector="119",
        hostname="github.com",
        repository="owner/repository",
        head_sha="d" * 40,
        base_sha=change.base_sha,
        base_ref="main",
    )

    def collect(_project: Path) -> ChangeSet:
        activity.append("collect")
        return change

    def revalidate(_project: Path) -> ChangeSet:
        activity.append("revalidate")
        return change

    with pytest.raises(PrePublishError, match="target PR head/base"):
        run_pre_publish_pipeline(
            _ROOT,
            cache_root=tmp_path / "cache",
            documentation_check=lambda _project: activity.append("documentation"),
            whitespace_check=lambda _project, _change: activity.append("whitespace"),
            deterministic_check=lambda _project, _change: activity.append("deterministic"),
            change_collector=collect,
            change_revalidator=revalidate,
            emit=lambda _message: None,
            publication_target=target,
        )

    assert activity == ["collect"]
    assert not (tmp_path / "cache").exists()


def test_clean_deterministic_pipeline_preserves_fingerprint_and_order(tmp_path: Path) -> None:
    change = _change()
    events: list[str] = []
    expected = _fingerprint(
        _fingerprint_inputs(
            change,
            {},
            {"mode": "deterministic-only", "independent_reviews": False},
        )
    )

    def collect(_project: Path) -> ChangeSet:
        events.append("collect")
        return change

    def revalidate(_project: Path) -> ChangeSet:
        events.append("revalidate")
        return change

    fingerprint = run_pre_publish_pipeline(
        _ROOT,
        documentation_check=lambda _project: events.append("documentation"),
        whitespace_check=lambda _project, _change: events.append("whitespace"),
        deterministic_check=lambda _project, _change: events.append("deterministic"),
        change_collector=collect,
        change_revalidator=revalidate,
        emit=lambda _message: None,
    )

    assert fingerprint == expected
    assert events == ["collect", "whitespace", "documentation", "deterministic", "revalidate"]
    assert not (tmp_path / "cache").exists()


def test_automatic_pipeline_defaults_to_deterministic_checks_without_reviewer(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    reviewer = FakeReviewer([PrePublishError("reviewer must not run")], events)
    change = _change()

    fingerprint = run_pre_publish_pipeline(
        _ROOT,
        runner=reviewer,
        cache_root=tmp_path / "cache",
        documentation_check=lambda _project: events.append("documentation"),
        whitespace_check=lambda _project, _change: events.append("whitespace"),
        deterministic_check=lambda _project, _change: events.append("deterministic"),
        change_collector=lambda _project: change,
        change_revalidator=lambda _project: change,
        emit=lambda _message: None,
    )

    assert fingerprint
    assert events == ["whitespace", "documentation", "deterministic"]
    assert reviewer.requests == []
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("uv run pytest", "ordinary"),
        ("echo legit push", "ordinary"),
        ('git -C "C:/repo with spaces" commit -m test', "commit"),
        ('& "C:/Program Files/Git/cmd/git.exe" --no-pager push', "publish"),
        ("git push origin feature", "publish"),
        ("  git push origin feature", "publish"),
        ("\tgit push origin feature", "publish"),
        ("  git commit -m test", "commit"),
        ("\tgit commit -m test", "commit"),
        ("  gh pr create --base main", "publish"),
        ("\tgh pr create --base main", "publish"),
        ("  gh pr ready 119", "publish"),
        ("\tgh pr ready 119", "publish"),
        ("  gh pr merge 119", "publish"),
        ("\tgh pr merge 119", "publish"),
        ("git --no-pager push origin feature", "publish"),
        ('git -c core.quotePath=false -C "C:/repo with spaces" push', "publish"),
        ("git -C. push origin feature", "publish"),
        ("git -cfoo.bar=baz push origin feature", "publish"),
        ("gh pr create --draft", "publish"),
        ("gh --repo owner/repository pr create --draft", "publish"),
        ("gh pr --repo=owner/repository merge 119 --squash", "publish"),
        ("gh -R owner/repository pr ready 119", "publish"),
        ("gh.exe pr ready 119", "publish"),
        ("gh pr merge 119 --squash", "publish"),
        ("GH_HOST=github.com gh pr create --draft", "publish"),
        ("env GH_HOST=github.com gh pr ready 119", "publish"),
        ("command gh pr merge 119", "publish"),
        ("sudo -E gh pr ready 119", "publish"),
        ("& gh pr merge 119", "publish"),
        ("(gh pr merge 119)", "publish"),
        ("$env:X='1'\ngh pr create --draft", "publish"),
        ("bash -lc 'gh pr merge 119 --squash'", "publish"),
        ("cmd /c gh pr ready 119", "publish"),
        ('powershell -Command "gh pr merge 119"', "publish"),
        ("Start-Process gh -ArgumentList 'pr create --base main'", "publish"),
        ("echo `git push origin feature`", "publish"),
        ("echo `gh pr create --base main`", "publish"),
        ("echo `gh pr ready 119`", "publish"),
        ("echo `gh pr merge 119`", "publish"),
        ("bash -lc 'git commit -m test && git push origin feature'", "commit-and-publish"),
        ("git commit -m test && git push", "commit-and-publish"),
        ("  git commit -m test && git push origin feature", "commit-and-publish"),
        ("git commit -m test && (gh pr create --draft)", "commit-and-publish"),
    ],
)
def test_command_classification(command: str, expected: str) -> None:
    assert classify_command(command) == expected


def test_numbered_pr_target_is_resolved_and_must_match_reviewed_shas(
    tmp_path: Path,
) -> None:
    captured: list[str] = []

    def process(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "headRefOid": "c" * 40,
                    "baseRefOid": "a" * 40,
                    "baseRefName": "main",
                    "url": "https://github.com/pikachu444/cae-material-platform/pull/119",
                }
            ),
            "",
        )

    target = resolve_publication_target(
        _ROOT,
        "gh --repo pikachu444/cae-material-platform pr merge 119 --squash",
        process_runner=process,
    )

    assert target == PublicationTarget(
        action="merge",
        selector="119",
        hostname="github.com",
        repository="pikachu444/cae-material-platform",
        head_sha="c" * 40,
        base_sha="a" * 40,
        base_ref="main",
    )
    assert captured == [
        "gh",
        "pr",
        "view",
        "119",
        "--repo",
        "pikachu444/cae-material-platform",
        "--json",
        "headRefOid,baseRefOid,baseRefName,url",
    ]
    with pytest.raises(PrePublishError, match="does not match"):
        _run(
            tmp_path,
            FakeReviewer([]),
            _change(),
            publication_target=replace(target, head_sha="e" * 40),
        )


def test_pr_url_and_git_push_must_target_current_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cross_repository(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "headRefOid": "c" * 40,
                    "baseRefOid": "a" * 40,
                    "baseRefName": "main",
                    "url": "https://github.com/other/repository/pull/119",
                }
            ),
            "",
        )

    with pytest.raises(PrePublishError, match="URL does not match"):
        resolve_publication_target(
            _ROOT,
            "gh pr merge https://github.com/other/repository/pull/119",
            process_runner=cross_repository,
        )

    with pytest.raises(PrePublishError, match="repository-selection"):
        resolve_publication_target(_ROOT, 'git -C "C:/another checkout" push origin feature')
    with pytest.raises(PrePublishError, match="repository-selection"):
        resolve_publication_target(_ROOT, "git -C. push origin feature")
    with pytest.raises(PrePublishError, match="repository-selection"):
        resolve_publication_target(_ROOT, "git -cfoo.bar=baz push origin feature")
    with pytest.raises(PrePublishError, match="repository-selection"):
        resolve_publication_target(
            _ROOT,
            "PUSH_URL=https://github.com/other/repository.git "
            "git --config-env=remote.origin.pushurl=PUSH_URL push origin feature",
        )
    with pytest.raises(PrePublishError, match="repository-selection"):
        resolve_publication_target(
            _ROOT,
            "git -c remote.origin.pushurl=https://github.com/other/repository.git "
            "push origin feature",
        )
    with pytest.raises(PrePublishError, match="directory-changing"):
        resolve_publication_target(_ROOT, "cd ../other && git push origin feature")

    values = {
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "feature",
        ("remote", "get-url", "origin"): (
            "https://github.com/pikachu444/cae-material-platform.git"
        ),
        ("rev-parse", "--verify", "origin/main"): "a" * 40,
        ("rev-parse", "--verify", "HEAD"): "c" * 40,
        ("ls-remote", "--exit-code", "origin", "refs/heads/main"): ("a" * 40 + "\trefs/heads/main"),
    }
    monkeypatch.setattr(
        "cmp.tools.pre_publish._git_text",
        lambda _project, arguments: values[tuple(arguments)],
    )
    assert resolve_publication_target(
        _ROOT, "git push --set-upstream origin feature"
    ) == PublicationTarget(
        action="push",
        selector="feature",
        hostname="github.com",
        repository="pikachu444/cae-material-platform",
        head_sha="c" * 40,
        base_sha="a" * 40,
        base_ref="main",
    )
    with pytest.raises(PrePublishError, match="refspec"):
        resolve_publication_target(_ROOT, "git push origin another-branch")


def test_pr_create_is_bound_to_current_head_main_and_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        ("remote", "get-url", "origin"): "https://github.com/owner/repository.git",
        ("rev-parse", "--verify", "origin/main"): "a" * 40,
        ("rev-parse", "--verify", "HEAD"): "c" * 40,
        ("ls-remote", "--exit-code", "origin", "refs/heads/main"): ("a" * 40 + "\trefs/heads/main"),
    }
    monkeypatch.setattr(
        "cmp.tools.pre_publish._git_text",
        lambda _project, arguments: values[tuple(arguments)],
    )

    target = resolve_publication_target(
        _ROOT,
        "gh --repo owner/repository pr create --draft --base main",
    )

    assert target == PublicationTarget(
        action="create",
        selector="current-branch",
        hostname="github.com",
        repository="owner/repository",
        head_sha="c" * 40,
        base_sha="a" * 40,
        base_ref="main",
    )

    with pytest.raises(PrePublishError, match="--head/-H"):
        resolve_publication_target(_ROOT, "gh pr create --head owner:other")
    with pytest.raises(PrePublishError, match="base must be main"):
        resolve_publication_target(_ROOT, "gh pr create -B develop")
    with pytest.raises(PrePublishError, match="explicitly specify --base main"):
        resolve_publication_target(_ROOT, "gh pr create --draft")
    with pytest.raises(PrePublishError, match="current origin"):
        resolve_publication_target(_ROOT, "gh --repo other/repository pr create --base main")

    values[("ls-remote", "--exit-code", "origin", "refs/heads/main")] = (
        "d" * 40 + "\trefs/heads/main"
    )
    with pytest.raises(PrePublishError, match="stale"):
        resolve_publication_target(_ROOT, "gh pr create --draft --base main")

    with pytest.raises(PrePublishError, match="GH_REPO/GH_HOST"):
        resolve_publication_target(_ROOT, "GH_REPO=other/repository gh pr create --base main")
    monkeypatch.setenv("GH_HOST", "example.invalid")
    with pytest.raises(PrePublishError, match="ambient GH_REPO/GH_HOST"):
        resolve_publication_target(_ROOT, "gh pr create --base main")


@pytest.mark.parametrize(
    "command",
    (
        "GH_REPO=other/repository gh pr create --base main",
        "env GH_HOST=example.invalid gh pr ready 119",
        "$env:GH_REPO='other/repository'; gh pr merge 119",
    ),
)
def test_pr_publication_rejects_command_local_github_context(command: str) -> None:
    with pytest.raises(PrePublishError, match="GH_REPO/GH_HOST"):
        resolve_publication_target(_ROOT, command)


def test_non_ui_pipeline_orders_documentation_code_and_skip_visual(tmp_path: Path) -> None:
    events: list[str] = []
    reviewer = FakeReviewer([_code_result()], events)

    _run(tmp_path, reviewer, _change(), events=events)

    assert events == ["diff", "whitespace", "documentation", "deterministic", "code"]
    assert reviewer.requests[0].profile.model == "gpt-5.6-terra"
    assert reviewer.requests[0].profile.reasoning_effort == "medium"
    assert reviewer.requests[0].profile.timeout_seconds == 120
    assert reviewer.requests[0].profile.max_tokens == 50_000


def test_pr_publication_uses_final_sol_high_profile(tmp_path: Path) -> None:
    reviewer = FakeReviewer([_code_result(), _code_result()])
    change = _change()
    target = PublicationTarget(
        action="create",
        selector="current-branch",
        hostname="github.com",
        repository="owner/repository",
        head_sha=change.head_sha,
        base_sha=change.base_sha,
        base_ref="main",
    )

    routine = _run(tmp_path, reviewer, change)
    final = _run(tmp_path, reviewer, change, publication_target=target)
    cached_final = _run(tmp_path, reviewer, change, publication_target=target)

    assert routine != final
    assert final == cached_final
    assert len(reviewer.requests) == 2
    assert reviewer.requests[1].profile.model == "gpt-5.6-sol"
    assert reviewer.requests[1].profile.reasoning_effort == "high"
    assert reviewer.requests[1].profile.timeout_seconds == 300
    assert reviewer.requests[1].profile.max_tokens == 50_000


def test_ui_pipeline_runs_visual_only_after_code_passes(tmp_path: Path) -> None:
    events: list[str] = []
    reviewer = FakeReviewer([_code_result(), _visual_result()], events)

    _run(tmp_path, reviewer, _change(visual=True), events=events)

    assert events == ["diff", "whitespace", "documentation", "deterministic", "code", "visual"]
    assert reviewer.requests[1].images
    assert reviewer.requests[1].profile.model == "gpt-5.6-sol"
    assert reviewer.requests[1].profile.reasoning_effort == "high"
    assert reviewer.requests[1].profile.timeout_seconds == 300
    assert reviewer.requests[1].profile.max_tokens == 40_000


def test_code_needs_changes_blocks_visual_and_cache(tmp_path: Path) -> None:
    reviewer = FakeReviewer([_code_result("NEEDS_CHANGES")])

    with pytest.raises(PrePublishError, match="code review NEEDS_CHANGES"):
        _run(tmp_path, reviewer, _change(visual=True))

    assert [request.kind for request in reviewer.requests] == ["code"]
    assert not list((tmp_path / "cache").rglob("pass.json"))


def test_failed_result_is_never_reused(tmp_path: Path) -> None:
    reviewer = FakeReviewer([_code_result("NEEDS_CHANGES"), _code_result()])

    with pytest.raises(PrePublishError, match="NEEDS_CHANGES"):
        _run(tmp_path, reviewer, _change())
    _run(tmp_path, reviewer, _change())

    assert len(reviewer.requests) == 2


def test_visual_needs_changes_blocks_publish(tmp_path: Path) -> None:
    reviewer = FakeReviewer([_code_result(), _visual_result("NEEDS_CHANGES")])

    with pytest.raises(PrePublishError, match="visual review NEEDS_CHANGES"):
        _run(tmp_path, reviewer, _change(visual=True))

    assert not list((tmp_path / "cache").rglob("pass.json"))


@pytest.mark.parametrize(
    "defect", ("threshold", "duplicate-criterion", "hard-gate", "hard-gate-score")
)
def test_visual_pass_cannot_bypass_authoritative_matrix(tmp_path: Path, defect: str) -> None:
    visual = _visual_result()
    screen = visual["screens"][0]
    if defect == "threshold":
        screen["criteria"][0]["score"] = 0
        screen["criteria"][1]["score"] = 0
        screen["criteria"][2]["score"] = 0
        screen["criteria"][3]["score"] = 0
        screen["total_score"] = 24
    elif defect == "duplicate-criterion":
        screen["criteria"][0]["id"] = "V-02"
    elif defect == "hard-gate":
        screen["hard_gate_pass"] = False
    else:
        screen["criteria"][0]["score"] = 0
        screen["total_score"] = 30

    with pytest.raises(PrePublishError, match=r"threshold|inconsistent|hard-gate score"):
        _run(
            tmp_path,
            FakeReviewer([_code_result(), visual]),
            _change(visual=True),
        )


@pytest.mark.parametrize("defect", ("missing", "wrong-viewport", "duplicate"))
def test_visual_result_must_cover_exact_current_manifest_inputs(
    tmp_path: Path, defect: str
) -> None:
    visual = _visual_result()
    if defect == "missing":
        visual["screens"] = []
    elif defect == "wrong-viewport":
        visual["screens"][0]["viewport"]["width"] = 1366
    else:
        visual["screens"].append(visual["screens"][0].copy())

    with pytest.raises(PrePublishError, match=r"violates its schema|exactly match|repeats"):
        _run(
            tmp_path,
            FakeReviewer([_code_result(), visual]),
            _change(visual=True),
        )


@pytest.mark.parametrize(
    "failure",
    [
        PrePublishError("timeout"),
        PrePublishError("authentication failed"),
        PrePublishError("CLI failed"),
    ],
)
def test_reviewer_runtime_failures_are_fail_closed(
    tmp_path: Path, failure: PrePublishError
) -> None:
    with pytest.raises(PrePublishError, match=str(failure)):
        _run(tmp_path, FakeReviewer([failure]), _change())


@pytest.mark.parametrize(
    "invalid",
    [
        "not-json",
        json.dumps({"verdict": "PASS"}),
        json.dumps({"verdict": "UNKNOWN", "summary": "bad", "findings": []}),
    ],
)
def test_invalid_json_or_schema_blocks_publish(tmp_path: Path, invalid: str) -> None:
    with pytest.raises(PrePublishError, match=r"invalid JSON|violates its schema"):
        _run(tmp_path, FakeReviewer([invalid]), _change())


def test_only_complete_pass_is_cached_and_same_fingerprint_is_reused(tmp_path: Path) -> None:
    reviewer = FakeReviewer([_code_result()])
    first = _run(tmp_path, reviewer, _change())
    second = _run(tmp_path, reviewer, _change())

    assert first == second
    assert len(reviewer.requests) == 1
    assert list((tmp_path / "cache" / first).glob("pass.json"))


@pytest.mark.parametrize("total", (26, 27, 28))
def test_visual_threshold_satisfies_repository_85_percent_minimum(
    tmp_path: Path, total: int
) -> None:
    visual = _visual_result()
    remaining = 32 - total
    for index in (4, 6, 10, 13, 0):
        reduction = min(2, remaining)
        visual["screens"][0]["criteria"][index]["score"] -= reduction
        remaining -= reduction
        if remaining == 0:
            break
    visual["screens"][0]["total_score"] = total
    reviewer = FakeReviewer([_code_result(), visual])

    if total < 28:
        with pytest.raises(PrePublishError, match="28/32"):
            _run(tmp_path, reviewer, _change(visual=True))
    else:
        _run(tmp_path, reviewer, _change(visual=True))


def test_ref_change_blocks_fresh_and_cached_pass(tmp_path: Path) -> None:
    initial = _change()
    changed = replace(initial, head_sha="d" * 40, diff_hash="diff-changed")

    with pytest.raises(PrePublishError, match="changed during review"):
        _run(
            tmp_path / "fresh",
            FakeReviewer([_code_result()]),
            initial,
            change_revalidator=lambda _project: changed,
        )
    assert not list((tmp_path / "fresh").rglob("pass.json"))

    reviewer = FakeReviewer([_code_result()])
    _run(tmp_path / "cached", reviewer, initial)
    with pytest.raises(PrePublishError, match="changed during review"):
        _run(
            tmp_path / "cached",
            reviewer,
            initial,
            change_revalidator=lambda _project: changed,
        )
    assert len(reviewer.requests) == 1


def test_diff_prompt_schema_and_image_inputs_invalidate_fingerprint(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    for relative in (
        "docs/14-testing/review-prompts/code-review.md",
        "docs/14-testing/review-prompts/visual-review.md",
        "contracts/review/code-review.schema.json",
        "contracts/review/visual-review.schema.json",
    ):
        target = assets / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ROOT / relative, target)
    reviewer = FakeReviewer(
        [
            _code_result(),
            _code_result(),
            _code_result(),
            _code_result(),
            _code_result(),
            _visual_result(),
        ]
    )

    first = _run(tmp_path, reviewer, _change(), asset_root=assets)
    second = _run(tmp_path, reviewer, _change(diff_hash="diff-b"), asset_root=assets)
    code_prompt = assets / "docs/14-testing/review-prompts/code-review.md"
    code_prompt.write_text(
        code_prompt.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8"
    )
    third = _run(tmp_path, reviewer, _change(diff_hash="diff-b"), asset_root=assets)
    code_schema = assets / "contracts/review/code-review.schema.json"
    code_schema.write_text(code_schema.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    fourth = _run(tmp_path, reviewer, _change(diff_hash="diff-b"), asset_root=assets)
    visual_change = _change(visual=True, diff_hash="diff-c")
    fifth = _run(tmp_path, reviewer, visual_change, asset_root=assets)

    assert len({first, second, third, fourth, fifth}) == 5
    assert len(reviewer.requests) == 6


def test_fingerprint_includes_reviewer_and_screenshot_settings() -> None:
    change = _change(visual=True)
    assets = {"prompt": "one"}
    first = _fingerprint(_fingerprint_inputs(change, assets, {"sandbox": "read-only"}))
    changed_image = replace(
        change,
        image_hashes={next(iter(change.image_hashes)): "image-b"},
    )
    second = _fingerprint(_fingerprint_inputs(changed_image, assets, {"sandbox": "read-only"}))
    third = _fingerprint(_fingerprint_inputs(change, assets, {"sandbox": "workspace-write"}))
    target = PublicationTarget(
        action="ready",
        selector="119",
        hostname="github.com",
        repository="owner/repository",
        head_sha=change.head_sha,
        base_sha=change.base_sha,
        base_ref="main",
    )
    fourth = _fingerprint(_fingerprint_inputs(change, assets, {"sandbox": "read-only"}, target))

    assert len({first, second, third, fourth}) == 4


def test_reviewer_worktree_mutation_blocks_pass(tmp_path: Path) -> None:
    states = iter((b"clean", b"dirty"))

    with pytest.raises(PrePublishError, match="changed the worktree"):
        _run(
            tmp_path,
            FakeReviewer([_code_result()]),
            _change(),
            worktree_reader=lambda _project: next(states),
        )


def test_codex_exec_uses_ephemeral_read_only_no_hooks_and_handles_space_paths(
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    project = tmp_path / "repo with spaces"
    project.mkdir()
    schema = tmp_path / "schema with spaces.json"
    schema.write_text("{}", encoding="utf-8")
    result = tmp_path / "result with spaces.json"
    log = tmp_path / "review with spaces.log"

    def process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        result.write_text(json.dumps(_code_result()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "tokens used\n1,000")

    runner = CodexExecRunner(
        Path("C:/Program Files/OpenAI Codex/codex.exe"),
        "binary-sha",
        process_runner=process,
    )
    runner.run(
        ReviewRequest(
            kind="code",
            project=project,
            prompt="review",
            schema_path=schema,
            result_path=result,
            log_path=log,
        )
    )

    command = captured["command"]
    assert command[:5] == [
        str(Path("C:/Program Files/OpenAI Codex/codex.exe")),
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
    ]
    assert command[5] == "read-only"
    assert "features.hooks=false" in command
    assert command[command.index("--model") + 1] == "gpt-5.6-terra"
    assert 'model_reasoning_effort="medium"' in command
    assert command[command.index("--cd") + 1] == str(project)
    assert captured["kwargs"]["env"]["CMP_CODEX_REVIEW_ACTIVE"] == "1"
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"


def test_review_prompt_embeds_bounded_materials_and_forbids_tool_exploration() -> None:
    change = replace(
        _change(),
        changed_files=(
            "backend/src/cmp/tools/pre_publish.py",
            "tests/contracts/test_pre_publish.py",
        ),
    )
    with _isolated_review_diff(change):
        code = _prompt(
            _ROOT,
            _ROOT,
            "docs/14-testing/review-prompts/code-review.md",
            "code",
            change,
        )
        visual = _prompt(
            _ROOT,
            _ROOT,
            "docs/14-testing/review-prompts/visual-review.md",
            "visual",
            _change(visual=True),
        )

    assert "### AGENTS.md" in code
    assert "### Exact unified diff" in code
    assert "diff --git a/backend/src/cmp/tools/pre_publish.py" in code
    assert "### Changed-test inventory" in code
    assert "test_codex_exec_token_usage_is_fail_closed" in code
    assert "Do not call shell, MCP, browser, network, or other tools" in code
    assert "### docs/01-product/visual-acceptance-matrix.md" in visual
    assert "### docs/user-guide/screenshot-manifest.yaml" in visual
    assert "images/current/materials-search-1440x900.png" in visual
    assert "Issue #261 M1A20" not in visual
    assert len(code.encode("utf-8")) < 400_000
    assert len(visual.encode("utf-8")) < 400_000
    assert "Do not call shell, MCP, browser, network, or other tools" in visual


def test_codex_exec_token_usage_is_fail_closed(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    request = ReviewRequest(
        kind="code",
        project=tmp_path,
        prompt="review",
        schema_path=tmp_path / "schema.json",
        result_path=result,
        log_path=tmp_path / "review.log",
    )

    def excessive(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        result.write_text(json.dumps(_code_result()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "tokens used\n50,001")

    with pytest.raises(PrePublishError, match="exceeding the 50000 token limit"):
        CodexExecRunner(Path("codex"), "sha", process_runner=excessive).run(request)

    def missing(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        result.write_text(json.dumps(_code_result()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(PrePublishError, match="did not report token usage"):
        CodexExecRunner(Path("codex"), "sha", process_runner=missing).run(request)


@pytest.mark.skipif(os.name != "nt", reason="WindowsApps discovery is Windows-only")
def test_windowsapps_discovery_requires_matching_runtime_and_sandbox_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "WindowsApps/OpenAI.Codex/resources/codex.exe"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"same-codex")
    runtime = tmp_path / "local/OpenAI/Codex/bin/runtime/codex.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"same-codex")
    (runtime.parent / "codex-command-runner.exe").write_bytes(b"runner")
    (runtime.parent / "codex-windows-sandbox-setup.exe").write_bytes(b"setup")
    monkeypatch.setenv("CMP_CODEX_EXECUTABLE", str(source))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    runner = CodexExecRunner.discover(tmp_path)

    assert runner._executable == runtime.resolve()

    (runtime.parent / "codex-windows-sandbox-setup.exe").unlink()
    with pytest.raises(PrePublishError, match="sandbox helpers"):
        CodexExecRunner.discover(tmp_path)


def test_codex_exec_timeout_and_missing_result_are_fail_closed(tmp_path: Path) -> None:
    request = ReviewRequest(
        kind="code",
        project=tmp_path,
        prompt="review",
        schema_path=tmp_path / "schema.json",
        result_path=tmp_path / "result.json",
        log_path=tmp_path / "review.log",
    )

    def timeout(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("codex", 1)

    with pytest.raises(PrePublishError, match="timed out"):
        CodexExecRunner(Path("codex"), "sha", timeout_seconds=1, process_runner=timeout).run(
            request
        )

    def no_result(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(PrePublishError, match="did not create"):
        CodexExecRunner(Path("codex"), "sha", process_runner=no_result).run(request)

    def auth_failure(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "authentication required")

    with pytest.raises(PrePublishError, match="authentication required"):
        CodexExecRunner(Path("codex"), "sha", process_runner=auth_failure).run(request)


def test_ui_impact_runs_visual_review_only_for_actual_ui_source_changes() -> None:
    for path in (
        "apps/web/src/app.tsx",
        "apps/web/src/design/tokens.ts",
        "apps/web/src/components/grid.ts",
        "apps/web/src/styles.css",
    ):
        assert _is_ui_impact(path), path
    for path in (
        "apps/web/src/app.test.tsx",
        "docs/user-guide/navigation-contract.yaml",
        "docs/user-guide/screenshot-manifest.yaml",
        "docs/user-guide/images/current/materials.png",
        "docs/01-product/visual-acceptance-matrix.md",
        "docs/00-research/images/gui-reference/granta-list-results.png",
        "backend/src/cmp/tools/pre_publish.py",
    ):
        assert not _is_ui_impact(path), path


def test_local_pre_push_binds_origin_current_branch_and_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    values = {
        ("rev-parse", "--show-toplevel"): str(_ROOT),
        ("remote", "get-url", "--push", "origin"): "git@github.com:owner/repository.git",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "feature",
        ("rev-parse", "HEAD"): head,
    }
    monkeypatch.setattr(
        "cmp.tools.pre_publish._git_text",
        lambda _project, arguments: values[tuple(arguments)],
    )
    validate_pre_push_input(
        _ROOT,
        f"refs/heads/feature {head} refs/heads/feature {'0' * 40}\n",
        remote_name="origin",
        remote_location="git@github.com:owner/repository.git",
    )

    with pytest.raises(PrePublishError, match="exactly one"):
        validate_pre_push_input(
            _ROOT,
            "",
            remote_name="origin",
            remote_location="git@github.com:owner/repository.git",
        )
    with pytest.raises(PrePublishError, match="not the reviewed HEAD"):
        validate_pre_push_input(
            _ROOT,
            f"refs/heads/feature {'1' * 40} refs/heads/feature {'0' * 40}\n",
            remote_name="origin",
            remote_location="git@github.com:owner/repository.git",
        )
    with pytest.raises(PrePublishError, match="checked-out branch"):
        validate_pre_push_input(
            _ROOT,
            f"refs/heads/feature {head} refs/heads/main {'0' * 40}\n",
            remote_name="origin",
            remote_location="git@github.com:owner/repository.git",
        )
    with pytest.raises(PrePublishError, match="checked-out branch"):
        validate_pre_push_input(
            _ROOT,
            f"refs/heads/other {head} refs/heads/feature {'0' * 40}\n",
            remote_name="origin",
            remote_location="git@github.com:owner/repository.git",
        )
    with pytest.raises(PrePublishError, match="configured origin"):
        validate_pre_push_input(
            _ROOT,
            f"refs/heads/feature {head} refs/heads/feature {'0' * 40}\n",
            remote_name="secondary",
            remote_location="git@github.com:other/repository.git",
        )


def test_pre_push_target_binds_fresh_remote_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "c" * 40
    base = "a" * 40
    values = {
        ("rev-parse", "--show-toplevel"): str(_ROOT),
        ("remote", "get-url", "--push", "origin"): "git@github.com:owner/repository.git",
        ("remote", "get-url", "origin"): "git@github.com:owner/repository.git",
        ("symbolic-ref", "--quiet", "--short", "HEAD"): "feature",
        ("rev-parse", "HEAD"): head,
        ("rev-parse", "--verify", "origin/main"): base,
        ("rev-parse", "--verify", "HEAD"): head,
        ("ls-remote", "--exit-code", "origin", "refs/heads/main"): (
            base + "\trefs/heads/main"
        ),
    }
    monkeypatch.setattr(
        "cmp.tools.pre_publish._git_text",
        lambda _project, arguments: values[tuple(arguments)],
    )

    target = pre_push_publication_target(
        _ROOT,
        f"refs/heads/feature {head} refs/heads/feature {'0' * 40}\n",
        remote_name="origin",
        remote_location="git@github.com:owner/repository.git",
    )

    assert target == PublicationTarget(
        action="push",
        selector="feature",
        hostname="github.com",
        repository="owner/repository",
        head_sha=head,
        base_sha=base,
        base_ref="main",
    )


def test_deleted_current_capture_falls_back_to_manifest_and_keeps_base_image(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "capture-deletion"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repository,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    image_root = repository / "docs/user-guide/images/current"
    image_root.mkdir(parents=True)
    kept = image_root / "kept-1440x900.png"
    removed = image_root / "removed-1440x900.png"
    kept.write_bytes(b"kept")
    removed.write_bytes(b"removed")
    ui_source = repository / "apps/web/src/obsolete.tsx"
    ui_source.parent.mkdir(parents=True)
    ui_source.write_text("export const obsolete = true;\n", encoding="utf-8")
    manifest = repository / "docs/user-guide/screenshot-manifest.yaml"
    manifest.write_text(
        "captures:\n"
        "  - image: images/current/kept-1440x900.png\n"
        "    width: 1440\n"
        "    height: 900\n"
        "  - image: images/current/removed-1440x900.png\n"
        "    width: 1440\n"
        "    height: 900\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repository, check=True)
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=repository,
        check=True,
    )

    removed.unlink()
    archive_target = repository / "archive/obsolete.txt"
    archive_target.parent.mkdir()
    ui_source.rename(archive_target)
    manifest.write_text(
        "captures:\n"
        "  - image: images/current/kept-1440x900.png\n"
        "    width: 1440\n"
        "    height: 900\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-m", "remove obsolete capture"], cwd=repository, check=True)

    change = collect_change_set(repository)
    base_images = _base_images(repository, change, tmp_path / "base-images")

    assert change.current_images == (kept.resolve(),)
    assert change.deleted_current_images == ("docs/user-guide/images/current/removed-1440x900.png",)
    assert "apps/web/src/obsolete.tsx" in change.changed_files
    assert "archive/obsolete.txt" in change.changed_files
    assert "apps/web/src/obsolete.tsx" in change.ui_impact_files
    assert any(path.name == "removed-1440x900.png" for path in base_images)


def test_hooks_use_one_pre_publish_entry_and_keep_stop_documentation_gate() -> None:
    hooks = json.loads((_ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    pre_commands = [hook["command"] for group in hooks["PreToolUse"] for hook in group["hooks"]]
    stop_commands = [hook["command"] for group in hooks["Stop"] for hook in group["hooks"]]

    assert len(pre_commands) == 1
    assert "git rev-parse --show-toplevel" in pre_commands[0]
    assert "pre_publish_gate.py" in pre_commands[0]
    assert len(stop_commands) == 1
    assert "git rev-parse --show-toplevel" in stop_commands[0]
    assert "documentation_gate.py" in stop_commands[0]

    pre_windows = hooks["PreToolUse"][0]["hooks"][0]["commandWindows"]
    stop_windows = hooks["Stop"][0]["hooks"][0]["commandWindows"]
    assert "Set-Location -LiteralPath $root" in pre_windows
    assert "pre_publish_gate.py" in pre_windows
    assert "Set-Location -LiteralPath $root" in stop_windows
    assert "documentation_gate.py" in stop_windows


def test_codex_hook_routes_ordinary_commit_and_publish_to_one_expected_gate() -> None:
    adapter = runpy.run_path(str(_ROOT / ".codex/hooks/pre_publish_gate.py"))
    events: list[object] = []
    evaluate = adapter["evaluate"]
    evaluate.__globals__["_documentation_reason"] = lambda _project, mode: events.append(mode)
    evaluate.__globals__["resolve_publication_target"] = lambda _project, _command: None
    evaluate.__globals__["run_pre_publish_pipeline"] = (
        lambda _project, independent_reviews, emit, publication_target: events.append(
            ("publish", independent_reviews)
        )
    )

    assert (
        evaluate(
            {"hook_event_name": "PreToolUse", "tool_input": {"command": "uv run pytest"}},
            _ROOT,
        )
        is None
    )
    assert events == []
    assert (
        evaluate(
            {"hook_event_name": "PreToolUse", "tool_input": {"command": "git commit -m x"}},
            _ROOT,
        )
        is None
    )
    assert events == ["staged"]
    assert (
        evaluate(
            {"hook_event_name": "PreToolUse", "tool_input": {"command": "gh pr ready 119"}},
            _ROOT,
        )
        is None
    )
    assert events == ["staged", ("publish", False)]
    assert "separately" in evaluate(
        {
            "hook_event_name": "PreToolUse",
            "tool_input": {"command": "git commit -m x && git push"},
        },
        _ROOT,
    )


@pytest.mark.parametrize(
    "command",
    [
        "bash -lc 'gh pr merge 119 --squash'",
        "cmd /c gh pr ready 119",
        'powershell -Command "gh pr create --base main"',
        "Start-Process gh -ArgumentList 'pr merge 119'",
        "echo `git push origin feature`",
        "echo `gh pr create --base main`",
        "echo `gh pr ready 119`",
        "echo `gh pr merge 119`",
    ],
)
def test_codex_hook_denies_nested_publication_without_running_pipeline(command: str) -> None:
    adapter = runpy.run_path(str(_ROOT / ".codex/hooks/pre_publish_gate.py"))
    evaluate = adapter["evaluate"]
    calls: list[str] = []
    evaluate.__globals__["run_pre_publish_pipeline"] = lambda *_args, **_kwargs: calls.append(
        "pipeline"
    )

    reason = evaluate(
        {"hook_event_name": "PreToolUse", "tool_input": {"command": command}},
        _ROOT,
    )

    assert reason is not None and "nested shell/process" in reason
    assert calls == []


def test_codex_hook_rechecks_numbered_pr_target_after_review() -> None:
    adapter = runpy.run_path(str(_ROOT / ".codex/hooks/pre_publish_gate.py"))
    evaluate = adapter["evaluate"]
    target = PublicationTarget(
        action="ready",
        selector="119",
        hostname="github.com",
        repository="owner/repository",
        head_sha="c" * 40,
        base_sha="a" * 40,
        base_ref="main",
    )
    targets = iter((target, replace(target, head_sha="d" * 40)))
    evaluate.__globals__["resolve_publication_target"] = lambda _project, _command: next(targets)
    evaluate.__globals__["run_pre_publish_pipeline"] = (
        lambda _project, independent_reviews, emit, publication_target: None
    )

    reason = evaluate(
        {"hook_event_name": "PreToolUse", "tool_input": {"command": "gh pr ready 119"}},
        _ROOT,
    )

    assert reason == "Target PR head/base changed during review; rerun the publication command."


def test_versioned_pre_push_installation_uses_common_gate_with_space_path(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository with spaces"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    (repository / ".githooks").mkdir()
    shutil.copy2(_ROOT / ".githooks/pre-push", repository / ".githooks/pre-push")
    installer = runpy.run_path(str(_ROOT / "scripts/install_git_hooks.py"))

    installer["install_hooks"](repository)
    installer["verify_hooks"](repository)

    configured = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert configured == ".githooks"
    hook = (repository / ".githooks/pre-push").read_text(encoding="utf-8")
    assert 'uv run cmp-pre-publish --root "$repo_root" --trigger git-pre-push' in hook
    assert '--remote-name "$1" --remote-location "$2"' in hook
    assert "--independent-review" not in hook


def test_hook_installer_does_not_replace_custom_hook_path(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "--local", "core.hooksPath", "custom-hooks"],
        cwd=repository,
        check=True,
    )
    installer = runpy.run_path(str(_ROOT / "scripts/install_git_hooks.py"))

    with pytest.raises(installer["HookInstallationError"], match="refusing to replace"):
        installer["install_hooks"](repository)

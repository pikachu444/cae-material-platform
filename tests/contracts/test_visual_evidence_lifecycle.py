from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from cmp.tools import documentation_impact
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    _can_use_unchanged_current_family,
    _load_visual_evidence_config,
    evaluate_documentation_impact,
    verify_documentation_impact,
)

ROOT = Path(__file__).resolve().parents[2]
BASE_SHA = "94d8a1cdefa104fb41865171093b0657966b159f"
VIEWPORTS = ("1366x768", "1440x900", "1920x1080", "2560x1440", "3840x2160")
ISSUE_167_EXCEPTION_FILES = (
    "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
    "originals/administration-database-1920x1080.png",
    "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
    "originals/administration-database-2560x1440.png",
    "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
    "originals/administration-database-3840x2160.png",
)
ISSUE_184_ROOT = "docs/17-evidence/images/issue-184-high-dpi-global-implementation"


def _git(project: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _manifest(
    *,
    current: str = "docs/user-guide/images/current",
    current_exception_paths: tuple[str, ...] = ISSUE_167_EXCEPTION_FILES,
    frozen_exception_paths: tuple[str, ...] = (ISSUE_184_ROOT,),
) -> str:
    current_exception = "\n".join(
        [
            "    - lifecycle: current",
            "      paths:",
            *(f'        - "{path}"' for path in current_exception_paths),
        ]
    )
    frozen_exception = "\n".join(
        [
            "    - lifecycle: frozen",
            "      paths:",
            *(f'        - "{path}"' for path in frozen_exception_paths),
        ]
    )
    return f"""\
version: 3
policy: {{}}
rules: []
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: "{current}"
    frozen: "docs/17-evidence/images"
    transient: ".artifacts"
  exceptions:
{current_exception}
{frozen_exception}
"""


def _write(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8")


def _init_repo(project: Path) -> str:
    _git(project, "init", "-b", "main")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Visual Evidence Tests")
    _git(project, "add", ".")
    _git(project, "commit", "-m", "base")
    base = _git(project, "rev-parse", "HEAD")
    _git(project, "branch", "-M", "feature")
    _git(project, "update-ref", "refs/remotes/origin/main", base)
    return base


def _current_family(prefix: str = "materials-search") -> set[str]:
    return {
        f"docs/user-guide/images/current/{prefix}-{viewport}.png" for viewport in VIEWPORTS
    }


def test_production_css_requires_promoted_current_five_view_family() -> None:
    changed = {
        "apps/web/src/materials.css",
        "docs/user-guide/materials.md",
        "docs/user-guide/screenshot-manifest.yaml",
        *_current_family(),
    }

    report = evaluate_documentation_impact(changed)

    assert report.visual_files == ("apps/web/src/materials.css",)
    assert not hasattr(report, "byte_identical_visual_files")
    assert not hasattr(report, "visual_preservation_issue")


def test_transient_or_legacy_evidence_never_satisfies_css_change() -> None:
    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact(
            {"apps/web/src/materials.css", ".artifacts/materials-1366x768.png"}
        )
    with pytest.raises(DocumentationImpactError, match=r"docs/17-evidence/images/legacy\.png"):
        evaluate_documentation_impact(
            {"apps/web/src/materials.css", "docs/17-evidence/images/legacy.png"}
        )


def test_old_css_byte_identical_manifest_does_not_bypass_current_evidence() -> None:
    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact(
            {
                "apps/web/src/materials.css",
                "docs/17-evidence/images/issue-261-css-proof/manifest.json",
            }
        )


def _css_worktree_fixture(tmp_path: Path, *, evidence: str) -> Path:
    _write(tmp_path / ".gitignore", ".artifacts/\n")
    _write(tmp_path / "docs/documentation-manifest.yaml", _manifest())
    _write(tmp_path / "apps/web/src/materials.css", ".materials { display: grid; }\n")
    _write(tmp_path / "docs/user-guide/materials.md", "# Materials\n")
    _write(
        tmp_path / "docs/user-guide/screenshot-manifest.yaml",
        "captures: []\nallowed_duplicate_groups: []\n",
    )
    _init_repo(tmp_path)

    _write(
        tmp_path / "apps/web/src/materials.css",
        ".materials { display: grid; min-width: 0; }\n",
    )
    if evidence == "promoted":
        _write(tmp_path / "docs/user-guide/materials.md", "# Materials\n\nUpdated.\n")
        _write(
            tmp_path / "docs/user-guide/screenshot-manifest.yaml",
            "captures:\n"
            + "".join(
                f"  - image: images/current/materials-search-{viewport}.png\n"
                for viewport in VIEWPORTS
            )
            + "allowed_duplicate_groups: []\n",
        )
        for viewport in VIEWPORTS:
            _write(
                tmp_path
                / f"docs/user-guide/images/current/materials-search-{viewport}.png",
                b"\x89PNG\r\n\x1a\ncurrent",
            )
        for phase in ("before", "after", "crops"):
            _write(
                tmp_path / f".artifacts/{phase}/materials-search-1920x1080.png",
                b"\x89PNG\r\n\x1a\ntransient",
            )
    elif evidence == "historical":
        _write(
            tmp_path / "docs/17-evidence/images/issue-test/before.png",
            b"\x89PNG\r\n\x1a\nhistorical",
        )
    elif evidence != "transient":
        raise AssertionError(f"unknown evidence fixture: {evidence}")
    return tmp_path


def test_worktree_css_change_accepts_promoted_family_and_ignores_artifacts(
    tmp_path: Path,
) -> None:
    project = _css_worktree_fixture(tmp_path, evidence="promoted")

    report = verify_documentation_impact(project, "worktree")

    assert report.visual_files == ("apps/web/src/materials.css",)
    assert all(not path.startswith(".artifacts/") for path in report.changed_files)
    assert _git(project, "check-ignore", ".artifacts/before/materials-search-1920x1080.png")


def _partial_current_family_fixture(
    tmp_path: Path,
    *,
    manifest_ref: bool = True,
    guide_ref: bool = True,
    missing_base_member: bool = False,
) -> tuple[Path, str, set[str]]:
    """Create four changed family members plus one unchanged base member."""

    _write(tmp_path / ".gitignore", ".artifacts/\n")
    _write(tmp_path / "docs/documentation-manifest.yaml", _manifest())
    _write(tmp_path / "apps/web/src/materials.css", ".materials { display: grid; }\n")
    _write(tmp_path / "docs/user-guide/materials.md", "# Materials\n")
    _write(tmp_path / "docs/user-guide/screenshot-manifest.yaml", "captures: []\n")
    for viewport in VIEWPORTS:
        _write(
            tmp_path
            / f"docs/user-guide/images/current/materials-search-{viewport}.png",
            f"base-{viewport}".encode(),
        )
    base_sha = _init_repo(tmp_path)
    if missing_base_member:
        (tmp_path / "docs/user-guide/images/current/materials-search-3840x2160.png").unlink()

    _write(tmp_path / "apps/web/src/materials.css", ".materials { display: grid; min-width: 0; }\n")
    references = "\n".join(
        f"images/current/materials-search-{viewport}.png" for viewport in VIEWPORTS
    )
    _write(
        tmp_path / "docs/user-guide/screenshot-manifest.yaml",
        "captures:\n"
        + "\n".join(
            f"  - image: images/current/materials-search-{viewport}.png" for viewport in VIEWPORTS
        )
        + "\n",
    )
    _write(
        tmp_path / "docs/user-guide/materials.md",
        "# Materials\n\n" + (references if guide_ref else "Updated.\n"),
    )
    if not manifest_ref:
        _write(tmp_path / "docs/user-guide/screenshot-manifest.yaml", "captures: []\n")
    changed: set[str] = {
        "apps/web/src/materials.css",
        "docs/user-guide/materials.md",
        "docs/user-guide/screenshot-manifest.yaml",
    }
    for viewport in VIEWPORTS[:-1]:
        path = f"docs/user-guide/images/current/materials-search-{viewport}.png"
        _write(tmp_path / path, f"changed-{viewport}".encode())
        changed.add(path)
    return tmp_path, base_sha, changed


def test_missing_same_stem_viewport_is_allowed_only_with_both_changed_doc_refs(
    tmp_path: Path,
) -> None:
    project, base_sha, changed = _partial_current_family_fixture(tmp_path)

    assert _can_use_unchanged_current_family(
        project, base_sha, changed, set(changed) - {
            "docs/user-guide/materials.md",
            "docs/user-guide/screenshot-manifest.yaml",
        }
    )
    # The direct helper is the fail-closed boundary; the public gate remains
    # covered by the promoted-family tests above.
    assert not _can_use_unchanged_current_family(
        project,
        base_sha,
        changed,
        {
            path
            for path in changed
            if path != "docs/user-guide/images/current/materials-search-1366x768.png"
        },
    )


@pytest.mark.parametrize(
    ("manifest_ref", "guide_ref", "missing_base_member"),
    ((False, True, False), (True, False, False), (True, True, True)),
)
def test_unchanged_family_rejects_missing_manifest_guide_or_base_member(
    tmp_path: Path,
    manifest_ref: bool,
    guide_ref: bool,
    missing_base_member: bool,
) -> None:
    project, base_sha, changed = _partial_current_family_fixture(
        tmp_path,
        manifest_ref=manifest_ref,
        guide_ref=guide_ref,
        missing_base_member=missing_base_member,
    )
    current_pngs = {
        path for path in changed if path.lower().endswith(".png")
    }

    assert not _can_use_unchanged_current_family(
        project, base_sha, changed, current_pngs
    )


def test_unchanged_family_rejects_wrong_stem_and_without_changed_member(
    tmp_path: Path,
) -> None:
    project, base_sha, changed = _partial_current_family_fixture(tmp_path)
    wrong_stem = {
        path.replace("materials-search-", "different-family-")
        for path in changed
        if path.lower().endswith(".png")
    }
    assert not _can_use_unchanged_current_family(project, base_sha, changed, wrong_stem)
    assert not _can_use_unchanged_current_family(project, base_sha, changed, set())


@pytest.mark.parametrize("evidence", ("transient", "historical"))
def test_worktree_css_change_rejects_ignored_or_historical_evidence(
    tmp_path: Path,
    evidence: str,
) -> None:
    project = _css_worktree_fixture(tmp_path, evidence=evidence)

    with pytest.raises(DocumentationImpactError):
        verify_documentation_impact(project, "worktree")


@pytest.mark.parametrize(
    "content",
    (
        "version: 3\nversion: 3\n",
        "version: 3\nvisual_evidence: [not-a-map]\n",
        """version: 3
visual_evidence:
  raster_extensions: [".gif"]
  roots:
    current: docs/user-guide/images/current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions: []
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: C:/absolute/current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions: []
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: docs\\user-guide\\images\\current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions: []
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: docs/user-guide/images/../current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions: []
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: docs/user-guide/images/current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions:
    - lifecycle: archived
      paths: [docs/17-evidence/images/archive]
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: docs/17-evidence/images/current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions: []
""",
        """version: 3
visual_evidence:
  raster_extensions: [".png", ".jpg", ".jpeg"]
  roots:
    current: docs/user-guide/images/current
    frozen: docs/17-evidence/images
    transient: .artifacts
  exceptions:
    - lifecycle: frozen
      paths: [docs/17-evidence/images/issue-a]
    - lifecycle: current
      paths: [docs/17-evidence/images/issue-a/nested]
""",
    ),
)
def test_visual_evidence_manifest_fails_closed(tmp_path: Path, content: str) -> None:
    path = tmp_path / "docs/documentation-manifest.yaml"
    _write(path, content)

    with pytest.raises(DocumentationImpactError):
        _load_visual_evidence_config(tmp_path)


def test_arbitrary_current_exception_cannot_unlock_frozen_raster(tmp_path: Path) -> None:
    arbitrary = "docs/17-evidence/images/issue-arbitrary/after/not-approved.png"
    _write(
        tmp_path / "docs/documentation-manifest.yaml",
        _manifest(current_exception_paths=(*ISSUE_167_EXCEPTION_FILES, arbitrary)),
    )

    with pytest.raises(DocumentationImpactError, match=r"approved.*exception policy"):
        _load_visual_evidence_config(tmp_path)


def test_frozen_default_reports_the_exact_changed_path() -> None:
    path = "docs/17-evidence/images/old-route/normal.jpg"

    with pytest.raises(DocumentationImpactError, match=path):
        evaluate_documentation_impact({path})


def test_issue_351_cleanup_requires_one_complete_approved_root(tmp_path: Path) -> None:
    _write(tmp_path / "docs/documentation-manifest.yaml", _manifest())
    approved_root = (
        tmp_path / "docs/17-evidence/images/issue-160-activity-density"
    )
    _write(approved_root / "first.png", b"\x89PNG\r\n\x1a\nfirst")
    _write(approved_root / "second.png", b"\x89PNG\r\n\x1a\nsecond")
    _init_repo(tmp_path)

    (approved_root / "first.png").unlink()
    with pytest.raises(DocumentationImpactError, match="complete approved root"):
        verify_documentation_impact(tmp_path, "worktree")

    (approved_root / "second.png").unlink()
    approved_root.rmdir()
    report = verify_documentation_impact(tmp_path, "worktree")

    assert any(
        path.endswith("issue-160-activity-density/first.png")
        for path in report.changed_files
    )


def test_issue_351_cleanup_does_not_unlock_an_adjacent_frozen_root(tmp_path: Path) -> None:
    _write(tmp_path / "docs/documentation-manifest.yaml", _manifest())
    adjacent = tmp_path / "docs/17-evidence/images/issue-160-unapproved/first.png"
    _write(adjacent, b"\x89PNG\r\n\x1a\nadjacent")
    _init_repo(tmp_path)

    adjacent.unlink()

    with pytest.raises(DocumentationImpactError, match="frozen visual evidence is immutable"):
        verify_documentation_impact(tmp_path, "worktree")


def test_issue_167_exception_requires_both_coupling_manifests() -> None:
    image = (
        "docs/17-evidence/images/issue-289-administration-database-workflow/after/"
        "originals/administration-database-1920x1080.png"
    )
    dependencies = {
        "docs/product/service-reference-manifest.yaml",
        "docs/17-evidence/images/issue-289-administration-database-workflow/visual-evidence.yaml",
    }

    assert evaluate_documentation_impact({image, *dependencies}).visual_files == ()
    with pytest.raises(DocumentationImpactError, match=image):
        evaluate_documentation_impact({image})


def test_actual_device_223_coupling_and_delete_rule() -> None:
    root = "docs/17-evidence/images/issue-223-windows-4k"
    image = f"{root}/after/normal-3840x2160.png"

    assert evaluate_documentation_impact({image, f"{root}/manifest.json"}).changed_files
    with pytest.raises(DocumentationImpactError, match="same-root manifest"):
        evaluate_documentation_impact({image})
    with pytest.raises(DocumentationImpactError, match="delete or rename"):
        evaluate_documentation_impact(
            {image: False, f"{root}/visual-evidence.yaml": True}
        )


def _issue_184_fixture(tmp_path: Path) -> tuple[Path, str, str, str]:
    names = [f"material-detail-{viewport}.png" for viewport in VIEWPORTS]
    # The base contract requires ten names per density; the first five are
    # enough to exercise a shared target, and the remainder are distinct.
    names.extend(f"solver-card-preview-{viewport}.png" for viewport in VIEWPORTS)
    base_json = {
        "full_screen_density_completeness": {
            density: {
                "expected": 90,
                "present": 80,
                "missing": names[:10],
            }
            for density in ("compact", "standard", "large")
        }
    }
    _write(tmp_path / "docs/documentation-manifest.yaml", _manifest())
    evidence_path = (
        tmp_path
        / "docs/17-evidence/images/issue-184-high-dpi-global-implementation/visual-evidence.json"
    )
    _write(evidence_path, json.dumps(base_json, indent=2) + "\n")
    base_sha = _init_repo(tmp_path)
    target = "material-detail-1366x768.png"
    target_path = (
        tmp_path
        / "docs/17-evidence/images/issue-184-high-dpi-global-implementation/after/compact"
        / target
    )
    _write(target_path, b"\x89PNG\r\n\x1a\nsynthetic")
    current_json = json.loads(evidence_path.read_text(encoding="utf-8"))
    current_json["full_screen_density_completeness"]["compact"]["missing"].remove(target)
    current_json["full_screen_density_completeness"]["compact"]["present"] += 1
    _write(evidence_path, json.dumps(current_json, indent=2) + "\n")
    return (
        tmp_path,
        target,
        str(target_path.relative_to(tmp_path)).replace("\\", "/"),
        base_sha,
    )


def test_issue_184_uses_base_derived_30_add_only_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _, target_path, policy_base = _issue_184_fixture(tmp_path)
    monkeypatch.setattr(documentation_impact, "_ISSUE_184_POLICY_BASE", policy_base)

    report = verify_documentation_impact(project, "worktree")

    assert target_path in report.changed_files


def test_issue_184_rejects_a_31st_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _, _, policy_base = _issue_184_fixture(tmp_path)
    monkeypatch.setattr(documentation_impact, "_ISSUE_184_POLICY_BASE", policy_base)
    extra = (
        project
        / "docs/17-evidence/images/issue-184-high-dpi-global-implementation/after/compact"
        / "not-in-base-missing-list.png"
    )
    _write(extra, b"\x89PNG\r\n\x1a\nsynthetic")
    with pytest.raises(DocumentationImpactError, match="base-derived 30"):
        verify_documentation_impact(project, "worktree")


def _commit_issue_184_state(project: Path) -> str:
    _git(project, "add", ".")
    _git(project, "commit", "-m", "record issue-184 evidence batch")
    commit = _git(project, "rev-parse", "HEAD")
    _git(project, "update-ref", "refs/remotes/origin/main", commit)
    return commit


def _issue_184_manifest_path(project: Path) -> Path:
    return (
        project
        / "docs/17-evidence/images/issue-184-high-dpi-global-implementation/visual-evidence.json"
    )


def _add_issue_184_target(project: Path, density: str, name: str) -> None:
    target = (
        project
        / f"docs/17-evidence/images/issue-184-high-dpi-global-implementation/after/{density}/{name}"
    )
    _write(target, b"\x89PNG\r\n\x1a\nsynthetic-next")
    manifest_path = _issue_184_manifest_path(project)
    current_json = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = current_json["full_screen_density_completeness"][density]
    item["missing"].remove(name)
    item["present"] += 1
    _write(manifest_path, json.dumps(current_json, indent=2) + "\n")


def test_issue_184_supports_partial_batches_from_a_later_merge_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _, _, policy_base = _issue_184_fixture(tmp_path)
    monkeypatch.setattr(documentation_impact, "_ISSUE_184_POLICY_BASE", policy_base)
    _commit_issue_184_state(project)

    _add_issue_184_target(project, "compact", "material-detail-1440x900.png")

    report = verify_documentation_impact(project, "worktree")

    assert any(
        path.endswith("after/compact/material-detail-1440x900.png")
        for path in report.changed_files
    )


@pytest.mark.parametrize("operation", ("modify", "delete", "rename"))
def test_issue_184_rejects_later_modification_deletion_and_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    project, _, target_path, policy_base = _issue_184_fixture(tmp_path)
    monkeypatch.setattr(documentation_impact, "_ISSUE_184_POLICY_BASE", policy_base)
    _commit_issue_184_state(project)
    target = project / target_path

    if operation == "modify":
        _write(target, b"\x89PNG\r\n\x1a\nmodified")
    elif operation == "delete":
        target.unlink()
    else:
        renamed = target.with_name("renamed-allowed-target.png")
        _git(
            project,
            "mv",
            str(target.relative_to(project)).replace("\\", "/"),
            str(renamed.relative_to(project)).replace("\\", "/"),
        )

    with pytest.raises(DocumentationImpactError, match="additions only"):
        verify_documentation_impact(project, "worktree")


def test_removed_issue_261_scripts_are_exactly_the_base_set_and_recoverable() -> None:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", BASE_SHA, "scripts"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    expected = sorted(
        path
        for path in result.stdout.splitlines()
        if path.startswith("scripts/")
        and "/" not in path.removeprefix("scripts/")
        and "issue_261" in Path(path).name
    )
    assert len(expected) == 37
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--no-renames",
            "--name-status",
            "--diff-filter=D",
            BASE_SHA,
            "--",
            "scripts",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    deleted = {
        line.split("\t", 1)[1]
        for line in diff.stdout.splitlines()
        if line.startswith("D\t")
    }
    assert deleted == set(expected)
    assert not any(path.startswith("scripts/fixtures/") for path in deleted)
    assert all(not (ROOT / path).exists() for path in expected)
    for path in expected:
        subprocess.run(
            ["git", "cat-file", "-e", f"{BASE_SHA}:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )


def test_historical_script_links_use_the_fixed_base_blob() -> None:
    expected = "https://github.com/pikachu444/cae-material-platform/blob/"
    for relative, name in (
        (
            "docs/17-evidence/issue-261-css-inventory-and-migration-plan.md",
            "check_issue_261_css_inventory.mjs",
        ),
        (
            "docs/17-evidence/issue-261-m1e5-producer-routed-residual.md",
            "capture_issue_261_m1e5_visual_evidence.py",
        ),
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert f"{expected}{BASE_SHA}/scripts/{name})" in content

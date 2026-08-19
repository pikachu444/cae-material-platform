from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import TypedDict

import pytest
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    DocumentationImpactException,
    _find_declarations,
    _identifier_occurrences,
    _nonblank_lines,
    _parse_name_status,
    _parse_name_status_entries,
    _static_imports,
    _validate_binding_order,
    _validate_exception,
    evaluate_documentation_impact,
    verify_documentation_impact,
)

BASE_SHA = "a" * 40
PRIMITIVES_PATH = "apps/web/src/design/primitives.css"
BASE_PRIMITIVES = ".ux-button { font-weight: 650; }\n"
CURRENT_PRIMITIVES = """\
.ux-button { font-weight: 650; }
.ux-semantic-text { color: var(--ux-text); }
"""


class _StructuralFixture(TypedDict):
    project: Path
    base_sha: str
    exception: Path
    source: Path
    secondary: Path
    target: Path


class _CssVisualPreservationFixture(TypedDict):
    project: Path
    base_sha: str
    evidence_relative: str
    manifest: Path
    screenshot_manifest: Path
    visual_files: tuple[str, ...]
    after: Path


def _git(project: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def foundation_exception(
    *,
    visual_files: tuple[str, ...] = (
        PRIMITIVES_PATH,
        "apps/web/src/design/semantic-ui.tsx",
    ),
    source_sha: str = BASE_SHA,
    preserved_computed_value_files: tuple[str, ...] = (PRIMITIVES_PATH,),
) -> DocumentationImpactException:
    return DocumentationImpactException(
        path="docs/14-testing/documentation-impact-exceptions/issue-257.yaml",
        issue="#257",
        source_sha=source_sha,
        classification="non-user-visible-foundation",
        reason="The shared foundation has no current product route consumer.",
        visual_files=visual_files,
        unconsumed_modules=("apps/web/src/design/semantic-ui.tsx",),
        preserved_computed_value_files=preserved_computed_value_files,
    )


def write_foundation(
    tmp_path: Path,
    *,
    primitives: str = CURRENT_PRIMITIVES,
) -> dict[str, str]:
    module = tmp_path / "apps/web/src/design/semantic-ui.tsx"
    module.parent.mkdir(parents=True)
    module.write_text("export const SemanticText = () => null;\n", encoding="utf-8")
    (tmp_path / PRIMITIVES_PATH).write_text(primitives, encoding="utf-8")
    return {PRIMITIVES_PATH: BASE_PRIMITIVES}


def _structural_fixture(
    tmp_path: Path,
    *,
    package_moved: bool = False,
    base_secondary_import: str = "./source",
) -> _StructuralFixture:
    source_root = tmp_path / "apps/web/src"
    source_root.mkdir(parents=True)
    secondary_source = """\
import type { StepInput } from "./source";

export function Secondary(value: StepInput): Record<string, unknown> {
  return { value };
}
"""
    if base_secondary_import != "./source":
        secondary_source = secondary_source.replace(
            'from "./source";', f'from "{base_secondary_import}";'
        )
    base_sources = {
        "apps/web/src/contracts.ts": "export type CommonProcessingStep = { id: string };\n",
        "apps/web/src/dependency.ts": 'export const dependency = "dependency";\n',
        "apps/web/src/source.tsx": """\
import { Fragment } from "react";
import type React from "react";
import type { CommonProcessingStep } from "./contracts";
import { dependency } from "./dependency";

type StepInput = { steps: CommonProcessingStep[] };
function formatStep(value: number): string | null {
  return `${dependency}-${value} µ`;
}

function unrelatedMetadata(): { specimen: string; revision: string } {
  return { specimen: "synthetic", revision: "v1" };
}

export const retainedSteps: CommonProcessingStep[] = [];
export function Source(value: StepInput): Record<string, unknown> {
  return { value: formatStep(value.steps.length), dependency };
}
""",
        "apps/web/src/secondary.tsx": secondary_source,
    }
    if package_moved:
        base_sources["apps/web/src/source.tsx"] = base_sources["apps/web/src/source.tsx"].replace(
            "  return `${dependency}-${value} µ`;",
            '  return Fragment.createElement("span", { value }) as unknown as string;',
        )
    for path, text in base_sources.items():
        file = tmp_path / Path(*path.split("/"))
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)

    (tmp_path / "apps/web/src/source.tsx").write_text(
        """\
import { Fragment } from "react";
import type React from "react";
import type { CommonProcessingStep } from "./contracts";
import { dependency } from "./dependency";
import { formatStep, type StepInput } from "./source-extracted";


function unrelatedMetadata(): { specimen: string; revision: string } {
  return { specimen: "synthetic", revision: "v1" };
}

export const retainedSteps: CommonProcessingStep[] = [];
export function Source(value: StepInput): Record<string, unknown> {
  return { value: formatStep(value.steps.length), dependency };
}
""",
        encoding="utf-8",
    )
    (tmp_path / "apps/web/src/secondary.tsx").write_text(
        """\
import type { StepInput } from "./source-extracted";

export function Secondary(value: StepInput): Record<string, unknown> {
  return { value };
}
""",
        encoding="utf-8",
    )
    target_text = """\
import type { CommonProcessingStep } from "./contracts";
import { dependency } from "./dependency";

export type StepInput = { steps: CommonProcessingStep[] };
export function formatStep(value: number): string | null {
  return `${dependency}-${value} µ`;
}
"""
    if package_moved:
        target_text = target_text.replace(
            "  return `${dependency}-${value} µ`;",
            '  return Fragment.createElement("span", { value }) as unknown as string;',
        )
    (tmp_path / "apps/web/src/source-extracted.ts").write_text(
        target_text,
        encoding="utf-8",
    )
    exception = tmp_path / "docs/14-testing/documentation-impact-exceptions/issue-268.yaml"
    exception.parent.mkdir(parents=True)
    exception.write_text(
        f"""\
schemaVersion: cmp.documentation-impact-exception.v1
issue: "#268"
sourceSha: {base_sha}
classification: non-user-visible-structural-extraction
reason: This extraction preserves runtime behavior while moving shared declarations.
visualFiles:
  - apps/web/src/source.tsx
  - apps/web/src/secondary.tsx
verification:
  importOnlyFiles:
    - apps/web/src/secondary.tsx
  relocations:
    - source: apps/web/src/source.tsx
      target: apps/web/src/source-extracted.ts
      declarations:
        - StepInput
        - formatStep
""",
        encoding="utf-8",
    )
    return {
        "project": tmp_path,
        "base_sha": base_sha,
        "exception": exception,
        "source": tmp_path / "apps/web/src/source.tsx",
        "secondary": tmp_path / "apps/web/src/secondary.tsx",
        "target": tmp_path / "apps/web/src/source-extracted.ts",
    }


def _import_only_fixture(tmp_path: Path) -> Path:
    source_root = tmp_path / "apps/web/src"
    source_root.mkdir(parents=True)
    sources = {
        "apps/web/src/legacy.ts": (
            'import { transform } from "./transform-a";\n'
            "export type Shape = { label: string };\n"
            "export const helper = (value: Shape) => transform(value.label);\n"
        ),
        "apps/web/src/feature.ts": (
            'import { transform } from "./transform-a";\n'
            "export type Shape = { label: string };\n"
            "export const helper = (value: Shape) => transform(value.label);\n"
        ),
        "apps/web/src/transform-a.ts": "export const transform = (value: string) => value;\n",
        "apps/web/src/transform-b.ts": (
            "export const transform = (value: string) => value.toUpperCase();\n"
        ),
        "apps/web/src/setup.ts": "export {};\n",
        "apps/web/src/other-setup.ts": "export {};\n",
        "apps/web/src/view.tsx": """\
import React from "react";
import "./setup";
import { helper, type Shape } from "./legacy";

export function View({ value }: { value: Shape }) {
  return <div>{helper(value)}</div>;
}
""",
    }
    for path, source in sources.items():
        file = tmp_path / Path(*path.split("/"))
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)

    view = tmp_path / "apps/web/src/view.tsx"
    view.write_text(
        view.read_text(encoding="utf-8").replace('from "./legacy";', 'from "./feature";'),
        encoding="utf-8",
    )
    return view


def _css_visual_preservation_fixture(
    tmp_path: Path,
    *,
    evidence_name: str = "issue-261-css-proof-m1a0",
    viewports: tuple[str, ...] = (
        "1366x768",
        "1440x900",
        "1920x1080",
        "2560x1440",
        "3840x2160",
    ),
) -> _CssVisualPreservationFixture:
    visual_files = (
        "apps/web/src/design/layout.css",
        "apps/web/src/features/modeling/ui/stages/data/data.css",
    )
    for path in visual_files:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(".data-panel { display: grid; }\n", encoding="utf-8")

    current_root = tmp_path / "docs/user-guide/images/current"
    current_root.mkdir(parents=True)
    for viewport in viewports:
        (current_root / f"data-{viewport}.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + viewport.encode("ascii")
        )
    screenshot_manifest = tmp_path / "docs/user-guide/screenshot-manifest.yaml"
    screenshot_manifest.parent.mkdir(parents=True, exist_ok=True)
    screenshot_manifest.write_text(
        "captures:\n"
        + "".join(f"  - image: images/current/data-{viewport}.png\n" for viewport in viewports)
        + "allowed_duplicate_groups: []\n",
        encoding="utf-8",
    )

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)

    (tmp_path / visual_files[0]).write_text(".shared-panel { min-width: 0; }\n", encoding="utf-8")
    (tmp_path / visual_files[1]).write_text(
        ".data-panel { display: grid; min-width: 0; }\n", encoding="utf-8"
    )
    visual_file_sha256 = {
        path: hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() for path in visual_files
    }

    evidence_relative = f"docs/17-evidence/images/{evidence_name}"
    evidence_root = tmp_path / evidence_relative
    images: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    current_matches: list[dict[str, str]] = []
    duplicate_groups: list[str] = []
    for viewport in viewports:
        name = f"data-{viewport}.png"
        current = f"docs/user-guide/images/current/{name}"
        before = f"{evidence_relative}/before/originals/{name}"
        after = f"{evidence_relative}/after/originals/{name}"
        value = (tmp_path / current).read_bytes()
        digest = hashlib.sha256(value).hexdigest()
        for path in (before, after):
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        images.extend(
            (
                {
                    "phase": "before",
                    "kind": "original",
                    "state": "normal",
                    "path": before,
                    "viewport": viewport,
                    "sha256": digest,
                },
                {
                    "phase": "after",
                    "kind": "original",
                    "state": "normal",
                    "path": after,
                    "viewport": viewport,
                    "sha256": digest,
                },
            )
        )
        pairs.append(
            {
                "name": name,
                "before_sha256": digest,
                "after_sha256": digest,
                "byte_equal": True,
            }
        )
        current_matches.append({"current": current, "before": before, "after": after})
        duplicate_groups.append(
            "  - rationale: byte-identical CSS migration evidence\n"
            "    images:\n"
            f"      - {current}\n"
            f"      - {before}\n"
            f"      - {after}\n"
        )
    screenshot_manifest.write_text(
        "captures:\n"
        + "".join(f"  - image: images/current/data-{viewport}.png\n" for viewport in viewports)
        + "allowed_duplicate_groups:\n"
        + "".join(duplicate_groups),
        encoding="utf-8",
    )
    manifest = evidence_root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "implementation_base": base_sha,
                "browser_zoom_percent": 100,
                "device_pixel_ratio": 1,
                "density": "standard",
                "documentation_impact": {
                    "schema_version": "cmp.documentation-impact.css-byte-identical.v1",
                    "issue": "#261",
                    "source_sha": base_sha,
                    "classification": "behavior-preserving-css-migration",
                    "visual_files": list(visual_files),
                    "visual_file_sha256": visual_file_sha256,
                    "current_matches": current_matches,
                },
                "original_pairs": pairs,
                "images": images,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "project": tmp_path,
        "base_sha": base_sha,
        "evidence_relative": evidence_relative,
        "manifest": manifest,
        "screenshot_manifest": screenshot_manifest,
        "visual_files": visual_files,
        "after": evidence_root / "after/originals" / f"data-{viewports[0]}.png",
    }


def _add_followup_css_visual_preservation(
    fixture: _CssVisualPreservationFixture,
    *,
    evidence_name: str = "issue-261-css-proof-m1a1",
) -> Path:
    project = Path(fixture["project"])
    first_manifest = Path(fixture["manifest"])
    first_relative = str(fixture["evidence_relative"])
    visual_files = tuple(fixture["visual_files"])

    _git(project, "add", ".")
    _git(project, "commit", "-m", "record first CSS migration")
    first_commit = _git(project, "rev-parse", "HEAD")

    for index, path in enumerate(visual_files):
        target = project / path
        target.write_text(
            target.read_text(encoding="utf-8")
            + f".followup-{index} {{ min-height: {index + 1}px; }}\n",
            encoding="utf-8",
        )

    followup_relative = f"docs/17-evidence/images/{evidence_name}"
    followup_root = project / followup_relative
    data = json.loads(first_manifest.read_text(encoding="utf-8"))
    for image in data["images"]:
        old_path = image["path"]
        new_path = old_path.replace(first_relative, followup_relative)
        target = project / new_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((project / old_path).read_bytes())
        image["path"] = new_path
    for match in data["documentation_impact"]["current_matches"]:
        match["before"] = match["before"].replace(first_relative, followup_relative)
        match["after"] = match["after"].replace(first_relative, followup_relative)
    data["implementation_base"] = first_commit
    data["documentation_impact"]["source_sha"] = first_commit
    data["documentation_impact"]["visual_file_sha256"] = {
        path: hashlib.sha256((project / path).read_bytes()).hexdigest() for path in visual_files
    }
    followup_manifest = followup_root / "manifest.json"
    followup_manifest.parent.mkdir(parents=True, exist_ok=True)
    followup_manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    screenshot_manifest = Path(fixture["screenshot_manifest"])
    content = screenshot_manifest.read_text(encoding="utf-8")
    for match in data["documentation_impact"]["current_matches"]:
        first_after = match["after"].replace(followup_relative, first_relative)
        addition = f"      - {match['before']}\n      - {match['after']}\n"
        content = content.replace(
            f"      - {first_after}\n",
            f"      - {first_after}\n{addition}",
        )
    screenshot_manifest.write_text(content, encoding="utf-8")
    return followup_manifest


def _mutate_structural_fixture(fixture: _StructuralFixture, case: str) -> None:
    project = Path(fixture["project"])
    exception = Path(fixture["exception"])
    source = Path(fixture["source"])
    secondary = Path(fixture["secondary"])
    target = Path(fixture["target"])
    yaml_text = exception.read_text(encoding="utf-8")

    if case == "source_sha":
        exception.write_text(
            yaml_text.replace(f"sourceSha: {fixture['base_sha']}", f"sourceSha: {'b' * 40}"),
            encoding="utf-8",
        )
    elif case == "visual_files":
        exception.write_text(
            yaml_text.replace(
                "  - apps/web/src/source.tsx\n  - apps/web/src/secondary.tsx",
                "  - apps/web/src/mismatch.tsx\n  - apps/web/src/secondary.tsx",
            ),
            encoding="utf-8",
        )
    elif case == "declaration_text":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "return `${dependency}-${value} µ`;", "return `${dependency}-${value}!`;"
            ),
            encoding="utf-8",
        )
    elif case == "existing_export":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "export const retainedSteps", "const retainedSteps"
            ),
            encoding="utf-8",
        )
    elif case == "residual_source":
        source.write_text(
            source.read_text(encoding="utf-8") + "export const Added = <div />;\n",
            encoding="utf-8",
        )
    elif case == "target_residual":
        target.write_text(
            target.read_text(encoding="utf-8") + "\nconst extra = 1;\n",
            encoding="utf-8",
        )
    elif case == "stale_target":
        _git(project, "add", "apps/web/src/source-extracted.ts")
        _git(project, "commit", "-m", "target exists at base")
        new_base = _git(project, "rev-parse", "HEAD")
        _git(project, "update-ref", "refs/remotes/origin/main", new_base)
        exception.write_text(
            yaml_text.replace(fixture["base_sha"], new_base),
            encoding="utf-8",
        )
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif case == "missing_target":
        target.unlink()
    elif case == "wrong_target":
        exception.write_text(
            yaml_text.replace("apps/web/src/source-extracted.ts", "apps/web/src/wrong.ts"),
            encoding="utf-8",
        )
    elif case == "import_statement":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                'import { formatStep, type StepInput } from "./source-extracted";',
                'import { formatStep, type StepInput } from "./source-extracted"',
            ),
            encoding="utf-8",
        )
    elif case == "import_order":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                'import type { CommonProcessingStep } from "./contracts";\n'
                'import { dependency } from "./dependency";\n'
                'import { formatStep, type StepInput } from "./source-extracted";',
                'import { formatStep, type StepInput } from "./source-extracted";\n'
                'import type { CommonProcessingStep } from "./contracts";\n'
                'import { dependency } from "./dependency";',
            ),
            encoding="utf-8",
        )
    elif case == "import_module":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                'from "./contracts";', 'from "./wrong-module";'
            ),
            encoding="utf-8",
        )
    elif case == "import_binding":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "formatStep, type StepInput", "other, type StepInput"
            ),
            encoding="utf-8",
        )
    elif case == "import_type_value":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "{ formatStep, type StepInput }", "{ formatStep, StepInput }"
            ),
            encoding="utf-8",
        )
    elif case == "target_binding_order":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "{ formatStep, type StepInput }", "{ type StepInput, formatStep }"
            ),
            encoding="utf-8",
        )
    elif case == "runtime_import_only":
        secondary.write_text(
            secondary.read_text(encoding="utf-8").replace(
                "import type { StepInput }", "import { StepInput }"
            ),
            encoding="utf-8",
        )
    elif case == "unrelated_type_rewrite":
        secondary.write_text(
            secondary.read_text(encoding="utf-8").replace(
                'from "./source-extracted";', 'from "./contracts";'
            ),
            encoding="utf-8",
        )
    elif case == "no_rewrite":
        secondary.write_text(
            secondary.read_text(encoding="utf-8").replace(
                'from "./source-extracted";', 'from "./source.tsx";'
            ),
            encoding="utf-8",
        )
    elif case == "import_only_residual":
        secondary.write_text(
            secondary.read_text(encoding="utf-8") + "\nexport const Added = <span />;\n",
            encoding="utf-8",
        )
    elif case == "unreferenced_target_binding":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'import { dependency } from "./dependency";',
                'import { dependency, retainedSteps } from "./dependency";',
            ),
            encoding="utf-8",
        )
    elif case == "missing_target_binding":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'import { dependency } from "./dependency";',
                'import { } from "./dependency";',
            ),
            encoding="utf-8",
        )
    elif case == "unused_moved_dependency":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'import { dependency } from "./dependency";\n', ""
            ),
            encoding="utf-8",
        )
    elif case == "missing_moved_dependency":
        target.write_text(
            target.read_text(encoding="utf-8").replace('from "./dependency";', 'from "./missing";'),
            encoding="utf-8",
        )
    elif case == "duplicate_target_module":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'import { dependency } from "./dependency";\n',
                'import { dependency } from "./dependency";\n'
                'import { dependency } from "./dependency";\n',
            ),
            encoding="utf-8",
        )
    elif case == "target_all_type_form":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'import type { CommonProcessingStep } from "./contracts";',
                'import { type CommonProcessingStep } from "./contracts";',
            ),
            encoding="utf-8",
        )
    elif case == "duplicate_yaml_key":
        exception.write_text(yaml_text + 'issue: "#269"\n', encoding="utf-8")
    elif case == "duplicate_yaml_path":
        exception.write_text(
            yaml_text.replace(
                "  - apps/web/src/secondary.tsx\nverification:",
                "  - apps/web/src/secondary.tsx\n  - apps/web/src/secondary.tsx\nverification:",
            ),
            encoding="utf-8",
        )
    elif case == "duplicate_yaml_name":
        exception.write_text(
            yaml_text.replace(
                "        - formatStep\n",
                "        - formatStep\n        - formatStep\n",
            ),
            encoding="utf-8",
        )
    elif case == "ambiguous_relative":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'from "./dependency";', 'from "./dependency/";'
            ),
            encoding="utf-8",
        )
    elif case == "missing_relative":
        target.write_text(
            target.read_text(encoding="utf-8").replace('from "./dependency";', 'from "./missing";'),
            encoding="utf-8",
        )
    else:
        raise AssertionError(f"unknown structural mutation {case}")


def test_structural_extraction_fe04a_worktree_and_staged_round_trip(
    tmp_path: Path,
) -> None:
    fixture = _structural_fixture(tmp_path)

    report = verify_documentation_impact(tmp_path, "worktree")
    assert set(report.exempted_visual_files) == {
        "apps/web/src/source.tsx",
        "apps/web/src/secondary.tsx",
    }
    _git(tmp_path, "add", ".")
    assert verify_documentation_impact(tmp_path, "worktree") == report
    assert verify_documentation_impact(tmp_path, "staged") == report

    Path(fixture["target"]).unlink()
    with pytest.raises(DocumentationImpactError, match="absent in current worktree"):
        verify_documentation_impact(tmp_path, "worktree")


def test_structural_extraction_allows_unrelated_nonvisual_typescript_change(
    tmp_path: Path,
) -> None:
    _structural_fixture(tmp_path)
    (tmp_path / "apps/web/src/unrelated.ts").write_text(
        "export const unrelated = true;\n", encoding="utf-8"
    )

    report = verify_documentation_impact(tmp_path, "worktree")

    assert "apps/web/src/unrelated.ts" in report.changed_files


def test_structural_residual_ignores_blank_gaps_but_rejects_nonblank_changes(
    tmp_path: Path,
) -> None:
    fixture = _structural_fixture(tmp_path)
    source = Path(fixture["source"])
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "function unrelatedMetadata", "\n\n\nfunction unrelatedMetadata"
        ),
        encoding="utf-8",
    )

    verify_documentation_impact(tmp_path, "worktree")

    source.write_text(
        source.read_text(encoding="utf-8").replace("return { value:", "return {  value:"),
        encoding="utf-8",
    )
    with pytest.raises(DocumentationImpactError, match="residual source bytes"):
        verify_documentation_impact(tmp_path, "worktree")


def test_nonblank_lines_preserve_nonblank_bytes() -> None:
    assert _nonblank_lines("\nalpha\n  \nbeta\n") == "alpha\nbeta"
    assert _nonblank_lines("alpha\n beta") != _nonblank_lines("alpha\nbeta")


def test_structural_extraction_rejects_moved_package_binding(tmp_path: Path) -> None:
    _structural_fixture(tmp_path, package_moved=True)

    with pytest.raises(DocumentationImpactError, match="unsupported package import"):
        verify_documentation_impact(tmp_path, "worktree")


@pytest.mark.parametrize(
    ("base_secondary_import", "message"),
    (
        ("./contracts", "expected relocation source"),
        ("react", "unsupported relative import"),
    ),
)
def test_import_only_rewrite_requires_original_base_source(
    tmp_path: Path,
    base_secondary_import: str,
    message: str,
) -> None:
    _structural_fixture(tmp_path, base_secondary_import=base_secondary_import)

    with pytest.raises(DocumentationImpactError, match=message):
        verify_documentation_impact(tmp_path, "worktree")


def test_structural_parser_accepts_annotated_functions_and_template_dependency() -> None:
    declarations = _find_declarations(
        """\
type CommonProcessingStep = { id: string };
function scalar(value: number): number { return value; }
function steps(value: CommonProcessingStep[]): CommonProcessingStep[] { return value; }
function optional(value: string): string | null { return value; }
function record(value: Record<string, unknown>): Record<string, unknown> { return value; }
function multiline(
  value: number,
  items: CommonProcessingStep[],
): string | null { return `${value}-${items.length}`; }
function templated(dependency: string): string { return `${dependency}`; }
"""
    )

    assert {declaration.name for declaration in declarations} == {
        "CommonProcessingStep",
        "scalar",
        "steps",
        "optional",
        "record",
        "multiline",
        "templated",
    }


def test_structural_parser_handles_nested_jsx_and_regex_expression() -> None:
    declarations = _find_declarations(
        r"""
function render(value: string): string {
  const match = /item\/\d+/.exec(value);
  return <section><span>{match?.[0]}</span><input /></section>;
}
"""
    )

    assert [declaration.name for declaration in declarations] == ["render"]


def test_structural_parser_handles_jsx_contractions_and_string_literals() -> None:
    declarations = _find_declarations(
        r"""
function render(): string {
  const ordinary = 'server';
  return <p>The server's result <span>is valid</span>.</p>;
}
"""
    )

    assert [declaration.name for declaration in declarations] == ["render"]
    with pytest.raises(DocumentationImpactError, match="unterminated string literal"):
        _find_declarations("function broken(): string { const value = 'unterminated; }")


def test_required_declaration_does_not_skip_unsupported_return_annotation() -> None:
    with pytest.raises(DocumentationImpactError, match="function return annotation"):
        _find_declarations(
            "function required(): { specimen: string } { return { specimen: 'x' }; }",
            required_names={"required"},
        )


@pytest.mark.parametrize(
    ("source", "message"),
    (
        ("function generic<T>(value: T): T { return value; }", "non-generic"),
        ("function noBody(value: number): number;", "unsupported function|requires a body"),
        ("type Missing = number", "requires a semicolon"),
        ("const Missing = 1", "requires a semicolon"),
    ),
)
def test_structural_parser_rejects_unsupported_declarations(source: str, message: str) -> None:
    with pytest.raises(DocumentationImpactError, match=message):
        _find_declarations(source)


def test_identifier_occurrences_ignore_deceptive_literals_and_comments() -> None:
    deceptive = "// dependency\nconst text = 'dependency'; const staticText = `dependency`;"
    actual = "const text = `${dependency}`;"

    assert "dependency" not in _identifier_occurrences(deceptive)
    assert "dependency" in _identifier_occurrences(actual)


def test_target_import_binding_order_accepts_valid_partitions() -> None:
    _validate_binding_order(
        _static_imports('import { alpha, type Beta, type Zeta } from "./dep";')[0],
        "target.ts",
        target_dependency=True,
    )
    _validate_binding_order(
        _static_imports('import type { Alpha, Beta } from "./types";')[0],
        "target.ts",
        target_dependency=True,
    )


def test_static_imports_accept_multiline_named_bindings() -> None:
    statement = """\
import {
  alpha,
  type Beta,
} from "./dep";
"""

    assert [
        (binding.imported, binding.local, binding.kind)
        for binding in _static_imports(statement)[0].bindings
    ] == [("alpha", "alpha", "value"), ("Beta", "Beta", "type")]


def test_static_imports_reject_missing_semicolon_after_named_bindings() -> None:
    with pytest.raises(DocumentationImpactError, match="static import requires a semicolon"):
        _static_imports('import { alpha } from "./dep"\nconst value = 1;')


@pytest.mark.parametrize(
    ("statement", "message"),
    (
        ('import { type Alpha, value } from "./dep";', "values before inline types"),
        ('import { beta, alpha } from "./dep";', "lexicographically ordered"),
        ('import { type Beta, type Alpha } from "./dep";', "lexicographically ordered"),
        ('import { type Alpha } from "./dep";', "all-type import must use import type"),
    ),
)
def test_target_import_binding_order_rejects_ambiguous_forms(
    statement: str,
    message: str,
) -> None:
    with pytest.raises(DocumentationImpactError, match=message):
        _validate_binding_order(
            _static_imports(statement)[0],
            "target.ts",
            target_dependency=True,
        )


@pytest.mark.parametrize(
    "case",
    (
        "source_sha",
        "visual_files",
        "declaration_text",
        "existing_export",
        "residual_source",
        "target_residual",
        "stale_target",
        "missing_target",
        "wrong_target",
        "import_statement",
        "import_order",
        "import_module",
        "import_binding",
        "import_type_value",
        "target_binding_order",
        "runtime_import_only",
        "unrelated_type_rewrite",
        "no_rewrite",
        "import_only_residual",
        "unreferenced_target_binding",
        "missing_target_binding",
        "unused_moved_dependency",
        "missing_moved_dependency",
        "duplicate_target_module",
        "target_all_type_form",
        "duplicate_yaml_key",
        "duplicate_yaml_path",
        "duplicate_yaml_name",
        "ambiguous_relative",
        "missing_relative",
    ),
)
def test_structural_extraction_rejects_invalid_variants(
    tmp_path: Path,
    case: str,
) -> None:
    fixture = _structural_fixture(tmp_path)
    _mutate_structural_fixture(fixture, case)

    expected = {
        "source_sha": "does not match",
        "visual_files": "changed visual source",
        "declaration_text": "declaration bytes changed",
        "existing_export": "residual source bytes",
        "residual_source": "residual source bytes",
        "target_residual": "residual code",
        "stale_target": "already exists at merge base",
        "missing_target": "complete changed set",
        "wrong_target": "complete changed set",
        "import_statement": "static import requires a semicolon|residual source bytes",
        "import_order": "exactly one target import",
        "import_module": "existing import module",
        "import_binding": "target import bindings",
        "import_type_value": "import bindings",
        "target_binding_order": "values before inline types",
        "runtime_import_only": "type-only import bindings",
        "unrelated_type_rewrite": "undeclared relocation target",
        "no_rewrite": "undeclared relocation target",
        "import_only_residual": "residual source bytes",
        "unreferenced_target_binding": "dependency bindings",
        "missing_target_binding": "non-empty named imports",
        "unused_moved_dependency": "unused or missing dependencies",
        "missing_moved_dependency": "resolves to 0 candidates",
        "duplicate_target_module": "duplicate import groups",
        "target_all_type_form": "all-type import must use import type",
        "duplicate_yaml_key": "duplicate YAML key",
        "duplicate_yaml_path": "duplicate entries",
        "duplicate_yaml_name": "duplicate declarations",
        "ambiguous_relative": "ambiguous import",
        "missing_relative": "resolves to 0 candidates",
    }[case]
    with pytest.raises(DocumentationImpactError, match=expected):
        verify_documentation_impact(tmp_path, "worktree")


def test_visual_source_alone_is_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact({"apps/web/src/material-library.tsx"})


def test_byte_identical_css_migration_accepts_m1a0_only_registered_five_viewport_evidence(
    tmp_path: Path,
) -> None:
    _css_visual_preservation_fixture(tmp_path)

    report = verify_documentation_impact(tmp_path, "worktree")

    assert report.byte_identical_visual_files == (
        "apps/web/src/design/layout.css",
        "apps/web/src/features/modeling/ui/stages/data/data.css",
    )
    assert report.visual_preservation_issue == "#261"
    assert report.exempted_visual_files == ()
    _git(tmp_path, "add", ".")
    assert verify_documentation_impact(tmp_path, "staged") == report


def test_byte_identical_css_migration_accepts_m1a1_only_registered_five_viewport_evidence(
    tmp_path: Path,
) -> None:
    _css_visual_preservation_fixture(
        tmp_path,
        evidence_name="issue-261-css-proof-m1a1",
    )

    report = verify_documentation_impact(tmp_path, "worktree")

    assert report.byte_identical_visual_files == (
        "apps/web/src/design/layout.css",
        "apps/web/src/features/modeling/ui/stages/data/data.css",
    )
    assert report.visual_preservation_issue == "#261"


def test_byte_identical_css_migration_selects_sole_current_hash_proof_after_m1a0(
    tmp_path: Path,
) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    _add_followup_css_visual_preservation(fixture)

    report = verify_documentation_impact(tmp_path, "worktree")

    assert report.byte_identical_visual_files == (
        "apps/web/src/design/layout.css",
        "apps/web/src/features/modeling/ui/stages/data/data.css",
    )
    assert report.visual_preservation_issue == "#261"


def test_byte_identical_css_migration_rejects_two_current_hash_proofs(tmp_path: Path) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    current_manifest = _add_followup_css_visual_preservation(fixture)
    duplicate = (
        tmp_path
        / "docs/17-evidence/images/issue-261-css-proof-m1a1-duplicate/manifest.json"
    )
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(current_manifest.read_bytes())

    with pytest.raises(DocumentationImpactError, match="must match the current CSS hashes"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_rejects_modified_stale_historical_proof(
    tmp_path: Path,
) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    _add_followup_css_visual_preservation(fixture)
    historical = Path(fixture["manifest"])
    historical.write_text(
        historical.read_text(encoding="utf-8").replace(
            '"density": "standard"',
            '"density": "standard" ',
        ),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="must be committed and unchanged"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_rejects_actual_pixel_bytes_drift(tmp_path: Path) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    Path(fixture["after"]).write_bytes(Path(fixture["after"]).read_bytes() + b"drift")

    with pytest.raises(DocumentationImpactError, match="bytes differ"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_requires_all_five_viewports(tmp_path: Path) -> None:
    _css_visual_preservation_fixture(
        tmp_path,
        viewports=("1366x768", "1440x900", "1920x1080", "2560x1440"),
    )

    with pytest.raises(DocumentationImpactError, match="missing mandatory viewports"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_requires_exact_visual_source_coverage(
    tmp_path: Path,
) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    manifest = Path(fixture["manifest"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["documentation_impact"]["visual_files"].pop()
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(DocumentationImpactError, match="must exactly match"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_rejects_stale_css_hash(tmp_path: Path) -> None:
    _css_visual_preservation_fixture(tmp_path)
    css = tmp_path / "apps/web/src/features/modeling/ui/stages/data/data.css"
    css.write_text(css.read_text(encoding="utf-8") + ".late-change { color: red; }\n")

    with pytest.raises(DocumentationImpactError, match="CSS SHA-256 differs"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_cannot_cover_a_tsx_change(tmp_path: Path) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    view = tmp_path / "apps/web/src/view.tsx"
    view.write_text("export const View = () => <div />;\n", encoding="utf-8")
    manifest = Path(fixture["manifest"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["documentation_impact"]["visual_files"].append("apps/web/src/view.tsx")
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(DocumentationImpactError, match="only production CSS"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_requires_registered_duplicate_provenance(
    tmp_path: Path,
) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    screenshot_manifest = Path(fixture["screenshot_manifest"])
    content = screenshot_manifest.read_text(encoding="utf-8")
    first_group = content.index("  - rationale: byte-identical CSS migration evidence")
    second_group = content.index(
        "  - rationale: byte-identical CSS migration evidence", first_group + 1
    )
    screenshot_manifest.write_text(content[:first_group] + content[second_group:], encoding="utf-8")

    with pytest.raises(DocumentationImpactError, match="registered duplicate group"):
        verify_documentation_impact(tmp_path, "worktree")


def test_byte_identical_css_migration_requires_ancestor_source_sha(tmp_path: Path) -> None:
    fixture = _css_visual_preservation_fixture(tmp_path)
    manifest = Path(fixture["manifest"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["implementation_base"] = "b" * 40
    data["documentation_impact"]["source_sha"] = "b" * 40
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(DocumentationImpactError, match="not an ancestor"):
        verify_documentation_impact(tmp_path, "worktree")


def test_visual_source_and_guide_without_evidence_are_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="screenshot-manifest"):
        evaluate_documentation_impact(
            {
                "apps/web/src/material-library.tsx",
                "docs/user-guide/18-search-first-materials.md",
            }
        )


def test_visual_source_with_guide_manifest_and_png_is_accepted() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/src/material-library.tsx",
            "docs/user-guide/18-search-first-materials.md",
            "docs/user-guide/screenshot-manifest.yaml",
            "docs/user-guide/images/current/materials-search-next.png",
        }
    )
    assert report.visual_files == ("apps/web/src/material-library.tsx",)


def test_import_only_relative_named_rewire_does_not_require_visual_evidence(
    tmp_path: Path,
) -> None:
    _import_only_fixture(tmp_path)

    report = verify_documentation_impact(tmp_path, "worktree")

    assert report.visual_files == ()
    assert report.exempted_visual_files == ()


def test_import_only_rewire_rejects_non_import_source_change(tmp_path: Path) -> None:
    view = _import_only_fixture(tmp_path)
    view.write_text(
        view.read_text(encoding="utf-8")
        .replace("<div>", "<section>")
        .replace("</div>", "</section>"),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        verify_documentation_impact(tmp_path, "worktree")


def test_import_only_rewire_rejects_binding_change(tmp_path: Path) -> None:
    view = _import_only_fixture(tmp_path)
    view.write_text(
        view.read_text(encoding="utf-8").replace(
            "{ helper, type Shape }", "{ helper as changedHelper, type Shape }"
        ),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        verify_documentation_impact(tmp_path, "worktree")


def test_import_only_rewire_rejects_same_named_runtime_export_with_changed_behavior(
    tmp_path: Path,
) -> None:
    _import_only_fixture(tmp_path)
    feature = tmp_path / "apps/web/src/feature.ts"
    feature.write_text(
        feature.read_text(encoding="utf-8").replace(
            "transform(value.label);", "transform(value.label).toUpperCase();"
        ),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        verify_documentation_impact(tmp_path, "worktree")


def test_import_only_rewire_rejects_unchanged_export_with_changed_runtime_dependency(
    tmp_path: Path,
) -> None:
    _import_only_fixture(tmp_path)
    feature = tmp_path / "apps/web/src/feature.ts"
    feature.write_text(
        feature.read_text(encoding="utf-8").replace(
            'from "./transform-a";', 'from "./transform-b";'
        ),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        verify_documentation_impact(tmp_path, "worktree")


def test_static_import_parser_accepts_self_closing_jsx_after_literal_attribute() -> None:
    imports = _static_imports(
        'import { helper } from "./helper";\nexport const View = () => <line className="grid" />;\n'
    )

    assert len(imports) == 1
    assert imports[0].module == "./helper"


@pytest.mark.parametrize(
    ("original", "replacement"),
    (
        ('from "react";', 'from "preact";'),
        ('import "./setup";', 'import "./other-setup";'),
    ),
)
def test_import_only_rewire_rejects_protected_import_change(
    tmp_path: Path,
    original: str,
    replacement: str,
) -> None:
    view = _import_only_fixture(tmp_path)
    view.write_text(
        view.read_text(encoding="utf-8").replace(original, replacement),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        verify_documentation_impact(tmp_path, "worktree")


def test_app_route_change_without_navigation_contract_is_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="navigation-contract"):
        evaluate_documentation_impact(
            {
                "apps/web/src/app.tsx",
                "docs/user-guide/18-search-first-materials.md",
                "docs/user-guide/screenshot-manifest.yaml",
                "docs/user-guide/images/current/navigation-next.png",
            }
        )


def test_test_only_change_is_accepted() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/src/material-library.test.tsx",
            "tests/contracts/test_documentation_impact.py",
        }
    )
    assert report.visual_files == ()


def test_storybook_only_change_is_accepted_without_product_documentation() -> None:
    report = evaluate_documentation_impact(
        {
            "apps/web/.storybook/preview.css",
            "apps/web/src/design/semantic-ui.stories.tsx",
        }
    )

    assert report.visual_files == ()


def test_exact_non_user_visible_foundation_exception_is_accepted(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/main.tsx").write_text(
        'import "./styles.css";\n',
        encoding="utf-8",
    )
    exception = foundation_exception()
    visual_files = set(exception.visual_files)

    validated = _validate_exception(
        tmp_path,
        exception,
        visual_files,
        BASE_SHA,
        base_files=base_files,
    )
    report = evaluate_documentation_impact(visual_files, exception=validated)

    assert report.exempted_visual_files == exception.visual_files
    assert report.exception_issue == "#257"
    assert validated.derived_selectors == ("ux-semantic-text",)


def test_foundation_exception_cannot_bypass_repository_validation() -> None:
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="must pass repository validation"):
        # Deliberately violate the static API to exercise its runtime validation.
        evaluate_documentation_impact(
            set(exception.visual_files),
            exception=exception,  # type: ignore[arg-type]
        )


def test_foundation_exception_rejects_route_or_feature_visual_source(
    tmp_path: Path,
) -> None:
    exception = foundation_exception(
        visual_files=("apps/web/src/material-library.tsx",),
    )

    with pytest.raises(DocumentationImpactError, match="only files under"):
        _validate_exception(
            tmp_path,
            exception,
            {"apps/web/src/material-library.tsx"},
            BASE_SHA,
        )


def test_foundation_exception_rejects_shared_layout_as_preserved_value(tmp_path: Path) -> None:
    exception = foundation_exception(
        visual_files=(
            "apps/web/src/design/layout.css",
            "apps/web/src/design/semantic-ui.tsx",
        ),
        preserved_computed_value_files=("apps/web/src/design/layout.css",),
    )

    with pytest.raises(DocumentationImpactError, match="only shared tokens"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
        )


def test_foundation_exception_requires_exact_sha_and_visual_paths(tmp_path: Path) -> None:
    exception = foundation_exception(source_sha="b" * 40)

    with pytest.raises(DocumentationImpactError, match="does not match"):
        _validate_exception(tmp_path, exception, set(exception.visual_files), BASE_SHA)

    exception = foundation_exception()
    with pytest.raises(DocumentationImpactError, match="must exactly match"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files) | {"apps/web/src/design/typography.css"},
            BASE_SHA,
        )


def test_foundation_exception_rejects_a_product_module_consumer(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/app.tsx").write_text(
        'import { SemanticText } from "./design/semantic-ui";\n',
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="referenced by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_product_selector_use(tmp_path: Path) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/materials.tsx").write_text(
        'export const Materials = () => <span className="ux-semantic-text" />;\n',
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="used by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_scans_css_consumers_for_derived_selectors(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(tmp_path)
    (tmp_path / "apps/web/src/materials.css").write_text(
        ".materials .ux-semantic-text { color: red; }\n",
        encoding="utf-8",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="used by product source"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_unproven_existing_appearance_change(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 700; }
.ux-semantic-text { color: var(--ux-text); }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="cannot prove unchanged appearance"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_new_rule_for_an_existing_selector(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 650; }
.ux-button:hover { color: red; }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="isolated class"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_foundation_exception_rejects_negated_novel_class_bypass(
    tmp_path: Path,
) -> None:
    base_files = write_foundation(
        tmp_path,
        primitives="""\
.ux-button { font-weight: 650; }
.ux-button:not(.ux-foundation-new) { color: red; }
""",
    )
    exception = foundation_exception()

    with pytest.raises(DocumentationImpactError, match="positive isolated class"):
        _validate_exception(
            tmp_path,
            exception,
            set(exception.visual_files),
            BASE_SHA,
            base_files=base_files,
        )


def test_openapi_workflow_change_requires_current_guide() -> None:
    with pytest.raises(DocumentationImpactError, match="OpenAPI workflow"):
        evaluate_documentation_impact({"contracts/http/openapi.yaml"})

    report = evaluate_documentation_impact(
        {
            "contracts/http/openapi.yaml",
            "docs/user-guide/18-search-first-materials.md",
        }
    )
    assert report.changed_files


def test_name_status_collector_keeps_deletion_rename_source_and_type_change() -> None:
    paths = _parse_name_status(
        b"D\0apps/web/src/deleted.tsx\0"
        b"R100\0apps/web/src/renamed.css\0archive/renamed.txt\0"
        b"T\0apps/web/src/type-changed.css\0"
    )

    assert paths == {
        "apps/web/src/deleted.tsx",
        "apps/web/src/renamed.css",
        "archive/renamed.txt",
        "apps/web/src/type-changed.css",
    }
    with pytest.raises(DocumentationImpactError, match="visual sources"):
        evaluate_documentation_impact(paths)


def test_deleted_visual_evidence_cannot_satisfy_current_documentation_gate() -> None:
    entries = _parse_name_status_entries(
        b"M\0apps/web/src/app.tsx\0"
        b"M\0docs/user-guide/navigation-contract.yaml\0"
        b"M\0docs/user-guide/screenshot-manifest.yaml\0"
        b"D\0docs/user-guide/deleted.md\0"
        b"D\0docs/user-guide/images/current/deleted.png\0"
    )

    with pytest.raises(DocumentationImpactError, match="current docs/user-guide"):
        evaluate_documentation_impact(entries)
    with pytest.raises(DocumentationImpactError, match="current user-guide PNG"):
        evaluate_documentation_impact(entries)

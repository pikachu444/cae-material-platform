from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TypedDict

import pytest
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    DocumentationImpactException,
    _find_declarations,
    _identifier_occurrences,
    _is_import_only_visual_change,
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


def _git(project: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fixture_patch_sha256(
    project: Path,
    base_sha: str,
    head_sha: str,
    paths: list[str],
) -> str:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--binary",
            "--full-index",
            f"{base_sha}...{head_sha}",
            "--",
            *sorted(paths),
        ],
        cwd=project,
        check=True,
        capture_output=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def _write_fixture_file(project: Path, path: str, value: str) -> None:
    target = project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def _composition_attestation_fixture(tmp_path: Path, case: str = "approved") -> None:
    base_files = {
        "apps/web/src/app.tsx": "export const App = () => <main>route</main>;\n",
        "docs/user-guide/navigation-contract.yaml": "version: 1\n",
    }
    for path, value in base_files.items():
        _write_fixture_file(tmp_path, path, value)
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")

    _git(tmp_path, "switch", "-c", "feature")
    feature_files = {
        "apps/web/e2e/issue263-app-routing.spec.ts": "export const routeSpec = true;\n",
        "apps/web/frontend-guard-baseline.json": "{}\n",
        "apps/web/src/app.tsx": (
            'import { RouteComposition } from "./app/route-composition";\n'
            "export const App = () => <RouteComposition />;\n"
        ),
        "apps/web/src/app/legacy-route-pages.tsx": "export const Legacy = () => null;\n",
        "apps/web/src/app/navigation.test.tsx": "export const navigationTest = true;\n",
        "apps/web/src/app/navigation.ts": "export const navigate = (value: string) => value;\n",
        "apps/web/src/app/product-session.tsx": "export const ProductSession = () => null;\n",
        "apps/web/src/app/route-composition.test.tsx": "export const routeTest = true;\n",
        "apps/web/src/app/route-composition.tsx": (
            "export const RouteComposition = () => <main>route</main>;\n"
        ),
        "apps/web/src/app/routes.test.ts": "export const routesTest = true;\n",
        "apps/web/src/app/routes.ts": 'export const routes = ["/materials"];\n',
        "docs/12-roadmap/frontend-refactoring-roadmap.md": "FE-08A complete\n",
        "docs/17-evidence/issue-263-fe08a-app-route-composition.md": "No visible change.\n",
        "docs/user-guide/navigation-contract.yaml": "version: 2\n",
    }
    for path, value in feature_files.items():
        _write_fixture_file(tmp_path, path, value)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "extract app composition")
    approved_head = _git(tmp_path, "rev-parse", "HEAD")
    changed_paths = sorted(feature_files)
    visual_files = [
        "apps/web/src/app.tsx",
        "apps/web/src/app/legacy-route-pages.tsx",
        "apps/web/src/app/product-session.tsx",
        "apps/web/src/app/route-composition.tsx",
    ]
    visual_digest = _fixture_patch_sha256(
        tmp_path, base_sha, approved_head, visual_files
    )
    attested_digest = _fixture_patch_sha256(
        tmp_path, base_sha, approved_head, changed_paths
    )

    _git(tmp_path, "switch", "-c", "policy", base_sha)
    attested_source = "0" * 40 if case == "wrong_base" else base_sha
    attested_visual = visual_files[:-1] if case == "wrong_path_set" else visual_files
    targets = [
        "apps/web/src/app/legacy-route-pages.tsx",
        "apps/web/src/app/navigation.ts",
        "apps/web/src/app/product-session.tsx",
        "apps/web/src/app/route-composition.tsx",
        "apps/web/src/app/routes.ts",
    ]
    if case == "missing_target":
        targets = targets[:-1]
    tests = [
        "apps/web/e2e/issue263-app-routing.spec.ts",
        "apps/web/src/app/navigation.test.tsx",
        "apps/web/src/app/route-composition.test.tsx",
        "apps/web/src/app/routes.test.ts",
    ]
    if case == "missing_test":
        tests = tests[:-1]
    navigation_contract = (
        "docs/user-guide/missing-navigation-contract.yaml"
        if case == "missing_contract"
        else "docs/user-guide/navigation-contract.yaml"
    )
    if case == "wrong_digest":
        visual_digest = "f" * 64
    if case == "wrong_attested_digest":
        attested_digest = "e" * 64
    exception_lines = [
        "schemaVersion: cmp.documentation-impact-exception.v1",
        'issue: "#263"',
        f"sourceSha: {attested_source}",
        "classification: non-user-visible-composition-attestation",
        "reason: Exact audited app composition extraction with no visible behavior change.",
        "visualFiles:",
        *(f"  - {path}" for path in attested_visual),
        "verification:",
        "  compositionTargets:",
        *(f"    - {path}" for path in targets),
        "  characterizationTests:",
        *(f"    - {path}" for path in tests),
        f"  navigationContract: {navigation_contract}",
        f"  visualPatchSha256: {visual_digest}",
        f"  attestedPatchSha256: {attested_digest}",
        "  independentAudit: APPROVE",
        "  productOwnerDisposition: no-visible-change",
    ]
    exception_path = (
        "docs/14-testing/documentation-impact-exceptions/issue-263.yaml"
    )
    _write_fixture_file(tmp_path, exception_path, "\n".join(exception_lines) + "\n")
    if case == "main_visual_drift":
        _write_fixture_file(
            tmp_path,
            "apps/web/src/unrelated-main-view.tsx",
            "export const MainView = () => <aside>new main UI</aside>;\n",
        )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "approve exact composition patch")
    policy_head = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", policy_head)
    _git(tmp_path, "switch", "feature")
    if case in {"rebased", "main_visual_drift"}:
        _git(tmp_path, "rebase", "policy")

    mutations = {
        "copy": (
            "apps/web/src/app/route-composition.tsx",
            "export const RouteComposition = () => <main>changed copy</main>;\n",
        ),
        "jsx": (
            "apps/web/src/app/route-composition.tsx",
            'export const RouteComposition = () => <main aria-label="changed">route</main>;\n',
        ),
        "dom": (
            "apps/web/src/app/route-composition.tsx",
            "export const RouteComposition = () => <section>route</section>;\n",
        ),
        "style": (
            "apps/web/src/app/route-composition.tsx",
            'export const RouteComposition = () => <main style={{ color: "red" }}>route</main>;\n',
        ),
        "route": (
            "apps/web/src/app/routes.ts",
            'export const routes = ["/administration"];\n',
        ),
        "behavior": (
            "apps/web/src/app/navigation.ts",
            "export const navigate = (value: string) => value.toUpperCase();\n",
        ),
        "extra_css": ("apps/web/src/app/extra.css", ".route { color: red; }\n"),
        "extra_route": (
            "apps/web/src/app/extra-route.ts",
            'export const extraRoute = "/extra";\n',
        ),
    }
    if case in mutations:
        path, value = mutations[case]
        _write_fixture_file(tmp_path, path, value)
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", f"mutate {case}")
    if case == "incomplete_extraction":
        (tmp_path / "apps/web/src/app/navigation.ts").unlink()
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-m", "leave extraction incomplete")
    if case == "same_diff_attestation":
        policy_yaml = _git(tmp_path, "show", f"origin/main:{exception_path}")
        _write_fixture_file(tmp_path, exception_path, policy_yaml + "\n")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-m", "self-attest feature diff")


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


@pytest.mark.parametrize("case", ("approved", "rebased"))
def test_exact_base_absent_app_composition_attestation_is_accepted(
    tmp_path: Path,
    case: str,
) -> None:
    _composition_attestation_fixture(tmp_path, case)

    report = verify_documentation_impact(tmp_path, "range")

    assert report.exception_issue == "#263"
    assert report.exempted_visual_files == (
        "apps/web/src/app.tsx",
        "apps/web/src/app/legacy-route-pages.tsx",
        "apps/web/src/app/product-session.tsx",
        "apps/web/src/app/route-composition.tsx",
    )


@pytest.mark.parametrize(
    "case",
    (
        "wrong_base",
        "wrong_digest",
        "wrong_attested_digest",
        "wrong_path_set",
        "missing_target",
        "missing_test",
        "missing_contract",
        "main_visual_drift",
        "same_diff_attestation",
        "copy",
        "jsx",
        "dom",
        "style",
        "route",
        "behavior",
        "extra_css",
        "extra_route",
        "incomplete_extraction",
    ),
)
def test_composition_attestation_is_fail_closed(
    tmp_path: Path,
    case: str,
) -> None:
    _composition_attestation_fixture(tmp_path, case)

    with pytest.raises(DocumentationImpactError):
        verify_documentation_impact(tmp_path, "range")


def test_visual_source_and_guide_without_evidence_are_rejected() -> None:
    with pytest.raises(DocumentationImpactError, match="screenshot-manifest"):
        evaluate_documentation_impact(
            {
                "apps/web/src/material-library.tsx",
                "docs/user-guide/18-search-first-materials.md",
            }
        )


def test_visual_source_with_guide_manifest_and_png_is_accepted() -> None:
    current_images = {
        "docs/user-guide/images/current/materials-search-next-1366x768.png",
        "docs/user-guide/images/current/materials-search-next-1440x900.png",
        "docs/user-guide/images/current/materials-search-next-1920x1080.png",
        "docs/user-guide/images/current/materials-search-next-2560x1440.png",
        "docs/user-guide/images/current/materials-search-next-3840x2160.png",
    }
    report = evaluate_documentation_impact(
        {
            "apps/web/src/material-library.tsx",
            "docs/user-guide/18-search-first-materials.md",
            "docs/user-guide/screenshot-manifest.yaml",
            *current_images,
        },
    )
    assert report.visual_files == ("apps/web/src/material-library.tsx",)


def test_import_only_relative_named_rewire_does_not_require_visual_evidence(
    tmp_path: Path,
) -> None:
    _import_only_fixture(tmp_path)

    report = verify_documentation_impact(tmp_path, "worktree")

    assert report.visual_files == ()
    assert report.exempted_visual_files == ()


def test_import_only_added_side_effect_css_is_attributed_to_changed_css(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "apps/web/src"
    source_root.mkdir(parents=True)
    view = source_root / "view.tsx"
    view.write_text(
        'import "./base.css";\nexport const View = () => <div />;\n',
        encoding="utf-8",
    )
    (source_root / "base.css").write_text(".base { display: block; }\n", encoding="utf-8")
    owner = source_root / "owner.css"
    owner.write_text(".owner { display: block; }\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)

    view.write_text(
        'import "./base.css";\nimport "./owner.css";\n'
        "export const View = () => <div />;\n",
        encoding="utf-8",
    )
    owner.write_text(".owner { display: grid; }\n", encoding="utf-8")

    assert _is_import_only_visual_change(tmp_path, base_sha, "apps/web/src/view.tsx")


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

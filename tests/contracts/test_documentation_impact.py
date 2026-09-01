from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TypedDict, cast

import pytest
import yaml
from cmp.tools import documentation_impact
from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    DocumentationImpactException,
    _attested_patch_sha256,
    _find_declarations,
    _identifier_occurrences,
    _is_import_only_visual_change,
    _nonblank_lines,
    _parse_name_status,
    _parse_name_status_entries,
    _static_imports,
    _validate_binding_order,
    _validate_exception,
    _validate_retired_materials_reference_changes,
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


def _guard_baseline(source_sha: str, *, owner_issue: str = "#256") -> str:
    return f"""{{
  "schemaVersion": "cmp.frontend-guard-baseline.v1",
  "sourceSha": "{source_sha}",
  "ownerIssue": "{owner_issue}",
  "hotspots": [],
  "debt": [],
  "exceptions": []
}}
"""


def _composition_attestation_fixture(tmp_path: Path, case: str = "approved") -> None:
    base_files = {
        "apps/web/frontend-guard-baseline.json": _guard_baseline("1" * 40),
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
        "apps/web/frontend-guard-baseline.json": _guard_baseline(base_sha),
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
        "docs/planning/frontend-refactoring-roadmap.md": "FE-08A complete\n",
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
    attested_digest = _attested_patch_sha256(tmp_path, base_sha, changed_paths)

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
        "docs/testing/documentation-impact-exceptions/issue-263.yaml"
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
        _write_fixture_file(
            tmp_path,
            "apps/web/frontend-guard-baseline.json",
            _guard_baseline(policy_head),
        )
        _git(tmp_path, "add", "apps/web/frontend-guard-baseline.json")
        _git(tmp_path, "commit", "-m", "refresh frontend guard source")

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
    if case == "wrong_guard_source":
        _write_fixture_file(
            tmp_path,
            "apps/web/frontend-guard-baseline.json",
            _guard_baseline("2" * 40),
        )
        _git(tmp_path, "add", "apps/web/frontend-guard-baseline.json")
        _git(tmp_path, "commit", "-m", "break frontend guard source")
    if case == "guard_content_change":
        _write_fixture_file(
            tmp_path,
            "apps/web/frontend-guard-baseline.json",
            _guard_baseline(base_sha, owner_issue="#999"),
        )
        _git(tmp_path, "add", "apps/web/frontend-guard-baseline.json")
        _git(tmp_path, "commit", "-m", "change other frontend guard content")
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
        path="docs/testing/documentation-impact-exceptions/issue-257.yaml",
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
    exception = tmp_path / "docs/testing/documentation-impact-exceptions/issue-268.yaml"
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


def _css_relocation_fixture(
    tmp_path: Path, case: str = "valid"
) -> tuple[Path, dict[str, object], dict[str, bool], str]:
    def rule(selector: str, body: str) -> str:
        return f"{selector} {{\n{body}\n}}\n"

    layout_rules = (
        (
            ".materials-scroll-rail-y",
            "  grid-row: 1;\n  grid-column: 2;\n  border-width: 0 0 0 1px;",
        ),
        (
            ".materials-scroll-rail-x",
            "  grid-row: 2;\n  grid-column: 1;\n  border-width: 1px 0 0;",
        ),
    )
    materials_rules = (
        (
            ".materials-scroll-shell",
            "  display: grid;\n  min-width: 0;\n  min-height: 0;",
        ),
        (
            '.materials-scroll-shell[data-scroll-y="true"]',
            "  grid-template-columns: minmax(0, 1fr) var(--ux-scrollbar-track-size);",
        ),
        (
            '.materials-scroll-shell[data-scroll-x="true"]',
            "  grid-template-rows: minmax(0, 1fr) var(--ux-scrollbar-track-size);",
        ),
        (".materials-scroll-rail", "  border: 1px solid #9bb1bb;\n  background: #dce7ec;"),
        (".materials-scroll-thumb", "  position: absolute;\n  display: block;"),
        (
            ".materials-scroll-rail-y .materials-scroll-thumb",
            "  top: 2px;\n  right: 2px;\n  left: 2px;",
        ),
        (
            ".materials-scroll-rail-x .materials-scroll-thumb",
            "  top: 2px;\n  bottom: 2px;\n  left: 2px;",
        ),
        (".materials-scroll-rail:hover .materials-scroll-thumb", "  background: #315f72;"),
        (".materials-scroll-rail:focus-visible", "  outline: 2px solid var(--ux-focus);"),
        (".materials-scroll-corner", "  grid-row: 2;\n  grid-column: 2;"),
    )
    layout_path = "apps/web/src/design/layout.css"
    materials_path = "apps/web/src/features/materials/ui/materials.css"
    owner_path = "apps/web/src/materials-scroll-rail.tsx"
    target_path = "apps/web/src/materials-scroll-rail.css"
    main_path = "apps/web/src/main.tsx"
    main_import = (
        'import "./other";\n'
        if case == "unreachable_owner"
        else 'import "./materials-scroll-rail";\n'
    )
    base_files = {
        layout_path: rule(".retained-layout", "  padding: 1px;")
        + "\n"
        + "\n".join(rule(*item).rstrip("\n") for item in layout_rules)
        + "\n\n"
        + rule(".tail-layout", "  margin: 1px;").rstrip("\n")
        + "\n",
        materials_path: rule(".retained-material", "  color: red;")
        + "\n"
        + "\n".join(rule(*item).rstrip("\n") for item in materials_rules)
        + "\n\n"
        + rule(".tail-material", "  color: blue;").rstrip("\n")
        + "\n",
        owner_path: 'import { SCROLL_RAIL_METRICS } from "./design/metrics";\n\n'
        "export function Rail() {\n  return SCROLL_RAIL_METRICS;\n}\n",
        main_path: main_import,
    }
    current_files = {
        layout_path: rule(".retained-layout", "  padding: 1px;")
        + "\n"
        + rule(".tail-layout", "  margin: 1px;"),
        materials_path: rule(".retained-material", "  color: red;")
        + "\n"
        + rule(".tail-material", "  color: blue;"),
        owner_path: base_files[owner_path].replace(
            'import { SCROLL_RAIL_METRICS } from "./design/metrics";\n',
            'import { SCROLL_RAIL_METRICS } from "./design/metrics";\n'
            'import "./materials-scroll-rail.css";\n',
        ),
        target_path: "\n".join(
            rule(*item).rstrip("\n") for item in (*layout_rules, *materials_rules)
        )
        + "\n",
    }
    base_files["apps/web/src/other.css"] = ".unrelated { color: green; }\n"
    if case == "unreachable_owner":
        base_files["apps/web/src/other.tsx"] = "export const Other = true;\n"
    for path, value in base_files.items():
        _write_fixture_file(tmp_path, path, value)
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base CSS ownership")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)
    for path, value in current_files.items():
        _write_fixture_file(tmp_path, path, value)

    if case == "declaration_body":
        current_files[target_path] = current_files[target_path].replace(
            "  grid-row: 1;", "  grid-row: 2;", 1
        )
    elif case == "stale_source":
        current_files[layout_path] += rule(*layout_rules[0])
    elif case == "residual_source":
        current_files[layout_path] += rule(".residual-change", "  color: black;")
    elif case == "target_order":
        first = rule(*layout_rules[0]).rstrip("\n")
        second = rule(*layout_rules[1]).rstrip("\n")
        current_files[target_path] = current_files[target_path].replace(
            f"{first}\n{second}", f"{second}\n{first}", 1
        )
    elif case == "target_undeclared":
        current_files[target_path] += rule(".undeclared", "  color: black;")
    elif case == "owner_import":
        current_files[owner_path] = current_files[owner_path].replace(
            'import "./materials-scroll-rail.css";\n', ""
        )
    elif case == "owner_import_wrong":
        current_files[owner_path] = current_files[owner_path].replace(
            'import "./materials-scroll-rail.css";', 'import "./other.css";'
        )
    elif case == "parallel_selector":
        base_files["apps/web/src/other.css"] = ".materials-scroll-rail { color: red; }\n"
        _write_fixture_file(
            tmp_path, "apps/web/src/other.css", base_files["apps/web/src/other.css"]
        )
    elif case == "parallel_selector_group":
        base_files["apps/web/src/other.css"] = (
            ".materials-scroll-rail, .other { color: red; }\n"
        )
        _write_fixture_file(
            tmp_path, "apps/web/src/other.css", base_files["apps/web/src/other.css"]
        )
    elif case == "source_sha":
        pass
    elif case in {"valid", "visual_set", "unreachable_owner", "parallel_selector_group"}:
        pass
    else:
        raise AssertionError(f"unknown CSS relocation mutation {case}")
    for path, value in current_files.items():
        _write_fixture_file(tmp_path, path, value)

    exception_path = "docs/testing/documentation-impact-exceptions/issue-331.yaml"
    yaml_lines = [
        "schemaVersion: cmp.documentation-impact-exception.v1",
        'issue: "#331"',
        f"sourceSha: {base_sha}",
        "classification: non-user-visible-css-ownership-relocation",
        "reason: This exact CSS ownership relocation preserves rendered behavior "
        "and cascade order.",
        "visualFiles:",
        f"  - {layout_path}",
        f"  - {materials_path}",
        f"  - {target_path}",
        "verification:",
        "  importOnlyFiles:",
        f"    - {owner_path}",
        "  relocations:",
    ]
    for source, selectors in ((layout_path, layout_rules), (materials_path, materials_rules)):
        yaml_lines.extend(
            [
                f"    - source: {source}",
                f"      target: {target_path}",
                "      selectors:",
                *(f"        - '{selector}'" for selector, _body in selectors),
            ]
        )
    _write_fixture_file(tmp_path, exception_path, "\n".join(yaml_lines) + "\n")
    raw = yaml.safe_load((tmp_path / exception_path).read_text(encoding="utf-8"))
    changed = {
        layout_path: True,
        materials_path: True,
        target_path: True,
        owner_path: True,
    }
    if case == "source_sha":
        raw["sourceSha"] = "b" * 40
    if case == "visual_set":
        changed["apps/web/src/other.css"] = True
    return tmp_path, raw, changed, base_sha


def _css_retirement_fixture(
    tmp_path: Path, case: str = "valid"
) -> tuple[Path, dict[str, object], dict[str, bool], str]:
    def rule(selector: str, body: str) -> str:
        return f"{selector} {{\n{body}\n}}\n"

    layout_path = "apps/web/src/design/layout.css"
    deleted_source_path = "apps/web/src/styles.css"
    target_path = "apps/web/src/features/modeling/ui/stages/export/modeling-export-stage.css"
    main_path = "apps/web/src/main.tsx"
    preview_path = "apps/web/.storybook/preview.ts"
    app_path = "apps/web/src/app.tsx"
    parallel_path = "apps/web/src/parallel.css"
    retired_selector = ".selection-delivery-command .ux-button"
    moved_selector = ".export-status-ready-to-create"
    layout_base = (
        rule(".retained-layout", "  padding: 1px;")
        + rule(retired_selector, "  width: 100%;")
        + rule(".tail-layout", "  margin: 1px;")
    )
    styles_base = (
        "/* Historical Export source comments remain after the moved rule. */\n"
        + rule(moved_selector, "  color: #276b49;")
        + "/* The deleted source has no remaining production rules. */\n"
    )
    if case == "deleted_source_residual":
        styles_base += rule(".leftover", "  color: red;")
    target_base = rule(".existing-target", "  color: green;") + rule(
        ".tail-target", "  color: blue;"
    )
    main_base = 'import "./app";\nimport "./styles.css";\n\nexport const App = true;\n'
    preview_base = (
        'import "../src/styles.css";\n\nexport const Preview = true;\n'
    )
    app_base = (
        'import "./features/modeling/ui/stages/export/modeling-export-stage.css";\n'
        "export const App = true;\n"
    )
    parallel_base = ".unrelated { color: green; }\n"
    base_files = {
        layout_path: layout_base,
        deleted_source_path: styles_base,
        target_path: target_base,
        main_path: main_base,
        preview_path: preview_base,
        app_path: app_base,
        parallel_path: parallel_base,
    }
    current_files = {
        layout_path: layout_base.replace(rule(retired_selector, "  width: 100%;"), ""),
        target_path: target_base + rule(moved_selector, "  color: #276b49;"),
        main_path: main_base.replace('import "./styles.css";\n', ""),
        preview_path: preview_base.replace('import "../src/styles.css";\n', ""),
        app_path: app_base,
        parallel_path: parallel_base,
    }
    if case in {"unlisted_importer", "dynamic_importer"}:
        unlisted_path = "apps/web/src/unlisted-importer.tsx"
        unlisted_importer = (
            'import "./styles.css";\nexport const Unlisted = true;\n'
            if case == "unlisted_importer"
            else 'const styles = import("./styles.css");\nexport const Unlisted = styles;\n'
        )
        base_files[unlisted_path] = unlisted_importer
        current_files[unlisted_path] = unlisted_importer
    for path, value in base_files.items():
        _write_fixture_file(tmp_path, path, value)
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Documentation Impact Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base CSS retirement")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "branch", "-M", "feature")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)
    for path, value in current_files.items():
        _write_fixture_file(tmp_path, path, value)
    (tmp_path / Path(*deleted_source_path.split("/"))).unlink()

    if case == "existing_target_drift":
        current_files[target_path] += rule(".target-drift", "  color: purple;")
    elif case == "removed_import_drift":
        current_files[main_path] = current_files[main_path].replace(
            'import "./app";\n', 'import "./app";\nimport "./app";\n', 1
        )
    elif case == "retirement_produced":
        current_files[app_path] += 'const produced = "selection-delivery-command";\n'
    elif case == "retirement_parallel":
        current_files[parallel_path] = rule(retired_selector, "  width: 100%;")
    elif case not in {
        "valid",
        "deleted_source_residual",
        "unlisted_importer",
        "dynamic_importer",
    }:
        raise AssertionError(f"unknown CSS retirement mutation {case}")
    for path, value in current_files.items():
        _write_fixture_file(tmp_path, path, value)

    exception_path = "docs/testing/documentation-impact-exceptions/issue-331.yaml"
    yaml_text = f"""schemaVersion: cmp.documentation-impact-exception.v1
issue: "#331"
sourceSha: {base_sha}
classification: non-user-visible-css-ownership-relocation
reason: This exact CSS relocation and retirement preserves the current visual surface.
visualFiles:
  - {layout_path}
  - {deleted_source_path}
  - {target_path}
verification:
  importOnlyFiles:
    - {main_path}
    - {preview_path}
  relocations:
    - source: {deleted_source_path}
      target: {target_path}
      selectors:
        - {moved_selector}
  retirements:
    - source: {layout_path}
      selectors:
        - '{retired_selector}'
"""
    _write_fixture_file(tmp_path, exception_path, yaml_text)
    raw = yaml.safe_load((tmp_path / exception_path).read_text(encoding="utf-8"))
    changed = {
        layout_path: True,
        deleted_source_path: False,
        target_path: True,
        main_path: True,
        preview_path: True,
    }
    return tmp_path, raw, changed, base_sha


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("source_sha", "does not match"),
        ("declaration_body", "declaration bytes changed"),
        ("stale_source", "retains moved CSS selector"),
        ("residual_source", "changes residual source bytes"),
        ("target_order", "undeclared CSS rule|out of order"),
        ("target_undeclared", "undeclared CSS rule|out of order"),
        ("owner_import", "exactly one side-effect import"),
        ("owner_import_wrong", "exactly one side-effect import"),
        ("parallel_selector", "parallel CSS truth"),
        ("unreachable_owner", "not reachable from apps/web/src/main.tsx"),
        ("parallel_selector_group", "parallel CSS truth"),
        ("visual_set", "visualFiles must exactly match"),
    ],
)
def test_css_ownership_relocation_is_fail_closed(tmp_path: Path, case: str, message: str) -> None:
    project, raw, changed, base_sha = _css_relocation_fixture(tmp_path, case)
    exception = documentation_impact._parse_exception(
        "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
    )
    if case == "valid":
        raise AssertionError("the valid case is covered by the positive test")
    with pytest.raises(DocumentationImpactError, match=message):
        _validate_exception(
            project,
            exception,
            changed,
            base_sha,
            changed=changed,
        )


def test_css_ownership_relocation_accepts_exact_ordered_family(tmp_path: Path) -> None:
    project, raw, changed, base_sha = _css_relocation_fixture(tmp_path)
    exception = documentation_impact._parse_exception(
        "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
    )
    validated = _validate_exception(
        project,
        exception,
        changed,
        base_sha,
        changed=changed,
    )
    assert validated.exception.classification == "non-user-visible-css-ownership-relocation"
    assert validated.exception.css_relocations[0].selectors == (
        ".materials-scroll-rail-y",
        ".materials-scroll-rail-x",
    )


def test_css_ownership_relocation_rejects_grouped_declared_selector(
    tmp_path: Path,
) -> None:
    _project, raw, _changed, _base_sha = _css_relocation_fixture(tmp_path)
    verification = cast(dict[str, object], raw["verification"])
    relocations = cast(list[dict[str, object]], verification["relocations"])
    selectors = cast(list[str], relocations[0]["selectors"])
    selectors[0] = (
        ".materials-scroll-rail-y, .parallel"
    )
    with pytest.raises(
        DocumentationImpactError,
        match="exactly one top-level selector branch",
    ):
        documentation_impact._parse_exception(
            "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
        )


def test_css_ownership_relocation_accepts_deleted_source_and_retirement(
    tmp_path: Path,
) -> None:
    project, raw, changed, base_sha = _css_retirement_fixture(tmp_path)
    exception = documentation_impact._parse_exception(
        "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
    )
    validated = _validate_exception(
        project,
        exception,
        changed,
        base_sha,
        changed=changed,
    )
    assert validated.exception.css_retirements[0].selectors == (
        ".selection-delivery-command .ux-button",
    )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("deleted_source_residual", "non-comment residual CSS"),
        ("existing_target_drift", "existing target bytes"),
        ("removed_import_drift", "changes imports beyond"),
        ("retirement_produced", "production producer"),
        ("retirement_parallel", "parallel CSS truth"),
        ("unlisted_importer", "import owners"),
        ("dynamic_importer", "dynamic CSS import"),
    ],
)
def test_css_ownership_relocation_final_shape_is_fail_closed(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    project, raw, changed, base_sha = _css_retirement_fixture(tmp_path, case)
    exception = documentation_impact._parse_exception(
        "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
    )
    with pytest.raises(DocumentationImpactError, match=message):
        _validate_exception(
            project,
            exception,
            changed,
            base_sha,
            changed=changed,
        )


def test_css_ownership_relocation_final_shape_rejects_grouped_selector(
    tmp_path: Path,
) -> None:
    _project, raw, _changed, _base_sha = _css_retirement_fixture(tmp_path)
    verification = cast(dict[str, object], raw["verification"])
    retirements = cast(list[dict[str, object]], verification["retirements"])
    selectors = cast(list[str], retirements[0]["selectors"])
    selectors[0] = ".selection-delivery-command, .parallel"
    with pytest.raises(
        DocumentationImpactError,
        match="exactly one top-level selector branch",
    ):
        documentation_impact._parse_exception(
            "docs/testing/documentation-impact-exceptions/issue-331.yaml", raw
        )


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
        "wrong_guard_source",
        "guard_content_change",
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


def test_static_import_parser_treats_numeric_division_as_code() -> None:
    imports = _static_imports(
        'import type { Shape } from "./contract";\n'
        "const ratio = 1 / (1 + 0.5);\n"
    )

    assert len(imports) == 1
    assert imports[0].module == "./contract"


def test_import_only_rewire_allows_optional_property_import_type_owner_change(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "apps/web/src"
    source_root.mkdir(parents=True)
    (source_root / "legacy.ts").write_text(
        "export interface Shape { id: string }\n"
        "export type Classification = 'internal';\n",
        encoding="utf-8",
    )
    (source_root / "owned.ts").write_text(
        "export interface Shape { id: string }\n"
        "export type Classification = 'internal';\n",
        encoding="utf-8",
    )
    view = source_root / "view.tsx"
    view.write_text(
        'import type { Shape } from "./legacy";\n'
        "interface Props {\n"
        '  classification?: import("./legacy").Classification;\n'
        "}\n"
        "export const View = ({ classification }: Props & Shape) => <div>{classification}</div>;\n",
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

    view.write_text(
        view.read_text(encoding="utf-8").replace('"./legacy"', '"./owned"'),
        encoding="utf-8",
    )

    assert _is_import_only_visual_change(tmp_path, base_sha, "apps/web/src/view.tsx")


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


def test_exact_exception_relocation_cannot_act_as_a_changed_waiver() -> None:
    source = "docs/archive/documentation-impact-exceptions/issue-257.yaml"
    current = "docs/testing/documentation-impact-exceptions/issue-257.yaml"
    ordinary = "docs/testing/review-prompts/code-review.md"

    exact = _parse_name_status_entries(
        f"R100\0{source}\0{current}\0".encode()
    )
    changed = _parse_name_status_entries(
        f"R099\0{source}\0{current}\0".encode()
    )
    ordinary_rename = _parse_name_status_entries(
        f"R100\0{source}\0{ordinary}\0".encode()
    )

    assert exact == {source: False, current: False}
    assert changed == {source: False, current: True}
    assert ordinary_rename == {source: False, ordinary: True}


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


def _retired_material_fixture(tmp_path: Path) -> tuple[Path, str, tuple[str, ...]]:
    paths = tuple(
        f"docs/17-evidence/images/issue-167-service-reference/material-{name}.png"
        for name in ("normal", "empty")
    )
    for index, path in enumerate(paths):
        _write_fixture_file(tmp_path, path, f"legacy-{index}\n")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Retirement Tests")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "legacy Materials references")
    base = _git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, base, paths


def _retired_entries(paths: tuple[str, ...]) -> dict[str, bool]:
    return {
        **{path: False for path in paths},
        "docs/product/service-reference-manifest.yaml": True,
        "docs/user-guide/screenshot-manifest.yaml": True,
        "docs/user-guide/materials.md": True,
    }


def test_retired_material_policy_accepts_only_the_complete_exact_delete_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, base, paths = _retired_material_fixture(tmp_path)
    digests = {
        path: hashlib.sha256(
            documentation_impact._git_blob_bytes(project, base, path)
        ).hexdigest()
        for path in paths
    }
    monkeypatch.setattr(
        documentation_impact, "_RETIRED_STATIC_MATERIALS_REFERENCE_SHA256", digests
    )
    for path in paths:
        (project / path).unlink()

    _validate_retired_materials_reference_changes(
        _retired_entries(paths), project=project, merge_base=base
    )


@pytest.mark.parametrize("case", ("partial", "hash", "adjacent", "coupling", "readd"))
def test_retired_material_policy_rejects_partial_hash_adjacent_coupling_or_readd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    project, base, paths = _retired_material_fixture(tmp_path)
    digests = {
        path: hashlib.sha256(
            documentation_impact._git_blob_bytes(project, base, path)
        ).hexdigest()
        for path in paths
    }
    monkeypatch.setattr(
        documentation_impact, "_RETIRED_STATIC_MATERIALS_REFERENCE_SHA256", digests
    )
    for path in paths:
        (project / path).unlink()
    entries = _retired_entries(paths)
    if case == "partial":
        entries.pop(paths[-1])
    elif case == "hash":
        digests[paths[0]] = "0" * 64
    elif case == "adjacent":
        entries[
            "docs/17-evidence/images/issue-167-service-reference/adjacent.png"
        ] = False
    elif case == "coupling":
        entries.pop("docs/user-guide/screenshot-manifest.yaml")
    else:
        _write_fixture_file(project, paths[0], "readded\n")

    with pytest.raises(DocumentationImpactError):
        _validate_retired_materials_reference_changes(
            entries, project=project, merge_base=base
        )

"""Reject user-visible changes that omit their current documentation evidence."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml

ImpactMode = Literal["staged", "range", "worktree"]

_GUIDE_PREFIX = "docs/user-guide/"
_SCREENSHOT_MANIFEST = "docs/user-guide/screenshot-manifest.yaml"
_NAVIGATION_CONTRACT = "docs/user-guide/navigation-contract.yaml"
_CURRENT_IMAGE_PREFIX = "docs/user-guide/images/current/"
_EXCEPTION_PREFIX = "docs/14-testing/documentation-impact-exceptions/"
_EXCEPTION_SCHEMA = "cmp.documentation-impact-exception.v1"
_NON_USER_VISIBLE_CLASSIFICATION = "non-user-visible-foundation"
_SHARED_DESIGN_PREFIX = "apps/web/src/design/"
_PRESERVED_FOUNDATION_FILES = {
    "apps/web/src/design/primitives.css",
    "apps/web/src/design/tokens.css",
    "apps/web/src/design/typography.css",
}
_OPENAPI_CONTRACTS = {
    "contracts/http/openapi.yaml",
    "contracts/http/openapi.baseline.yaml",
}


class DocumentationImpactError(RuntimeError):
    """Raised when changed files do not include required current documentation."""


@dataclass(frozen=True, slots=True)
class DocumentationImpactReport:
    changed_files: tuple[str, ...]
    visual_files: tuple[str, ...]
    exempted_visual_files: tuple[str, ...]
    exception_issue: str | None
    requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentationImpactException:
    path: str
    issue: str
    source_sha: str
    classification: str
    reason: str
    visual_files: tuple[str, ...]
    unconsumed_modules: tuple[str, ...]
    preserved_computed_value_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedDocumentationImpactException:
    exception: DocumentationImpactException
    derived_selectors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CssRule:
    context: tuple[str, ...]
    selector: str
    declarations: tuple[tuple[str, str], ...]


def _normalize(paths: Iterable[str]) -> set[str]:
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


def _git_lines(project: Path, arguments: list[str], *, allow_failure: bool = False) -> set[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=not allow_failure,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return _normalize(result.stdout.splitlines())


def _parse_name_status_entries(value: bytes) -> dict[str, bool]:
    tokens = [token for token in value.split(b"\0") if token]
    entries: dict[str, bool] = {}
    index = 0
    while index < len(tokens):
        status = tokens[index].decode("ascii", errors="strict")
        index += 1
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count > len(tokens):
            raise DocumentationImpactError("git name-status output is malformed")
        paths = [
            token.decode("utf-8", errors="strict").replace("\\", "/")
            for token in tokens[index : index + path_count]
        ]
        if path_count == 2:
            entries[paths[0]] = entries.get(paths[0], False)
            entries[paths[1]] = True
        else:
            entries[paths[0]] = entries.get(paths[0], False) or not status.startswith("D")
        index += path_count
    return entries


def _parse_name_status(value: bytes) -> set[str]:
    return set(_parse_name_status_entries(value))


def git_changed_entries(
    project: Path,
    arguments: list[str],
    *,
    allow_failure: bool = False,
) -> dict[str, bool]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            "-z",
            "--diff-filter=ACMRTD",
            *arguments,
        ],
        cwd=project,
        check=not allow_failure,
        capture_output=True,
    )
    if result.returncode != 0:
        return {}
    return _parse_name_status_entries(result.stdout)


def git_changed_paths(
    project: Path,
    arguments: list[str],
    *,
    allow_failure: bool = False,
) -> set[str]:
    return set(git_changed_entries(project, arguments, allow_failure=allow_failure))


def _merge_entries(target: dict[str, bool], source: Mapping[str, bool]) -> None:
    for path, can_supply_evidence in source.items():
        target[path] = target.get(path, False) or can_supply_evidence


def changed_entries(project: Path, mode: ImpactMode) -> dict[str, bool]:
    if mode == "staged":
        return git_changed_entries(project, ["--cached"])
    if mode == "range":
        return git_changed_entries(project, ["origin/main...HEAD"], allow_failure=True)
    changed: dict[str, bool] = {}
    _merge_entries(changed, git_changed_entries(project, []))
    _merge_entries(changed, git_changed_entries(project, ["--cached"]))
    _merge_entries(
        changed,
        {
            path: True
            for path in _git_lines(project, ["ls-files", "--others", "--exclude-standard"])
        },
    )
    _merge_entries(
        changed,
        git_changed_entries(project, ["origin/main...HEAD"], allow_failure=True),
    )
    return changed


def changed_files(project: Path, mode: ImpactMode) -> set[str]:
    return set(changed_entries(project, mode))


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    return (
        "tests" in pure.parts
        or "__tests__" in pure.parts
        or ".test." in name
        or ".spec." in name
        or ".stories." in name
        or path.startswith("apps/web/e2e/")
        or path.startswith("apps/web/.storybook/")
    )


def _is_visual_source(path: str) -> bool:
    return (
        path.startswith("apps/web/")
        and PurePosixPath(path).suffix.lower() in {".tsx", ".css"}
        and not _is_test_path(path)
    )


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise DocumentationImpactError(f"{field} entries must be non-empty strings")
        normalized = item.strip().replace("\\", "/")
        if any(character in normalized for character in "*?[]{}"):
            raise DocumentationImpactError(f"{field} does not allow wildcard paths")
        items.append(normalized)
    if len(set(items)) != len(items):
        raise DocumentationImpactError(f"{field} contains duplicate entries")
    return tuple(sorted(items))


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DocumentationImpactError(f"{field} must be a mapping")
    return value


def _parse_exception(path: str, raw: object) -> DocumentationImpactException:
    data = _mapping(raw, path)
    expected_keys = {
        "schemaVersion",
        "issue",
        "sourceSha",
        "classification",
        "reason",
        "visualFiles",
        "verification",
    }
    if set(data) != expected_keys:
        raise DocumentationImpactError(
            f"{path} keys must be exactly {', '.join(sorted(expected_keys))}"
        )
    if data["schemaVersion"] != _EXCEPTION_SCHEMA:
        raise DocumentationImpactError(f"{path} has an unsupported schemaVersion")
    issue = data["issue"]
    if not isinstance(issue, str) or not re.fullmatch(r"#[1-9][0-9]*", issue):
        raise DocumentationImpactError(f"{path} issue must be a GitHub issue reference")
    expected_paths = {
        f"{_EXCEPTION_PREFIX}issue-{issue[1:]}.yaml",
        f"{_EXCEPTION_PREFIX}issue-{issue[1:]}.yml",
    }
    if path not in expected_paths:
        raise DocumentationImpactError(f"{path} filename must match issue {issue}")
    source_sha = data["sourceSha"]
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise DocumentationImpactError(f"{path} sourceSha must be a lowercase 40-character SHA")
    if data["classification"] != _NON_USER_VISIBLE_CLASSIFICATION:
        raise DocumentationImpactError(f"{path} classification is not allowed")
    reason = data["reason"]
    if not isinstance(reason, str) or len(reason.strip()) < 20:
        raise DocumentationImpactError(f"{path} reason must explain the non-user-visible boundary")

    verification = _mapping(data["verification"], f"{path} verification")
    verification_keys = {
        "unconsumedModules",
        "preservedComputedValueFiles",
    }
    if set(verification) != verification_keys:
        raise DocumentationImpactError(
            f"{path} verification keys must be exactly "
            f"{', '.join(sorted(verification_keys))}"
        )
    return DocumentationImpactException(
        path=path,
        issue=issue,
        source_sha=source_sha,
        classification=data["classification"],
        reason=reason.strip(),
        visual_files=_string_list(data["visualFiles"], f"{path} visualFiles"),
        unconsumed_modules=_string_list(
            verification["unconsumedModules"],
            f"{path} verification.unconsumedModules",
        ),
        preserved_computed_value_files=_string_list(
            verification["preservedComputedValueFiles"],
            f"{path} verification.preservedComputedValueFiles",
        ),
    )


def _load_changed_exception(
    project: Path,
    evidence: set[str],
) -> DocumentationImpactException | None:
    candidates = sorted(
        path
        for path in evidence
        if path.startswith(_EXCEPTION_PREFIX) and path.endswith((".yaml", ".yml"))
    )
    if not candidates:
        return None
    if len(candidates) != 1:
        raise DocumentationImpactError("exactly one documentation-impact exception may change")
    path = candidates[0]
    try:
        raw = yaml.safe_load((project / path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DocumentationImpactError(f"cannot read {path}: {error}") from error
    return _parse_exception(path, raw)


def _production_source_paths(project: Path) -> Iterable[Path]:
    source = project / "apps/web/src"
    if not source.exists():
        return ()
    return (
        path
        for path in source.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".css", ".ts", ".tsx"}
        and not _is_test_path(path.relative_to(project).as_posix())
    )


def _normalize_css(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _closing_brace(text: str, opening: int, source: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    raise DocumentationImpactError(f"cannot parse unmatched CSS block in {source}")


def _css_declarations(body: str, source: str, selector: str) -> tuple[tuple[str, str], ...]:
    declarations: list[tuple[str, str]] = []
    for raw_declaration in body.split(";"):
        declaration = raw_declaration.strip()
        if not declaration:
            continue
        if ":" not in declaration:
            raise DocumentationImpactError(
                f"cannot prove CSS declaration {declaration!r} in {source} ({selector})"
            )
        property_name, value = declaration.split(":", 1)
        normalized_property = property_name.strip()
        normalized_value = _normalize_css(value)
        if not normalized_property or not normalized_value:
            raise DocumentationImpactError(
                f"cannot prove empty CSS declaration in {source} ({selector})"
            )
        declarations.append((normalized_property, normalized_value))
    if len({name for name, _value in declarations}) != len(declarations):
        raise DocumentationImpactError(
            f"cannot prove duplicate CSS declarations in {source} ({selector})"
        )
    return tuple(declarations)


def _css_rules(
    text: str,
    source: str,
    context: tuple[str, ...] = (),
) -> tuple[_CssRule, ...]:
    without_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    rules: list[_CssRule] = []
    cursor = 0
    while True:
        opening = without_comments.find("{", cursor)
        if opening < 0:
            if without_comments[cursor:].strip().strip(";"):
                raise DocumentationImpactError(f"cannot parse trailing CSS in {source}")
            break
        header = without_comments[cursor:opening].strip()
        if ";" in header:
            header = header.rsplit(";", 1)[1].strip()
        if not header:
            raise DocumentationImpactError(f"cannot parse empty CSS selector in {source}")
        closing = _closing_brace(without_comments, opening, source)
        body = without_comments[opening + 1 : closing]
        normalized_header = _normalize_css(header)
        if normalized_header.startswith(("@media ", "@supports ", "@container ", "@layer ")):
            rules.extend(
                _css_rules(body, source, (*context, normalized_header))
            )
        elif normalized_header.startswith("@"):
            raise DocumentationImpactError(
                f"cannot prove CSS at-rule {normalized_header!r} in {source}"
            )
        else:
            rules.append(
                _CssRule(
                    context=context,
                    selector=normalized_header,
                    declarations=_css_declarations(body, source, normalized_header),
                )
            )
        cursor = closing + 1
    return tuple(rules)


def _css_rule_map(
    rules: tuple[_CssRule, ...],
    source: str,
) -> dict[tuple[tuple[str, ...], str], _CssRule]:
    mapped: dict[tuple[tuple[str, ...], str], _CssRule] = {}
    for rule in rules:
        key = (rule.context, rule.selector)
        if key in mapped:
            raise DocumentationImpactError(
                f"cannot prove repeated CSS selector {rule.selector!r} in {source}"
            )
        mapped[key] = rule
    return mapped


def _base_file_text(project: Path, source_sha: str, path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "show", f"{source_sha}:{path}"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError(
            f"cannot read {path} at exception sourceSha {source_sha}"
        ) from error
    return result.stdout


def _class_selectors(selector: str) -> set[str]:
    return set(re.findall(r"\.(-?[_a-zA-Z][_a-zA-Z0-9-]*)", selector))


def _required_positive_classes(selector: str, source: str) -> set[str]:
    without_attributes = re.sub(r"\[[^\]]*\]", "", selector)
    if "[" in without_attributes or "]" in without_attributes or ":" in without_attributes:
        raise DocumentationImpactError(
            f"cannot prove new CSS selector {selector!r} in {source} requires "
            "a positive isolated class"
        )
    return _class_selectors(without_attributes)


def _prove_preserved_css(
    project: Path,
    exception: DocumentationImpactException,
    *,
    base_files: Mapping[str, str] | None = None,
) -> tuple[set[str], set[str]]:
    rule_map = dict[tuple[tuple[str, ...], str], _CssRule]
    parsed: dict[str, tuple[rule_map, rule_map]] = {}
    all_base_classes: set[str] = set()
    new_variables: dict[str, str] = {}
    replacements: list[tuple[str, str, str, str]] = []

    for path in exception.preserved_computed_value_files:
        current_path = project / path
        try:
            current_text = current_path.read_text(encoding="utf-8")
        except OSError as error:
            raise DocumentationImpactError(f"cannot read changed CSS {path}: {error}") from error
        if base_files is None:
            base_text = _base_file_text(project, exception.source_sha, path)
        else:
            try:
                base_text = base_files[path]
            except KeyError as error:
                raise DocumentationImpactError(
                    f"test base content is missing for {path}"
                ) from error
        base_rules = _css_rule_map(_css_rules(base_text, path), path)
        current_rules = _css_rule_map(_css_rules(current_text, path), path)
        parsed[path] = (base_rules, current_rules)
        all_base_classes.update(
            class_name
            for rule in base_rules.values()
            for class_name in _class_selectors(rule.selector)
        )

        missing_rules = set(base_rules) - set(current_rules)
        if missing_rules:
            raise DocumentationImpactError(
                f"{exception.path} cannot prove unchanged appearance: {path} removes CSS rules"
            )
        for key, base_rule in base_rules.items():
            current_rule = current_rules[key]
            base_declarations = dict(base_rule.declarations)
            current_declarations = dict(current_rule.declarations)
            missing_declarations = set(base_declarations) - set(current_declarations)
            if missing_declarations:
                raise DocumentationImpactError(
                    f"{exception.path} cannot prove unchanged appearance: {path} removes "
                    f"declarations from {base_rule.selector}"
                )
            for property_name, current_value in current_declarations.items():
                if property_name not in base_declarations:
                    if (
                        not base_rule.context
                        and base_rule.selector == ":root"
                        and property_name.startswith("--")
                    ):
                        if property_name in new_variables:
                            raise DocumentationImpactError(
                                f"{exception.path} defines new CSS variable "
                                f"{property_name} more than once"
                            )
                        new_variables[property_name] = current_value
                        continue
                    raise DocumentationImpactError(
                        f"{exception.path} cannot prove unchanged appearance: {path} adds "
                        f"a declaration to existing selector {base_rule.selector}"
                    )
                base_value = base_declarations[property_name]
                if current_value != base_value:
                    replacements.append(
                        (path, f"{base_rule.selector} {property_name}", base_value, current_value)
                    )

    variable_reference = re.compile(r"var\((--[-_a-zA-Z0-9]+)\)")
    for path, declaration, base_value, current_value in replacements:
        match = variable_reference.fullmatch(current_value)
        if match is None or new_variables.get(match.group(1)) != base_value:
            raise DocumentationImpactError(
                f"{exception.path} cannot prove unchanged appearance: {path} changes "
                f"{declaration} from {base_value!r} to {current_value!r}"
            )

    derived_selectors: set[str] = set()
    for path, (base_rules, current_rules) in parsed.items():
        for key in set(current_rules) - set(base_rules):
            selector = current_rules[key].selector
            branches = [branch.strip() for branch in selector.split(",")]
            for branch in branches:
                novel_classes = (
                    _required_positive_classes(branch, path) - all_base_classes
                )
                if not novel_classes:
                    raise DocumentationImpactError(
                        f"{exception.path} cannot prove new CSS selector {branch!r} in {path} "
                        "is isolated from existing product markup"
                    )
                derived_selectors.update(novel_classes)
    if not derived_selectors:
        raise DocumentationImpactError(
            f"{exception.path} must add an automatically derivable isolated CSS selector"
        )
    return derived_selectors, set(new_variables)


def _validate_exception(
    project: Path,
    exception: DocumentationImpactException,
    visual_files: set[str],
    merge_base: str,
    *,
    base_files: Mapping[str, str] | None = None,
) -> _ValidatedDocumentationImpactException:
    if exception.source_sha != merge_base:
        raise DocumentationImpactError(
            f"{exception.path} sourceSha {exception.source_sha} does not match "
            f"origin/main merge-base {merge_base}"
        )
    if set(exception.visual_files) != visual_files:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must exactly match the changed visual sources"
        )
    if not visual_files:
        raise DocumentationImpactError(
            f"{exception.path} is stale because no visual source changed"
        )
    if any(not path.startswith(_SHARED_DESIGN_PREFIX) for path in visual_files):
        raise DocumentationImpactError(
            f"{exception.path} can cover only files under {_SHARED_DESIGN_PREFIX}"
        )
    covered = set(exception.unconsumed_modules) | set(
        exception.preserved_computed_value_files
    )
    if covered != visual_files:
        raise DocumentationImpactError(
            f"{exception.path} verification files must exactly cover visualFiles"
        )
    if any(path not in visual_files for path in exception.unconsumed_modules):
        raise DocumentationImpactError(
            f"{exception.path} unconsumedModules must be changed visual sources"
        )
    if any(
        PurePosixPath(path).suffix.lower() not in {".ts", ".tsx"}
        for path in exception.unconsumed_modules
    ):
        raise DocumentationImpactError(
            f"{exception.path} unconsumedModules allows only TypeScript modules"
        )
    if not set(exception.preserved_computed_value_files).issubset(
        _PRESERVED_FOUNDATION_FILES
    ):
        raise DocumentationImpactError(
            f"{exception.path} preservedComputedValueFiles can include only shared "
            "tokens, typography, and primitives"
        )

    derived_selectors, new_variables = _prove_preserved_css(
        project,
        exception,
        base_files=base_files,
    )
    ignored_sources = set(exception.unconsumed_modules) | set(
        exception.preserved_computed_value_files
    )
    for source_path in _production_source_paths(project):
        relative = source_path.relative_to(project).as_posix()
        if relative in ignored_sources:
            continue
        text = source_path.read_text(encoding="utf-8")
        for module in exception.unconsumed_modules:
            module_name = PurePosixPath(module).stem
            if module_name in text:
                raise DocumentationImpactError(
                    f"{exception.path} module {module} is referenced by product source {relative}"
                )
        for selector in derived_selectors:
            if re.search(rf"(?<![-_a-zA-Z0-9]){re.escape(selector)}(?![-_a-zA-Z0-9])", text):
                raise DocumentationImpactError(
                    f"{exception.path} selector {selector} is used by product source {relative}"
                )
        for variable in new_variables:
            if variable in text:
                raise DocumentationImpactError(
                    f"{exception.path} CSS variable {variable} is used by product source {relative}"
                )
    return _ValidatedDocumentationImpactException(
        exception=exception,
        derived_selectors=tuple(sorted(derived_selectors)),
    )


def _merge_base(project: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "merge-base", "origin/main", "HEAD"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError("cannot resolve origin/main merge-base") from error
    merge_base = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", merge_base):
        raise DocumentationImpactError("origin/main merge-base is not a full Git SHA")
    return merge_base


def evaluate_documentation_impact(
    paths: Iterable[str] | Mapping[str, bool],
    *,
    exception: _ValidatedDocumentationImpactException | None = None,
) -> DocumentationImpactReport:
    if exception is not None and not isinstance(
        exception, _ValidatedDocumentationImpactException
    ):
        raise DocumentationImpactError(
            "documentation-impact exceptions must pass repository validation"
        )
    if isinstance(paths, Mapping):
        normalized_entries = {
            path.strip().replace("\\", "/"): can_supply_evidence
            for path, can_supply_evidence in paths.items()
            if path.strip()
        }
        changed = set(normalized_entries)
        evidence = {path for path, allowed in normalized_entries.items() if allowed}
    else:
        changed = _normalize(paths)
        evidence = changed
    visual = sorted(path for path in changed if _is_visual_source(path))
    exempted_visual = set(exception.exception.visual_files) if exception else set()
    if exempted_visual - set(visual):
        raise DocumentationImpactError(
            "documentation-impact exception lists a path that is not a changed visual source"
        )
    visual_requiring_documentation = sorted(set(visual) - exempted_visual)
    guide_changed = any(
        path.startswith(_GUIDE_PREFIX) and path.endswith(".md") for path in evidence
    )
    manifest_changed = _SCREENSHOT_MANIFEST in evidence
    png_changed = any(
        path.startswith(_CURRENT_IMAGE_PREFIX) and path.lower().endswith(".png")
        for path in evidence
    )
    requirements: list[str] = []

    if visual_requiring_documentation:
        if not guide_changed:
            requirements.append("update a current docs/user-guide/*.md workflow")
        if not manifest_changed:
            requirements.append("update docs/user-guide/screenshot-manifest.yaml")
        if not png_changed:
            requirements.append("add or update a current user-guide PNG")

    app_changed = "apps/web/src/app.tsx" in changed
    if app_changed and _NAVIGATION_CONTRACT not in evidence:
        requirements.append("update docs/user-guide/navigation-contract.yaml for app.tsx")

    workflow_contract_changed = bool(changed & _OPENAPI_CONTRACTS)
    if workflow_contract_changed and not guide_changed:
        requirements.append("update a current user guide for the OpenAPI workflow change")

    if requirements:
        visual_note = f"; visual sources: {', '.join(visual)}" if visual else ""
        raise DocumentationImpactError("; ".join(requirements) + visual_note)

    return DocumentationImpactReport(
        changed_files=tuple(sorted(changed)),
        visual_files=tuple(visual),
        exempted_visual_files=tuple(sorted(exempted_visual)),
        exception_issue=exception.exception.issue if exception else None,
        requirements=(),
    )


def verify_documentation_impact(root: Path, mode: ImpactMode) -> DocumentationImpactReport:
    project = root.resolve()
    entries = changed_entries(project, mode)
    evidence = {path for path, can_supply_evidence in entries.items() if can_supply_evidence}
    exception = _load_changed_exception(project, evidence)
    validated_exception = None
    if exception is not None:
        visual_files = {path for path in entries if _is_visual_source(path)}
        validated_exception = _validate_exception(
            project,
            exception,
            visual_files,
            _merge_base(project),
        )
    return evaluate_documentation_impact(entries, exception=validated_exception)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("staged", "range", "worktree"), default="staged")
    args = parser.parse_args()
    try:
        report = verify_documentation_impact(args.root, args.mode)
    except (OSError, subprocess.CalledProcessError, DocumentationImpactError) as error:
        parser.exit(1, f"documentation impact check failed: {error}\n")
    exception_note = (
        f", {len(report.exempted_visual_files)} documented N/A by {report.exception_issue}"
        if report.exception_issue
        else ""
    )
    print(
        "documentation impact check passed: "
        f"{len(report.changed_files)} changed files, {len(report.visual_files)} visual sources"
        f"{exception_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

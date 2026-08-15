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
_NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION = "non-user-visible-structural-extraction"
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
    import_only_files: tuple[str, ...] = ()
    relocations: tuple[_Relocation, ...] = ()


@dataclass(frozen=True, slots=True)
class _Relocation:
    source: str
    target: str
    declarations: tuple[str, ...]


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


_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def _canonical_repo_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocumentationImpactError(f"{field} must be a non-empty canonical path")
    if value != value.strip():
        raise DocumentationImpactError(f"{field} must be a canonical path")
    if "\\" in value or any(character in value for character in "*?[]{}"):
        raise DocumentationImpactError(f"{field} must use canonical POSIX paths")
    if value.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", value):
        raise DocumentationImpactError(f"{field} must be repository-relative")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DocumentationImpactError(f"{field} contains ambiguous path segments")
    normalized = PurePosixPath(value).as_posix()
    if normalized != value:
        raise DocumentationImpactError(f"{field} must be canonical")
    if not value.startswith("apps/web/src/"):
        raise DocumentationImpactError(f"{field} must be under apps/web/src")
    return value


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


def _path_list(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise DocumentationImpactError(
            f"{field} must be {'an empty or non-empty' if allow_empty else 'a non-empty'} list"
        )
    items = tuple(_canonical_repo_path(item, f"{field} entry") for item in value)
    if len(set(items)) != len(items):
        raise DocumentationImpactError(f"{field} contains duplicate entries")
    return tuple(sorted(items))


class _UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate keys at every mapping depth."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise DocumentationImpactError("documentation-impact YAML keys must be strings")
        if key in mapping:
            raise DocumentationImpactError(f"duplicate YAML key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


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
    classification = data["classification"]
    if classification not in {
        _NON_USER_VISIBLE_CLASSIFICATION,
        _NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION,
    }:
        raise DocumentationImpactError(f"{path} classification is not allowed")
    reason = data["reason"]
    if not isinstance(reason, str) or len(reason.strip()) < 20:
        raise DocumentationImpactError(f"{path} reason must explain the non-user-visible boundary")

    verification = _mapping(data["verification"], f"{path} verification")
    parsed_relocations: list[_Relocation] = []
    if classification == _NON_USER_VISIBLE_CLASSIFICATION:
        verification_keys = {
            "unconsumedModules",
            "preservedComputedValueFiles",
        }
        if set(verification) != verification_keys:
            raise DocumentationImpactError(
                f"{path} verification keys must be exactly {', '.join(sorted(verification_keys))}"
            )
        unconsumed_modules = _string_list(
            verification["unconsumedModules"],
            f"{path} verification.unconsumedModules",
        )
        preserved_computed_value_files = _string_list(
            verification["preservedComputedValueFiles"],
            f"{path} verification.preservedComputedValueFiles",
        )
        import_only_files: tuple[str, ...] = ()
    else:
        verification_keys = {"importOnlyFiles", "relocations"}
        if set(verification) != verification_keys:
            raise DocumentationImpactError(
                f"{path} verification keys must be exactly {', '.join(sorted(verification_keys))}"
            )
        import_only_files = _path_list(
            verification["importOnlyFiles"],
            f"{path} verification.importOnlyFiles",
            allow_empty=True,
        )
        raw_relocations = verification["relocations"]
        if not isinstance(raw_relocations, list) or not raw_relocations:
            raise DocumentationImpactError(
                f"{path} verification.relocations must be a non-empty list"
            )
        parsed_relocations: list[_Relocation] = []
        for index, raw_relocation in enumerate(raw_relocations):
            relocation = _mapping(raw_relocation, f"{path} verification.relocations[{index}]")
            if set(relocation) != {"source", "target", "declarations"}:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] keys must be exactly "
                    "declarations, source, target"
                )
            source = _canonical_repo_path(
                relocation["source"],
                f"{path} verification.relocations[{index}].source",
            )
            target = _canonical_repo_path(
                relocation["target"],
                f"{path} verification.relocations[{index}].target",
            )
            if source == target:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] source and target must differ"
                )
            declarations = relocation["declarations"]
            if not isinstance(declarations, list) or not declarations:
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}].declarations must be non-empty"
                )
            names: list[str] = []
            for name in declarations:
                if not isinstance(name, str) or _IDENTIFIER_RE.fullmatch(name) is None:
                    raise DocumentationImpactError(
                        f"{path} verification.relocations[{index}] has an invalid declaration name"
                    )
                names.append(name)
            if len(set(names)) != len(names):
                raise DocumentationImpactError(
                    f"{path} verification.relocations[{index}] has duplicate declarations"
                )
            parsed_relocations.append(
                _Relocation(source=source, target=target, declarations=tuple(names))
            )
        sources = [item.source for item in parsed_relocations]
        targets = [item.target for item in parsed_relocations]
        names = [name for item in parsed_relocations for name in item.declarations]
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            raise DocumentationImpactError(
                f"{path} verification.relocations contains duplicate source or target"
            )
        if len(set(names)) != len(names):
            raise DocumentationImpactError(
                f"{path} verification.relocations contains duplicate declaration names"
            )
        if set(sources) & set(import_only_files) or set(targets) & set(import_only_files):
            raise DocumentationImpactError(f"{path} verification paths overlap")
        unconsumed_modules = ()
        preserved_computed_value_files = ()
    return DocumentationImpactException(
        path=path,
        issue=issue,
        source_sha=source_sha,
        classification=classification,
        reason=reason.strip(),
        visual_files=_string_list(data["visualFiles"], f"{path} visualFiles"),
        unconsumed_modules=unconsumed_modules,
        preserved_computed_value_files=preserved_computed_value_files,
        import_only_files=import_only_files,
        relocations=tuple(parsed_relocations),
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
        raw = yaml.load((project / path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError, DocumentationImpactError) as error:
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
            rules.extend(_css_rules(body, source, (*context, normalized_header)))
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
        )
        return result.stdout.decode("utf-8", errors="strict")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        raise DocumentationImpactError(
            f"cannot read {path} at exception sourceSha {source_sha}"
        ) from error


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
                novel_classes = _required_positive_classes(branch, path) - all_base_classes
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


@dataclass(frozen=True, slots=True)
class _TsToken:
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Declaration:
    name: str
    kind: Literal["type", "value"]
    start: int
    end: int
    export: bool
    defining_start: int
    defining_end: int


@dataclass(frozen=True, slots=True)
class _ImportBinding:
    imported: str
    local: str
    kind: Literal["type", "value"]
    raw: str


@dataclass(frozen=True, slots=True)
class _StaticImport:
    start: int
    end: int
    text: str
    module: str
    module_quote: str
    module_start: int
    module_end: int
    bindings: tuple[_ImportBinding, ...]
    form: str
    type_only: bool
    has_default_or_namespace: bool
    side_effect: bool


def _line_start(text: str, offset: int) -> int:
    return text.rfind("\n", 0, offset) + 1


def _scan_ts(text: str, *, include_template_expressions: bool = False) -> tuple[_TsToken, ...]:
    """Scan enough TypeScript lexical structure to fail closed on ambiguous source."""
    tokens: list[_TsToken] = []
    i = 0
    previous: _TsToken | None = None

    def add(kind: str, start: int, end: int) -> None:
        nonlocal previous
        token = _TsToken(kind=kind, text=text[start:end], start=start, end=end)
        tokens.append(token)
        previous = token

    def regex_allowed() -> bool:
        if previous is None:
            return True
        if previous.kind == "identifier" and previous.text not in {
            "return",
            "throw",
            "case",
            "delete",
            "void",
            "typeof",
            "instanceof",
            "in",
            "of",
            "yield",
            "await",
        }:
            return False
        return previous.text not in {
            ")",
            "]",
            "}",
            "<",
            "++",
            "--",
        }

    def skip_string(start: int, quote: str) -> int:
        index = start + 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == quote:
                return index + 1
            if char in "\r\n":
                raise DocumentationImpactError("unterminated string literal")
            index += 1
        raise DocumentationImpactError("unterminated string literal")

    def skip_regex(start: int) -> int:
        index = start + 1
        in_class = False
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                index += 1
                while index < len(text) and (text[index].isalpha() or text[index].isdigit()):
                    index += 1
                return index
            elif char in "\r\n":
                raise DocumentationImpactError("unterminated regular expression literal")
            index += 1
        raise DocumentationImpactError("unterminated regular expression literal")

    def skip_template(start: int) -> int:
        index = start + 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "`":
                return index + 1
            if (
                char == "$"
                and index + 1 < len(text)
                and text[index + 1] == "{"
                and include_template_expressions
            ):
                # Scan the expression in place, retaining its identifier tokens.  A
                # nested scanner is intentionally conservative and requires balanced
                # braces before returning to the template text.
                depth = 1
                index += 2
                expression_start = index
                quote: str | None = None
                escaped = False
                while index < len(text) and depth:
                    current = text[index]
                    if quote is not None:
                        if escaped:
                            escaped = False
                        elif current == "\\":
                            escaped = True
                        elif current == quote:
                            quote = None
                        index += 1
                        continue
                    if current in {"'", '"'}:
                        quote = current
                    elif current == "`":
                        # Nested templates are accepted only when they close.
                        nested_end = skip_template(index)
                        index = nested_end
                        continue
                    elif current == "{":
                        depth += 1
                    elif current == "}":
                        depth -= 1
                    index += 1
                if depth:
                    raise DocumentationImpactError("unterminated template expression")
                nested = _scan_ts(
                    text[expression_start : index - 1],
                    include_template_expressions=True,
                )
                for token in nested:
                    tokens.append(
                        _TsToken(
                            token.kind,
                            token.text,
                            token.start + expression_start,
                            token.end + expression_start,
                        )
                    )
                index += 0
                continue
            index += 1
        raise DocumentationImpactError("unterminated template literal")

    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i + 2)
            i = len(text) if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise DocumentationImpactError("unterminated block comment")
            i = end + 2
            continue
        if (
            char == "'"
            and previous is not None
            and previous.kind == "identifier"
            and previous.end == i
        ):
            add("punctuation", i, i + 1)
            i += 1
            continue
        if char in {'"', "'"}:
            end = skip_string(i, char)
            add("literal", i, end)
            i = end
            continue
        if char == "`":
            end = skip_template(i)
            add("template", i, end)
            i = end
            continue
        if char == "/" and regex_allowed() and not text.startswith("/=", i):
            end = skip_regex(i)
            add("regex", i, end)
            i = end
            continue
        match = _IDENTIFIER_RE.match(text, i)
        if match:
            add("identifier", i, match.end())
            i = match.end()
            continue
        # Keep multi-character operators together only where this affects parsing.
        operator = next(
            (
                candidate
                for candidate in (
                    "=>",
                    "===",
                    "!==",
                    "==",
                    "!=",
                    "<=",
                    ">=",
                    "&&",
                    "||",
                    "??",
                    "++",
                    "--",
                    "?.",
                    "...",
                    "**",
                )
                if text.startswith(candidate, i)
            ),
            char,
        )
        add("punctuation", i, i + len(operator))
        i += len(operator)
    return tuple(sorted(tokens, key=lambda token: (token.start, token.end)))


def _matching_token(tokens: tuple[_TsToken, ...], index: int, opening: str, closing: str) -> int:
    depth = 0
    for cursor in range(index, len(tokens)):
        token = tokens[cursor].text
        if token == opening:
            depth += 1
        elif token == closing:
            depth -= 1
            if depth == 0:
                return cursor
    raise DocumentationImpactError("unbalanced TypeScript declaration")


def _validate_function_return_annotation(
    tokens: tuple[_TsToken, ...], start: int, end: int
) -> None:
    if start >= end or tokens[start].text != ":":
        return
    parts = tokens[start + 1 : end]
    if not parts or not any(token.kind == "identifier" for token in parts):
        raise DocumentationImpactError("function return annotation must contain an identifier")
    angle = square = 0
    for token in parts:
        if token.kind in {"literal", "template", "regex"}:
            raise DocumentationImpactError("function return annotation contains a literal")
        if token.text in {"{", "}", "(", ")", "=", "=>", ";"}:
            raise DocumentationImpactError("unsupported function return annotation")
        if token.text == "<":
            angle += 1
        elif token.text == ">":
            angle -= 1
            if angle < 0:
                raise DocumentationImpactError("unbalanced function return annotation")
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
            if square < 0:
                raise DocumentationImpactError("unbalanced function return annotation")
        elif token.kind == "punctuation" and token.text not in {
            ".",
            ",",
            "|",
            "&",
            "?",
            "<",
            ">",
            "[",
            "]",
        }:
            raise DocumentationImpactError("unsupported function return annotation")
    if angle or square:
        raise DocumentationImpactError("unbalanced function return annotation")


def _find_declarations(
    text: str,
    *,
    required_names: set[str] | None = None,
) -> tuple[_Declaration, ...]:
    tokens = _scan_ts(text)
    declarations: list[_Declaration] = []
    found_names: set[str] = set()

    def record(declaration: _Declaration) -> bool:
        declarations.append(declaration)
        found_names.add(declaration.name)
        return bool(required_names) and required_names <= found_names

    brace = paren = square = 0
    cursor = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if token.text == "{":
            brace += 1
            cursor += 1
            continue
        if token.text == "}":
            brace -= 1
            if brace < 0:
                raise DocumentationImpactError("unbalanced TypeScript braces")
            cursor += 1
            continue
        if token.text == "(":
            paren += 1
            cursor += 1
            continue
        if token.text == ")":
            paren -= 1
            if paren < 0:
                raise DocumentationImpactError("unbalanced TypeScript parentheses")
            cursor += 1
            continue
        if token.text == "[":
            square += 1
            cursor += 1
            continue
        if token.text == "]":
            square -= 1
            if square < 0:
                raise DocumentationImpactError("unbalanced TypeScript brackets")
            cursor += 1
            continue
        if brace or paren or square:
            cursor += 1
            continue
        export = token.text == "export"
        keyword_index = cursor + 1 if export else cursor
        if keyword_index >= len(tokens) or _line_start(text, token.start) != token.start:
            cursor += 1
            continue
        keyword = tokens[keyword_index].text
        if keyword not in {"type", "const", "function"}:
            cursor += 1
            continue
        keyword_token = tokens[keyword_index]
        if export and keyword_token.start != token.end + 1:
            raise DocumentationImpactError("export declaration must use a single ASCII space")
        if keyword_index + 1 >= len(tokens):
            raise DocumentationImpactError("declaration is missing its name")
        name_token = tokens[keyword_index + 1]
        if name_token.kind != "identifier":
            raise DocumentationImpactError("declaration name must be an identifier")
        name = name_token.text
        if keyword == "type":
            if keyword_index + 2 >= len(tokens) or tokens[keyword_index + 2].text != "=":
                raise DocumentationImpactError("only simple type declarations are supported")
            depth = 0
            end_index: int | None = None
            for probe in range(keyword_index + 3, len(tokens)):
                value = tokens[probe].text
                if value in {"{", "(", "[", "<"}:
                    depth += 1
                elif value in {"}", ")", "]", ">"}:
                    depth -= 1
                    if depth < 0:
                        raise DocumentationImpactError("unbalanced type declaration")
                elif value == ";" and depth == 0:
                    end_index = probe
                    break
            if end_index is None:
                raise DocumentationImpactError("type declaration requires a semicolon")
            if record(
                _Declaration(
                    name=name,
                    kind="type",
                    start=token.start,
                    end=tokens[end_index].end,
                    export=export,
                    defining_start=name_token.start,
                    defining_end=name_token.end,
                )
            ):
                return tuple(declarations)
            cursor = end_index + 1
            continue
        if keyword == "const":
            equal_index: int | None = None
            for probe in range(keyword_index + 2, len(tokens)):
                if tokens[probe].text == "=":
                    equal_index = probe
                    break
                if tokens[probe].text in {";", "const", "function", "type"}:
                    break
            if equal_index is None:
                raise DocumentationImpactError("const declaration requires an initializer")
            if equal_index == keyword_index + 2 and tokens[equal_index - 1].text != name:
                raise DocumentationImpactError("const declaration name is invalid")
            depth = 0
            end_index = None
            for probe in range(equal_index + 1, len(tokens)):
                value = tokens[probe].text
                if value in {"{", "(", "[", "<"}:
                    depth += 1
                elif value in {"}", ")", "]", ">"}:
                    depth -= 1
                    if depth < 0:
                        raise DocumentationImpactError("unbalanced const declaration")
                elif value == ";" and depth == 0:
                    end_index = probe
                    break
            if end_index is None:
                raise DocumentationImpactError("const declaration requires a semicolon")
            if record(
                _Declaration(
                    name=name,
                    kind="value",
                    start=token.start,
                    end=tokens[end_index].end,
                    export=export,
                    defining_start=name_token.start,
                    defining_end=name_token.end,
                )
            ):
                return tuple(declarations)
            cursor = end_index + 1
            continue
        # function
        open_index = keyword_index + 2
        if open_index >= len(tokens) or tokens[open_index].text != "(":
            raise DocumentationImpactError("only non-generic function declarations are supported")
        close_index = _matching_token(tokens, open_index, "(", ")")
        body_index = close_index + 1
        if body_index < len(tokens) and tokens[body_index].text == ":":
            body_index += 1
            while body_index < len(tokens) and tokens[body_index].text != "{":
                body_index += 1
        _validate_function_return_annotation(tokens, close_index + 1, body_index)
        if body_index >= len(tokens) or tokens[body_index].text != "{":
            raise DocumentationImpactError("function declaration requires a body")
        body_end = _matching_token(tokens, body_index, "{", "}")
        if record(
            _Declaration(
                name=name,
                kind="value",
                start=token.start,
                end=tokens[body_end].end,
                export=export,
                defining_start=name_token.start,
                defining_end=name_token.end,
            )
        ):
            return tuple(declarations)
        cursor = body_end + 1
    if brace or paren or square:
        raise DocumentationImpactError("unbalanced TypeScript source")
    return tuple(declarations)


def _static_imports(text: str) -> tuple[_StaticImport, ...]:
    """Parse top-level static import statements, retaining exact source spans."""
    tokens = _scan_ts(text)
    imports: list[_StaticImport] = []
    i = 0
    brace = paren = square = 0
    while i < len(tokens):
        token = tokens[i]
        if token.text == "{":
            brace += 1
        elif token.text == "}":
            brace -= 1
        elif token.text == "(":
            paren += 1
        elif token.text == ")":
            paren -= 1
        elif token.text == "[":
            square += 1
        elif token.text == "]":
            square -= 1
        if brace or paren or square or token.text != "import":
            i += 1
            continue
        # Dynamic import(...) is residual code, never a static import.
        if i + 1 < len(tokens) and tokens[i + 1].text == "(":
            i += 1
            continue
        statement_end = None
        import_brace = import_paren = import_square = 0
        for probe in range(i + 1, len(tokens)):
            probe_token = tokens[probe]
            if probe_token.text == ";":
                statement_end = probe
                break
            if (
                not (import_brace or import_paren or import_square)
                and "\n" in text[tokens[probe - 1].end : probe_token.start]
                and probe_token.text not in {"from", "as", "type"}
            ):
                # Bare import declarations may omit semicolons only at their own
                # risk; fail closed rather than treating ASI as a relocation.
                break
            if probe_token.text == "{":
                import_brace += 1
            elif probe_token.text == "}":
                import_brace -= 1
            elif probe_token.text == "(":
                import_paren += 1
            elif probe_token.text == ")":
                import_paren -= 1
            elif probe_token.text == "[":
                import_square += 1
            elif probe_token.text == "]":
                import_square -= 1
        if statement_end is None:
            raise DocumentationImpactError("static import requires a semicolon")
        end = tokens[statement_end].end
        start = token.start
        statement = text[start:end]
        module_match = list(re.finditer(r"(['\"])([^'\"]*)\1", statement))
        if not module_match:
            raise DocumentationImpactError("static import requires a quoted module literal")
        module_match_item = module_match[-1]
        module = module_match_item.group(2)
        module_quote = module_match_item.group(1)
        module_start = start + module_match_item.start(2)
        module_end = start + module_match_item.end(2)
        prefix = statement[: module_match_item.start()]
        type_only = bool(re.match(r"import\s+type(?:\s|\{)", prefix))
        side_effect = bool(re.match(r"import\s*['\"]", statement))
        has_default_or_namespace = False
        bindings: list[_ImportBinding] = []
        brace_match = re.search(r"\{(?P<body>.*)\}", prefix, flags=re.DOTALL)
        if brace_match:
            body = brace_match.group("body")
            for raw_item in body.split(","):
                item = raw_item.strip()
                if not item:
                    continue
                item_type = "type" if type_only or re.match(r"type\s+", item) else "value"
                if item_type == "type":
                    item = re.sub(r"^type\s+", "", item)
                alias_parts = re.split(r"\s+as\s+", item)
                if len(alias_parts) > 2:
                    raise DocumentationImpactError("malformed named import alias")
                imported = alias_parts[0].strip()
                local = alias_parts[-1].strip()
                if (
                    _IDENTIFIER_RE.fullmatch(imported) is None
                    or _IDENTIFIER_RE.fullmatch(local) is None
                ):
                    raise DocumentationImpactError("named imports must use identifiers")
                bindings.append(_ImportBinding(imported, local, item_type, raw_item))
        before_brace = prefix.split("{", 1)[0]
        before_brace = re.sub(r"^import\s+type\s*", "", before_brace)
        before_brace = re.sub(r"\s+from\s*$", "", before_brace).rstrip()
        if before_brace.strip():
            default_part = before_brace.replace("import", "", 1).strip().rstrip(",").strip()
            if default_part:
                has_default_or_namespace = True
                if default_part.startswith("*"):
                    namespace_match = re.search(
                        r"\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)", default_part
                    )
                    if namespace_match:
                        bindings.append(
                            _ImportBinding(
                                "*",
                                namespace_match.group(1),
                                "type" if type_only else "value",
                                default_part,
                            )
                        )
                    else:
                        raise DocumentationImpactError("malformed namespace import")
                elif _IDENTIFIER_RE.fullmatch(default_part):
                    bindings.append(
                        _ImportBinding(
                            "default", default_part, "type" if type_only else "value", default_part
                        )
                    )
                elif default_part:
                    raise DocumentationImpactError("malformed default import")
        form = "side-effect" if side_effect else ("type" if type_only else "named")
        imports.append(
            _StaticImport(
                start=start,
                end=end,
                text=statement,
                module=module,
                module_quote=module_quote,
                module_start=module_start,
                module_end=module_end,
                bindings=tuple(bindings),
                form=form,
                type_only=type_only,
                has_default_or_namespace=has_default_or_namespace,
                side_effect=side_effect,
            )
        )
        i = statement_end + 1
    return tuple(imports)


def _remove_spans(text: str, spans: Iterable[tuple[int, int]]) -> str:
    result = text
    for start, end in sorted(spans, reverse=True):
        # Whole-line declarations/imports remove their newline as well.  This
        # keeps the residual comparison byte-stable after an extraction.
        left = start
        right = end
        if _line_start(result, start) == start:
            if right < len(result) and result[right : right + 2] == "\r\n":
                right += 2
            elif right < len(result) and result[right] == "\n":
                right += 1
        result = result[:left] + result[right:]
    return result


def _nonblank_lines(text: str) -> str:
    """Compare residual source by exact nonblank lines, ignoring extraction gaps."""
    return "\n".join(line for line in text.split("\n") if line.strip())


def _identifier_occurrences(
    text: str, *, excluded: Iterable[tuple[int, int]] = ()
) -> tuple[str, ...]:
    excluded_spans = tuple(excluded)
    tokens = _scan_ts(text, include_template_expressions=True)
    occurrences: list[str] = []
    for token in tokens:
        if token.kind != "identifier":
            continue
        if any(start <= token.start < end for start, end in excluded_spans):
            continue
        occurrences.append(token.text)
    return tuple(occurrences)


def _git_blob_paths(project: Path, source_sha: str) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "-z", source_sha, "--", "apps/web/src"],
            cwd=project,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise DocumentationImpactError("cannot enumerate merge-base source files") from error
    paths: set[str] = set()
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        header, path_bytes = entry.split(b"\t", 1)
        mode, object_type, _sha = header.decode("ascii").split()
        path = path_bytes.decode("utf-8").replace("\\", "/")
        if object_type != "blob" or mode == "120000":
            continue
        paths.add(path)
    return paths


def _current_source_paths(project: Path, entries: Mapping[str, bool]) -> set[str]:
    tracked = _git_lines(project, ["ls-files"])
    candidates = {path for path in tracked if path.startswith("apps/web/src/")}
    candidates.update(
        path for path, supplied in entries.items() if supplied and path.startswith("apps/web/src/")
    )
    result: set[str] = set()
    for path in candidates:
        candidate = project / Path(*path.split("/"))
        try:
            if candidate.is_file() and not candidate.is_symlink():
                result.add(path)
        except OSError:
            continue
    return result


def _read_current(project: Path, path: str) -> str:
    candidate = project / Path(*path.split("/"))
    if candidate.is_symlink() or not candidate.is_file():
        raise DocumentationImpactError(f"{path} must be a current regular file")
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError as error:
        raise DocumentationImpactError(f"cannot read current source {path}: {error}") from error


def _read_base(
    project: Path, source_sha: str, path: str, base_files: Mapping[str, str] | None
) -> str:
    if base_files is not None and path in base_files:
        return base_files[path]
    return _base_file_text(project, source_sha, path)


def _resolve_relative_module(
    importer: str,
    specifier: str,
    universe: set[str],
    *,
    project: Path | None = None,
) -> str:
    if not specifier or "\\" in specifier or not specifier.startswith(("./", "../")):
        raise DocumentationImpactError(f"unsupported relative import {specifier!r} in {importer}")
    if any(value in specifier for value in ("?", "#")) or specifier.endswith("/"):
        raise DocumentationImpactError(f"ambiguous import specifier {specifier!r}")
    parent = PurePosixPath(importer).parent
    joined = PurePosixPath(parent, specifier)
    parts: list[str] = []
    for part in joined.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise DocumentationImpactError(f"import escapes apps/web/src: {specifier!r}")
            parts.pop()
        else:
            parts.append(part)
    resolved_base = "/".join(parts)
    if not resolved_base.startswith("apps/web/src/"):
        raise DocumentationImpactError(f"import escapes apps/web/src: {specifier!r}")
    suffix = PurePosixPath(resolved_base).suffix
    candidates: list[str]
    if suffix:
        if suffix not in {".ts", ".tsx"}:
            raise DocumentationImpactError(f"unsupported import suffix {specifier!r}")
        candidates = [resolved_base]
    else:
        candidates = [
            f"{resolved_base}.ts",
            f"{resolved_base}.tsx",
            f"{resolved_base}/index.ts",
            f"{resolved_base}/index.tsx",
        ]
    existing: list[str] = []
    for candidate in candidates:
        if candidate not in universe:
            continue
        if project is not None:
            path = project / Path(*candidate.split("/"))
            if path.is_symlink() or not path.is_file():
                continue
        existing.append(candidate)
    if len(existing) != 1:
        raise DocumentationImpactError(
            f"import {specifier!r} from {importer} resolves to {len(existing)} candidates"
        )
    return existing[0]


def _binding_tuple(import_item: _StaticImport) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (binding.imported, binding.local, binding.kind) for binding in import_item.bindings
    )


def _remove_named_bindings(statement: _StaticImport, removed: set[str]) -> str:
    if not removed:
        return statement.text
    opening = statement.text.find("{")
    closing = statement.text.rfind("}")
    if opening < 0 or closing < opening:
        raise DocumentationImpactError("cannot remove bindings from a non-named import")
    body = statement.text[opening + 1 : closing]
    chunks = body.split(",")
    kept: list[str] = []
    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        binding_name = re.split(r"\s+as\s+", re.sub(r"^type\s+", "", stripped))[-1].strip()
        if binding_name not in removed:
            kept.append(chunk)
    return statement.text[: opening + 1] + ",".join(kept) + statement.text[closing:]


def _decl_map(
    text: str,
    source: str,
    *,
    required_names: set[str] | None = None,
) -> dict[str, _Declaration]:
    try:
        declarations = _find_declarations(text, required_names=required_names)
    except DocumentationImpactError as error:
        raise DocumentationImpactError(f"cannot parse declarations in {source}: {error}") from error
    mapped: dict[str, _Declaration] = {}
    for declaration in declarations:
        if declaration.name in mapped:
            raise DocumentationImpactError(
                f"declaration {declaration.name} appears more than once in {source}"
            )
        mapped[declaration.name] = declaration
    return mapped


def _validate_source_imports(
    *,
    source: str,
    base_text: str,
    current_text: str,
    base_imports: tuple[_StaticImport, ...],
    current_imports: tuple[_StaticImport, ...],
    added_target_index: int | None,
    removable: Mapping[str, set[str]],
    import_only_rewrite: Mapping[int, str] | None = None,
) -> None:
    expected_current = len(base_imports) + (1 if added_target_index is not None else 0)
    if len(current_imports) != expected_current:
        raise DocumentationImpactError(f"{source} changes the number of static imports")
    current_without_target = [
        item for index, item in enumerate(current_imports) if index != added_target_index
    ]
    if len(current_without_target) != len(base_imports):
        raise DocumentationImpactError(f"{source} splits, merges, or moves imports")
    for ordinal, (base_item, current_item) in enumerate(
        zip(base_imports, current_without_target, strict=True)
    ):
        removed = removable.get(str(ordinal), set())
        if current_item.form != base_item.form or current_item.type_only != base_item.type_only:
            raise DocumentationImpactError(f"{source} changes import form at ordinal {ordinal}")
        if (
            current_item.has_default_or_namespace != base_item.has_default_or_namespace
            or current_item.side_effect != base_item.side_effect
        ):
            raise DocumentationImpactError(
                f"{source} changes default, namespace, or side-effect imports"
            )
        if current_item.module != base_item.module and (
            import_only_rewrite is None or ordinal not in import_only_rewrite
        ):
            raise DocumentationImpactError(f"{source} changes an existing import module")
        if import_only_rewrite is not None and ordinal in import_only_rewrite:
            if current_item.module != import_only_rewrite[ordinal]:
                raise DocumentationImpactError(
                    f"{source} rewrites the wrong type-only import module"
                )
            if not any(binding.kind == "type" for binding in base_item.bindings):
                raise DocumentationImpactError(f"{source} rewrites a runtime import module")
        expected_bindings = tuple(
            binding for binding in base_item.bindings if binding.local not in removed
        )
        if _binding_tuple(current_item) != _binding_tuple_for(expected_bindings):
            raise DocumentationImpactError(f"{source} changes import bindings at ordinal {ordinal}")
        if (
            not removed
            and current_item.text != base_item.text
            and (import_only_rewrite is None or ordinal not in import_only_rewrite)
        ):
            raise DocumentationImpactError(f"{source} changes import formatting or attributes")
        if removed and current_item.text != _remove_named_bindings(base_item, removed):
            raise DocumentationImpactError(f"{source} changes retained import bytes")


def _binding_tuple_for(bindings: Iterable[_ImportBinding]) -> tuple[tuple[str, str, str], ...]:
    return tuple((binding.imported, binding.local, binding.kind) for binding in bindings)


def _target_import_name_set(import_item: _StaticImport) -> set[tuple[str, str, str]]:
    if import_item.side_effect or import_item.has_default_or_namespace or not import_item.bindings:
        raise DocumentationImpactError("target imports must be non-empty named imports")
    return set(_binding_tuple(import_item))


def _validate_binding_order(
    import_item: _StaticImport,
    source: str,
    *,
    target_dependency: bool = False,
) -> None:
    bindings = import_item.bindings
    seen_type = False
    for binding in bindings:
        if binding.kind == "type":
            seen_type = True
        elif seen_type:
            raise DocumentationImpactError(
                f"{source} import bindings must list values before inline types"
            )
    value_names = [binding.local for binding in bindings if binding.kind == "value"]
    type_names = [binding.local for binding in bindings if binding.kind == "type"]
    if value_names != sorted(value_names) or type_names != sorted(type_names):
        raise DocumentationImpactError(
            f"{source} import bindings are not lexicographically ordered"
        )
    if target_dependency:
        if not value_names and not import_item.type_only:
            raise DocumentationImpactError(f"{source} all-type import must use import type")
        if value_names and import_item.type_only:
            raise DocumentationImpactError(f"{source} mixed import must use named import")


def _validate_structural_exception(
    project: Path,
    exception: DocumentationImpactException,
    visual_files: set[str],
    merge_base: str,
    *,
    changed: Mapping[str, bool] | None = None,
    base_files: Mapping[str, str] | None = None,
) -> _ValidatedDocumentationImpactException:
    if exception.source_sha != merge_base:
        raise DocumentationImpactError(
            f"{exception.path} sourceSha {exception.source_sha} does not match "
            f"origin/main merge-base {merge_base}"
        )
    changed_entries_map: Mapping[str, bool] = changed or {path: True for path in visual_files}
    changed_paths = set(changed_entries_map)
    relocations = exception.relocations
    sources = {item.source for item in relocations}
    targets = {item.target for item in relocations}
    import_only = set(exception.import_only_files)
    declared_visual = sources | import_only
    if visual_files != declared_visual:
        raise DocumentationImpactError(
            f"{exception.path} visualFiles must exactly match relocation sources "
            "and importOnlyFiles"
        )
    if any(
        _canonical_repo_path(path, exception.path) != path for path in declared_visual | targets
    ):
        raise DocumentationImpactError(f"{exception.path} contains non-canonical paths")
    if not declared_visual <= changed_paths or not targets <= changed_paths:
        raise DocumentationImpactError(
            f"{exception.path} paths must all be in the complete changed set"
        )
    if any(not changed_entries_map.get(path, False) for path in declared_visual | targets):
        raise DocumentationImpactError(
            f"{exception.path} source, import-only, and target paths must be current changes"
        )
    if any(PurePosixPath(path).suffix.lower() != ".tsx" for path in declared_visual):
        raise DocumentationImpactError(f"{exception.path} sources must be production .tsx files")
    if any(PurePosixPath(path).suffix.lower() != ".ts" or _is_test_path(path) for path in targets):
        raise DocumentationImpactError(
            f"{exception.path} targets must be production non-test .ts files"
        )
    changed_production = {
        path
        for path in changed_paths
        if path.startswith("apps/web/src/")
        and not _is_test_path(path)
        and PurePosixPath(path).suffix.lower() in {".ts", ".tsx"}
    }
    if changed_production != declared_visual | targets:
        raise DocumentationImpactError(
            f"{exception.path} changed production sources and targets must be declared exactly"
        )

    base_universe = (
        set(base_files or {})
        if base_files is not None
        else _git_blob_paths(project, exception.source_sha)
    )
    current_universe = _current_source_paths(project, changed_entries_map)
    if base_files is not None:
        current_universe.update(
            path
            for path in changed_paths
            if path.startswith("apps/web/src/") and (project / Path(*path.split("/"))).is_file()
        )
    for path in sources | import_only:
        if path not in base_universe:
            raise DocumentationImpactError(
                f"{exception.path} source {path} is absent at merge base"
            )
        if path not in current_universe:
            raise DocumentationImpactError(
                f"{exception.path} source {path} is absent in current worktree"
            )
    for path in targets:
        if path in base_universe:
            raise DocumentationImpactError(
                f"{exception.path} target {path} already exists at merge base"
            )
        if path not in current_universe:
            raise DocumentationImpactError(
                f"{exception.path} target {path} is absent in current worktree"
            )

    target_by_source: dict[str, list[_Relocation]] = {}
    for relocation in relocations:
        target_by_source.setdefault(relocation.source, []).append(relocation)
    global_names = {name for item in relocations for name in item.declarations}
    for source, source_relocations in target_by_source.items():
        moved_names = {name for item in source_relocations for name in item.declarations}
        base_text = _read_base(project, exception.source_sha, source, base_files)
        current_text = _read_current(project, source)
        base_declarations = _decl_map(base_text, source, required_names=moved_names)
        base_imports = _static_imports(base_text)
        current_imports = _static_imports(current_text)
        if any(name not in base_declarations for name in moved_names):
            raise DocumentationImpactError(
                f"{source} relocation declaration is not present at merge base"
            )
        # A declaration must be top-level and each relocation name is globally unique.
        if moved_names - global_names:
            raise DocumentationImpactError(f"{source} has undeclared moved declarations")
        base_decl_spans = [
            (base_declarations[name].start, base_declarations[name].end) for name in moved_names
        ]

        base_remaining = _remove_spans(
            base_text,
            [
                *(item for item in ((item.start, item.end) for item in base_imports)),
                *base_decl_spans,
            ],
        ).replace("\r\n", "\n")
        current_remaining = _remove_spans(
            current_text,
            [(item.start, item.end) for item in current_imports],
        ).replace("\r\n", "\n")
        if _nonblank_lines(base_remaining) != _nonblank_lines(current_remaining):
            raise DocumentationImpactError(f"{source} changes residual source bytes")

        moved_regions: list[str] = []
        expected_target_names: set[str] = set()
        target_paths = {item.target for item in source_relocations}
        if len(target_paths) != 1:
            raise DocumentationImpactError(f"{source} must use one target import statement")
        target_path = next(iter(target_paths))
        for relocation in source_relocations:
            target_text = _read_current(project, relocation.target)
            target_declarations = _decl_map(target_text, relocation.target)
            base_declaration_names = set(relocation.declarations)
            for name in base_declaration_names:
                base_declaration = base_declarations[name]
                target_declaration = target_declarations.get(name)
                if target_declaration is None:
                    raise DocumentationImpactError(
                        f"{relocation.target} is missing declaration {name}"
                    )
                expected_target_names.add(name)
                base_decl_text = base_text[base_declaration.start : base_declaration.end]
                target_decl_text = target_text[target_declaration.start : target_declaration.end]
                if target_decl_text != base_decl_text and not (
                    not base_declaration.export and target_decl_text == "export " + base_decl_text
                ):
                    raise DocumentationImpactError(
                        f"{name} declaration bytes changed during extraction"
                    )
                moved_regions.append(
                    _remove_spans(
                        target_decl_text,
                        [
                            (
                                target_declaration.defining_start - target_declaration.start,
                                target_declaration.defining_end - target_declaration.start,
                            )
                        ],
                    )
                )
            target_imports = _static_imports(target_text)
            target_spans = [(item.start, item.end) for item in target_imports]
            remaining_target = _remove_spans(
                target_text,
                [
                    *target_spans,
                    *(
                        (declaration.start, declaration.end)
                        for name, declaration in target_declarations.items()
                        if name in expected_target_names
                    ),
                ],
            )
            if remaining_target.strip():
                raise DocumentationImpactError(
                    f"{relocation.target} contains residual code or standalone comments"
                )

        moved_occurrences = set(_identifier_occurrences("\n".join(moved_regions)))
        remaining_occurrences = set(_identifier_occurrences(current_remaining))
        reference_names = {name for name in moved_names if name in remaining_occurrences}
        removable_by_ordinal: dict[str, set[str]] = {}
        base_bindings: dict[tuple[str, str], tuple[int, _ImportBinding, str]] = {}
        runtime_module_order: list[str] = []
        for ordinal, import_item in enumerate(base_imports):
            if not import_item.module.startswith(("./", "../")):
                if any(binding.local in moved_occurrences for binding in import_item.bindings):
                    raise DocumentationImpactError(
                        f"{source} moved declarations use unsupported package import "
                        f"{import_item.module!r}"
                    )
                continue
            resolved = _resolve_relative_module(source, import_item.module, base_universe)
            if (
                any(binding.kind == "value" for binding in import_item.bindings)
                and resolved not in runtime_module_order
            ):
                runtime_module_order.append(resolved)
            for binding in import_item.bindings:
                base_bindings[(binding.local, str(ordinal))] = (ordinal, binding, resolved)
        expected_target_dependencies: dict[str, list[_ImportBinding]] = {}
        for (_local, _ordinal), (ordinal, binding, resolved) in base_bindings.items():
            if binding.local in moved_occurrences:
                expected_target_dependencies.setdefault(resolved, []).append(binding)
                if binding.local not in remaining_occurrences:
                    removable_by_ordinal.setdefault(str(ordinal), set()).add(binding.local)

        target_imports = _static_imports(_read_current(project, target_path))
        target_universe = current_universe
        target_groups: list[tuple[str, _StaticImport]] = []
        target_group_paths: set[str] = set()
        for target_import in target_imports:
            resolved = _resolve_relative_module(
                target_path, target_import.module, target_universe, project=project
            )
            if resolved in target_group_paths:
                raise DocumentationImpactError(
                    f"{target_path} has duplicate import groups for {resolved}"
                )
            _target_import_name_set(target_import)
            _validate_binding_order(target_import, target_path, target_dependency=True)
            target_group_paths.add(resolved)
            target_groups.append((resolved, target_import))
        expected_modules = set(expected_target_dependencies)
        if {resolved for resolved, _ in target_groups} != expected_modules:
            raise DocumentationImpactError(f"{target_path} imports unused or missing dependencies")
        for resolved, target_import in target_groups:
            actual = _target_import_name_set(target_import)
            expected = {
                (binding.imported, binding.local, binding.kind)
                for binding in expected_target_dependencies[resolved]
            }
            if actual != expected:
                raise DocumentationImpactError(f"{target_path} changes dependency bindings")
            if not all(binding.local in moved_occurrences for binding in target_import.bindings):
                raise DocumentationImpactError(f"{target_path} imports an unreferenced dependency")
        type_groups = [
            resolved
            for resolved, item in target_groups
            if all(binding.kind == "type" for binding in item.bindings)
        ]
        runtime_groups = [
            resolved for resolved, item in target_groups if resolved not in type_groups
        ]
        if type_groups != sorted(type_groups):
            raise DocumentationImpactError(
                f"{target_path} type-only dependency groups are not sorted"
            )
        expected_runtime_order = [
            resolved for resolved in runtime_module_order if resolved in runtime_groups
        ]
        if runtime_groups != expected_runtime_order:
            raise DocumentationImpactError(f"{target_path} runtime dependency groups are reordered")

        added_target_import_indices = [
            index
            for index, item in enumerate(current_imports)
            if index >= len(base_imports)
            and _resolve_relative_module(source, item.module, current_universe, project=project)
            == target_path
        ]
        expected_source_bindings: set[tuple[str, str, str]] = set()
        for name in reference_names:
            declaration = base_declarations[name]
            expected_source_bindings.add(
                (name, name, "type" if declaration.kind == "type" else "value")
            )
        if expected_source_bindings:
            if len(added_target_import_indices) != 1:
                raise DocumentationImpactError(f"{source} must add exactly one target import")
            added = current_imports[added_target_import_indices[0]]
            _target_import_name_set(added)
            _validate_binding_order(added, source)
            if _target_import_name_set(added) != expected_source_bindings:
                raise DocumentationImpactError(f"{source} target import bindings are not exact")
            if added_target_import_indices[0] != len(current_imports) - 1:
                raise DocumentationImpactError(
                    f"{source} target import is not after pre-existing imports"
                )
        elif added_target_import_indices:
            raise DocumentationImpactError(f"{source} adds an unnecessary target import")
        _validate_source_imports(
            source=source,
            base_text=base_text,
            current_text=current_text,
            base_imports=base_imports,
            current_imports=current_imports,
            added_target_index=added_target_import_indices[0]
            if added_target_import_indices
            else None,
            removable=removable_by_ordinal,
        )

    for path in import_only:
        base_text = _read_base(project, exception.source_sha, path, base_files)
        current_text = _read_current(project, path)
        base_imports = _static_imports(base_text)
        current_imports = _static_imports(current_text)
        if len(base_imports) != len(current_imports):
            raise DocumentationImpactError(f"{path} changes type-only import statement count")
        base_residual = _remove_spans(
            base_text, [(item.start, item.end) for item in base_imports]
        ).replace("\r\n", "\n")
        current_residual = _remove_spans(
            current_text, [(item.start, item.end) for item in current_imports]
        ).replace("\r\n", "\n")
        if _nonblank_lines(base_residual) != _nonblank_lines(current_residual):
            raise DocumentationImpactError(f"{path} changes residual source bytes")
        rewrites: dict[int, str] = {}
        exact_rewrites = 0
        for index, (base_item, current_item) in enumerate(
            zip(base_imports, current_imports, strict=True)
        ):
            if (
                _binding_tuple(base_item) != _binding_tuple(current_item)
                or base_item.text == current_item.text
            ):
                if base_item.text != current_item.text and _binding_tuple(
                    base_item
                ) != _binding_tuple(current_item):
                    raise DocumentationImpactError(f"{path} changes type-only import bindings")
                continue
            type_bindings = [binding for binding in base_item.bindings if binding.kind == "type"]
            if not type_bindings or any(binding.kind != "type" for binding in base_item.bindings):
                raise DocumentationImpactError(f"{path} rewrites a runtime import")
            if any(binding.local not in global_names for binding in type_bindings):
                raise DocumentationImpactError(f"{path} rewrites an undeclared type binding")
            for binding in type_bindings:
                matching_sources = {
                    relocation.source
                    for relocation in exception.relocations
                    if binding.local in relocation.declarations
                }
                if len(matching_sources) != 1:
                    raise DocumentationImpactError(
                        f"{path} rewrites a type binding with no unique relocation source"
                    )
                base_source = _resolve_relative_module(
                    path, base_item.module, base_universe, project=project
                )
                expected_source = next(iter(matching_sources))
                if base_source != expected_source:
                    raise DocumentationImpactError(
                        f"{path} rewrites a type binding from {base_source}, "
                        f"expected relocation source {expected_source}"
                    )
            resolved_current = _resolve_relative_module(
                path, current_item.module, current_universe, project=project
            )
            matching_targets = {
                relocation.target
                for relocation in exception.relocations
                if any(binding.local in relocation.declarations for binding in type_bindings)
            }
            if len(matching_targets) != 1 or resolved_current not in matching_targets:
                raise DocumentationImpactError(
                    f"{path} rewrites to an undeclared relocation target"
                )
            if any(
                not any(
                    binding.local in relocation.declarations
                    and relocation.target == resolved_current
                    for relocation in exception.relocations
                )
                for binding in type_bindings
            ):
                raise DocumentationImpactError(f"{path} rewrites unrelated type bindings")
            rewrites[index] = current_item.module
            exact_rewrites += 1
        if exact_rewrites == 0:
            raise DocumentationImpactError(f"{path} has no exact relocated type import rewrite")
        _validate_source_imports(
            source=path,
            base_text=base_text,
            current_text=current_text,
            base_imports=base_imports,
            current_imports=current_imports,
            added_target_index=None,
            removable={},
            import_only_rewrite=rewrites,
        )
    return _ValidatedDocumentationImpactException(exception=exception, derived_selectors=())


def _validate_exception(
    project: Path,
    exception: DocumentationImpactException,
    visual_files: set[str] | Mapping[str, bool],
    merge_base: str,
    *,
    base_files: Mapping[str, str] | None = None,
    changed: Mapping[str, bool] | None = None,
) -> _ValidatedDocumentationImpactException:
    if exception.classification == _NON_USER_VISIBLE_STRUCTURAL_CLASSIFICATION:
        complete_changed = changed
        if complete_changed is None and isinstance(visual_files, Mapping):
            complete_changed = visual_files
        visual_set = (
            {path for path in visual_files if _is_visual_source(path)}
            if isinstance(visual_files, Mapping)
            else set(visual_files)
        )
        return _validate_structural_exception(
            project,
            exception,
            visual_set,
            merge_base,
            changed=complete_changed,
            base_files=base_files,
        )
    if isinstance(visual_files, Mapping):
        visual_files = {path for path in visual_files if _is_visual_source(path)}
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
    covered = set(exception.unconsumed_modules) | set(exception.preserved_computed_value_files)
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
    if not set(exception.preserved_computed_value_files).issubset(_PRESERVED_FOUNDATION_FILES):
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
    if exception is not None and not isinstance(exception, _ValidatedDocumentationImpactException):
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
        validated_exception = _validate_exception(
            project,
            exception,
            entries,
            _merge_base(project),
            changed=entries,
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

"""Static architecture rules for the modular-monolith package."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_DOMAIN_IMPORT_ROOTS = {
    "boto3",
    "fastapi",
    "sqlalchemy",
    "uvicorn",
}
PRIVATE_MODULE_LAYERS = {"adapters", "persistence", "repositories"}
PRODUCTION_PLUGIN_IMPORTS = {"plugins.production", "cmp.plugins.production"}


@dataclass(frozen=True, order=True, slots=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str


def _imports(tree: ast.AST) -> Iterable[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module


def _module_context(path: Path) -> str | None:
    parts = path.parts
    if "modules" not in parts:
        return None
    index = parts.index("modules")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _is_domain_path(path: Path) -> bool:
    return "domain" in path.parts


def _cross_module_private_layer(import_name: str, current_module: str | None) -> bool:
    if current_module is None or not import_name.startswith("cmp.modules."):
        return False
    parts = import_name.split(".")
    if len(parts) < 4:
        return False
    imported_module = parts[2]
    imported_layer = parts[3]
    return imported_module != current_module and imported_layer in PRIVATE_MODULE_LAYERS


def find_violations(root: Path) -> list[Violation]:
    """Return deterministic violations without importing application modules."""

    violations: list[Violation] = []
    for source in sorted(root.rglob("*.py")):
        relative = source.relative_to(root)
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(relative))
        except SyntaxError as error:
            violations.append(
                Violation(str(relative), error.lineno or 0, "ARCH-000", "invalid Python syntax")
            )
            continue

        current_module = _module_context(relative)
        for line, import_name in _imports(tree):
            import_root = import_name.split(".", maxsplit=1)[0]
            if _is_domain_path(relative) and import_root in FORBIDDEN_DOMAIN_IMPORT_ROOTS:
                violations.append(
                    Violation(
                        str(relative),
                        line,
                        "ARCH-001",
                        f"domain code imports framework/adapter dependency '{import_name}'",
                    )
                )
            if _cross_module_private_layer(import_name, current_module):
                violations.append(
                    Violation(
                        str(relative),
                        line,
                        "ARCH-002",
                        f"module imports another module's private layer '{import_name}'",
                    )
                )
            if any(
                import_name == forbidden or import_name.startswith(f"{forbidden}.")
                for forbidden in PRODUCTION_PLUGIN_IMPORTS
            ):
                violations.append(
                    Violation(
                        str(relative),
                        line,
                        "ARCH-003",
                        f"core imports production plugin implementation '{import_name}'",
                    )
                )
    return sorted(violations)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check modular-monolith dependency rules.")
    parser.add_argument("--root", type=Path, default=Path("backend/src"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    violations = find_violations(args.root)
    if violations:
        for item in violations:
            print(f"{item.path}:{item.line}: {item.rule} {item.detail}")
        return 1
    print(f"architecture check passed: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


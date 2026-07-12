"""Contract linting, example validation, and conservative OpenAPI compatibility checks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from cmp.tools.generate_client import render_client

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
POSITIVE_EXAMPLES = {
    "job-spec.json": "contracts/jobs/job-spec.schema.json",
    "result-manifest.json": "contracts/jobs/result-manifest.schema.json",
    "plugin-manifest.json": "contracts/plugins/plugin-manifest.schema.json",
    "material-model-ir.json": "contracts/ir/material-model-ir-envelope.schema.json",
    "me-response.json": "contracts/identity/me-response.schema.json",
    "revision-metadata.json": "contracts/revisions/revision-metadata.schema.json",
    "artifact-available-event.json": "contracts/events/artifact-available.schema.json",
    "audit-export.json": "contracts/audit/audit-export.schema.json",
}
NEGATIVE_EXAMPLES = {
    "job-spec-latest.json": "contracts/jobs/job-spec.schema.json",
    "me-response-missing-project.json": "contracts/identity/me-response.schema.json",
    "plugin-manifest-missing-digest.json": "contracts/plugins/plugin-manifest.schema.json",
    "revision-metadata-latest.json": "contracts/revisions/revision-metadata.schema.json",
    "artifact-available-event-storage-key.json": "contracts/events/artifact-available.schema.json",
    "audit-export-raw-payload.json": "contracts/audit/audit-export.schema.json",
}


def _mapping(value: object, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a mapping")
    return cast(dict[str, Any], value)


def load_yaml(path: Path) -> dict[str, Any]:
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))


def load_json(path: Path) -> dict[str, Any]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), str(path))


def _validate_openapi(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(document.get("openapi", "")).startswith("3.1."):
        errors.append("OpenAPI version must be 3.1.x")
    info = document.get("info")
    if not isinstance(info, dict) or not info.get("title") or not info.get("version"):
        errors.append("OpenAPI info.title and info.version are required")
    paths = document.get("paths")
    if not isinstance(paths, dict):
        errors.append("OpenAPI paths must be a mapping")
        return errors
    health = paths.get("/api/v1/health")
    if not isinstance(health, dict) or not isinstance(health.get("get"), dict):
        errors.append("GET /api/v1/health is required")
    elif health["get"].get("operationId") != "getHealth":
        errors.append("health operationId must be getHealth")
    return errors


def _validate_asyncapi(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(document.get("asyncapi", "")).startswith("3."):
        errors.append("AsyncAPI version must be 3.x")
    info = document.get("info")
    if not isinstance(info, dict) or not info.get("title") or not info.get("version"):
        errors.append("AsyncAPI info.title and info.version are required")
    if not isinstance(document.get("channels"), dict):
        errors.append("AsyncAPI channels must be a mapping")
    return errors


def validate_example(schema_path: Path, example_path: Path) -> list[str]:
    schema = load_json(schema_path)
    example = load_json(example_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in sorted(validator.iter_errors(example), key=str)]


def _validate_schema_files(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted((root / "contracts").rglob("*.schema.json")):
        try:
            Draft202012Validator.check_schema(load_json(path))
        except Exception as error:  # jsonschema exposes several schema exception types
            errors.append(f"{path.relative_to(root)}: invalid JSON Schema: {error}")
    return errors


def _validate_examples(root: Path) -> list[str]:
    errors: list[str] = []
    positive_dir = root / "contracts/examples/positive"
    for name, schema_relative in POSITIVE_EXAMPLES.items():
        failures = validate_example(root / schema_relative, positive_dir / name)
        errors.extend(f"positive/{name}: {failure}" for failure in failures)

    negative_dir = root / "contracts/examples/negative"
    for name, schema_relative in NEGATIVE_EXAMPLES.items():
        failures = validate_example(root / schema_relative, negative_dir / name)
        if not failures:
            errors.append(f"negative/{name}: fixture unexpectedly passed validation")
    return errors


def validate_contracts(root: Path) -> list[str]:
    errors = _validate_schema_files(root)
    errors.extend(_validate_openapi(load_yaml(root / "contracts/http/openapi.yaml")))
    errors.extend(_validate_asyncapi(load_yaml(root / "contracts/events/asyncapi.yaml")))
    errors.extend(_validate_examples(root))

    generated = root / "generated/python/cmp_api_client/client.py"
    expected = render_client(root / "contracts/http/openapi.yaml")
    if not generated.exists() or generated.read_text(encoding="utf-8") != expected:
        errors.append("generated health client is not up to date")
    return errors


def _schema_breaks(
    baseline: Mapping[str, Any], current: Mapping[str, Any], schema_name: str
) -> list[str]:
    breaks: list[str] = []
    old_required = set(baseline.get("required", []))
    new_required = set(current.get("required", []))
    for field in sorted(new_required - old_required):
        breaks.append(f"schema {schema_name}: field '{field}' became required")

    old_properties = baseline.get("properties", {})
    new_properties = current.get("properties", {})
    if isinstance(old_properties, dict) and isinstance(new_properties, dict):
        for field in sorted(set(old_properties) - set(new_properties)):
            breaks.append(f"schema {schema_name}: property '{field}' was removed")
    return breaks


def detect_openapi_breaks(
    baseline: Mapping[str, Any], current: Mapping[str, Any]
) -> list[str]:
    """Detect a conservative baseline of breaking removals and required-field changes."""

    breaks: list[str] = []
    old_paths = baseline.get("paths", {})
    new_paths = current.get("paths", {})
    if isinstance(old_paths, dict) and isinstance(new_paths, dict):
        for path, old_item in old_paths.items():
            if path not in new_paths:
                breaks.append(f"path removed: {path}")
                continue
            new_item = new_paths[path]
            if not isinstance(old_item, dict) or not isinstance(new_item, dict):
                continue
            for method in sorted(HTTP_METHODS.intersection(old_item)):
                if method not in new_item:
                    breaks.append(f"operation removed: {method.upper()} {path}")
                    continue
                old_responses = old_item[method].get("responses", {})
                new_responses = new_item[method].get("responses", {})
                if isinstance(old_responses, dict) and isinstance(new_responses, dict):
                    for response in sorted(set(old_responses) - set(new_responses)):
                        breaks.append(
                            f"response removed: {method.upper()} {path} status {response}"
                        )

    old_schemas = baseline.get("components", {}).get("schemas", {})
    new_schemas = current.get("components", {}).get("schemas", {})
    if isinstance(old_schemas, dict) and isinstance(new_schemas, dict):
        for name, old_schema in old_schemas.items():
            if name not in new_schemas:
                breaks.append(f"schema removed: {name}")
            elif isinstance(old_schema, dict) and isinstance(new_schemas[name], dict):
                breaks.extend(_schema_breaks(old_schema, new_schemas[name], name))
    return breaks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CMP public contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    lint = subparsers.add_parser("lint")
    lint.add_argument("--root", type=Path, default=Path.cwd())
    compat = subparsers.add_parser("compat")
    compat.add_argument("--baseline", type=Path, required=True)
    compat.add_argument("--current", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "lint":
        errors = validate_contracts(args.root)
        if errors:
            for error in errors:
                print(error)
            return 1
        print("contract lint passed")
        return 0

    breaks = detect_openapi_breaks(load_yaml(args.baseline), load_yaml(args.current))
    if breaks:
        for item in breaks:
            print(item)
        return 1
    print("OpenAPI compatibility check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


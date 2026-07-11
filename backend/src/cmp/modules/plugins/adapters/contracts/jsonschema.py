"""Validate T-17 manifest and extension schema contracts."""

from __future__ import annotations

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from cmp.modules.plugins.domain.registry import InvalidManifest


class JsonSchemaPluginContractValidator:
    def __init__(self) -> None:
        resource = files("cmp.modules.plugins.contracts").joinpath(
            "plugin-manifest.schema.json"
        )
        schema = json.loads(resource.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._manifest = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )

    def validate_manifest(self, document: object) -> None:
        errors = sorted(self._manifest.iter_errors(document), key=str)
        if errors:
            first = errors[0]
            path = ".".join(str(item) for item in first.absolute_path)
            raise InvalidManifest(f"{path or 'manifest'}: {first.message}")

    def validate_schema(self, document: object) -> None:
        if not isinstance(document, dict):
            raise InvalidManifest("registered schema must be an object")
        if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise InvalidManifest("registered schema must declare JSON Schema 2020-12")
        if not isinstance(document.get("$id"), str):
            raise InvalidManifest("registered schema requires a stable $id")
        try:
            Draft202012Validator.check_schema(document)
        except SchemaError as error:
            raise InvalidManifest("registered schema is not valid JSON Schema 2020-12") from error

"""Validate immutable Job Specs with the packaged JSON Schema 2020-12 contract."""

from __future__ import annotations

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from cmp.modules.jobs.domain.jobs import InvalidJobSpec


class JsonSchemaJobContractValidator:
    def __init__(self) -> None:
        schema_resource = files("cmp.modules.jobs.contracts").joinpath(
            "job-spec.schema.json"
        )
        schema = json.loads(schema_resource.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )

    def validate_job_spec(self, document: object) -> None:
        errors = sorted(self._validator.iter_errors(document), key=str)
        if errors:
            first = errors[0]
            path = ".".join(str(item) for item in first.absolute_path)
            location = path or "job_spec"
            raise InvalidJobSpec(f"{location}: {first.message}")

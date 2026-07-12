"""Validate language-neutral T-18 Job Spec, Result Manifest, and config contracts."""

from __future__ import annotations

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from cmp.modules.plugins.domain.execution import (
    InvalidExecutionRequest,
    InvalidResultManifest,
)


def _validator(name: str) -> Draft202012Validator:
    resource = files("cmp_plugin_sdk.contracts").joinpath(name)
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


class JsonSchemaRunnerContractValidator:
    def __init__(self) -> None:
        self._job = _validator("job-spec.schema.json")
        self._result = _validator("result-manifest.schema.json")

    @staticmethod
    def _first(validator: Draft202012Validator, document: object) -> str | None:
        errors = sorted(validator.iter_errors(document), key=str)
        if not errors:
            return None
        first = errors[0]
        path = ".".join(str(item) for item in first.absolute_path)
        return f"{path or 'document'}: {first.message}"

    def validate_job_spec(self, document: object) -> None:
        detail = self._first(self._job, document)
        if detail is not None:
            raise InvalidExecutionRequest(f"invalid Job Spec 1.0: {detail}")

    def validate_result_manifest(self, document: object) -> None:
        detail = self._first(self._result, document)
        if detail is not None:
            raise InvalidResultManifest(f"invalid Result Manifest 1.0: {detail}")

    def validate_instance(self, instance: object, schema: object) -> None:
        if not isinstance(schema, dict):
            raise InvalidExecutionRequest("registered config schema must be an object")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise InvalidExecutionRequest(
                "registered config schema is not JSON Schema 2020-12"
            ) from error
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        detail = self._first(validator, instance)
        if detail is not None:
            raise InvalidExecutionRequest(f"Job config violates its schema: {detail}")

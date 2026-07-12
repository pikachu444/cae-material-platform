"""Validate emitted CloudEvents against packaged JSON Schema 2020-12 contracts."""

from __future__ import annotations

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from cmp.modules.jobs.domain.events import CloudEventRecord, InvalidCloudEvent


class JsonSchemaEventContractValidator:
    def __init__(self) -> None:
        schema_resource = files("cmp.modules.jobs.contracts").joinpath(
            "artifact-available.schema.json"
        )
        schema = json.loads(schema_resource.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._validators = {
            "io.cmp.artifact.available.v1": Draft202012Validator(
                schema, format_checker=FormatChecker()
            )
        }

    def validate(self, event: CloudEventRecord) -> None:
        validator = self._validators.get(event.draft.event_type)
        if validator is None:
            raise InvalidCloudEvent("event_type has no registered immutable schema")
        errors = sorted(validator.iter_errors(event.envelope()), key=str)
        if errors:
            first = errors[0]
            path = ".".join(str(item) for item in first.absolute_path)
            location = path or "event"
            raise InvalidCloudEvent(f"{location}: {first.message}")


__all__ = ["JsonSchemaEventContractValidator"]

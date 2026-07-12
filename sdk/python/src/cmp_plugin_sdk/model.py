"""Framework-free public values implemented by Python plugin packages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import UUID

if TYPE_CHECKING:
    from cmp_plugin_sdk.context import RunContext

_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_DIAGNOSTIC_CODE = re.compile(r"^CMP-[A-Z0-9]+-[0-9]{4}$")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


class ExtensionType(StrEnum):
    IMPORTER = "importer"
    PROCESSOR = "processor"
    STATISTICAL_ANALYZER = "statistical_analyzer"
    MATERIAL_MODEL = "material_model"
    CALIBRATOR = "calibrator"
    VALIDATOR = "validator"
    SOLVER_EXPORTER = "solver_exporter"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExtensionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if _DIAGNOSTIC_CODE.fullmatch(self.code) is None:
            raise ValueError("diagnostic code must use CMP-CATEGORY-0000 form")
        _trimmed("diagnostic message", self.message, 4000)
        evidence = self.evidence or {}
        canonical = json.dumps(
            evidence,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        loaded = json.loads(canonical)
        if not isinstance(loaded, dict):
            raise ValueError("diagnostic evidence must be a JSON object")
        object.__setattr__(self, "evidence", loaded)

    def document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": dict(self.evidence or {}),
        }


@dataclass(frozen=True, slots=True)
class ExtensionDescriptor:
    extension_type: ExtensionType
    capabilities: tuple[str, ...]
    sdk_api: str = "1.0"

    def __post_init__(self) -> None:
        if not self.capabilities:
            raise ValueError("extension requires at least one capability")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("extension capabilities must be sorted and unique")
        if any(_CAPABILITY.fullmatch(value) is None for value in self.capabilities):
            raise ValueError("extension capability is invalid")
        if self.sdk_api != "1.0":
            raise ValueError("this SDK supports sdk_api 1.0 only")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    accepted: bool
    diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def ok(cls) -> ValidationReport:
        return cls(True)

    @classmethod
    def reject(cls, *diagnostics: Diagnostic) -> ValidationReport:
        if not diagnostics:
            raise ValueError("rejected validation requires a diagnostic")
        return cls(False, tuple(diagnostics))


@dataclass(frozen=True, slots=True)
class ExtensionOutcome:
    status: ExtensionStatus = ExtensionStatus.SUCCEEDED
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class JobInput:
    role: str
    entity_revision_id: UUID
    artifact_id: UUID
    sha256: str
    media_type: str


@dataclass(frozen=True, slots=True)
class ExpectedOutput:
    role: str
    schema_ref: str


@dataclass(frozen=True, slots=True)
class RunnerJobSpec:
    job_id: UUID
    attempt_id: UUID
    extension_type: ExtensionType
    plugin_id: str
    plugin_version: str
    package_digest: str
    operation: str
    inputs: tuple[JobInput, ...]
    config: dict[str, Any]
    config_schema_ref: str | None
    expected_outputs: tuple[ExpectedOutput, ...]
    seed: int
    deadline: datetime
    traceparent: str
    _document_json: str

    @classmethod
    def from_validated_document(cls, document: object) -> RunnerJobSpec:
        if not isinstance(document, dict):
            raise ValueError("Job Spec must be an object")
        value = cast(dict[str, Any], document)
        extension = cast(dict[str, Any], value["extension"])
        execution = cast(dict[str, Any], value["execution"])
        raw_deadline = str(execution["deadline"])
        deadline = datetime.fromisoformat(raw_deadline.replace("Z", "+00:00"))
        inputs = tuple(
            JobInput(
                role=str(item["role"]),
                entity_revision_id=UUID(str(item["entity_revision_id"])),
                artifact_id=UUID(str(item["artifact_id"])),
                sha256=str(item["sha256"]),
                media_type=str(item["media_type"]),
            )
            for item in cast(list[dict[str, Any]], value["inputs"])
        )
        outputs = tuple(
            ExpectedOutput(str(item["role"]), str(item["schema_ref"]))
            for item in cast(list[dict[str, Any]], value["expected_outputs"])
        )
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        config = json.loads(
            json.dumps(
                value["config"],
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        if not isinstance(config, dict):
            raise ValueError("Job Spec config must be an object")
        config_ref = value.get("config_schema_ref")
        return cls(
            job_id=UUID(str(value["job_id"])),
            attempt_id=UUID(str(value["attempt_id"])),
            extension_type=ExtensionType(str(extension["type"])),
            plugin_id=str(extension["plugin_id"]),
            plugin_version=str(extension["plugin_version"]),
            package_digest=str(extension["package_digest"]),
            operation=str(value["operation"]),
            inputs=inputs,
            config=config,
            config_schema_ref=str(config_ref) if config_ref is not None else None,
            expected_outputs=outputs,
            seed=int(execution["seed"]),
            deadline=deadline,
            traceparent=str(execution["traceparent"]),
            _document_json=canonical,
        )

    def document(self) -> dict[str, Any]:
        value = json.loads(self._document_json)
        if not isinstance(value, dict):
            raise RuntimeError("canonical Job Spec ceased to be an object")
        return value


class PluginExtension(Protocol):
    def describe(self) -> ExtensionDescriptor: ...

    def validate_job(self, job: RunnerJobSpec) -> ValidationReport: ...

    def run(self, context: RunContext, job: RunnerJobSpec) -> ExtensionOutcome: ...

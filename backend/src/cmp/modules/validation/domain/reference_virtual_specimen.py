"""Non-production reference virtual-specimen validation contracts.

T-27 deliberately models only the execution boundary: a versioned one-dimensional
reference template, a frozen Plan, and a result manifest that preserves deck/log/native
result artifacts.  It does *not* execute OpenRadioss or any other solver, and it does
not make an experimental validation verdict.  T-28 owns extraction, numerical-health,
metrics, and verdicts.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

REFERENCE_TEMPLATE_KIND = "reference_uniaxial_tensile_virtual_specimen"
REFERENCE_TEMPLATE_SCHEMA_ID = "urn:cmp:validation:reference-uniaxial-virtual-specimen:1.0.0"
REFERENCE_PLAN_KIND = "reference_uniaxial_tensile_validation"
REFERENCE_PLAN_SCHEMA_ID = "urn:cmp:validation:reference-uniaxial-validation-plan:1.0.0"
REFERENCE_SCHEMA_VERSION = "1.0.0"
REFERENCE_TARGET_SOLVER = "openradioss"
REFERENCE_TARGET_VERSION = "2025"
REFERENCE_TARGET_UNIT_SYSTEM = "kg_m_s"
REFERENCE_RUNNER_ID = "cmp.reference.inline-mock-runner"
REFERENCE_RUNNER_VERSION = "1.0.0"
REFERENCE_RUNNER_DIGEST = "c7ddb0df83e2304d7f0d754f1a8b94d0774d00b9fe434db853fbb21effcd0209"
REFERENCE_RUNNER_COMMAND_ID = "reference_inline_mock"
REFERENCE_NATIVE_RESULT_SCHEMA_ID = "urn:cmp:validation:reference-native-result:1.0.0"
REFERENCE_RUN_RESULT_MANIFEST_SCHEMA_ID = "urn:cmp:validation:run-result-manifest:1.0.0"
REFERENCE_DECK_SCHEMA_ID = "urn:cmp:validation:reference-deck:1.0.0"
REFERENCE_STDOUT_SCHEMA_ID = "urn:cmp:validation:reference-runner-stdout:1.0.0"
REFERENCE_STDERR_SCHEMA_ID = "urn:cmp:validation:reference-runner-stderr:1.0.0"
REFERENCE_METRIC_PROFILE_ID = "urn:cmp:validation:reference-relative-rmse:1.0.0"
REFERENCE_EXTRACTION_PROFILE_ID = "urn:cmp:validation:reference-native-curve-extractor:1.0.0"

_LABEL = re.compile(r"^[^\x00]{1,160}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(Exception):
    """Base error for the bounded reference validation slice."""


class InvalidValidationTemplate(ValidationError, ValueError):
    """A template violates the declared non-production reference contract."""


class InvalidValidationPlan(ValidationError, ValueError):
    """A plan does not pin one compatible immutable reference tuple."""


class ValidationConflict(ValidationError):
    """A command conflicts with immutable validation inputs or run state."""


class ValidationNotFound(ValidationError):
    """A validation resource is absent or hidden by tenant scope."""


class InvalidNativeResult(ValidationError, ValueError):
    """The bounded manual native-result contract is malformed or incompatible."""


class ValidationExecutionMode(StrEnum):
    REFERENCE_INLINE_MOCK = "reference_inline_mock"
    MANUAL_ATTACH = "manual_attach"


class ValidationRunStatus(StrEnum):
    QUEUED = "queued"
    WAITING_MANUAL = "waiting_manual"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SolverTerminationStatus(StrEnum):
    NORMAL = "normal"
    ABNORMAL = "abnormal"
    NOT_AVAILABLE = "not_available"


class ReferenceRunnerOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    LICENSE_UNAVAILABLE = "license_unavailable"
    QUEUE_TIMEOUT = "queue_timeout"
    SOLVER_FAILED = "solver_failed"


@dataclass(frozen=True, slots=True)
class ReferenceVirtualSpecimenTemplateContent:
    """Explicit geometry/mesh/BC/output declarations for one reference template revision."""

    template_label: str
    gauge_length_m: float
    cross_section_area_m2: float
    axial_element_count: int
    axial_displacement_end_m: float
    output_sample_count: int
    result_extraction_profile_id: str = REFERENCE_EXTRACTION_PROFILE_ID
    metric_profile_id: str = REFERENCE_METRIC_PROFILE_ID
    template_kind: str = REFERENCE_TEMPLATE_KIND
    target_solver: str = REFERENCE_TARGET_SOLVER
    target_version: str = REFERENCE_TARGET_VERSION
    target_unit_system: str = REFERENCE_TARGET_UNIT_SYSTEM
    runner_command_id: str = REFERENCE_RUNNER_COMMAND_ID
    non_production: bool = True

    def __post_init__(self) -> None:
        _label("template_label", self.template_label, InvalidValidationTemplate)
        _positive("gauge_length_m", self.gauge_length_m)
        _positive("cross_section_area_m2", self.cross_section_area_m2)
        if not 1 <= self.axial_element_count <= 10_000:
            raise InvalidValidationTemplate("axial_element_count must be between 1 and 10000")
        _positive("axial_displacement_end_m", self.axial_displacement_end_m)
        if self.axial_displacement_end_m >= self.gauge_length_m:
            raise InvalidValidationTemplate(
                "axial_displacement_end_m must remain below gauge_length_m for this reference"
            )
        if not 2 <= self.output_sample_count <= 10_000:
            raise InvalidValidationTemplate("output_sample_count must be between 2 and 10000")
        if self.result_extraction_profile_id != REFERENCE_EXTRACTION_PROFILE_ID:
            raise InvalidValidationTemplate("unsupported reference extraction profile")
        if self.metric_profile_id != REFERENCE_METRIC_PROFILE_ID:
            raise InvalidValidationTemplate("unsupported reference metric profile")
        if self.template_kind != REFERENCE_TEMPLATE_KIND:
            raise InvalidValidationTemplate("template_kind is fixed for the reference slice")
        _target(
            self.target_solver,
            self.target_version,
            self.target_unit_system,
            error_type=InvalidValidationTemplate,
        )
        if self.runner_command_id != REFERENCE_RUNNER_COMMAND_ID:
            raise InvalidValidationTemplate(
                "only the non-shell reference_inline_mock command identifier is allowed"
            )
        if not self.non_production:
            raise InvalidValidationTemplate("reference virtual specimen must be non-production")

    def canonical(self) -> dict[str, object]:
        return {
            "template_label": self.template_label,
            "template_kind": self.template_kind,
            "geometry": {
                "gauge_length_m": self.gauge_length_m,
                "cross_section_area_m2": self.cross_section_area_m2,
            },
            "mesh": {
                "topology": "reference_1d_axial_bar",
                "axial_element_count": self.axial_element_count,
            },
            "boundary_conditions": {
                "fixed_end": "axial_displacement_zero",
                "loaded_end": "axial_displacement",
                "axial_displacement_end_m": self.axial_displacement_end_m,
            },
            "output": {
                "quantities": [
                    "engineering_strain",
                    "engineering_stress_pa",
                    "axial_reaction_force_n",
                ],
                "sample_count": self.output_sample_count,
                "extraction_profile_id": self.result_extraction_profile_id,
                "metric_profile_id": self.metric_profile_id,
            },
            "target": {
                "solver": self.target_solver,
                "version": self.target_version,
                "unit_system": self.target_unit_system,
            },
            "runner_command_id": self.runner_command_id,
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class ReferenceValidationPlanContent:
    """One immutable validation input tuple, including the future experimental selection."""

    plan_label: str
    template_id: UUID
    template_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    solver_card_id: UUID
    solver_card_revision_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    runner_id: str = REFERENCE_RUNNER_ID
    runner_version: str = REFERENCE_RUNNER_VERSION
    runner_digest: str = REFERENCE_RUNNER_DIGEST
    plan_kind: str = REFERENCE_PLAN_KIND
    non_production: bool = True

    def __post_init__(self) -> None:
        _label("plan_label", self.plan_label, InvalidValidationPlan)
        for name, value in (
            ("template_id", self.template_id),
            ("template_revision_id", self.template_revision_id),
            ("material_model_id", self.material_model_id),
            ("material_model_revision_id", self.material_model_revision_id),
            ("solver_card_id", self.solver_card_id),
            ("solver_card_revision_id", self.solver_card_revision_id),
            ("experimental_selection_id", self.experimental_selection_id),
            ("experimental_selection_revision_id", self.experimental_selection_revision_id),
        ):
            _uuid(name, value, InvalidValidationPlan)
        if self.runner_id != REFERENCE_RUNNER_ID or self.runner_version != REFERENCE_RUNNER_VERSION:
            raise InvalidValidationPlan("unsupported reference runner capability")
        if self.runner_digest != REFERENCE_RUNNER_DIGEST:
            raise InvalidValidationPlan("reference runner digest does not match the capability")
        if self.plan_kind != REFERENCE_PLAN_KIND:
            raise InvalidValidationPlan("plan_kind is fixed for the reference slice")
        if not self.non_production:
            raise InvalidValidationPlan("reference validation Plan must be non-production")

    def canonical(self) -> dict[str, object]:
        return {
            "plan_label": self.plan_label,
            "plan_kind": self.plan_kind,
            "template": {
                "id": str(self.template_id),
                "revision_id": str(self.template_revision_id),
            },
            "material_model": {
                "id": str(self.material_model_id),
                "revision_id": str(self.material_model_revision_id),
            },
            "solver_card": {
                "id": str(self.solver_card_id),
                "revision_id": str(self.solver_card_revision_id),
            },
            "experimental_selection": {
                "id": str(self.experimental_selection_id),
                "revision_id": str(self.experimental_selection_revision_id),
            },
            "runner": {
                "id": self.runner_id,
                "version": self.runner_version,
                "digest": self.runner_digest,
            },
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class ValidationArtifactReference:
    """A typed immutable Artifact pointer retained by a Result Manifest."""

    artifact_id: UUID
    sha256: str

    def __post_init__(self) -> None:
        _uuid("artifact_id", self.artifact_id, ValidationConflict)
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValidationConflict("Artifact references require a lowercase SHA-256 digest")

    def canonical(self) -> dict[str, str]:
        return {"artifact_id": str(self.artifact_id), "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ValidationRunResultManifestContent:
    """Typed common result-manifest shape for mock managed and manual execution."""

    validation_run_id: UUID
    execution_mode: ValidationExecutionMode
    solver_termination: SolverTerminationStatus
    external_job_reference: str | None
    deck: ValidationArtifactReference
    stdout: ValidationArtifactReference
    stderr: ValidationArtifactReference
    native_result: ValidationArtifactReference | None
    native_result_state: str

    def __post_init__(self) -> None:
        _uuid("validation_run_id", self.validation_run_id, ValidationConflict)
        validate_external_job_reference(self.external_job_reference)
        if self.native_result_state not in {"available", "not_available"}:
            raise ValidationConflict("native_result_state is invalid")
        if (self.native_result is None) != (self.native_result_state == "not_available"):
            raise ValidationConflict("native result state does not match its Artifact reference")
        if (
            self.execution_mode is ValidationExecutionMode.MANUAL_ATTACH
            and not self.external_job_reference
        ):
            raise ValidationConflict("manual attachment requires an external_job_reference")
        if (
            self.execution_mode is ValidationExecutionMode.REFERENCE_INLINE_MOCK
            and self.external_job_reference
        ):
            raise ValidationConflict("reference inline mock runs cannot claim an external job")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_id": REFERENCE_RUN_RESULT_MANIFEST_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "validation_run_id": str(self.validation_run_id),
            "execution_mode": self.execution_mode.value,
            "solver_termination": self.solver_termination.value,
            "external_job_reference": self.external_job_reference,
            "deck": self.deck.canonical(),
            "stdout": self.stdout.canonical(),
            "stderr": self.stderr.canonical(),
            "native_result": self.native_result.canonical() if self.native_result else None,
            "native_result_state": self.native_result_state,
        }


@dataclass(frozen=True, slots=True)
class NativeResultDescriptor:
    """Small, parsed native-result facts retained without performing T-28 extraction."""

    solver_termination: SolverTerminationStatus
    point_count: int


@dataclass(frozen=True, slots=True)
class ReferenceRunnerTransition:
    status: ValidationRunStatus
    failure_code: str | None
    termination: SolverTerminationStatus
    native_result_available: bool


def reference_virtual_specimen_template_canonical(
    value: ReferenceVirtualSpecimenTemplateContent,
) -> dict[str, object]:
    return value.canonical()


def reference_validation_plan_canonical(value: ReferenceValidationPlanContent) -> dict[str, object]:
    return value.canonical()


def validate_external_job_reference(value: str | None) -> str | None:
    """Accept an opaque external job identifier, never an executable command string."""

    if value is not None and _REFERENCE.fullmatch(value) is None:
        raise ValidationConflict("external_job_reference contains unsupported characters")
    return value


def result_manifest_bytes(value: ValidationRunResultManifestContent) -> bytes:
    """Canonical immutable result-manifest bytes suitable for an Artifact."""

    return canonical_json_bytes(value.canonical())


def result_manifest_sha256(value: ValidationRunResultManifestContent) -> str:
    return content_sha256(value.canonical())


def map_reference_runner_outcome(outcome: ReferenceRunnerOutcome) -> ReferenceRunnerTransition:
    """Map explicit mock outcomes; no shell command or external status is interpreted here."""

    if outcome is ReferenceRunnerOutcome.SUCCEEDED:
        return ReferenceRunnerTransition(
            ValidationRunStatus.SUCCEEDED,
            None,
            SolverTerminationStatus.NORMAL,
            True,
        )
    if outcome is ReferenceRunnerOutcome.LICENSE_UNAVAILABLE:
        return ReferenceRunnerTransition(
            ValidationRunStatus.FAILED,
            "license_unavailable",
            SolverTerminationStatus.NOT_AVAILABLE,
            False,
        )
    if outcome is ReferenceRunnerOutcome.QUEUE_TIMEOUT:
        return ReferenceRunnerTransition(
            ValidationRunStatus.FAILED,
            "queue_timeout",
            SolverTerminationStatus.NOT_AVAILABLE,
            False,
        )
    return ReferenceRunnerTransition(
        ValidationRunStatus.FAILED,
        "solver_failed",
        SolverTerminationStatus.ABNORMAL,
        False,
    )


def render_reference_deck(
    *,
    run_id: UUID,
    template: ReferenceVirtualSpecimenTemplateContent,
    card_text: str,
    card_sha256: str,
) -> bytes:
    """Render a deterministic *reference deck assembly*, never a shell command or solver claim."""

    _uuid("run_id", run_id, ValidationConflict)
    if _SHA256.fullmatch(card_sha256) is None:
        raise ValidationConflict("solver card SHA-256 is invalid")
    if not card_text or len(card_text) > 20_000:
        raise ValidationConflict("reference card text is unavailable for deck assembly")
    lines = (
        "# CMP non-production reference virtual-specimen deck assembly",
        f"# schema: {REFERENCE_DECK_SCHEMA_ID}",
        f"# run_id: {run_id}",
        f"# source_solver_card_sha256: {card_sha256}",
        "# This artifact is intentionally not a production solver deck and is never executed here.",
        f"# geometry.gauge_length_m: {template.gauge_length_m:.12g}",
        f"# geometry.cross_section_area_m2: {template.cross_section_area_m2:.12g}",
        f"# mesh.axial_element_count: {template.axial_element_count}",
        f"# boundary.axial_displacement_end_m: {template.axial_displacement_end_m:.12g}",
        f"# output.sample_count: {template.output_sample_count}",
        "# ---- frozen reference card follows ----",
        card_text.rstrip("\n"),
        "# ---- end frozen reference card ----",
        "",
    )
    return "\n".join(lines).encode("utf-8")


def reference_mock_native_result_bytes(
    *,
    template: ReferenceVirtualSpecimenTemplateContent,
    youngs_modulus_pa: float,
) -> bytes:
    """Create deterministic synthetic native output for the T-27 mock runner only."""

    _positive("youngs_modulus_pa", youngs_modulus_pa)
    endpoint_strain = template.axial_displacement_end_m / template.gauge_length_m
    points = tuple(
        {
            "engineering_strain": endpoint_strain * ordinal / (template.output_sample_count - 1),
            "engineering_stress_pa": (
                youngs_modulus_pa * endpoint_strain * ordinal / (template.output_sample_count - 1)
            ),
        }
        for ordinal in range(template.output_sample_count)
    )
    return canonical_json_bytes(
        {
            "schema_id": REFERENCE_NATIVE_RESULT_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "source": "reference_inline_mock",
            "non_production": True,
            "target": {
                "solver": template.target_solver,
                "version": template.target_version,
                "unit_system": template.target_unit_system,
            },
            "solver_termination": SolverTerminationStatus.NORMAL.value,
            "points": points,
        }
    )


def validate_reference_native_result_bytes(
    value: bytes,
    *,
    template: ReferenceVirtualSpecimenTemplateContent,
) -> NativeResultDescriptor:
    """Validate a small reference native-result envelope without extracting a response verdict."""

    if not 1 <= len(value) <= 1_000_000:
        raise InvalidNativeResult("native result must contain between 1 and 1000000 bytes")
    try:
        document = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidNativeResult("reference native result must be UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise InvalidNativeResult("reference native result must be an object")
    if (
        document.get("schema_id") != REFERENCE_NATIVE_RESULT_SCHEMA_ID
        or document.get("schema_version") != REFERENCE_SCHEMA_VERSION
        or document.get("non_production") is not True
    ):
        raise InvalidNativeResult("native result schema is not the supported reference contract")
    target = document.get("target")
    if not isinstance(target, dict) or (
        target.get("solver"),
        target.get("version"),
        target.get("unit_system"),
    ) != (template.target_solver, template.target_version, template.target_unit_system):
        raise InvalidNativeResult("native result target does not match the pinned Template")
    raw_termination = document.get("solver_termination")
    if not isinstance(raw_termination, str):
        raise InvalidNativeResult("native result termination status is invalid")
    try:
        termination = SolverTerminationStatus(raw_termination)
    except ValueError as error:
        raise InvalidNativeResult("native result termination status is invalid") from error
    if termination is SolverTerminationStatus.NOT_AVAILABLE:
        raise InvalidNativeResult("a supplied native result cannot use not_available termination")
    points = document.get("points")
    if not isinstance(points, list) or not 2 <= len(points) <= 10_000:
        raise InvalidNativeResult("native result points must contain between 2 and 10000 entries")
    previous_strain: float | None = None
    for point in points:
        if not isinstance(point, dict):
            raise InvalidNativeResult("native result points must be objects")
        strain = point.get("engineering_strain")
        stress = point.get("engineering_stress_pa")
        if (
            isinstance(strain, bool)
            or isinstance(stress, bool)
            or not isinstance(strain, (int, float))
            or not isinstance(stress, (int, float))
            or not math.isfinite(float(strain))
            or not math.isfinite(float(stress))
            or float(strain) < 0
            or float(stress) < 0
        ):
            raise InvalidNativeResult("native result points must contain finite SI stress/strain")
        if previous_strain is not None and float(strain) < previous_strain:
            raise InvalidNativeResult("native result engineering strain must be nondecreasing")
        previous_strain = float(strain)
    return NativeResultDescriptor(termination, len(points))


def reference_runner_stdout(*, outcome: ReferenceRunnerOutcome) -> bytes:
    return canonical_json_bytes(
        {
            "schema_id": REFERENCE_STDOUT_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "runner_id": REFERENCE_RUNNER_ID,
            "outcome": outcome.value,
            "non_production": True,
        }
    )


def reference_runner_stderr(*, outcome: ReferenceRunnerOutcome) -> bytes:
    detail = {
        ReferenceRunnerOutcome.SUCCEEDED: "no stderr emitted",
        ReferenceRunnerOutcome.LICENSE_UNAVAILABLE: "synthetic license unavailable",
        ReferenceRunnerOutcome.QUEUE_TIMEOUT: "synthetic queue timeout",
        ReferenceRunnerOutcome.SOLVER_FAILED: "synthetic solver failure",
    }[outcome]
    return canonical_json_bytes(
        {
            "schema_id": REFERENCE_STDERR_SCHEMA_ID,
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "detail": detail,
            "non_production": True,
        }
    )


def _uuid(name: str, value: UUID, error_type: type[Exception]) -> None:
    if value.int == 0:
        raise error_type(f"{name} must be non-zero")


def _label(name: str, value: str, error_type: type[Exception]) -> None:
    if value != value.strip() or _LABEL.fullmatch(value) is None:
        raise error_type(f"{name} must be trimmed and contain 1..160 characters")


def _positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise InvalidValidationTemplate(f"{name} must be finite and positive")


def _target(
    solver: str,
    version: str,
    unit_system: str,
    *,
    error_type: type[Exception],
) -> None:
    if (solver, version, unit_system) != (
        REFERENCE_TARGET_SOLVER,
        REFERENCE_TARGET_VERSION,
        REFERENCE_TARGET_UNIT_SYSTEM,
    ):
        raise error_type("the reference template supports only the frozen OpenRadioss target tuple")

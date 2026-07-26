"""Commit common pipeline previews as exact, immutable Processing Output evidence (T-53)."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    GovernedTestDataSource,
)
from cmp.modules.datasets.domain.canonical_test_data import parse_canonical_test_data
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.mapping_profiles import MappingProfileService
from cmp.modules.processing.domain.common_pipeline import (
    CommonPipelineError,
    CurveStage,
    ProcessingPreview,
    ProcessingStep,
    ScalarResult,
    preview_pipeline,
    processing_preview_canonical,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import (
    RevisionRecord,
    TenantScope,
    canonical_json_bytes,
)

__all__ = ["CommonPipelineError"]

PROCESSING_OUTPUT_AGGREGATE_TYPE = "processing.common_output"
PROCESSING_OUTPUT_SCHEMA_ID = "urn:cmp:processing:common-output:1.2.0"
PROCESSING_OUTPUT_SCHEMA_VERSION = "1.2.0"
PROCESSING_OUTPUT_MEDIA_TYPE = "application/vnd.cmp.processing-output+json"


def _bounded_trimmed_text(name: str, value: str, limit: int = 160) -> None:
    if (
        not value
        or value != value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise CommonPipelineError(
            f"{name} must be trimmed and contain 1..{limit} characters"
        )


class ProcessingOutputNotFound(CommonPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class ExactRevisionPin:
    aggregate_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessingWorkupOverride:
    """A manual physical-workup decision that affected an executed output.

    This is deliberately separate from strict method options: the pipeline only
    receives options it understands, while the immutable output records the
    engineer-entered quantity, its canonical form, and why it was used.
    """

    kind: Literal["youngs_modulus", "necking_boundary"]
    original_value: float
    original_unit: str
    canonical_value: float
    canonical_unit: str
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in {"youngs_modulus", "necking_boundary"}:
            raise CommonPipelineError("unsupported workup override kind")
        if not math.isfinite(self.original_value) or not math.isfinite(self.canonical_value):
            raise CommonPipelineError("workup override values must be finite")
        if not self.original_unit.strip() or not self.canonical_unit.strip():
            raise CommonPipelineError("workup overrides require original and canonical units")
        if not self.reason.strip() or len(self.reason) > 2000:
            raise CommonPipelineError("workup override reason must contain 1..2000 characters")
        if self.kind == "youngs_modulus":
            if self.original_value <= 0 or self.canonical_value <= 0:
                raise CommonPipelineError("Young's modulus override values must be positive")
            if self.canonical_unit != "Pa":
                raise CommonPipelineError("Young's modulus overrides must use canonical Pa")
        if self.kind == "necking_boundary" and self.canonical_unit != "observed-point-index":
            raise CommonPipelineError(
                "necking-boundary overrides must use canonical observed-point-index"
            )


@dataclass(frozen=True, slots=True)
class FitDecisionParameter:
    name: str
    value: float
    unit: str
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        _bounded_trimmed_text("fit-decision parameter name", self.name)
        _bounded_trimmed_text("fit-decision parameter unit", self.unit)
        if not math.isfinite(self.value):
            raise CommonPipelineError("fit-decision parameter values must be finite")
        if self.lower is not None and (not math.isfinite(self.lower) or self.lower > self.value):
            raise CommonPipelineError("fit-decision parameter lower bound is invalid")
        if self.upper is not None and (not math.isfinite(self.upper) or self.upper < self.value):
            raise CommonPipelineError("fit-decision parameter upper bound is invalid")


@dataclass(frozen=True, slots=True)
class FitDecisionParameterSet:
    law: str
    parameters: tuple[FitDecisionParameter, ...]

    def __post_init__(self) -> None:
        _bounded_trimmed_text("fit-decision parameter-set law", self.law)
        if not self.parameters:
            raise CommonPipelineError("fit-decision parameter sets require a law and parameters")
        if len({parameter.name for parameter in self.parameters}) != len(self.parameters):
            raise CommonPipelineError("fit-decision parameter names must be unique per law")


@dataclass(frozen=True, slots=True)
class FitDecisionSnapshot:
    """Immutable, human-selected fit identity; never a recipe default or recommendation."""

    candidate_key: str
    mode: Literal["single", "blend"]
    primary_law: str
    secondary_law: str | None
    primary_weight: float | None
    parameter_sets: tuple[FitDecisionParameterSet, ...]
    fit_minimum: float
    fit_maximum: float
    extrapolation_maximum: float | None
    extrapolation_policy: str
    metric_definition: str
    metric_value: float
    requested_term_policy: str | None
    actual_term_count: int | None
    selection_reason: str
    warning_acknowledged: bool

    def __post_init__(self) -> None:
        _bounded_trimmed_text("fit-decision candidate key", self.candidate_key)
        _bounded_trimmed_text("fit-decision primary law", self.primary_law)
        _bounded_trimmed_text(
            "fit-decision extrapolation policy", self.extrapolation_policy
        )
        _bounded_trimmed_text("fit-decision metric definition", self.metric_definition)
        if self.secondary_law is not None:
            _bounded_trimmed_text("fit-decision secondary law", self.secondary_law)
        if self.requested_term_policy is not None:
            _bounded_trimmed_text(
                "fit-decision requested term policy", self.requested_term_policy
            )
        if (
            not all(
                math.isfinite(value)
                for value in (self.fit_minimum, self.fit_maximum, self.metric_value)
            )
            or self.fit_minimum >= self.fit_maximum
        ):
            raise CommonPipelineError("fit-decision fit range or metric is invalid")
        if self.extrapolation_maximum is not None and (
            not math.isfinite(self.extrapolation_maximum)
            or self.extrapolation_maximum < self.fit_maximum
        ):
            raise CommonPipelineError("fit-decision extrapolation maximum is invalid")
        _bounded_trimmed_text(
            "fit-decision selection reason", self.selection_reason, 2000
        )
        if self.mode == "single":
            if (
                self.secondary_law is not None
                or self.primary_weight is not None
                or len(self.parameter_sets) != 1
            ):
                raise CommonPipelineError(
                    "single-law fit decision must have one parameter set and no blend fields"
                )
        else:
            if (
                not self.secondary_law
                or self.secondary_law == self.primary_law
                or self.primary_weight is None
                or not 0 < self.primary_weight < 1
                or len(self.parameter_sets) != 2
            ):
                raise CommonPipelineError(
                    "blend fit decision requires distinct laws, ratio, and both parameter sets"
                )
        expected_laws = (
            (self.primary_law,)
            if self.mode == "single"
            else (self.primary_law, str(self.secondary_law))
        )
        if tuple(item.law for item in self.parameter_sets) != expected_laws:
            raise CommonPipelineError(
                "fit-decision parameter sets must follow the selected law identity"
            )
        if self.actual_term_count is not None and (
            not 1 <= self.actual_term_count <= 10 or self.mode != "single"
        ):
            raise CommonPipelineError(
                "actual polymer term count requires a single-law fit decision"
            )


def validate_workup_overrides(
    steps: tuple[ProcessingStep, ...],
    overrides: tuple[ProcessingWorkupOverride, ...],
) -> None:
    """Bind manual workup evidence to the exact options about to be executed."""

    by_kind: dict[str, ProcessingWorkupOverride] = {}
    for override in overrides:
        if override.kind in by_kind:
            raise CommonPipelineError("a Processing Output may contain one override per kind")
        by_kind[override.kind] = override

    manual_modulus = tuple(
        step
        for step in steps
        if step.method_id == "metal.elastic_modulus" and step.options.get("method") == "manual"
    )
    manual_necking = tuple(
        step
        for step in steps
        if step.method_id == "metal.engineering_to_true_plastic"
        and step.options.get("necking_policy") == "manual_index"
    )
    if len(manual_modulus) > 1 or len(manual_necking) > 1:
        raise CommonPipelineError(
            "Processing Output workup evidence is ambiguous across repeated steps"
        )

    _validate_youngs_modulus_override(
        manual_modulus[0] if manual_modulus else None,
        by_kind.get("youngs_modulus"),
    )
    _validate_necking_boundary_override(
        manual_necking[0] if manual_necking else None,
        by_kind.get("necking_boundary"),
    )


_FIT_METHODS = {
    "metal.hardening_fit_extrapolate",
    "polymer.prony_fit_compare",
    "polymer.dma_prony_fit_compare",
}


def validate_fit_decision(
    steps: tuple[ProcessingStep, ...],
    preview: ProcessingPreview,
    decision: FitDecisionSnapshot | None,
) -> None:
    """Bind a saved decision to the just-recomputed candidate stage, never UI labels."""

    matches = [
        (ordinal, step)
        for ordinal, step in enumerate(steps, start=1)
        if step.method_id in _FIT_METHODS
    ]
    if not matches:
        if decision is not None:
            raise CommonPipelineError("fit decision is only allowed when committing a fit step")
        return
    if len(matches) != 1:
        raise CommonPipelineError("a Processing Output may commit exactly one fit step")
    if decision is None:
        raise CommonPipelineError(
            "a Processing Output with a fit step requires an explicit fit decision"
        )
    ordinal, step = matches[0]
    stage = preview.stages[ordinal]
    scalar = {item.key: item for item in stage.scalar_results}
    if step.method_id == "metal.hardening_fit_extrapolate":
        _validate_metal_fit_decision(step, scalar, decision)
    else:
        _validate_polymer_fit_decision(
            step, stage, preview.independent_quantity, decision
        )


def _same_fit_value(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10):
        raise CommonPipelineError(f"fit decision {label} differs from recomputed fit evidence")


def _option_number(step: ProcessingStep, key: str) -> float:
    value = step.options.get(key)
    return _finite_number(value, key)


def _validate_metal_fit_decision(
    step: ProcessingStep, scalar: dict[str, ScalarResult], decision: FitDecisionSnapshot
) -> None:
    families = tuple(str(item) for item in step.options.get("families", []))
    primary = str(step.options.get("primary_family", ""))
    secondary = str(step.options.get("secondary_family", ""))
    weight = _option_number(step, "primary_weight")
    if decision.primary_law not in families:
        raise CommonPipelineError("fit decision primary law is not a recomputed candidate")
    if decision.mode == "single":
        if decision.candidate_key != decision.primary_law:
            raise CommonPipelineError("single-law fit decision key must identify its selected law")
        laws: tuple[str, ...] = (decision.primary_law,)
    else:
        if decision.primary_law != primary or decision.secondary_law != secondary:
            raise CommonPipelineError("blend decision laws differ from the executed fit")
        if decision.candidate_key != f"{primary}+{secondary}":
            raise CommonPipelineError("blend decision key must identify both selected laws")
        if decision.primary_weight is None:
            raise CommonPipelineError("blend decision requires a primary ratio")
        _same_fit_value(decision.primary_weight, weight, "blend ratio")
        laws = (primary, secondary)
    _same_fit_value(decision.fit_minimum, _option_number(step, "fit_minimum_strain"), "minimum")
    _same_fit_value(decision.fit_maximum, _option_number(step, "fit_maximum_strain"), "maximum")
    if decision.extrapolation_maximum is None:
        raise CommonPipelineError("metal fit decision requires an extrapolation maximum")
    _same_fit_value(
        float(decision.extrapolation_maximum),
        _option_number(step, "extrapolation_maximum_strain"),
        "extrapolation maximum",
    )
    if decision.extrapolation_policy != "bounded":
        raise CommonPipelineError("metal fit decision extrapolation policy must be bounded")
    if len(decision.parameter_sets) != len(laws):
        raise CommonPipelineError("fit decision parameter sets do not match selected metal laws")
    for parameter_set, law in zip(decision.parameter_sets, laws, strict=True):
        if parameter_set.law != law:
            raise CommonPipelineError("fit decision parameter-set law differs from selected law")
        expected_parameter_names = {
            key.removeprefix(f"{law}.parameter.")
            for key in scalar
            if key.startswith(f"{law}.parameter.")
            and not key.endswith((".lower", ".upper", ".initial"))
        }
        supplied_parameter_names = {parameter.name for parameter in parameter_set.parameters}
        if supplied_parameter_names != expected_parameter_names:
            raise CommonPipelineError(
                "fit decision parameter set is incomplete or contains unknown parameters"
            )
        for parameter in parameter_set.parameters:
            item = scalar.get(f"{law}.parameter.{parameter.name}")
            lower = scalar.get(f"{law}.parameter.{parameter.name}.lower")
            upper = scalar.get(f"{law}.parameter.{parameter.name}.upper")
            if not item or not lower or not upper:
                raise CommonPipelineError(
                    "fit decision parameter is not present in recomputed evidence"
                )
            if parameter.lower is None or parameter.upper is None:
                raise CommonPipelineError("metal fit decision parameters require recomputed bounds")
            _same_fit_value(parameter.value, item.value, parameter.name)
            _same_fit_value(float(parameter.lower), lower.value, parameter.name)
            _same_fit_value(float(parameter.upper), upper.value, parameter.name)
    metric = scalar.get(f"{decision.primary_law}.relative_rmse")
    if not metric or decision.metric_definition != "relative_rmse":
        raise CommonPipelineError(
            "fit decision metric definition is not the recomputed metal objective"
        )
    _same_fit_value(decision.metric_value, metric.value, "metric")


def _validate_polymer_fit_decision(
    step: ProcessingStep,
    stage: CurveStage,
    independent_quantity: str,
    decision: FitDecisionSnapshot,
) -> None:
    scalar = {item.key: item for item in stage.scalar_results}
    actual = scalar.get("prony_selected_term_count")
    if not actual:
        raise CommonPipelineError(
            "recomputed polymer fit did not produce an actual selected term count"
        )
    if not float(actual.value).is_integer():
        raise CommonPipelineError(
            "recomputed polymer fit produced a non-integer selected term count"
        )
    actual_count = int(actual.value)
    if decision.mode != "single" or decision.primary_law != "generalized_maxwell":
        raise CommonPipelineError(
            "polymer fit decision must identify one generalized-Maxwell result"
        )
    if (
        decision.actual_term_count != actual_count
        or decision.candidate_key != f"prony:{actual_count}"
    ):
        raise CommonPipelineError(
            "polymer decision must use the server-selected term result identity"
        )
    if decision.requested_term_policy != str(step.options.get("selection_mode")):
        raise CommonPipelineError(
            "polymer requested term policy differs from executed input intent"
        )
    if (
        decision.extrapolation_policy != "observed_only"
        or decision.extrapolation_maximum is not None
    ):
        raise CommonPipelineError("polymer decision must retain the observed-only range policy")
    independent = next(
        (item for item in stage.series if item.quantity == independent_quantity),
        None,
    )
    if independent is None or len(independent.values) < 2:
        raise CommonPipelineError(
            "polymer decision requires the recomputed observed independent range"
        )
    _same_fit_value(decision.fit_minimum, min(independent.values), "minimum")
    _same_fit_value(decision.fit_maximum, max(independent.values), "maximum")
    expected_parameter_keys = (
        "prony_equilibrium_modulus",
        *(
            key
            for ordinal in range(1, actual_count + 1)
            for key in (
                f"prony_g_ratio_{ordinal}",
                f"prony_relaxation_time_{ordinal}",
            )
        ),
    )
    parameter_set = decision.parameter_sets[0]
    supplied = {parameter.name: parameter for parameter in parameter_set.parameters}
    if set(supplied) != set(expected_parameter_keys):
        raise CommonPipelineError(
            "polymer decision parameters differ from the actual server result"
        )
    for key in expected_parameter_keys:
        evidence = scalar.get(key)
        parameter = supplied[key]
        if (
            evidence is None
            or parameter.unit != evidence.unit
            or parameter.lower is not None
            or parameter.upper is not None
        ):
            raise CommonPipelineError(
                "polymer decision parameter units or bounds differ from recomputed evidence"
            )
        _same_fit_value(parameter.value, evidence.value, key)
    metric = scalar.get(f"prony_{actual_count}_normalized_rmse")
    if not metric or decision.metric_definition != "normalized_rmse":
        raise CommonPipelineError("polymer decision metric differs from the actual server result")
    _same_fit_value(decision.metric_value, metric.value, "metric")


def _validate_youngs_modulus_override(
    step: ProcessingStep | None, override: ProcessingWorkupOverride | None
) -> None:
    if step is None:
        if override is not None:
            raise CommonPipelineError(
                "Young's modulus workup override requires an executed manual modulus step"
            )
        return
    if override is None:
        raise CommonPipelineError(
            "an executed manual Young's modulus step requires workup provenance"
        )
    if override.canonical_unit != "Pa" or override.original_unit not in {"GPa", "MPa"}:
        raise CommonPipelineError(
            "Young's modulus provenance requires GPa or MPa original unit and Pa"
        )
    executed = _finite_number(step.options.get("manual_modulus_pa"), "manual_modulus_pa")
    expected = override.original_value * (1e9 if override.original_unit == "GPa" else 1e6)
    if not _same_quantity(override.canonical_value, executed) or not _same_quantity(
        expected, override.canonical_value
    ):
        raise CommonPipelineError(
            "Young's modulus workup provenance must match the executed manual_modulus_pa"
        )


def _validate_necking_boundary_override(
    step: ProcessingStep | None, override: ProcessingWorkupOverride | None
) -> None:
    if step is None:
        if override is not None:
            raise CommonPipelineError(
                "necking-boundary workup override requires an executed manual-index step"
            )
        return
    if override is None:
        raise CommonPipelineError("an executed manual necking boundary requires workup provenance")
    if (
        override.original_unit != "observed-point-index"
        or override.canonical_unit != "observed-point-index"
    ):
        raise CommonPipelineError("necking-boundary provenance requires observed-point-index units")
    if (
        not float(override.original_value).is_integer()
        or not float(override.canonical_value).is_integer()
        or override.original_value < 0
        or override.canonical_value < 0
        or override.original_value != override.canonical_value
    ):
        raise CommonPipelineError(
            "necking-boundary provenance must be one nonnegative observed point index"
        )
    executed = step.options.get("manual_necking_index")
    if isinstance(executed, bool) or not isinstance(executed, int) or executed < 0:
        raise CommonPipelineError("manual_necking_index must be a nonnegative integer")
    if int(override.canonical_value) != executed:
        raise CommonPipelineError(
            "necking-boundary workup provenance must match the executed manual_necking_index"
        )


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CommonPipelineError(f"{label} must be a finite number")
    return float(value)


def _same_quantity(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-6)


@dataclass(frozen=True, slots=True)
class ProcessingOutputContent:
    label: str
    source_document: ExactRevisionPin
    source_document_sha256: str
    source_canonical_artifact_sha256: str
    mapping_profile: ExactRevisionPin
    mapping_profile_sha256: str
    steps: tuple[ProcessingStep, ...]
    independent_quantity: str
    stage_count: int
    final_point_count: int
    output_artifact_id: UUID
    output_sha256: str
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = ()
    fit_decision: FitDecisionSnapshot | None = None
    export_provenance: GovernedTestDataSource | None = None

    def __post_init__(self) -> None:
        if not self.label.strip() or len(self.label) > 200:
            raise CommonPipelineError("Processing Output label must contain 1..200 characters")
        if not self.steps:
            raise CommonPipelineError("committed Processing Output requires at least one step")
        if self.stage_count != len(self.steps) + 1 or self.final_point_count < 2:
            raise CommonPipelineError("Processing Output stage or point count is inconsistent")
        if len({override.kind for override in self.workup_overrides}) != len(self.workup_overrides):
            raise CommonPipelineError("a Processing Output may contain one override per kind")


@dataclass(frozen=True, slots=True)
class ProcessingOutputSnapshot:
    id: UUID
    current: RevisionRecord
    content: ProcessingOutputContent


@dataclass(frozen=True, slots=True)
class ProcessingOutputPreflight:
    source_document_sha256: str
    source_canonical_artifact_sha256: str
    mapping_profile_sha256: str
    preview: ProcessingPreview
    export_provenance: GovernedTestDataSource | None = None


@dataclass(frozen=True, slots=True)
class CommitProcessingOutput:
    classification: DataClassification
    label: str
    source_document: ExactRevisionPin
    mapping_profile: ExactRevisionPin
    steps: tuple[ProcessingStep, ...]
    change_reason: str
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = ()
    fit_decision: FitDecisionSnapshot | None = None


class ProcessingOutputRepository(Protocol):
    def output_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessingOutputContent]: ...

    def get_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> ProcessingOutputSnapshot: ...

    def list_outputs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]: ...


def processing_output_content_canonical(value: ProcessingOutputContent) -> dict[str, object]:
    return {
        "label": value.label,
        "source_document": {
            "aggregate_id": str(value.source_document.aggregate_id),
            "revision_id": str(value.source_document.revision_id),
        },
        "source_document_sha256": value.source_document_sha256,
        "source_canonical_artifact_sha256": value.source_canonical_artifact_sha256,
        "mapping_profile": {
            "aggregate_id": str(value.mapping_profile.aggregate_id),
            "revision_id": str(value.mapping_profile.revision_id),
        },
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "steps": [
            {
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options": step.options,
            }
            for step in value.steps
        ],
        "independent_quantity": value.independent_quantity,
        "stage_count": value.stage_count,
        "final_point_count": value.final_point_count,
        "output_artifact_id": str(value.output_artifact_id),
        "output_sha256": value.output_sha256,
        "workup_overrides": [
            {
                "kind": override.kind,
                "original_value": override.original_value,
                "original_unit": override.original_unit,
                "canonical_value": override.canonical_value,
                "canonical_unit": override.canonical_unit,
                "reason": override.reason,
            }
            for override in value.workup_overrides
        ],
        "fit_decision": fit_decision_canonical(value.fit_decision),
        "export_provenance": _export_provenance_canonical(value.export_provenance),
    }


def fit_decision_canonical(value: FitDecisionSnapshot | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "candidate_key": value.candidate_key,
        "mode": value.mode,
        "primary_law": value.primary_law,
        "secondary_law": value.secondary_law,
        "primary_weight": value.primary_weight,
        "parameter_sets": [
            {
                "law": parameter_set.law,
                "parameters": [
                    {
                        "name": parameter.name,
                        "value": parameter.value,
                        "unit": parameter.unit,
                        "lower": parameter.lower,
                        "upper": parameter.upper,
                    }
                    for parameter in parameter_set.parameters
                ],
            }
            for parameter_set in value.parameter_sets
        ],
        "fit_minimum": value.fit_minimum,
        "fit_maximum": value.fit_maximum,
        "extrapolation_maximum": value.extrapolation_maximum,
        "extrapolation_policy": value.extrapolation_policy,
        "metric_definition": value.metric_definition,
        "metric_value": value.metric_value,
        "requested_term_policy": value.requested_term_policy,
        "actual_term_count": value.actual_term_count,
        "selection_reason": value.selection_reason,
        "warning_acknowledged": value.warning_acknowledged,
    }


def _export_provenance_canonical(value: GovernedTestDataSource | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "material": {
            "aggregate_id": str(value.material.aggregate_id),
            "revision_id": str(value.material.revision_id),
        },
        "material_state": {
            "aggregate_id": str(value.material_state.aggregate_id),
            "revision_id": str(value.material_state.revision_id),
        },
        "test_run": {
            "aggregate_id": str(value.test_run.aggregate_id),
            "revision_id": str(value.test_run.revision_id),
        },
    }


def processing_output_document(
    *,
    output_id: UUID,
    source: ExactRevisionPin,
    source_canonical_sha256: str,
    profile: ExactRevisionPin,
    steps: tuple[ProcessingStep, ...],
    preview: ProcessingPreview,
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = (),
    fit_decision: FitDecisionSnapshot | None = None,
    export_provenance: GovernedTestDataSource | None = None,
) -> dict[str, object]:
    return {
        "document_type": "cmp.processing-output",
        "document_version": PROCESSING_OUTPUT_SCHEMA_VERSION,
        "output_id": str(output_id),
        "source_document": {
            "aggregate_id": str(source.aggregate_id),
            "revision_id": str(source.revision_id),
        },
        "source_canonical_artifact_sha256": source_canonical_sha256,
        "mapping_profile": {
            "aggregate_id": str(profile.aggregate_id),
            "revision_id": str(profile.revision_id),
        },
        "steps": [
            {
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options": step.options,
            }
            for step in steps
        ],
        "workup_overrides": [
            {
                "kind": override.kind,
                "original_value": override.original_value,
                "original_unit": override.original_unit,
                "canonical_value": override.canonical_value,
                "canonical_unit": override.canonical_unit,
                "reason": override.reason,
            }
            for override in workup_overrides
        ],
        "fit_decision": fit_decision_canonical(fit_decision),
        "export_provenance": _export_provenance_canonical(export_provenance),
        "result": processing_preview_canonical(preview),
    }


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise CommonPipelineError("authorization decision lacks Processing Output capability")


class CommonProcessingOutputService:
    def __init__(
        self,
        *,
        repository: ProcessingOutputRepository,
        test_data: CanonicalTestDataService,
        profiles: MappingProfileService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._test_data = test_data
        self._profiles = profiles
        self._artifacts = artifacts
        self._id = id_factory

    async def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitProcessingOutput,
    ) -> ProcessingOutputPreflight:
        """Validate exact inputs and execute without persisting an output."""

        _require(context, decision, Permission.PROCESSING_EXECUTE)
        validate_workup_overrides(command.steps, command.workup_overrides)
        source_snapshot, source_bytes = await self._test_data.export_document(
            context,
            decision,
            command.source_document.aggregate_id,
            command.source_document.revision_id,
        )
        profile_snapshot = self._profiles.get_profile_revision(
            context,
            decision,
            command.mapping_profile.aggregate_id,
            command.mapping_profile.revision_id,
        )
        if (
            source_snapshot.current.scope.classification != command.classification.value
            or profile_snapshot.current.scope.classification != command.classification.value
        ):
            raise CommonPipelineError(
                "Processing Output classification must match both exact input revisions"
            )
        document = parse_canonical_test_data(json.loads(source_bytes))
        preview = preview_pipeline(document, profile_snapshot.content, command.steps)
        validate_fit_decision(command.steps, preview, command.fit_decision)
        if preview.mapping_profile_sha256 != profile_snapshot.content.digest:
            raise CommonPipelineError("Mapping Profile digest pin differs from executed profile")
        return ProcessingOutputPreflight(
            source_document_sha256=preview.source_document_sha256,
            source_canonical_artifact_sha256=source_snapshot.content.canonical_sha256,
            mapping_profile_sha256=preview.mapping_profile_sha256,
            preview=preview,
            export_provenance=source_snapshot.content.governed_source,
        )

    async def commit(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitProcessingOutput,
    ) -> ProcessingOutputSnapshot:
        resolved = await self.preflight(context, decision, command)
        preview = resolved.preview
        output_id = self._id()
        output_bytes = canonical_json_bytes(
            processing_output_document(
                output_id=output_id,
                source=command.source_document,
                source_canonical_sha256=resolved.source_canonical_artifact_sha256,
                profile=command.mapping_profile,
                steps=command.steps,
                preview=preview,
                workup_overrides=command.workup_overrides,
                fit_decision=command.fit_decision,
                export_provenance=resolved.export_provenance,
            )
        )
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=command.classification,
            artifact_role="processing.common-output-json",
            schema_ref=PROCESSING_OUTPUT_SCHEMA_ID,
            media_type=PROCESSING_OUTPUT_MEDIA_TYPE,
            value=output_bytes,
            idempotency_key=f"common-processing-output:{output_id}",
        )
        content = ProcessingOutputContent(
            label=command.label,
            source_document=command.source_document,
            source_document_sha256=preview.source_document_sha256,
            source_canonical_artifact_sha256=resolved.source_canonical_artifact_sha256,
            mapping_profile=command.mapping_profile,
            mapping_profile_sha256=preview.mapping_profile_sha256,
            steps=command.steps,
            independent_quantity=preview.independent_quantity,
            stage_count=len(preview.stages),
            final_point_count=preview.stages[-1].point_count,
            output_artifact_id=artifact.artifact.id,
            output_sha256=artifact.artifact.sha256,
            workup_overrides=command.workup_overrides,
            fit_decision=command.fit_decision,
            export_provenance=resolved.export_provenance,
        )
        record = RevisionService(
            aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
            store=self._repository.output_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=output_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=PROCESSING_OUTPUT_SCHEMA_ID,
                schema_version=PROCESSING_OUTPUT_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingOutputSnapshot(output_id, record, content)

    def list_outputs(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_outputs(context=context, decision=decision)

    async def export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> tuple[ProcessingOutputSnapshot, bytes]:
        _require(context, decision, Permission.PROCESSING_READ)
        snapshot = self._repository.get_output(
            context=context, decision=decision, output_id=output_id
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            snapshot.content.output_artifact_id,
            maximum_bytes=64 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != snapshot.content.output_sha256:
            raise CommonPipelineError("Processing Output Artifact digest pin is inconsistent")
        return snapshot, value

    async def export_exact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        output_revision_id: UUID,
    ) -> tuple[ProcessingOutputSnapshot, bytes]:
        snapshot, value = await self.export(context, decision, output_id)
        if snapshot.current.revision_id != output_revision_id:
            raise ProcessingOutputNotFound("exact Processing Output revision is not visible")
        return snapshot, value

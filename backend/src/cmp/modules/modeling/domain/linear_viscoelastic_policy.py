"""Explicit calibration policy and immutable Plan validation.

This module owns parameter bounds, objective weights, optimizer settings, and exact Plan
serialization. It consumes governed input semantics but never runs a numerical solver.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    CandidateScopeMode,
    EQUAL_PER_POINT_RULE_VERSION,
    FLOAT64_EPSILON,
    LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_ID,
    LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_VERSION,
    LINEAR_VISCOELASTIC_MAX_TERM_COUNT,
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    LINEAR_VISCOELASTIC_SEED_STATUS,
    LinearViscoelasticPlanError,
    PointPartition,
    _decimal,
    _positive,
    _sha256,
    _uuid,
)
from cmp.modules.modeling.domain.linear_viscoelastic_input import (
    ArtifactPin,
    ChannelAvailability,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
)
from cmp.shared.domain.revisions import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class ParameterBound:
    """One explicit physical lower/start/upper bound."""

    name: str
    lower: Decimal | float
    start: Decimal | float
    upper: Decimal | float
    unit: str
    transform: str = "ln"

    def __post_init__(self) -> None:
        if not self.name or self.name != self.name.strip():
            raise LinearViscoelasticPlanError("parameter name must be trimmed")
        if self.transform != "ln":
            raise LinearViscoelasticPlanError("linear-viscoelastic parameters require ln transform")
        lower = _positive(self.lower, f"{self.name}.lower")
        start = _positive(self.start, f"{self.name}.start")
        upper = _positive(self.upper, f"{self.name}.upper")
        if not lower < start < upper:
            raise LinearViscoelasticPlanError(
                f"{self.name} requires strict positive lower < start < upper"
            )
        if not self.unit or self.unit != self.unit.strip():
            raise LinearViscoelasticPlanError("parameter unit must be trimmed")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "lower": str(_decimal(self.lower, f"{self.name}.lower")),
            "start": str(_decimal(self.start, f"{self.name}.start")),
            "upper": str(_decimal(self.upper, f"{self.name}.upper")),
            "unit": self.unit,
            "transform": self.transform,
        }


PhysicalParameterBound = ParameterBound


@dataclass(frozen=True, slots=True)
class CalibrationWeights:
    """Exact objective weights and explicit Pa scales."""

    relaxation_weight: Decimal = Decimal(1)
    dma_storage_weight: Decimal = Decimal("0.5")
    dma_loss_weight: Decimal = Decimal("0.5")
    relaxation_scale_pa: Decimal = Decimal(1)
    dma_storage_scale_pa: Decimal = Decimal(1)
    dma_loss_scale_pa: Decimal = Decimal(1)
    q_rule_version: str = EQUAL_PER_POINT_RULE_VERSION

    def __post_init__(self) -> None:
        for name in (
            "relaxation_weight",
            "dma_storage_weight",
            "dma_loss_weight",
            "relaxation_scale_pa",
            "dma_storage_scale_pa",
            "dma_loss_scale_pa",
        ):
            value = _decimal(getattr(self, name), name)
            if value <= 0:
                raise LinearViscoelasticPlanError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        if self.dma_storage_weight + self.dma_loss_weight != Decimal(1):
            raise LinearViscoelasticPlanError(
                "DMA storage/loss weights must be positive Decimals summing exactly to 1"
            )
        if self.q_rule_version != EQUAL_PER_POINT_RULE_VERSION:
            raise LinearViscoelasticPlanError("only equal_per_point@1.0.0 is supported")

    def canonical(self) -> dict[str, object]:
        return {
            "wd": "1",
            "relaxation_weight": str(self.relaxation_weight),
            "dma_storage_weight": str(self.dma_storage_weight),
            "dma_loss_weight": str(self.dma_loss_weight),
            "relaxation_scale_pa": str(self.relaxation_scale_pa),
            "dma_storage_scale_pa": str(self.dma_storage_scale_pa),
            "dma_loss_scale_pa": str(self.dma_loss_scale_pa),
            "q_rule_version": self.q_rule_version,
        }


@dataclass(frozen=True, slots=True)
class LinearViscoelasticCalibrationPlan:
    """Immutable, fully explicit numerical plan."""

    recommendation_policy: str
    plan_id: UUID = field(default_factory=uuid4)
    plan_revision_id: UUID = field(default_factory=uuid4)
    test_data: ExactRevisionPin | None = None
    canonical_artifact: ArtifactPin | None = None
    normalized_artifact: ArtifactPin | None = None
    raw_source_sha256: str | None = None
    import_profile: ExactRevisionPin | None = None
    profile_sha256: str | None = None
    processing_output: ExactRevisionPin | None = None
    processing_metadata_artifact: ArtifactPin | None = None
    processing_result_artifact: ArtifactPin | None = None
    input_semantics: GovernedViscoelasticInputSemantics | None = None
    term_counts: tuple[int, ...] = (1,)
    parameter_bounds: Mapping[int, tuple[ParameterBound, ...]] = field(default_factory=dict)
    start_vectors: Mapping[int, tuple[tuple[Decimal | float, ...], ...]] = field(
        default_factory=dict
    )
    weights: CalibrationWeights = field(default_factory=CalibrationWeights)
    ftol: float = 1e-8
    xtol: float = 1e-8
    gtol: float = 1e-8
    max_nfev: int = 1_000
    seed: int = 0
    seed_status: str = LINEAR_VISCOELASTIC_SEED_STATUS
    statuses: ChannelAvailability = field(default_factory=ChannelAvailability)
    schema_id: str = LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_ID
    schema_version: str = LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_VERSION
    # Governance metadata is deliberately appended after the existing numerical fields.  Legacy
    # #372 Plans therefore retain their exact canonical meaning and digest; new governed Plans
    # carry the exact source context required by review and production execution.
    setup_name: str | None = None
    material: ExactRevisionPin | None = None
    material_state: ExactRevisionPin | None = None
    input_mode: str | None = None
    based_on_plan_id: UUID | None = None
    based_on_plan_revision_id: UUID | None = None
    override_reason: str | None = None
    base_diff: Mapping[str, object] | None = None
    # None is the legacy/manual representation.  Keeping the field after all existing fields
    # means old positional construction and old canonical bytes remain unchanged.
    candidate_scope_mode: CandidateScopeMode | str | None = None

    def __post_init__(self) -> None:
        _uuid(self.plan_id, "plan_id")
        _uuid(self.plan_revision_id, "plan_revision_id")
        if self.recommendation_policy != LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY:
            raise LinearViscoelasticPlanError(
                "unsupported linear-viscoelastic recommendation policy"
            )
        if (
            self.schema_id != LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_ID
            or self.schema_version != LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_VERSION
        ):
            raise LinearViscoelasticPlanError("unsupported calibration Plan schema")
        if (
            not self.term_counts
            or tuple(sorted(self.term_counts)) != self.term_counts
            or len(set(self.term_counts)) != len(self.term_counts)
        ):
            raise LinearViscoelasticPlanError("term_counts must be explicit, unique, and ordered")
        if any(term < 1 or term > LINEAR_VISCOELASTIC_MAX_TERM_COUNT for term in self.term_counts):
            raise LinearViscoelasticPlanError("term_counts must be a subset of 1..10")
        if self.seed != 0 or self.seed_status != LINEAR_VISCOELASTIC_SEED_STATUS:
            raise LinearViscoelasticPlanError("transport seed must be integer 0/not_applicable")
        for name, tolerance in (("ftol", self.ftol), ("xtol", self.xtol), ("gtol", self.gtol)):
            if not math.isfinite(tolerance) or not FLOAT64_EPSILON < tolerance < 1:
                raise LinearViscoelasticPlanError(
                    f"{name} must satisfy float64 epsilon < value < 1"
                )
        if not 10 <= self.max_nfev <= 1_000_000:
            raise LinearViscoelasticPlanError("max_nfev must be within 10..1,000,000")
        if self.raw_source_sha256 is not None:
            _sha256(self.raw_source_sha256, "raw_source_sha256")
        if self.profile_sha256 is not None:
            _sha256(self.profile_sha256, "profile_sha256")
        required_evidence = (
            ("test_data", self.test_data, "INPUT_CANONICAL_TEST_DATA_REQUIRED"),
            ("canonical_artifact", self.canonical_artifact, "INPUT_CANONICAL_ARTIFACT_REQUIRED"),
            ("normalized_artifact", self.normalized_artifact, "INPUT_NORMALIZED_ARTIFACT_REQUIRED"),
            ("import_profile", self.import_profile, "INPUT_IMPORT_PROFILE_REQUIRED"),
        )
        for evidence_name, evidence_value, code in required_evidence:
            if evidence_value is None:
                raise LinearViscoelasticPlanError(
                    f"{evidence_name} exact immutable evidence is required ({code})"
                )
        if self.raw_source_sha256 is None:
            raise LinearViscoelasticPlanError(
                "raw_source_sha256 is required (INPUT_RAW_SOURCE_DIGEST_REQUIRED)"
            )
        if self.profile_sha256 is None:
            raise LinearViscoelasticPlanError(
                "profile_sha256 is required (INPUT_PROFILE_DIGEST_REQUIRED)"
            )
        if self.input_semantics is None:
            raise LinearViscoelasticPlanError(
                "server-resolved governed input semantics are required (INPUT_SEMANTICS_REQUIRED)"
            )
        if self.candidate_scope_mode is not None:
            try:
                scope_mode = CandidateScopeMode(str(self.candidate_scope_mode))
            except ValueError as error:
                raise LinearViscoelasticPlanError(
                    "candidate_scope_mode must be automatic or manual"
                ) from error
            object.__setattr__(self, "candidate_scope_mode", scope_mode)
        if self.candidate_scope_mode is CandidateScopeMode.AUTOMATIC:
            expected_terms = automatic_candidate_term_counts(self.input_semantics)
            if self.term_counts != expected_terms:
                raise LinearViscoelasticPlanError(
                    "automatic candidate scope must contain every feasible term count in order"
                )
        governance_values = (
            self.setup_name,
            self.material,
            self.material_state,
            self.input_mode,
            self.based_on_plan_id,
            self.based_on_plan_revision_id,
            self.override_reason,
            self.base_diff,
        )
        governed = any(value is not None for value in governance_values)
        if governed:
            if (
                self.setup_name is None
                or not self.setup_name.strip()
                or self.setup_name != self.setup_name.strip()
                or len(self.setup_name) > 255
                or "\x00" in self.setup_name
            ):
                raise LinearViscoelasticPlanError(
                    "governed calibration Plans require a trimmed setup_name"
                )
            if self.material is None or self.material_state is None:
                raise LinearViscoelasticPlanError(
                    "governed calibration Plans require exact Material and Material State pins"
                )
            if self.input_mode not in {
                "relaxation",
                "dma",
                "dma_frequency_master_curve",
            }:
                raise LinearViscoelasticPlanError(
                    "governed calibration Plans require a supported exact input_mode"
                )
            if self.input_semantics.mode != self.input_mode:
                raise LinearViscoelasticPlanError(
                    "input_mode must match the server-resolved input semantics mode"
                )
            if (self.based_on_plan_id is None) != (self.based_on_plan_revision_id is None):
                raise LinearViscoelasticPlanError(
                    "based_on_plan_id and based_on_plan_revision_id must be paired"
                )
            if self.based_on_plan_id is not None:
                _uuid(self.based_on_plan_id, "based_on_plan_id")
                assert self.based_on_plan_revision_id is not None
                _uuid(self.based_on_plan_revision_id, "based_on_plan_revision_id")
                if (
                    self.override_reason is None
                    or not self.override_reason.strip()
                    or self.override_reason != self.override_reason.strip()
                    or len(self.override_reason) > 2000
                    or "\x00" in self.override_reason
                ):
                    raise LinearViscoelasticPlanError(
                        "an Advanced clone requires a trimmed override_reason"
                    )
                if self.base_diff is None:
                    raise LinearViscoelasticPlanError(
                        "an Advanced clone requires a server-derived base_diff"
                    )
            elif self.override_reason is not None or self.base_diff is not None:
                raise LinearViscoelasticPlanError(
                    "override_reason and base_diff require an exact approved base Plan"
                )
            if self.base_diff is not None:
                # Validate the diff's JSON domain without allowing UUID/Decimal objects to leak
                # into a persisted immutable payload.
                canonical_json_bytes(self.base_diff)
        elif any(value is not None for value in (self.override_reason, self.base_diff)):
            raise LinearViscoelasticPlanError(
                "governance diff metadata cannot be attached to a legacy Plan"
            )
        processing_evidence = (
            self.processing_output,
            self.processing_metadata_artifact,
            self.processing_result_artifact,
        )
        if (
            self.input_semantics is not None
            and self.input_semantics.source_kind == "processing_output"
        ):
            if not all(item is not None for item in processing_evidence):
                raise LinearViscoelasticPlanError(
                    "processed input requires exact Processing Output and Artifact pins"
                )
        elif any(item is not None for item in processing_evidence):
            raise LinearViscoelasticPlanError(
                "direct governed input cannot carry Processing Output evidence"
            )
        if (
            self.import_profile is not None
            and self.import_profile.sha256 is not None
            and self.import_profile.sha256 != self.profile_sha256
        ):
            raise LinearViscoelasticPlanError(
                "Import Profile pin digest differs from resolved profile_sha256 "
                "(INPUT_PROFILE_DIGEST_MISMATCH)"
            )
        if self.canonical_artifact is not None and self.normalized_artifact is None:
            raise LinearViscoelasticPlanError("canonical and normalized Artifacts are paired")
        bounds = {int(key): tuple(value) for key, value in self.parameter_bounds.items()}
        starts = {
            int(key): tuple(tuple(vector) for vector in value)
            for key, value in self.start_vectors.items()
        }
        for term_count in self.term_counts:
            expected = _parameter_names(term_count)
            declared = bounds.get(term_count)
            vectors = starts.get(term_count)
            if declared is None or len(declared) != len(expected):
                raise LinearViscoelasticPlanError(
                    f"Plan must provide all physical bounds for {term_count}-term parameters"
                )
            if tuple(item.name for item in declared) != expected:
                raise LinearViscoelasticPlanError(
                    f"{term_count}-term bounds must be ordered as G_inf, G_i, tau_i"
                )
            _validate_tau_bound_order(declared, term_count)
            if not vectors:
                raise LinearViscoelasticPlanError(
                    f"Plan must provide one or more explicit start vectors for {term_count} terms"
                )
            for vector in vectors:
                if len(vector) != len(expected):
                    raise LinearViscoelasticPlanError(
                        f"{term_count}-term start vector length must be {len(expected)}"
                    )
                for bound, start_value in zip(declared, vector, strict=True):
                    numeric = _positive(start_value, f"{bound.name}.start_vector")
                    if not float(bound.lower) < numeric < float(bound.upper):
                        raise LinearViscoelasticPlanError(
                            f"start vector value for {bound.name} must be strictly within bounds"
                        )
        object.__setattr__(self, "parameter_bounds", bounds)
        object.__setattr__(self, "start_vectors", starts)
        if self.base_diff is not None:
            object.__setattr__(self, "base_diff", dict(self.base_diff))

    @classmethod
    def for_terms(
        cls,
        term_counts: Sequence[int],
        *,
        bounds: Mapping[int, Sequence[ParameterBound]],
        start_vectors: Mapping[int, Sequence[Sequence[Decimal | float]]],
        **kwargs: Any,
    ) -> Self:
        return cls(
            term_counts=tuple(term_counts),
            parameter_bounds={key: tuple(value) for key, value in bounds.items()},
            start_vectors={
                key: tuple(tuple(vector) for vector in value)
                for key, value in start_vectors.items()
            },
            **kwargs,
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical())).hexdigest()

    @property
    def is_governed(self) -> bool:
        """Whether this revision carries the Issue #377 approval context."""

        return self.setup_name is not None

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "plan_id": str(self.plan_id),
            "plan_revision_id": str(self.plan_revision_id),
            "test_data": self.test_data.canonical() if self.test_data else None,
            "canonical_artifact": self.canonical_artifact.canonical()
            if self.canonical_artifact
            else None,
            "normalized_artifact": self.normalized_artifact.canonical()
            if self.normalized_artifact
            else None,
            "raw_source_sha256": self.raw_source_sha256,
            "import_profile": self.import_profile.canonical() if self.import_profile else None,
            "profile_sha256": self.profile_sha256,
            "processing_output": (
                self.processing_output.canonical() if self.processing_output else None
            ),
            "processing_metadata_artifact": (
                self.processing_metadata_artifact.canonical()
                if self.processing_metadata_artifact
                else None
            ),
            "processing_result_artifact": (
                self.processing_result_artifact.canonical()
                if self.processing_result_artifact
                else None
            ),
            "input_semantics": (self.input_semantics.canonical() if self.input_semantics else None),
            "recommendation_policy": self.recommendation_policy,
            "term_counts": list(self.term_counts),
            "parameter_bounds": {
                str(term): [bound.canonical() for bound in values]
                for term, values in self.parameter_bounds.items()
            },
            "start_vectors": {
                str(term): [
                    [str(_decimal(value, "start_vector")) for value in vector] for vector in values
                ]
                for term, values in self.start_vectors.items()
            },
            "weights": self.weights.canonical(),
            "optimizer": {
                "method": "trf",
                "x_scale": "jac",
                "transform": "ln",
                "ftol": self.ftol,
                "xtol": self.xtol,
                "gtol": self.gtol,
                "max_nfev": self.max_nfev,
            },
            "seed": self.seed,
            "seed_status": self.seed_status,
            "statuses": self.statuses.canonical(),
        }
        # Explicit manual is intentionally omitted: absent and manual are the same legacy
        # canonical representation and therefore retain their historical digest.
        if self.candidate_scope_mode is CandidateScopeMode.AUTOMATIC:
            result["candidate_scope_mode"] = CandidateScopeMode.AUTOMATIC.value
        if self.is_governed:
            result.update(
                {
                    "setup_name": self.setup_name,
                    "material": self.material.canonical() if self.material else None,
                    "material_state": (
                        self.material_state.canonical() if self.material_state else None
                    ),
                    "input_mode": self.input_mode,
                    "based_on_plan_id": (
                        str(self.based_on_plan_id) if self.based_on_plan_id else None
                    ),
                    "based_on_plan_revision_id": (
                        str(self.based_on_plan_revision_id)
                        if self.based_on_plan_revision_id
                        else None
                    ),
                    "override_reason": self.override_reason,
                    "base_diff": dict(self.base_diff) if self.base_diff is not None else None,
                }
            )
        return result


def maximum_supported_prony_term_count(observation_count: int) -> int:
    """Return the complete data-feasible Prony range cap for one resolved input."""

    return max(0, min(LINEAR_VISCOELASTIC_MAX_TERM_COUNT, (observation_count - 1) // 2))


def calibration_observation_count(semantics: GovernedViscoelasticInputSemantics) -> int:
    """Count solver observations from the exact resolved calibration row partitions."""

    calibration_rows = sum(
        item.partition is PointPartition.CALIBRATION for item in semantics.point_dispositions
    )
    return calibration_rows * (2 if semantics.mode in {"dma", "dma_frequency_master_curve"} else 1)


def automatic_candidate_term_counts(
    semantics: GovernedViscoelasticInputSemantics,
) -> tuple[int, ...]:
    """Return every feasible term count without inventing an optimizer policy.

    Bounds and start values remain explicit reviewed Plan content. Automatic mode only owns
    the candidate *scope*; it must not fabricate production parameter ranges from row counts.
    """
    observation_count = calibration_observation_count(semantics)
    maximum = maximum_supported_prony_term_count(observation_count)
    if maximum < 1:
        raise LinearViscoelasticPlanError(
            "automatic candidate scope requires at least one feasible Prony term"
        )
    return tuple(range(1, maximum + 1))


def _parameter_names(term_count: int) -> tuple[str, ...]:
    return (
        "G_inf_pa",
        *(f"G_{index}_pa" for index in range(1, term_count + 1)),
        *(f"tau_{index}_s" for index in range(1, term_count + 1)),
    )


def _validate_tau_bound_order(bounds: Sequence[ParameterBound], term_count: int) -> None:
    lower = [float(bounds[1 + term_count + index].lower) for index in range(term_count)]
    upper = [float(bounds[1 + term_count + index].upper) for index in range(term_count)]
    if any(upper[index] >= lower[index + 1] for index in range(term_count - 1)):
        raise LinearViscoelasticPlanError(
            "tau intervals must be disjoint and ordered: upper_i < lower_(i+1)"
        )

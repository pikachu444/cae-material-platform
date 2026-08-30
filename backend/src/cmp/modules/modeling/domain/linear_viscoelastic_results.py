"""Immutable calibration result, candidate, recommendation, and evidence records."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    LINEAR_VISCOELASTIC_BIC_RULE_VERSION,
    LINEAR_VISCOELASTIC_MAX_TERM_COUNT,
    RankStatus,
    RunStatus,
    UncertaintyStatus,
    _sha256,
    _uuid,
)
from cmp.shared.domain.revisions import canonical_json_bytes


@dataclass(frozen=True, slots=True)
class RankDiagnostic:
    singular_values: tuple[float, ...]
    sigma_max: float
    threshold: float
    rank: int
    status: RankStatus
    warning_code: str | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "singular_values": list(self.singular_values),
            "sigma_max": self.sigma_max,
            "threshold": self.threshold,
            "rank": self.rank,
            "status": self.status.value,
            "warning_code": self.warning_code,
        }


@dataclass(frozen=True, slots=True)
class ObjectiveEvaluation:
    ordinal: int
    transformed_parameters: tuple[float, ...]
    physical_parameters: tuple[float, ...]
    residuals: tuple[float, ...]
    objective: float

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "transformed_parameters": list(self.transformed_parameters),
            "physical_parameters": list(self.physical_parameters),
            "residuals": list(self.residuals),
            "objective": self.objective,
        }


@dataclass(frozen=True, slots=True)
class NumericalAttempt:
    ordinal: int
    term_count: int
    start_vector: tuple[float, ...]
    transformed_start_vector: tuple[float, ...]
    status: int
    message: str
    nfev: int
    cost: float
    optimality: float
    active_mask: tuple[int, ...]
    physical_parameters: tuple[float, ...]
    transformed_parameters: tuple[float, ...]
    residuals: tuple[float, ...]
    rss: float
    rank: RankDiagnostic
    warnings: tuple[str, ...]
    objective_history: tuple[ObjectiveEvaluation, ...]
    converged: bool
    physical: bool

    @property
    def candidate_eligible(self) -> bool:
        return self.converged and self.physical

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "term_count": self.term_count,
            "start_vector": list(self.start_vector),
            "transformed_start_vector": list(self.transformed_start_vector),
            "optimizer": {
                "status": self.status,
                "message": self.message,
                "nfev": self.nfev,
                "cost": self.cost,
                "optimality": self.optimality,
                "active_mask": list(self.active_mask),
            },
            "physical_parameters": list(self.physical_parameters),
            "transformed_parameters": list(self.transformed_parameters),
            "residuals": list(self.residuals),
            "rss": self.rss,
            "rank": self.rank.canonical(),
            "warnings": list(self.warnings),
            "converged": self.converged,
            "physical": self.physical,
        }


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    candidate_id: UUID
    attempt_ordinal: int
    term_count: int
    physical_parameters: tuple[float, ...]
    transformed_parameters: tuple[float, ...]
    rss: float
    bic: float
    calibration_residuals: tuple[float, ...]
    holdout_residuals: tuple[float, ...]
    rank: RankDiagnostic
    warnings: tuple[str, ...]
    uncertainty_status: UncertaintyStatus = UncertaintyStatus.NOT_PROVIDED

    def __post_init__(self) -> None:
        _uuid(self.candidate_id, "candidate_id")
        if self.term_count < 1 or self.term_count > LINEAR_VISCOELASTIC_MAX_TERM_COUNT:
            raise ValueError("candidate term_count must be within 1..10")
        if self.uncertainty_status is not UncertaintyStatus.NOT_PROVIDED:
            raise ValueError("uncertainty is not provided by this bounded slice")

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical())).hexdigest()

    def canonical(self) -> dict[str, object]:
        return {
            "candidate_id": str(self.candidate_id),
            "attempt_ordinal": self.attempt_ordinal,
            "term_count": self.term_count,
            "physical_parameters": list(self.physical_parameters),
            "transformed_parameters": list(self.transformed_parameters),
            "rss": self.rss,
            "bic": self.bic,
            "calibration_residuals": list(self.calibration_residuals),
            "holdout_residuals": list(self.holdout_residuals),
            "rank": self.rank.canonical(),
            "warnings": list(self.warnings),
            "uncertainty_status": self.uncertainty_status.value,
        }


@dataclass(frozen=True, slots=True)
class CalibrationRecommendation:
    recommendation_id: UUID
    candidate_id: UUID
    candidate_digest: str
    rule_version: str = LINEAR_VISCOELASTIC_BIC_RULE_VERSION

    def __post_init__(self) -> None:
        _uuid(self.recommendation_id, "recommendation_id")
        _uuid(self.candidate_id, "candidate_id")
        _sha256(self.candidate_digest, "candidate_digest")
        if self.rule_version != LINEAR_VISCOELASTIC_BIC_RULE_VERSION:
            raise ValueError("unsupported BIC rule")

    def canonical(self) -> dict[str, object]:
        return {
            "recommendation_id": str(self.recommendation_id),
            "candidate_id": str(self.candidate_id),
            "candidate_digest": self.candidate_digest,
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True, slots=True)
class CalibrationRunResult:
    run_id: UUID
    plan_revision_id: UUID
    status: RunStatus
    attempts: tuple[NumericalAttempt, ...]
    candidates: tuple[CalibrationCandidate, ...]
    recommendation: CalibrationRecommendation | None
    objective_history_artifact_ids: tuple[UUID, ...] = ()
    response_residual_artifact_ids: tuple[UUID, ...] = ()
    execution_ledger_sha256: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    recovery_hint: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.run_id, "run_id")
        _uuid(self.plan_revision_id, "plan_revision_id")
        if self.status is RunStatus.SUCCEEDED and not self.candidates:
            raise ValueError("successful calibration run requires at least one candidate")
        if self.status is RunStatus.FAILED and self.candidates:
            raise ValueError("failed calibration run cannot expose candidates")
        if self.execution_ledger_sha256 is not None:
            _sha256(self.execution_ledger_sha256, "execution_ledger_sha256")

    def terminal_canonical(self) -> dict[str, object]:
        """Canonical digest payload; execution/job ledger is intentionally excluded."""

        return {
            "run_id": str(self.run_id),
            "plan_revision_id": str(self.plan_revision_id),
            "status": self.status.value,
            "attempts": [attempt.canonical() for attempt in self.attempts],
            "candidates": [candidate.canonical() for candidate in self.candidates],
            "recommendation": self.recommendation.canonical() if self.recommendation else None,
            "failure_code": self.failure_code,
            "failure_detail": self.failure_detail,
            "recovery_hint": self.recovery_hint,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.terminal_canonical())).hexdigest()

    def canonical(self) -> dict[str, object]:
        result = self.terminal_canonical()
        result["execution_ledger_sha256"] = self.execution_ledger_sha256
        result["objective_history_artifact_ids"] = [
            str(value) for value in self.objective_history_artifact_ids
        ]
        result["response_residual_artifact_ids"] = [
            str(value) for value in self.response_residual_artifact_ids
        ]
        return result

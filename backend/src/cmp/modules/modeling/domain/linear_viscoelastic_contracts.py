"""Shared contracts and validation helpers for linear-viscoelastic modeling domains.

This module owns the stable enums, schema identifiers, and small validation primitives shared by
governed inputs, explicit calibration policy, numerical results, and selection evidence.
"""

from __future__ import annotations

import math
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_ID = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-plan:1.0.0"
)
LINEAR_VISCOELASTIC_CALIBRATION_PLAN_SCHEMA_VERSION = "1.0.0"
LINEAR_VISCOELASTIC_CALIBRATION_RESULT_SCHEMA_ID = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0"
)
LINEAR_VISCOELASTIC_CALIBRATION_RESULT_SCHEMA_VERSION = "1.0.0"
LINEAR_VISCOELASTIC_RESPONSE_RESIDUALS_SCHEMA_ID = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
)
LINEAR_VISCOELASTIC_OBJECTIVE_HISTORY_SCHEMA_ID = (
    "urn:cmp:modeling:linear-viscoelastic-calibration-objective-history:1.0.0"
)
LINEAR_VISCOELASTIC_BIC_RULE_VERSION = "linear_viscoelastic_bic@1.0.0"
# The recommendation ordering is part of the immutable Plan contract.  The value names the
# already-approved deterministic tie-break used by the isolated calibrator.
LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY = "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"
NORMALIZED_ARRAY_EVIDENCE_RULE_VERSION = "normalized_arrow_float64_to_numpy@1.0.0"
SELECTED_ARRAY_DIGEST_RULE_VERSION = "linear_viscoelastic_selected_arrays@1.0.0"
EQUAL_PER_POINT_RULE_VERSION = "equal_per_point@1.0.0"
LINEAR_VISCOELASTIC_PLUGIN_ID = "cmp.linear_viscoelastic.calibrator"
LINEAR_VISCOELASTIC_PLUGIN_VERSION = "1.0.2"
LINEAR_VISCOELASTIC_SEED_STATUS = "not_applicable"
LINEAR_VISCOELASTIC_MAX_TERM_COUNT = 10
FLOAT64_EPSILON = 2.220446049250313e-16

_SHA256 = set("0123456789abcdef")


class LinearViscoelasticCalibrationError(Exception):
    """Base error for the governed linear-viscoelastic calibration boundary."""


class LinearViscoelasticInputError(LinearViscoelasticCalibrationError, ValueError):
    """Input evidence or a typed channel violates the bounded contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INPUT_INVALID",
        recovery_hint: str = "Create a new immutable governed source/profile revision.",
    ) -> None:
        self.code = code
        self.recovery_hint = recovery_hint
        super().__init__(message)


class LinearViscoelasticPlanError(LinearViscoelasticCalibrationError, ValueError):
    """A calibration plan is not explicit, deterministic, or physically bounded."""


class LinearViscoelasticSelectionError(LinearViscoelasticCalibrationError, ValueError):
    """An engineer selection does not reference an immutable valid candidate."""


class LinearViscoelasticChannel(StrEnum):
    RELAXATION = "relaxation"
    DMA_STORAGE = "dma_storage"
    DMA_LOSS = "dma_loss"


class PointPartition(StrEnum):
    CALIBRATION = "CALIBRATION"
    HOLDOUT = "HOLDOUT"
    EXCLUDED = "EXCLUDED"


SourceOrdinalDisposition = PointPartition
CalibrationPartition = PointPartition


class CandidateScopeMode(StrEnum):
    """How the immutable Plan chooses the feasible Prony term scope."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"


class DataAvailability(StrEnum):
    PROVIDED = "PROVIDED"
    NOT_PROVIDED = "NOT_PROVIDED"


class UncertaintyStatus(StrEnum):
    NOT_PROVIDED = "NOT_PROVIDED"


class RankStatus(StrEnum):
    FULL_RANK = "FULL_RANK"
    RANK_DEFICIENT = "RANK_DEFICIENT"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


class ExecutionFailureCode(StrEnum):
    CALCULATION_CANCELLED = "CALCULATION_CANCELLED"
    CALCULATION_TIMED_OUT = "CALCULATION_TIMED_OUT"
    EXECUTION_ISOLATION_UNAVAILABLE = "EXECUTION_ISOLATION_UNAVAILABLE"
    EXECUTION_PACKAGE_INTEGRITY_FAILED = "EXECUTION_PACKAGE_INTEGRITY_FAILED"
    EXECUTION_REQUEST_INVALID = "EXECUTION_REQUEST_INVALID"
    EXECUTION_RESULT_INVALID = "EXECUTION_RESULT_INVALID"
    CALCULATION_FAILED = "CALCULATION_FAILED"
    EXECUTION_INTERNAL_ERROR = "EXECUTION_INTERNAL_ERROR"


def _as_float(value: Decimal | float | int, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise LinearViscoelasticInputError(f"{name} must be a finite number") from error
    if not math.isfinite(result):
        raise LinearViscoelasticInputError(f"{name} must be finite")
    return result


def _decimal(value: Decimal | float | int, name: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError) as error:
        raise LinearViscoelasticInputError(f"{name} must be a finite decimal") from error
    if not result.is_finite():
        raise LinearViscoelasticInputError(f"{name} must be finite")
    return result


def _positive(value: Decimal | float | int, name: str) -> float:
    result = _as_float(value, name)
    if result <= 0:
        raise LinearViscoelasticInputError(f"{name} must be positive")
    return result


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in _SHA256 for char in value):
        raise LinearViscoelasticInputError(f"{name} must be lowercase SHA-256 hex")


def _uuid(value: UUID, name: str) -> None:
    if not isinstance(value, UUID) or value.int == 0:
        raise LinearViscoelasticInputError(f"{name} must be a non-zero UUID")


def _status(value: DataAvailability | str, name: str) -> DataAvailability:
    try:
        return value if isinstance(value, DataAvailability) else DataAvailability(value)
    except ValueError as error:
        raise LinearViscoelasticInputError(f"{name} must be PROVIDED or NOT_PROVIDED") from error

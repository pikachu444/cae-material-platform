"""Pure validation/decoding for isolated linear-viscoelastic run results.

The isolated plugin owns numerical calculation.  This module only turns its immutable JSON
result into the typed modeling contract and rejects malformed or internally inconsistent values
before a Run is changed.  Artifact identities are supplied by the host after their bytes have
been verified; plugin JSON can never choose those identities.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import cast
from uuid import UUID

from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
    NumericalAttempt,
    ObjectiveEvaluation,
    RankDiagnostic,
    RankStatus,
    RunStatus,
    UncertaintyStatus,
)
from cmp.modules.plugins.domain.execution import InvalidResultManifest

RESULT_SCHEMA_ID = "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0"
RESULT_SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_RESULT_KEYS = {
    "schema_id",
    "schema_version",
    "run_id",
    "plan_revision_id",
    "status",
    "attempts",
    "candidates",
    "recommendation",
    "failure_code",
    "failure_detail",
    "recovery_hint",
    "execution_ledger_sha256",
    "objective_history_artifact_ids",
    "response_residual_artifact_ids",
}
_REQUIRED_RESULT_KEYS = {
    "schema_id",
    "schema_version",
    "run_id",
    "plan_revision_id",
    "status",
    "attempts",
    "candidates",
    "recommendation",
    "failure_code",
    "failure_detail",
    "recovery_hint",
}
_ATTEMPT_KEYS = {
    "ordinal",
    "term_count",
    "start_vector",
    "transformed_start_vector",
    "status",
    "message",
    "nfev",
    "cost",
    "optimality",
    "active_mask",
    "physical_parameters",
    "transformed_parameters",
    "residuals",
    "rss",
    "rank",
    "warnings",
    "objective_history",
    "converged",
    "physical",
}
_ATTEMPT_OUTER_KEYS = {
    "ordinal",
    "term_count",
    "start_vector",
    "transformed_start_vector",
    "optimizer",
    "physical_parameters",
    "transformed_parameters",
    "residuals",
    "rss",
    "rank",
    "warnings",
    "objective_history",
    "converged",
    "physical",
}
_OPTIMIZER_KEYS = {"status", "message", "nfev", "cost", "optimality", "active_mask"}
_ATTEMPT_REQUIRED_KEYS = _ATTEMPT_KEYS - {"objective_history"}
_ATTEMPT_OUTER_REQUIRED_KEYS = _ATTEMPT_OUTER_KEYS - {"objective_history"}
_RANK_KEYS = {"singular_values", "sigma_max", "threshold", "rank", "status", "warning_code"}
_CANDIDATE_KEYS = {
    "candidate_id",
    "attempt_ordinal",
    "term_count",
    "physical_parameters",
    "transformed_parameters",
    "rss",
    "bic",
    "calibration_residuals",
    "holdout_residuals",
    "rank",
    "warnings",
    "uncertainty_status",
}
_RECOMMENDATION_KEYS = {
    "recommendation_id",
    "candidate_id",
    "candidate_digest",
    "rule_version",
}


def _object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidResultManifest(f"{name} must be an object")
    return cast(Mapping[str, object], value)


def _array(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise InvalidResultManifest(f"{name} must be an array")
    return cast(Sequence[object], value)


def _int(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidResultManifest(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise InvalidResultManifest(f"{name} must be at least {minimum}")
    return value


def _number(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidResultManifest(f"{name} must be a number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise InvalidResultManifest(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise InvalidResultManifest(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise InvalidResultManifest(f"{name} must be at least {minimum}")
    return result


def _numbers(value: object, name: str) -> tuple[float, ...]:
    return tuple(
        _number(item, f"{name}[{index}]")
        for index, item in enumerate(_array(value, name))
    )


def _uuid(value: object, name: str) -> UUID:
    try:
        result = UUID(str(value))
    except (AttributeError, ValueError, TypeError) as error:
        raise InvalidResultManifest(f"{name} must be a UUID") from error
    if result.int == 0:
        raise InvalidResultManifest(f"{name} must be non-zero")
    return result


def _strings(value: object, name: str) -> tuple[str, ...]:
    values = _array(value, name)
    if any(not isinstance(item, str) or not item or item != item.strip() for item in values):
        raise InvalidResultManifest(f"{name} must contain non-empty strings")
    return tuple(cast(str, item) for item in values)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidResultManifest(f"{name} must be a non-empty string")
    return value


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise InvalidResultManifest(f"{name} must be lowercase SHA-256 hex")
    return value


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidResultManifest(f"{name} must be a boolean")
    return value


def _keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        detail = f"missing={missing!r}" if missing else f"extra={extra!r}"
        raise InvalidResultManifest(f"{name} fields are not exact ({detail})")


def _rank(value: object, name: str) -> RankDiagnostic:
    payload = _object(value, name)
    _keys(payload, _RANK_KEYS, name)
    try:
        status = RankStatus(str(payload["status"]))
    except ValueError as error:
        raise InvalidResultManifest(f"{name}.status is invalid") from error
    warning = payload["warning_code"]
    if warning is not None and (not isinstance(warning, str) or not warning.strip()):
        raise InvalidResultManifest(f"{name}.warning_code is invalid")
    return RankDiagnostic(
        singular_values=_numbers(payload["singular_values"], f"{name}.singular_values"),
        sigma_max=_number(payload["sigma_max"], f"{name}.sigma_max", minimum=0),
        threshold=_number(payload["threshold"], f"{name}.threshold", minimum=0),
        rank=_int(payload["rank"], f"{name}.rank", minimum=0),
        status=status,
        warning_code=warning,
    )


def _history(value: object, name: str) -> ObjectiveEvaluation:
    payload = _object(value, name)
    # The first package revision emits only ordinal/objective.  Empty vectors are the explicit
    # contract representation for that compact history; a future richer payload is validated
    # when all three vectors are supplied.
    allowed = {"ordinal", "transformed_parameters", "physical_parameters", "residuals", "objective"}
    if set(payload) - allowed or not {"ordinal", "objective"}.issubset(payload):
        raise InvalidResultManifest(f"{name} fields are invalid")
    return ObjectiveEvaluation(
        ordinal=_int(payload["ordinal"], f"{name}.ordinal", minimum=0),
        transformed_parameters=_numbers(
            payload.get("transformed_parameters", ()), f"{name}.transformed_parameters"
        ),
        physical_parameters=_numbers(
            payload.get("physical_parameters", ()), f"{name}.physical_parameters"
        ),
        residuals=_numbers(payload.get("residuals", ()), f"{name}.residuals"),
        objective=_number(payload["objective"], f"{name}.objective", minimum=0),
    )


def _attempt(value: object, index: int) -> NumericalAttempt:
    name = f"attempts[{index}]"
    payload = _object(value, name)
    if "optimizer" in payload:
        if not _ATTEMPT_OUTER_REQUIRED_KEYS.issubset(payload) or set(payload) - _ATTEMPT_OUTER_KEYS:
            missing = sorted(_ATTEMPT_OUTER_REQUIRED_KEYS - set(payload))
            extra = sorted(set(payload) - _ATTEMPT_OUTER_KEYS)
            raise InvalidResultManifest(
                f"{name} fields are not exact (missing={missing!r}, extra={extra!r})"
            )
        optimizer = _object(payload["optimizer"], f"{name}.optimizer")
        _keys(optimizer, _OPTIMIZER_KEYS, f"{name}.optimizer")
        normalized = dict(payload)
        normalized.update(optimizer)
    else:
        if not _ATTEMPT_REQUIRED_KEYS.issubset(payload) or set(payload) - _ATTEMPT_KEYS:
            missing = sorted(_ATTEMPT_REQUIRED_KEYS - set(payload))
            extra = sorted(set(payload) - _ATTEMPT_KEYS)
            raise InvalidResultManifest(
                f"{name} fields are not exact (missing={missing!r}, extra={extra!r})"
            )
        normalized = dict(payload)
    rank = _rank(normalized["rank"], f"{name}.rank")
    return NumericalAttempt(
        ordinal=_int(normalized["ordinal"], f"{name}.ordinal", minimum=1),
        term_count=_int(normalized["term_count"], f"{name}.term_count", minimum=1),
        start_vector=_numbers(normalized["start_vector"], f"{name}.start_vector"),
        transformed_start_vector=_numbers(
            normalized["transformed_start_vector"], f"{name}.transformed_start_vector"
        ),
        status=_int(normalized["status"], f"{name}.status"),
        message=_string(normalized["message"], f"{name}.message"),
        nfev=_int(normalized["nfev"], f"{name}.nfev", minimum=0),
        cost=_number(normalized["cost"], f"{name}.cost", minimum=0),
        optimality=_number(normalized["optimality"], f"{name}.optimality", minimum=0),
        active_mask=tuple(
            _int(item, f"{name}.active_mask[{item_index}]")
            for item_index, item in enumerate(
                _array(normalized["active_mask"], f"{name}.active_mask")
            )
        ),
        physical_parameters=_numbers(
            normalized["physical_parameters"], f"{name}.physical_parameters"
        ),
        transformed_parameters=_numbers(
            normalized["transformed_parameters"], f"{name}.transformed_parameters"
        ),
        residuals=_numbers(normalized["residuals"], f"{name}.residuals"),
        rss=_number(normalized["rss"], f"{name}.rss", minimum=0),
        rank=rank,
        warnings=_strings(normalized["warnings"], f"{name}.warnings"),
        objective_history=tuple(
            _history(item, f"{name}.objective_history[{history_index}]")
            for history_index, item in enumerate(
                _array(
                    normalized.get("objective_history", ()), f"{name}.objective_history"
                )
            )
        ),
        converged=_boolean(normalized["converged"], f"{name}.converged"),
        physical=_boolean(normalized["physical"], f"{name}.physical"),
    )


def _candidate(value: object, index: int) -> CalibrationCandidate:
    name = f"candidates[{index}]"
    payload = _object(value, name)
    _keys(payload, _CANDIDATE_KEYS, name)
    uncertainty = payload["uncertainty_status"]
    try:
        uncertainty_status = UncertaintyStatus(str(uncertainty))
    except ValueError as error:
        raise InvalidResultManifest(f"{name}.uncertainty_status is invalid") from error
    return CalibrationCandidate(
        candidate_id=_uuid(payload["candidate_id"], f"{name}.candidate_id"),
        attempt_ordinal=_int(payload["attempt_ordinal"], f"{name}.attempt_ordinal", minimum=1),
        term_count=_int(payload["term_count"], f"{name}.term_count", minimum=1),
        physical_parameters=_numbers(
            payload["physical_parameters"], f"{name}.physical_parameters"
        ),
        transformed_parameters=_numbers(
            payload["transformed_parameters"], f"{name}.transformed_parameters"
        ),
        rss=_number(payload["rss"], f"{name}.rss", minimum=0),
        bic=_number(payload["bic"], f"{name}.bic"),
        calibration_residuals=_numbers(
            payload["calibration_residuals"], f"{name}.calibration_residuals"
        ),
        holdout_residuals=_numbers(payload["holdout_residuals"], f"{name}.holdout_residuals"),
        rank=_rank(payload["rank"], f"{name}.rank"),
        warnings=_strings(payload["warnings"], f"{name}.warnings"),
        uncertainty_status=uncertainty_status,
    )


def _recommendation(value: object) -> CalibrationRecommendation | None:
    if value is None:
        return None
    payload = _object(value, "recommendation")
    _keys(payload, _RECOMMENDATION_KEYS, "recommendation")
    return CalibrationRecommendation(
        recommendation_id=_uuid(payload["recommendation_id"], "recommendation.recommendation_id"),
        candidate_id=_uuid(payload["candidate_id"], "recommendation.candidate_id"),
        candidate_digest=_digest(
            payload["candidate_digest"], "recommendation.candidate_digest"
        ),
        rule_version=_string(payload["rule_version"], "recommendation.rule_version"),
    )


def _artifact_ids(value: object, name: str) -> tuple[UUID, ...]:
    return tuple(_uuid(item, f"{name}[{index}]") for index, item in enumerate(_array(value, name)))


def _decode_json(value: bytes | bytearray | str) -> object:
    try:
        return json.loads(
            value,
            parse_constant=lambda token: (_ for _ in ()).throw(
                InvalidResultManifest(f"JSON constant {token!r} is not finite")
            ),
        )
    except InvalidResultManifest:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise InvalidResultManifest("calibration run-result is not valid JSON") from error


def document_sha256(value: object) -> str:
    """Return the digest of the canonical run-result JSON transport."""

    if isinstance(value, (bytes, bytearray, str)):
        value = _decode_json(value)
    try:
        from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

        return content_sha256(json.loads(canonical_json_bytes(value)))
    except (TypeError, ValueError) as error:
        raise InvalidResultManifest("calibration run-result cannot be canonicalized") from error


def parse_calibration_run_result(
    value: object, *, expected_document_sha256: str | None = None
) -> CalibrationRunResult:
    """Decode one exact plugin run-result document without executing numerical code."""

    if isinstance(value, (bytes, bytearray, str)):
        value = _decode_json(value)
    if expected_document_sha256 is not None:
        if _SHA256.fullmatch(expected_document_sha256) is None:
            raise InvalidResultManifest("run-result document digest is invalid")
        if document_sha256(value) != expected_document_sha256:
            raise InvalidResultManifest("run-result document digest differs from its bytes")
    payload = _object(value, "calibration run-result")
    if not _REQUIRED_RESULT_KEYS.issubset(payload) or set(payload) - _RESULT_KEYS:
        missing = sorted(_REQUIRED_RESULT_KEYS - set(payload))
        extra = sorted(set(payload) - _RESULT_KEYS)
        raise InvalidResultManifest(
            "calibration run-result fields are not exact "
            f"(missing={missing!r}, extra={extra!r})"
        )
    if (
        payload["schema_id"] != RESULT_SCHEMA_ID
        or payload["schema_version"] != RESULT_SCHEMA_VERSION
    ):
        raise InvalidResultManifest("calibration run-result schema identity is invalid")
    try:
        status = RunStatus(str(payload["status"]))
    except ValueError as error:
        raise InvalidResultManifest("calibration run-result status is invalid") from error
    if status not in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
        raise InvalidResultManifest("calibration run-result must be terminal succeeded or failed")
    attempts = tuple(
        _attempt(item, index)
        for index, item in enumerate(_array(payload["attempts"], "attempts"))
    )
    candidates = tuple(
        _candidate(item, index)
        for index, item in enumerate(_array(payload["candidates"], "candidates"))
    )
    if not attempts:
        raise InvalidResultManifest("calibration run-result requires numerical attempts")
    attempt_ordinals = {item.ordinal for item in attempts}
    if len(attempt_ordinals) != len(attempts):
        raise InvalidResultManifest("numerical attempt ordinals must be unique")
    candidate_ids = {item.candidate_id for item in candidates}
    if len(candidate_ids) != len(candidates):
        raise InvalidResultManifest("candidate identities must be unique")
    for attempt in attempts:
        if attempt.term_count > 10:
            raise InvalidResultManifest("numerical term count must be within 1..10")
        parameter_count = 1 + 2 * attempt.term_count
        if len(attempt.start_vector) != parameter_count:
            raise InvalidResultManifest("numerical start vector length differs from term count")
        if len(attempt.transformed_start_vector) != parameter_count:
            raise InvalidResultManifest(
                "numerical transformed start vector length differs from term count"
            )
        if len(attempt.physical_parameters) != parameter_count:
            raise InvalidResultManifest(
                "numerical physical parameter length differs from term count"
            )
        if len(attempt.transformed_parameters) != parameter_count:
            raise InvalidResultManifest(
                "numerical transformed parameter length differs from term count"
            )
        if len(attempt.active_mask) != parameter_count:
            raise InvalidResultManifest("numerical active-mask length differs from term count")
        if any(value <= 0 for value in attempt.physical_parameters):
            raise InvalidResultManifest("numerical physical parameters must be positive")
        if attempt.rank.rank > min(len(attempt.rank.singular_values), parameter_count):
            raise InvalidResultManifest("numerical rank exceeds its singular-value evidence")
        if attempt.rank.status is RankStatus.FULL_RANK and attempt.rank.rank < parameter_count:
            raise InvalidResultManifest("full-rank evidence does not cover all parameters")
        for history in attempt.objective_history:
            if history.transformed_parameters and len(
                history.transformed_parameters
            ) != parameter_count:
                raise InvalidResultManifest(
                    "objective history transformed parameter length differs from term count"
                )
            if history.physical_parameters and len(history.physical_parameters) != parameter_count:
                raise InvalidResultManifest(
                    "objective history physical parameter length differs from term count"
                )
    for candidate in candidates:
        if candidate.attempt_ordinal not in attempt_ordinals:
            raise InvalidResultManifest("candidate references an unknown numerical attempt")
        attempt = next(item for item in attempts if item.ordinal == candidate.attempt_ordinal)
        if candidate.term_count != attempt.term_count:
            raise InvalidResultManifest("candidate term count differs from its numerical attempt")
        parameter_count = 1 + 2 * candidate.term_count
        if len(candidate.physical_parameters) != parameter_count or len(
            candidate.transformed_parameters
        ) != parameter_count:
            raise InvalidResultManifest("candidate parameter length differs from term count")
        if any(value <= 0 for value in candidate.physical_parameters):
            raise InvalidResultManifest("candidate physical parameters must be positive")
        if candidate.physical_parameters != attempt.physical_parameters:
            raise InvalidResultManifest("candidate physical parameters differ from its attempt")
        if candidate.transformed_parameters != attempt.transformed_parameters:
            raise InvalidResultManifest(
                "candidate transformed parameters differ from its attempt"
            )
        if candidate.calibration_residuals != attempt.residuals:
            raise InvalidResultManifest("candidate residuals differ from its attempt")
        if candidate.rank.rank > min(len(candidate.rank.singular_values), parameter_count):
            raise InvalidResultManifest("candidate rank exceeds its singular-value evidence")
        if candidate.rank.status is RankStatus.FULL_RANK and candidate.rank.rank < parameter_count:
            raise InvalidResultManifest(
                "candidate full-rank evidence does not cover all parameters"
            )
    recommendation = _recommendation(payload["recommendation"])
    if status is RunStatus.SUCCEEDED:
        if not candidates or recommendation is None:
            raise InvalidResultManifest("successful result requires candidates and recommendation")
    elif candidates or recommendation is not None:
        raise InvalidResultManifest("failed result cannot expose candidates or recommendation")
    if recommendation is not None:
        recommendation_candidate = next(
            (item for item in candidates if item.candidate_id == recommendation.candidate_id), None
        )
        if (
            recommendation_candidate is None
            or recommendation.candidate_digest != recommendation_candidate.digest
        ):
            raise InvalidResultManifest("recommendation does not pin the exact candidate digest")
    failure_code = payload["failure_code"]
    failure_detail = payload["failure_detail"]
    recovery_hint = payload["recovery_hint"]
    if any(
        value is not None and (not isinstance(value, str) or not value.strip())
        for value in (failure_code, failure_detail, recovery_hint)
    ):
        raise InvalidResultManifest("failure fields must be null or non-empty strings")
    if status is RunStatus.SUCCEEDED and any(
        value is not None for value in (failure_code, failure_detail, recovery_hint)
    ):
        raise InvalidResultManifest("successful result cannot carry failure fields")
    if status is RunStatus.FAILED and failure_code is None:
        raise InvalidResultManifest("failed result requires a stable failure code")
    return CalibrationRunResult(
        run_id=_uuid(payload["run_id"], "run_id"),
        plan_revision_id=_uuid(payload["plan_revision_id"], "plan_revision_id"),
        status=status,
        attempts=attempts,
        candidates=candidates,
        recommendation=recommendation,
        objective_history_artifact_ids=_artifact_ids(
            payload.get("objective_history_artifact_ids", ()), "objective_history_artifact_ids"
        ),
        response_residual_artifact_ids=_artifact_ids(
            payload.get("response_residual_artifact_ids", ()), "response_residual_artifact_ids"
        ),
        execution_ledger_sha256=(
            _digest(payload["execution_ledger_sha256"], "execution_ledger_sha256")
            if payload.get("execution_ledger_sha256") is not None
            else None
        ),
        failure_code=cast(str | None, failure_code),
        failure_detail=cast(str | None, failure_detail),
        recovery_hint=cast(str | None, recovery_hint),
    )


def validate_result_digest(result: CalibrationRunResult, expected_digest: str) -> None:
    """Check the terminal digest independently of the transport manifest digest."""

    if not isinstance(expected_digest, str) or expected_digest != result.digest:
        raise InvalidResultManifest("calibration run-result digest differs from its typed content")


__all__ = ["document_sha256", "parse_calibration_run_result", "validate_result_digest"]

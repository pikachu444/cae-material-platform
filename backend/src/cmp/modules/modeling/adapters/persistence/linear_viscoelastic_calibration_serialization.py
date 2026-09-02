"""Lossless typed payload mappers for linear-viscoelastic calibration persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    ArtifactPin,
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
    CalibrationWeights,
    ChannelAvailability,
    DataAvailability,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
    InputChannelSemantics,
    LinearViscoelasticCalibrationPlan,
    LinearViscoelasticSelection,
    NumericalAttempt,
    ObjectiveEvaluation,
    ParameterBound,
    PointDisposition,
    PointPartition,
    RankDiagnostic,
    RankStatus,
    RunStatus,
    UncertaintyStatus,
)

from .linear_viscoelastic_calibration_tables import JsonScalar


def _as_uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _as_json_float(value: object) -> float:
    return float(cast(JsonScalar, value))


def _as_json_int(value: object) -> int:
    return int(cast(JsonScalar, value))


def _as_float_tuple(value: object) -> tuple[float, ...]:
    return tuple(_as_json_float(item) for item in cast(Sequence[JsonScalar], value))


def plan_from_payload(payload: Mapping[str, object]) -> LinearViscoelasticCalibrationPlan:
    test_data = payload.get("test_data")
    canonical_artifact = payload.get("canonical_artifact")
    normalized_artifact = payload.get("normalized_artifact")
    import_profile = payload.get("import_profile")
    processing_output = payload.get("processing_output")
    processing_metadata_artifact = payload.get("processing_metadata_artifact")
    processing_result_artifact = payload.get("processing_result_artifact")
    recommendation_policy = payload.get("recommendation_policy")
    if not isinstance(recommendation_policy, str) or not recommendation_policy:
        raise ValueError("recommendation_policy is required in the immutable Plan payload")
    optimizer = cast(Mapping[str, object], payload.get("optimizer") or {})
    weights = cast(Mapping[str, object], payload.get("weights") or {})
    statuses = cast(Mapping[str, object], payload.get("statuses") or {})
    semantics = cast(Mapping[str, object], payload.get("input_semantics") or {})
    bounds_payload = cast(Mapping[str, object], payload.get("parameter_bounds") or {})
    starts_payload = cast(Mapping[str, object], payload.get("start_vectors") or {})
    base_diff = payload.get("base_diff")
    if base_diff is not None and not isinstance(base_diff, Mapping):
        raise ValueError("base_diff must be an object")

    def revision_pin(value: object) -> ExactRevisionPin | None:
        if value is None:
            return None
        item = cast(Mapping[str, object], value)
        return ExactRevisionPin(
            _as_uuid(item["id"]),
            _as_uuid(item["revision_id"]),
            str(item["sha256"]) if item.get("sha256") is not None else None,
        )

    def artifact_pin(value: object) -> ArtifactPin | None:
        if value is None:
            return None
        item = cast(Mapping[str, object], value)
        return ArtifactPin(
            _as_uuid(item["artifact_id"]),
            str(item["sha256"]),
            str(item["media_type"]) if item.get("media_type") is not None else None,
        )

    parameter_bounds = {
        int(term): tuple(
            ParameterBound(
                str(bound["name"]),
                Decimal(str(bound["lower"])),
                Decimal(str(bound["start"])),
                Decimal(str(bound["upper"])),
                str(bound["unit"]),
                str(bound.get("transform", "ln")),
            )
            for bound in cast(Sequence[Mapping[str, object]], values)
        )
        for term, values in bounds_payload.items()
    }
    start_vectors = {
        int(term): tuple(
            tuple(Decimal(str(item)) for item in vector)
            for vector in cast(Sequence[Sequence[JsonScalar]], values)
        )
        for term, values in starts_payload.items()
    }
    input_semantics = GovernedViscoelasticInputSemantics(
        mode=str(semantics.get("mode", "")),
        deformation_mode=str(semantics.get("deformation_mode", "")),
        channels=tuple(
            InputChannelSemantics(
                key=str(item["key"]),
                quantity_semantics=str(item["quantity_semantics"]),
                axis_role=str(item["axis_role"]),
                original_unit_string=str(item["original_unit_string"]),
                normalized_unit=str(item["normalized_unit"]),
            )
            for item in cast(Sequence[Mapping[str, object]], semantics.get("channels", ()))
        ),
        point_dispositions=tuple(
            PointDisposition(
                ordinal=_as_json_int(item["ordinal"]),
                partition=PointPartition(str(item["partition"])),
                exclusion_reason=(
                    str(item["exclusion_reason"])
                    if item.get("exclusion_reason") is not None
                    else None
                ),
            )
            for item in cast(
                Sequence[Mapping[str, object]],
                semantics.get("point_dispositions", ()),
            )
        ),
        selected_temperature_k=(
            Decimal(str(semantics["selected_temperature_k"]))
            if semantics.get("selected_temperature_k") is not None
            else None
        ),
        temperature_source=str(semantics.get("temperature_source", "not_provided")),
        strain_amplitude=(
            Decimal(str(semantics["strain_amplitude"]))
            if semantics.get("strain_amplitude") is not None
            else None
        ),
        strain_amplitude_quantity=str(
            semantics.get("strain_amplitude_quantity", "mechanics.strain.shear")
        ),
        strain_amplitude_unit=str(semantics.get("strain_amplitude_unit", "1")),
        frequency_kind=str(semantics.get("frequency_kind", "not_applicable")),
        angular_frequency_conversion=str(
            semantics.get("angular_frequency_conversion", "not_applicable")
        ),
        source_kind=str(semantics.get("source_kind", "governed_test_data")),
        processing_method=(
            str(semantics["processing_method"])
            if semantics.get("processing_method") is not None
            else None
        ),
    )
    return LinearViscoelasticCalibrationPlan(
        plan_id=_as_uuid(payload["plan_id"]),
        plan_revision_id=_as_uuid(payload["plan_revision_id"]),
        test_data=revision_pin(test_data),
        canonical_artifact=artifact_pin(canonical_artifact),
        normalized_artifact=artifact_pin(normalized_artifact),
        raw_source_sha256=str(payload["raw_source_sha256"]),
        import_profile=revision_pin(import_profile),
        profile_sha256=str(payload["profile_sha256"]),
        processing_output=revision_pin(processing_output),
        processing_metadata_artifact=artifact_pin(processing_metadata_artifact),
        processing_result_artifact=artifact_pin(processing_result_artifact),
        input_semantics=input_semantics,
        recommendation_policy=recommendation_policy,
        term_counts=tuple(
            _as_json_int(item) for item in cast(Sequence[JsonScalar], payload["term_counts"])
        ),
        parameter_bounds=parameter_bounds,
        start_vectors=start_vectors,
        weights=CalibrationWeights(
            relaxation_weight=Decimal(str(weights.get("relaxation_weight", "1"))),
            dma_storage_weight=Decimal(str(weights.get("dma_storage_weight", "0.5"))),
            dma_loss_weight=Decimal(str(weights.get("dma_loss_weight", "0.5"))),
            relaxation_scale_pa=Decimal(str(weights.get("relaxation_scale_pa", "1"))),
            dma_storage_scale_pa=Decimal(str(weights.get("dma_storage_scale_pa", "1"))),
            dma_loss_scale_pa=Decimal(str(weights.get("dma_loss_scale_pa", "1"))),
            q_rule_version=str(weights.get("q_rule_version", "equal_per_point@1.0.0")),
        ),
        ftol=_as_json_float(optimizer.get("ftol", 1e-8)),
        xtol=_as_json_float(optimizer.get("xtol", 1e-8)),
        gtol=_as_json_float(optimizer.get("gtol", 1e-8)),
        max_nfev=_as_json_int(optimizer.get("max_nfev", 1_000)),
        seed=_as_json_int(payload.get("seed", 0)),
        seed_status=str(payload.get("seed_status", "not_applicable")),
        statuses=ChannelAvailability(
            **{name: DataAvailability(str(value)) for name, value in statuses.items()}
        ),
        schema_id=str(payload.get("schema_id", "")),
        schema_version=str(payload.get("schema_version", "")),
        setup_name=(str(payload["setup_name"]) if payload.get("setup_name") is not None else None),
        material=revision_pin(payload.get("material")),
        material_state=revision_pin(payload.get("material_state")),
        input_mode=(str(payload["input_mode"]) if payload.get("input_mode") is not None else None),
        based_on_plan_id=(
            _as_uuid(payload["based_on_plan_id"])
            if payload.get("based_on_plan_id") is not None
            else None
        ),
        based_on_plan_revision_id=(
            _as_uuid(payload["based_on_plan_revision_id"])
            if payload.get("based_on_plan_revision_id") is not None
            else None
        ),
        override_reason=(
            str(payload["override_reason"]) if payload.get("override_reason") is not None else None
        ),
        base_diff=(dict(cast(Mapping[str, object], base_diff)) if base_diff is not None else None),
        candidate_scope_mode=(
            str(payload["candidate_scope_mode"])
            if payload.get("candidate_scope_mode") is not None
            else None
        ),
    )


def rank_from_payload(payload: Mapping[str, object]) -> RankDiagnostic:
    return RankDiagnostic(
        singular_values=_as_float_tuple(payload.get("singular_values", ())),
        sigma_max=_as_json_float(payload.get("sigma_max", 0.0)),
        threshold=_as_json_float(payload.get("threshold", 0.0)),
        rank=_as_json_int(payload.get("rank", 0)),
        status=RankStatus(str(payload.get("status", RankStatus.FULL_RANK.value))),
        warning_code=(
            str(payload["warning_code"]) if payload.get("warning_code") is not None else None
        ),
    )


def result_from_payload(payload: Mapping[str, object]) -> CalibrationRunResult:
    attempts: list[NumericalAttempt] = []
    for item in cast(Sequence[Mapping[str, object]], payload.get("attempts", ())):
        optimizer = cast(Mapping[str, object], item.get("optimizer") or {})
        attempts.append(
            NumericalAttempt(
                ordinal=_as_json_int(item["ordinal"]),
                term_count=_as_json_int(item["term_count"]),
                start_vector=_as_float_tuple(item.get("start_vector", ())),
                transformed_start_vector=_as_float_tuple(item.get("transformed_start_vector", ())),
                status=_as_json_int(optimizer.get("status", 0)),
                message=str(optimizer.get("message", "")),
                nfev=_as_json_int(optimizer.get("nfev", 0)),
                cost=_as_json_float(optimizer.get("cost", 0.0)),
                optimality=_as_json_float(optimizer.get("optimality", 0.0)),
                active_mask=tuple(
                    _as_json_int(value)
                    for value in cast(Sequence[JsonScalar], optimizer.get("active_mask", ()))
                ),
                physical_parameters=_as_float_tuple(item.get("physical_parameters", ())),
                transformed_parameters=_as_float_tuple(item.get("transformed_parameters", ())),
                residuals=_as_float_tuple(item.get("residuals", ())),
                rss=_as_json_float(item.get("rss", 0.0)),
                rank=rank_from_payload(cast(Mapping[str, object], item.get("rank") or {})),
                warnings=tuple(
                    str(value) for value in cast(Sequence[object], item.get("warnings", ()))
                ),
                objective_history=tuple(
                    ObjectiveEvaluation(
                        ordinal=_as_json_int(history["ordinal"]),
                        transformed_parameters=_as_float_tuple(
                            history.get("transformed_parameters", ())
                        ),
                        physical_parameters=_as_float_tuple(history.get("physical_parameters", ())),
                        residuals=_as_float_tuple(history.get("residuals", ())),
                        objective=_as_json_float(history.get("objective", 0.0)),
                    )
                    for history in cast(
                        Sequence[Mapping[str, object]], item.get("objective_history", ())
                    )
                ),
                converged=bool(item.get("converged", False)),
                physical=bool(item.get("physical", False)),
            )
        )
    candidates = tuple(
        CalibrationCandidate(
            candidate_id=_as_uuid(item["candidate_id"]),
            attempt_ordinal=_as_json_int(item["attempt_ordinal"]),
            term_count=_as_json_int(item["term_count"]),
            physical_parameters=_as_float_tuple(item.get("physical_parameters", ())),
            transformed_parameters=_as_float_tuple(item.get("transformed_parameters", ())),
            rss=_as_json_float(item.get("rss", 0.0)),
            bic=_as_json_float(item.get("bic", 0.0)),
            calibration_residuals=_as_float_tuple(item.get("calibration_residuals", ())),
            holdout_residuals=_as_float_tuple(item.get("holdout_residuals", ())),
            rank=rank_from_payload(cast(Mapping[str, object], item.get("rank") or {})),
            warnings=tuple(
                str(value) for value in cast(Sequence[object], item.get("warnings", ()))
            ),
            uncertainty_status=UncertaintyStatus(
                str(item.get("uncertainty_status", UncertaintyStatus.NOT_PROVIDED.value))
            ),
        )
        for item in cast(Sequence[Mapping[str, object]], payload.get("candidates", ()))
    )
    recommendation_payload = payload.get("recommendation")
    recommendation = None
    if recommendation_payload is not None:
        item = cast(Mapping[str, object], recommendation_payload)
        recommendation = CalibrationRecommendation(
            recommendation_id=_as_uuid(item["recommendation_id"]),
            candidate_id=_as_uuid(item["candidate_id"]),
            candidate_digest=str(item["candidate_digest"]),
            rule_version=str(item.get("rule_version", "linear_viscoelastic_bic@1.0.0")),
        )
    return CalibrationRunResult(
        run_id=_as_uuid(payload["run_id"]),
        plan_revision_id=_as_uuid(payload["plan_revision_id"]),
        status=RunStatus(str(payload["status"])),
        attempts=tuple(attempts),
        candidates=candidates,
        recommendation=recommendation,
        objective_history_artifact_ids=tuple(
            _as_uuid(value)
            for value in cast(Sequence[object], payload.get("objective_history_artifact_ids", ()))
        ),
        response_residual_artifact_ids=tuple(
            _as_uuid(value)
            for value in cast(Sequence[object], payload.get("response_residual_artifact_ids", ()))
        ),
        execution_ledger_sha256=(
            str(payload["execution_ledger_sha256"])
            if payload.get("execution_ledger_sha256") is not None
            else None
        ),
        failure_code=(str(payload["failure_code"]) if payload.get("failure_code") else None),
        failure_detail=(str(payload["failure_detail"]) if payload.get("failure_detail") else None),
        recovery_hint=(str(payload["recovery_hint"]) if payload.get("recovery_hint") else None),
    )


def selection_from_payload(payload: Mapping[str, object]) -> LinearViscoelasticSelection:
    return LinearViscoelasticSelection(
        selection_id=_as_uuid(payload["selection_id"]),
        selection_revision_id=_as_uuid(payload["selection_revision_id"]),
        plan_revision_id=_as_uuid(payload["plan_revision_id"]),
        run_id=_as_uuid(payload["run_id"]),
        candidate_id=_as_uuid(payload["candidate_id"]),
        candidate_digest=str(payload["candidate_digest"]),
        reason=str(payload["reason"]),
        warning_acknowledgements=tuple(
            cast(Mapping[str, object], value)
            for value in cast(Sequence[object], payload.get("warning_acknowledgements", ()))
        ),
        actor=_as_uuid(payload["actor"]),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
    )


# Private aliases preserve the original mapper names for the repository adapter while keeping
# implementation ownership in this serialization module.
_plan_from_payload = plan_from_payload
_rank_from_payload = rank_from_payload
_result_from_payload = result_from_payload
_selection_from_payload = selection_from_payload

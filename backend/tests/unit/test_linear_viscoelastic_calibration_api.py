from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.modeling.adapters.api.linear_viscoelastic_calibration import (
    LinearViscoelasticPlanRequest,
    PlanApprovalResponse,
    PlanContextMatchResponse,
    PlanContextResolveRequest,
    ProcessedFitInputResponse,
    ProcessedLinearViscoelasticPlanRequest,
    PromotionRequest,
    RunResponse,
)
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationRunProjection,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ProcessedViscoelasticFitInput,
    ProcessedViscoelasticFitInputChannel,
    ProcessedViscoelasticFitInputRow,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    PlanApprovalRecord,
    PlanApprovalState,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    ExactRevisionPin,
    PointPartition,
)
from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    RankStatus,
    RunStatus,
    UncertaintyStatus,
)
from cmp.modules.modeling.domain.linear_viscoelastic_results import (
    CalibrationCandidate,
    CalibrationRunResult,
    RankDiagnostic,
)
from pydantic import ValidationError


def _request_document() -> dict[str, object]:
    return {
        "test_data": {"id": str(UUID(int=1)), "revision_id": str(UUID(int=2))},
        "selected_temperature_k": "298.15",
        "point_dispositions": [
            {
                "ordinal": ordinal,
                "partition": "CALIBRATION",
                "exclusion_reason": None,
            }
            for ordinal in range(3)
        ],
        "availability": {
            "ramp": "NOT_PROVIDED",
            "sweep": "NOT_PROVIDED",
            "preconditioning": "NOT_PROVIDED",
            "linear_range": "NOT_PROVIDED",
        },
        "term_counts": [1],
        "parameter_bounds": {
            "1": [
                {
                    "name": "G_inf_pa",
                    "lower": 1.0,
                    "start": 4.0,
                    "upper": 20.0,
                    "unit": "Pa",
                    "transform": "ln",
                },
                {
                    "name": "G_1_pa",
                    "lower": 1.0,
                    "start": 2.0,
                    "upper": 10.0,
                    "unit": "Pa",
                    "transform": "ln",
                },
                {
                    "name": "tau_1_s",
                    "lower": 0.01,
                    "start": 0.1,
                    "upper": 1.0,
                    "unit": "s",
                    "transform": "ln",
                },
            ]
        },
        "start_vectors": {"1": [[4.0, 2.0, 0.1]]},
        "weights": {
            "relaxation_weight": "1",
            "dma_storage_weight": "0.5",
            "dma_loss_weight": "0.5",
            "relaxation_scale_pa": "1",
            "dma_storage_scale_pa": "1",
            "dma_loss_scale_pa": "1",
            "q_rule_version": "equal_per_point@1.0.0",
        },
        "optimizer": {
            "method": "trf",
            "x_scale": "jac",
            "transform": "ln",
            "ftol": 1e-8,
            "xtol": 1e-8,
            "gtol": 1e-8,
            "max_nfev": 1000,
        },
        "recommendation_policy": "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0",
        "change_reason": "Create an exact governed calibration Plan",
    }


def test_plan_request_accepts_only_server_resolvable_source_identity() -> None:
    document = _request_document()

    request = LinearViscoelasticPlanRequest.model_validate(document)

    assert request.test_data.id == UUID(int=1)
    assert request.test_data.revision_id == UUID(int=2)
    assert request.optimizer.method == "trf"
    assert request.recommendation_policy == (
        "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0"
    )

    for forbidden in (
        "canonical_artifact",
        "normalized_artifact",
        "raw_source_sha256",
        "import_profile",
        "profile_sha256",
        "classification",
    ):
        with pytest.raises(ValidationError) as error:
            invalid = deepcopy(document)
            invalid[forbidden] = "client-controlled"
            LinearViscoelasticPlanRequest.model_validate(invalid)
        assert any(
            item["loc"] == (forbidden,) and item["type"] == "extra_forbidden"
            for item in error.value.errors()
        )


@pytest.mark.parametrize(
    "path",
    (
        ("selected_temperature_k",),
        ("point_dispositions",),
        ("availability",),
        ("weights",),
        ("optimizer",),
        ("recommendation_policy",),
        ("optimizer", "ftol"),
        ("optimizer", "max_nfev"),
    ),
)
def test_plan_request_has_no_hidden_numerical_or_input_defaults(
    path: tuple[str, ...],
) -> None:
    document = _request_document()
    target = document
    for part in path[:-1]:
        target = cast(dict[str, object], target[part])
    del target[path[-1]]

    with pytest.raises(ValidationError) as error:
        LinearViscoelasticPlanRequest.model_validate(document)

    assert any(item["loc"] == path and item["type"] == "missing" for item in error.value.errors())


def test_promotion_request_requires_all_exact_catalog_revisions() -> None:
    document = {
        "material": {"id": str(UUID(int=10)), "revision_id": str(UUID(int=11))},
        "material_state": {"id": str(UUID(int=12)), "revision_id": str(UUID(int=13))},
        "property_set": {"id": str(UUID(int=14)), "revision_id": str(UUID(int=15))},
        "change_reason": "Promote the exact engineer Selection",
    }
    parsed = PromotionRequest.model_validate(document)
    assert parsed.material.revision_id == UUID(int=11)
    assert parsed.material_state.revision_id == UUID(int=13)
    assert parsed.property_set.revision_id == UUID(int=15)

    for missing in ("material", "material_state", "property_set", "change_reason"):
        invalid = deepcopy(document)
        del invalid[missing]
        with pytest.raises(ValidationError) as error:
            PromotionRequest.model_validate(invalid)
        assert any(item["loc"] == (missing,) for item in error.value.errors())

    invalid = deepcopy(document)
    invalid["candidate_id"] = str(UUID(int=16))
    with pytest.raises(ValidationError) as error:
        PromotionRequest.model_validate(invalid)
    assert any(
        item["loc"] == ("candidate_id",) and item["type"] == "extra_forbidden"
        for item in error.value.errors()
    )


def test_processed_plan_request_pins_output_and_derives_row_policy_server_side() -> None:
    document = _request_document()
    document["processing_output"] = document.pop("test_data")
    del document["selected_temperature_k"]
    del document["point_dispositions"]
    cast(dict[str, object], document["availability"])["sweep"] = "PROVIDED"

    request = ProcessedLinearViscoelasticPlanRequest.model_validate(document)
    command = request.to_command("processed-plan-key")

    assert command.processing_output_id == UUID(int=1)
    assert command.processing_output_revision_id == UUID(int=2)
    assert command.idempotency_key == "processed-plan-key"
    assert command.availability.sweep.value == "PROVIDED"
    for forbidden in ("selected_temperature_k", "point_dispositions", "result_artifact"):
        invalid = deepcopy(document)
        invalid[forbidden] = "client-controlled"
        with pytest.raises(ValidationError) as error:
            ProcessedLinearViscoelasticPlanRequest.model_validate(invalid)
        assert any(
            item["loc"] == (forbidden,) and item["type"] == "extra_forbidden"
            for item in error.value.errors()
        )


def test_governed_plan_request_exposes_exact_setup_and_advanced_clone_contract() -> None:
    document = _request_document()
    document.update(
        {
            "setup_name": "Approved relaxation setup",
            "material": {"id": str(UUID(int=10)), "revision_id": str(UUID(int=11))},
            "material_state": {"id": str(UUID(int=12)), "revision_id": str(UUID(int=13))},
            "input_mode": "relaxation",
            "based_on_plan_id": str(UUID(int=14)),
            "based_on_plan_revision_id": str(UUID(int=15)),
            "override_reason": "Compare a separately approved optimizer tolerance.",
        }
    )
    request = LinearViscoelasticPlanRequest.model_validate(document)
    command = request.to_command("advanced-clone")

    assert command.setup_name == "Approved relaxation setup"
    assert command.material == ExactRevisionPin(UUID(int=10), UUID(int=11))
    assert command.material_state == ExactRevisionPin(UUID(int=12), UUID(int=13))
    assert command.input_mode == "relaxation"
    assert command.based_on_plan_id == UUID(int=14)
    assert command.based_on_plan_revision_id == UUID(int=15)
    assert command.override_reason == "Compare a separately approved optimizer tolerance."

    for forbidden in ("canonical_artifact", "raw_source_sha256", "profile_sha256"):
        invalid = deepcopy(document)
        invalid[forbidden] = "client-controlled"
        with pytest.raises(ValidationError) as error:
            LinearViscoelasticPlanRequest.model_validate(invalid)
        assert any(item["type"] == "extra_forbidden" for item in error.value.errors())


def test_governed_source_identity_and_mode_are_optional_client_hints() -> None:
    document = _request_document()
    document["setup_name"] = "Server-resolved setup"
    document.pop("material", None)
    document.pop("material_state", None)
    document.pop("input_mode", None)

    request = LinearViscoelasticPlanRequest.model_validate(document)
    command = request.to_command(None)

    assert command.setup_name == "Server-resolved setup"
    assert command.material is None
    assert command.material_state is None
    assert command.input_mode is None


def test_exact_context_request_and_approval_response_pin_review_evidence() -> None:
    request = PlanContextResolveRequest.model_validate(
        {
            "material": {"id": str(UUID(int=10)), "revision_id": str(UUID(int=11))},
            "material_state": {"id": str(UUID(int=12)), "revision_id": str(UUID(int=13))},
            "test_data": {"id": str(UUID(int=14)), "revision_id": str(UUID(int=15))},
            "processing_output": None,
            "input_mode": "relaxation",
        }
    )
    query = request.to_query()
    assert query.material == ExactRevisionPin(UUID(int=10), UUID(int=11))
    assert query.material_state == ExactRevisionPin(UUID(int=12), UUID(int=13))
    assert query.test_data == ExactRevisionPin(UUID(int=14), UUID(int=15))
    assert query.processing_output is None

    approval = PlanApprovalRecord(
        plan_id=UUID(int=20),
        plan_revision_id=UUID(int=21),
        plan_sha256="a" * 64,
        classification=DataClassification.INTERNAL,
        plan_created_by=UUID(int=22),
        review_request_id=UUID(int=23),
        review_decision_id=UUID(int=24),
        evidence_sha256="b" * 64,
        approved_at=datetime(2026, 9, 1, tzinfo=UTC),
        approved_by=UUID(int=25),
        state=PlanApprovalState.ACTIVE,
        setup_name="Exact setup",
        material=ExactRevisionPin(UUID(int=10), UUID(int=11)),
        material_state=ExactRevisionPin(UUID(int=12), UUID(int=13)),
        test_data=ExactRevisionPin(UUID(int=14), UUID(int=15), "c" * 64),
        processing_output=None,
        input_mode="relaxation",
    )
    response = PlanApprovalResponse.from_domain(approval).model_dump(mode="json")
    match = PlanContextMatchResponse.from_domain(approval).model_dump(mode="json")

    assert response["state"] == "active"
    assert response["review_request_id"] == str(UUID(int=23))
    assert response["review_decision_id"] == str(UUID(int=24))
    assert response["evidence_sha256"] == "b" * 64
    assert response["material"] == {
        "id": str(UUID(int=10)),
        "revision_id": str(UUID(int=11)),
        "sha256": None,
    }
    assert match["approval"] == response


def test_processed_fit_input_response_exposes_values_without_internal_identity() -> None:
    response = ProcessedFitInputResponse.from_domain(
        ProcessedViscoelasticFitInput(
            mode="dma_frequency_master_curve",
            coordinate_quantity="frequency.angular.reduced",
            coordinate_unit="rad/s",
            response_channels=(
                ProcessedViscoelasticFitInputChannel(
                    "dma_storage", "mechanics.modulus.storage", "Pa"
                ),
                ProcessedViscoelasticFitInputChannel(
                    "dma_loss", "mechanics.modulus.loss", "Pa"
                ),
            ),
            reference_temperature_k=Decimal("313.15"),
            rows=(
                ProcessedViscoelasticFitInputRow(
                    ordinal=0,
                    coordinate=6.283185307179586,
                    storage_modulus_pa=3_000_000.0,
                    loss_modulus_pa=100_000.0,
                    partition=PointPartition.CALIBRATION,
                    exclusion_reason=None,
                ),
                ProcessedViscoelasticFitInputRow(
                    ordinal=1,
                    coordinate=None,
                    storage_modulus_pa=0.0,
                    loss_modulus_pa=-1.0,
                    partition=PointPartition.EXCLUDED,
                    exclusion_reason="invalid reduced frequency",
                ),
            ),
        )
    )
    payload = response.model_dump(mode="json")

    assert payload["rows"][0]["coordinate"] == 6.283185307179586
    assert payload["rows"][0]["storage_modulus_pa"] == 3_000_000.0
    assert payload["rows"][1] == {
        "ordinal": 1,
        "coordinate": None,
        "storage_modulus_pa": 0.0,
        "loss_modulus_pa": -1.0,
        "partition": "EXCLUDED",
        "exclusion_reason": "invalid reduced frequency",
    }
    forbidden = {"id", "revision_id", "artifact_id", "sha256", "schema_ref", "digest"}
    assert forbidden.isdisjoint(payload)
    assert forbidden.isdisjoint(payload["rows"][0])


def test_run_response_transports_server_candidate_digest_for_selection() -> None:
    run_id = UUID(int=20)
    plan_revision_id = UUID(int=21)
    candidate = CalibrationCandidate(
        candidate_id=UUID(int=22),
        attempt_ordinal=1,
        term_count=1,
        physical_parameters=(1.0, 2.0, 0.1),
        transformed_parameters=(0.0, 0.69, -2.3),
        rss=1.0,
        bic=2.0,
        calibration_residuals=(1.0, -1.0),
        holdout_residuals=(2.0,),
        rank=RankDiagnostic((1.0,), 1.0, 0.1, 1, RankStatus.FULL_RANK),
        warnings=(),
        uncertainty_status=UncertaintyStatus.NOT_PROVIDED,
    )
    result = CalibrationRunResult(
        run_id=run_id,
        plan_revision_id=plan_revision_id,
        status=RunStatus.SUCCEEDED,
        attempts=(),
        candidates=(candidate,),
        recommendation=None,
    )
    projection = CalibrationRunProjection(
        id=run_id,
        plan_id=UUID(int=23),
        plan_revision_id=plan_revision_id,
        plan_sha256="a" * 64,
        classification=DataClassification.INTERNAL,
        job_id=UUID(int=24),
        status=RunStatus.SUCCEEDED.value,
        result=result,
        execution_ledger=(),
        idempotency_key="api-test",
        request_sha256="b" * 64,
        created_at=datetime.now(UTC),
        created_by=UUID(int=25),
    )

    response = RunResponse.from_domain(projection)

    assert response.candidates[0]["candidate_sha256"] == candidate.digest

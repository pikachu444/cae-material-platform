from __future__ import annotations

from copy import deepcopy
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.modeling.adapters.api.linear_viscoelastic_calibration import (
    LinearViscoelasticPlanRequest,
    ProcessedLinearViscoelasticPlanRequest,
    PromotionRequest,
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

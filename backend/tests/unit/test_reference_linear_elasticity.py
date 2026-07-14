from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    InvalidReferenceModel,
    ReferenceCalibrationEvidence,
    ReferenceLinearElasticContent,
    reference_linear_elastic_canonical,
    reference_linear_elastic_ir,
)

MATERIAL = UUID("d1000000-0000-4000-8000-000000000001")
MATERIAL_REVISION = UUID("d1000000-0000-4000-8000-000000000002")
STATE = UUID("d1000000-0000-4000-8000-000000000003")
STATE_REVISION = UUID("d1000000-0000-4000-8000-000000000004")
PROPERTY_SET = UUID("d1000000-0000-4000-8000-000000000005")
PROPERTY_SET_REVISION = UUID("d1000000-0000-4000-8000-000000000006")
MODEL = UUID("d1000000-0000-4000-8000-000000000007")
MODEL_REVISION = UUID("d1000000-0000-4000-8000-000000000008")
SELECTION = UUID("d1000000-0000-4000-8000-000000000009")
SELECTION_REVISION = UUID("d1000000-0000-4000-8000-00000000000a")
RUN = UUID("d1000000-0000-4000-8000-00000000000b")
CANDIDATE = UUID("d1000000-0000-4000-8000-00000000000c")
DIAGNOSTICS = UUID("d1000000-0000-4000-8000-00000000000d")


def _content(**changes: object) -> ReferenceLinearElasticContent:
    values: dict[str, object] = {
        "material_id": MATERIAL,
        "material_revision_id": MATERIAL_REVISION,
        "material_state_id": STATE,
        "material_state_revision_id": STATE_REVISION,
        "property_set_id": PROPERTY_SET,
        "property_set_revision_id": PROPERTY_SET_REVISION,
        "density_kg_per_m3": 7850.0,
        "youngs_modulus_pa": 210_000_000_000.0,
        "poisson_ratio": 0.3,
        "source_yield_stress_pa": 355_000_000.0,
    }
    values.update(changes)
    return ReferenceLinearElasticContent(**values)  # type: ignore[arg-type]


def test_reference_ir_is_typed_solver_neutral_and_preserves_unmapped_source_value() -> None:
    content = _content()

    canonical = reference_linear_elastic_canonical(content)
    ir = reference_linear_elastic_ir(
        content,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
    )

    assert canonical["model_family_id"] == REFERENCE_MODEL_FAMILY_ID
    assert canonical["source_yield_stress_pa"] == 355_000_000.0
    assert "key" not in canonical
    assert "value" not in canonical
    model_family = ir["model_family"]
    payload = ir["payload"]
    assert isinstance(model_family, dict)
    assert isinstance(payload, dict)
    assert model_family["id"] == REFERENCE_MODEL_FAMILY_ID
    assert payload["model"] == "isotropic_linear_elasticity"
    assert payload["density"] == {"value": 7850.0, "unit": "kg/m3"}
    disposition = payload["source_property_disposition"]
    assert isinstance(disposition, dict)
    assert disposition["yield_stress"] == {
        "value": 355_000_000.0,
        "unit": "Pa",
        "status": "not_applicable_to_linear_elasticity",
    }
    assert ir["non_production"] is True


@pytest.mark.parametrize("poisson_ratio", (-1.0, 0.5, float("nan")))
def test_reference_ir_rejects_unstable_isotropic_constants(poisson_ratio: float) -> None:
    with pytest.raises(InvalidReferenceModel, match="stable isotropic interval"):
        _content(poisson_ratio=poisson_ratio)


def test_reference_ir_rejects_nonpositive_unmapped_yield_source_value() -> None:
    with pytest.raises(InvalidReferenceModel, match="source_yield_stress_pa"):
        _content(source_yield_stress_pa=0.0)


def test_reference_ir_records_typed_candidate_selection_evidence_without_changing_model_schema(
) -> None:
    evidence = ReferenceCalibrationEvidence(
        calibration_selection_id=SELECTION,
        calibration_selection_revision_id=SELECTION_REVISION,
        calibration_run_id=RUN,
        calibration_candidate_id=CANDIDATE,
        calibration_candidate_sha256="c" * 64,
        diagnostics_artifact_id=DIAGNOSTICS,
        diagnostics_sha256="d" * 64,
    )
    content = _content(calibration_evidence=evidence)

    canonical = reference_linear_elastic_canonical(content)
    ir = reference_linear_elastic_ir(
        content,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
    )

    assert canonical["calibration_evidence"] == {
        "status": "reference_candidate_selected",
        "selection_id": str(SELECTION),
        "selection_revision_id": str(SELECTION_REVISION),
        "calibration_run_id": str(RUN),
        "calibration_candidate_id": str(CANDIDATE),
        "calibration_candidate_sha256": "c" * 64,
        "diagnostics_artifact_id": str(DIAGNOSTICS),
        "diagnostics_sha256": "d" * 64,
    }
    assert ir["calibration_evidence"] == {
        "status": "reference_candidate_selected",
        "selection_id": str(SELECTION),
        "selection_revision_id": str(SELECTION_REVISION),
        "calibration_run_id": str(RUN),
        "candidate_id": str(CANDIDATE),
        "candidate_sha256": f"sha256:{'c' * 64}",
        "diagnostics_artifact_id": str(DIAGNOSTICS),
        "diagnostics_sha256": f"sha256:{'d' * 64}",
        "selection_decision": "accepted_for_reference_ir_promotion",
    }

from __future__ import annotations

import math
from uuid import uuid4

import pytest
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ElastoplasticExportTarget,
    build_reference_elastoplastic_solver_card,
    preflight_reference_elastoplastic_export,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningPointOrigin,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    InvalidVoceProjection,
    ReferenceVoceTabulatedPlasticityContent,
    voce_fixed_grid_hardening_curve,
)


def test_fixed_grid_projects_exact_voce_parameters_and_explicit_extension() -> None:
    points = voce_fixed_grid_hardening_curve(
        sigma_0_pa=300e6,
        q_pa=200e6,
        b=12.0,
        characterized_max_true_plastic_strain=0.2,
        extension_max_true_plastic_strain=0.5,
        sampling_point_count=21,
        acknowledge_constant_extension=True,
    )

    assert len(points) == 22
    assert points[0].true_plastic_strain == 0.0
    assert points[0].true_yield_stress_pa == 300e6
    assert points[0].origin is HardeningPointOrigin.CALIBRATED_VOCE_SAMPLE
    assert points[10].true_yield_stress_pa == pytest.approx(
        300e6 + 200e6 * (1.0 - math.exp(-12.0 * 0.1))
    )
    assert points[-1].true_plastic_strain == 0.5
    assert points[-1].true_yield_stress_pa == points[-2].true_yield_stress_pa
    assert points[-1].origin is HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION


def test_fixed_grid_rejects_silent_extension_and_underspecified_grid() -> None:
    with pytest.raises(InvalidVoceProjection, match="acknowledgement"):
        voce_fixed_grid_hardening_curve(
            sigma_0_pa=300e6,
            q_pa=200e6,
            b=12.0,
            characterized_max_true_plastic_strain=0.2,
            extension_max_true_plastic_strain=0.5,
            sampling_point_count=21,
            acknowledge_constant_extension=False,
        )


def test_projected_voce_ir_exports_openradioss_and_abaqus_from_same_curve() -> None:
    points = voce_fixed_grid_hardening_curve(
        sigma_0_pa=300e6,
        q_pa=200e6,
        b=12.0,
        characterized_max_true_plastic_strain=0.2,
        extension_max_true_plastic_strain=0.5,
        sampling_point_count=21,
        acknowledge_constant_extension=True,
    )
    ids = [uuid4() for _ in range(17)]
    content = ReferenceVoceTabulatedPlasticityContent(
        material_id=ids[0],
        material_revision_id=ids[1],
        material_state_id=ids[2],
        material_state_revision_id=ids[3],
        property_set_id=ids[4],
        property_set_revision_id=ids[5],
        calibration_input_scope_id=ids[6],
        calibration_input_scope_revision_id=ids[7],
        voce_calibration_plan_id=ids[8],
        voce_calibration_plan_revision_id=ids[9],
        voce_calibration_run_id=ids[10],
        voce_calibration_candidate_id=ids[11],
        voce_calibration_candidate_sha256="a" * 64,
        voce_candidate_selection_id=ids[12],
        voce_candidate_selection_revision_id=ids[13],
        hardening_curve_artifact_id=ids[14],
        hardening_curve_sha256="b" * 64,
        hardening_curve_point_count=len(points),
        sampling_point_count=21,
        density_kg_per_m3=7800.0,
        youngs_modulus_pa=210e9,
        poisson_ratio=0.3,
        initial_yield_stress_pa=300e6,
        q_pa=200e6,
        b=12.0,
        characterized_max_true_plastic_strain=0.2,
        extension_max_true_plastic_strain=0.5,
        post_necking_approximation_acknowledged=True,
    )
    model_id, revision_id = ids[15], ids[16]

    for target in (
        ElastoplasticExportTarget("openradioss", "2025", "kg_m_s"),
        ElastoplasticExportTarget("abaqus", "2025", "kg_m_s"),
    ):
        report = preflight_reference_elastoplastic_export(
            material_model_id=model_id,
            material_model_revision_id=revision_id,
            content=content,
            target=target,
        )
        _, card = build_reference_elastoplastic_solver_card(
            material_model_id=model_id,
            material_model_revision_id=revision_id,
            source=content,
            points=points,
            target=target,
            expected_mapping_report_sha256=report.digest,
            solver_material_id=101,
            material_name="CALIBRATED_STEEL",
        )
        assert card.model_schema_digest == content.model_schema_digest
        if target.solver == "openradioss":
            assert "/MAT/LAW36/101/1" in card.card_text
        else:
            assert "*PLASTIC, HARDENING=ISOTROPIC" in card.card_text
    with pytest.raises(InvalidVoceProjection, match="between 21 and 501"):
        voce_fixed_grid_hardening_curve(
            sigma_0_pa=300e6,
            q_pa=200e6,
            b=12.0,
            characterized_max_true_plastic_strain=0.2,
            extension_max_true_plastic_strain=0.5,
            sampling_point_count=20,
            acknowledge_constant_extension=True,
        )

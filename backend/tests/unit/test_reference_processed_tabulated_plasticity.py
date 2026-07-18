from __future__ import annotations

from dataclasses import replace
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ElastoplasticExportTarget,
    build_reference_elastoplastic_solver_card,
    preflight_reference_elastoplastic_export,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningCurvePoint,
    HardeningPointOrigin,
    hardening_curve_from_parquet,
    hardening_curve_parquet_bytes,
)
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST,
    REFERENCE_PROCESSED_SELECTION_PROFILE_ID,
    InvalidProcessedProjection,
    ReferenceProcessedTabulatedPlasticityContent,
    reference_processed_tabulated_plasticity_canonical,
    reference_processed_tabulated_plasticity_ir,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _points() -> tuple[HardeningCurvePoint, ...]:
    return tuple(
        HardeningCurvePoint(
            true_plastic_strain=ordinal / 40,
            true_yield_stress_pa=250e6 + ordinal * 5e6,
            origin=HardeningPointOrigin.PROCESSING_SELECTED_SAMPLE,
        )
        for ordinal in range(21)
    )


def _content() -> ReferenceProcessedTabulatedPlasticityContent:
    return ReferenceProcessedTabulatedPlasticityContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        processing_output_id=_id(7),
        processing_output_revision_id=_id(8),
        processing_output_sha256="1" * 64,
        source_test_data_id=_id(9),
        source_test_data_revision_id=_id(10),
        mapping_profile_id=_id(11),
        mapping_profile_revision_id=_id(12),
        candidate_families=("voce", "swift"),
        primary_family="swift",
        secondary_family="voce",
        primary_weight=0.5,
        fit_minimum_true_plastic_strain=0.0001,
        characterized_max_true_plastic_strain=0.1,
        extension_max_true_plastic_strain=0.5,
        hardening_curve_artifact_id=_id(13),
        hardening_curve_sha256="2" * 64,
        hardening_curve_point_count=21,
        density_kg_per_m3=7850,
        youngs_modulus_pa=210e9,
        poisson_ratio=0.3,
        initial_yield_stress_pa=250e6,
        post_necking_approximation_acknowledged=True,
    )


def test_processed_projection_round_trips_typed_curve_and_lineage() -> None:
    points = _points()
    payload = hardening_curve_parquet_bytes(
        points,
        transformation_profile_id=REFERENCE_PROCESSED_SELECTION_PROFILE_ID,
        transformation_profile_digest=REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST,
    )

    assert (
        hardening_curve_from_parquet(
            payload,
            transformation_profile_id=REFERENCE_PROCESSED_SELECTION_PROFILE_ID,
            transformation_profile_digest=REFERENCE_PROCESSED_SELECTION_PROFILE_DIGEST,
        )
        == points
    )
    content = _content()
    canonical = reference_processed_tabulated_plasticity_canonical(content)
    ir = reference_processed_tabulated_plasticity_ir(
        material_model_id=_id(20),
        material_model_revision_id=_id(21),
        content=content,
    )
    processing_output = cast(dict[str, Any], canonical["processing_output"])
    selection = cast(dict[str, Any], canonical["selection"])
    source_revisions = cast(dict[str, Any], ir["source_revisions"])
    assert processing_output["revision_id"] == str(_id(8))
    assert selection["candidate_families"] == ["voce", "swift"]
    assert source_revisions["source_test_data_revision_id"] == str(_id(10))


def test_processed_projection_rejects_unbounded_or_undeclared_selection() -> None:
    with pytest.raises(InvalidProcessedProjection, match="selected families"):
        replace(_content(), primary_family="ghosh")


@pytest.mark.parametrize("solver", ["abaqus", "openradioss"])
def test_processed_projection_generates_explicit_multisolver_cards(solver: str) -> None:
    source = _content()
    points = _points()
    target = ElastoplasticExportTarget(solver, "2025", "kg_m_s")
    report = preflight_reference_elastoplastic_export(
        material_model_id=_id(20),
        material_model_revision_id=_id(21),
        content=source,
        target=target,
    )
    _, card = build_reference_elastoplastic_solver_card(
        material_model_id=_id(20),
        material_model_revision_id=_id(21),
        source=source,
        points=points,
        target=target,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=42,
        material_name="DP600_PROCESSED",
    )

    assert report.model_schema_digest == source.model_schema_digest
    assert "bounded extension" in report.items[4].detail
    expected_keyword = "*PLASTIC" if solver == "abaqus" else "/MAT/LAW36"
    assert expected_keyword in card.card_text

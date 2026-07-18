import json
from dataclasses import replace
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingReportMismatch,
    build_neutral_hyperelastic_solver_card,
    neutral_hyperelastic_capability_manifest,
    preflight_neutral_hyperelastic_export,
)
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    CurveStage,
    EvidenceStatus,
    InvalidNeutralMaterial,
    NeutralCandidateSelection,
    NeutralCurve,
    NeutralDatasetSource,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralMaterialDocument,
    OptionalRevisionEvidence,
    RevisionReference,
    neutral_material_from_json_bytes,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationRole,
    OgdenTestMode,
)

IDS = tuple(UUID(int=value) for value in range(1, 24))
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def _reference(offset: int) -> RevisionReference:
    return RevisionReference(IDS[offset], IDS[offset + 1])


def _document(
    *, parameters: NeutralHyperelasticParameters | None = None
) -> NeutralMaterialDocument:
    dataset = _reference(14)
    curves = tuple(
        NeutralCurve(
            stage=stage,
            dataset_revision_id=dataset.revision_id,
            test_mode=OgdenTestMode.UNIAXIAL_TENSION,
            x_quantity="strain.engineering",
            x_unit="1",
            y_quantity=(
                "stress.nominal.residual" if stage is CurveStage.RESIDUAL else "stress.nominal"
            ),
            y_unit="Pa",
            x=(0.0, 0.1, 0.2),
            y=(0.0, 1_000_000.0, 2_000_000.0),
        )
        for stage in CurveStage
    )
    return NeutralMaterialDocument(
        document_id=IDS[0],
        organization_id=IDS[1],
        project_id=IDS[2],
        classification="internal",
        material=_reference(3),
        material_state=_reference(5),
        property_set=_reference(7),
        calibration_plan=_reference(9),
        scientific_profile=_reference(11),
        mapping_profile=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE,
            "T-55E consumes a governed normalized Dataset revision directly.",
        ),
        processing_recipe=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE,
            "No Processing Recipe was used for this exact reference run.",
        ),
        source_datasets=(
            NeutralDatasetSource(
                dataset=dataset,
                role=OgdenCalibrationRole.CALIBRATION,
                test_mode=OgdenTestMode.UNIAXIAL_TENSION,
                normalized_artifact_id=IDS[16],
                normalized_artifact_sha256=DIGEST_A,
            ),
        ),
        curves=curves,
        selection=NeutralCandidateSelection(
            calibration_run_id=IDS[17],
            candidate_id=IDS[18],
            candidate_sha256=DIGEST_B,
            diagnostics_artifact_id=IDS[19],
            diagnostics_sha256=DIGEST_C,
            reason="Lowest reference objective with a monotonic fitted-domain response.",
            objective_total=0.001,
            calibration_normalized_rmse=0.01,
            holdout_normalized_rmse=None,
            stability_status="monotonic_on_fitted_domain",
            warnings=("no_holdout_data",),
        ),
        material_model_ir=NeutralHyperelasticIR(
            model=_reference(20),
            schema_id="urn:cmp:modeling:reference-hyperelastic:1.0.0",
            schema_version="1.0.0",
            model_schema_digest="d" * 64,
            parameters=parameters
            or NeutralHyperelasticParameters(
                HyperelasticFamily.MOONEY_RIVLIN,
                c10_pa=1_000_000.0,
                c01_pa=250_000.0,
            ),
            density_kg_per_m3=1100.0,
            volumetric_response="incompressible",
        ),
        applicable_strain_min=0.0,
        applicable_strain_max=0.2,
        validation_status="reference_numerical_checks_passed",
    )


@pytest.mark.parametrize(
    "parameters",
    (
        NeutralHyperelasticParameters(HyperelasticFamily.NEO_HOOKEAN, c10_pa=1.0),
        NeutralHyperelasticParameters(HyperelasticFamily.MOONEY_RIVLIN, c10_pa=1.0, c01_pa=2.0),
        NeutralHyperelasticParameters(
            HyperelasticFamily.YEOH, c10_pa=1.0, c20_pa=-0.2, c30_pa=0.03
        ),
        NeutralHyperelasticParameters(HyperelasticFamily.OGDEN_1, mu_pa=1.0, alpha=2.0),
    ),
)
def test_neutral_material_round_trip_is_deterministic_for_each_typed_family(
    parameters: NeutralHyperelasticParameters,
) -> None:
    source = _document(parameters=parameters)

    encoded = source.to_json_bytes()
    decoded = neutral_material_from_json_bytes(encoded)

    assert decoded == source
    assert decoded.to_json_bytes() == encoded
    assert json.loads(encoded)["content_sha256"] == source.content_sha256


def test_neutral_material_rejects_digest_tampering() -> None:
    raw = json.loads(_document().to_json_bytes())
    raw["candidate_selection"]["reason"] = "Silently changed selection reason."

    with pytest.raises(InvalidNeutralMaterial, match="content_sha256"):
        neutral_material_from_json_bytes(json.dumps(raw).encode())


def test_neutral_material_rejects_family_parameter_smuggling() -> None:
    with pytest.raises(InvalidNeutralMaterial, match="requires exactly"):
        NeutralHyperelasticParameters(
            HyperelasticFamily.NEO_HOOKEAN,
            c10_pa=1.0,
            alpha=2.0,
        )


def test_optional_revision_evidence_cannot_hide_a_moving_or_missing_reference() -> None:
    with pytest.raises(InvalidNeutralMaterial, match="requires a reference"):
        OptionalRevisionEvidence(EvidenceStatus.EXACT_REVISION, "A profile was used.")
    with pytest.raises(InvalidNeutralMaterial, match="forbids one"):
        OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE,
            "No recipe was used.",
            _reference(0),
        )


def test_neutral_material_requires_all_observed_predicted_and_residual_stages() -> None:
    document = _document()

    with pytest.raises(InvalidNeutralMaterial, match="normalized, fitted, and residual"):
        replace(
            document,
            curves=tuple(
                curve for curve in document.curves if curve.stage is not CurveStage.RESIDUAL
            ),
        )


@pytest.mark.parametrize("family", tuple(HyperelasticFamily))
@pytest.mark.parametrize("solver", ("abaqus", "openradioss"))
def test_neutral_hyperelastic_preflight_and_card_cover_declared_families(
    family: HyperelasticFamily, solver: str
) -> None:
    parameters = {
        HyperelasticFamily.NEO_HOOKEAN: lambda: NeutralHyperelasticParameters(
            family, c10_pa=1_000_000.0
        ),
        HyperelasticFamily.MOONEY_RIVLIN: lambda: NeutralHyperelasticParameters(
            family, c10_pa=800_000.0, c01_pa=200_000.0
        ),
        HyperelasticFamily.YEOH: lambda: NeutralHyperelasticParameters(
            family, c10_pa=1_000_000.0, c20_pa=-20_000.0, c30_pa=3_000.0
        ),
        HyperelasticFamily.OGDEN_1: lambda: NeutralHyperelasticParameters(
            family, mu_pa=2_000_000.0, alpha=2.5
        ),
    }[family]()
    source = _document(parameters=parameters)
    target = NeutralHyperelasticExportTarget(solver, "2025", "kg_m_s")

    report = preflight_neutral_hyperelastic_export(
        neutral_material_id=source.document_id,
        neutral_material_revision_id=source.material_model_ir.model.revision_id,
        source=source,
        target=target,
    )
    _, card = build_neutral_hyperelastic_solver_card(
        neutral_material_id=source.document_id,
        neutral_material_revision_id=source.material_model_ir.model.revision_id,
        source=source,
        target=target,
        expected_mapping_report_sha256=report.digest,
        solver_material_id=301,
        material_name="ELASTOMER_REFERENCE",
    )

    assert report.exportable
    assert card.card_text.endswith("\n")
    assert family.value in card.canonical()["family"]
    assert ("*HYPERELASTIC" in card.card_text) is (solver == "abaqus")
    assert ("/MAT/LAW" in card.card_text) is (solver == "openradioss")


def test_neutral_hyperelastic_openradioss_mappings_expose_transform_and_approximation() -> None:
    source = _document()
    report = preflight_neutral_hyperelastic_export(
        neutral_material_id=source.document_id,
        neutral_material_revision_id=source.material_model_ir.model.revision_id,
        source=source,
        target=NeutralHyperelasticExportTarget("openradioss", "2025", "kg_m_s"),
    )

    statuses = {item.name: item.status for item in report.items}
    assert statuses["constitutive_parameters"] == "transformed"
    assert statuses["volumetric_response"] == "approximated"


def test_neutral_hyperelastic_card_requires_acknowledged_current_report() -> None:
    source = _document()
    with pytest.raises(NeutralHyperelasticMappingReportMismatch):
        build_neutral_hyperelastic_solver_card(
            neutral_material_id=source.document_id,
            neutral_material_revision_id=source.material_model_ir.model.revision_id,
            source=source,
            target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
            expected_mapping_report_sha256="0" * 64,
            solver_material_id=301,
            material_name="ELASTOMER_REFERENCE",
        )


def test_neutral_hyperelastic_capability_manifest_is_digest_pinned() -> None:
    manifest = neutral_hyperelastic_capability_manifest()

    assert len(manifest["capabilities"]) == 8
    assert len(str(manifest["manifest_sha256"])) == 64

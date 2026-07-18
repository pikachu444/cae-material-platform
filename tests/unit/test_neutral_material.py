import json
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingReportMismatch,
    build_neutral_hyperelastic_solver_card,
    neutral_hyperelastic_capability_manifest,
    preflight_neutral_hyperelastic_export,
)
from cmp.modules.modeling.application.neutral_material import _metal_curves
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    HYPERELASTIC_CURVE_STAGES,
    CurveStage,
    EvidenceStatus,
    InvalidNeutralMaterial,
    NeutralArtifactReference,
    NeutralCandidateSelection,
    NeutralCurve,
    NeutralDatasetKind,
    NeutralDatasetRole,
    NeutralDatasetSource,
    NeutralElastoplasticIR,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralLinearViscoelasticIR,
    NeutralMaterialDocument,
    NeutralProcessingSelection,
    NeutralPronyOverlay,
    NeutralPronyTerm,
    NeutralTestMode,
    OptionalRevisionEvidence,
    RevisionReference,
    neutral_material_from_json_bytes,
)
from jsonschema import Draft202012Validator

IDS = tuple(UUID(int=value) for value in range(1, 24))
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
NEUTRAL_SCHEMA = json.loads(
    (Path(__file__).parents[2] / "contracts/modeling/neutral-material.schema.json").read_text(
        encoding="utf-8"
    )
)


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
            test_mode=NeutralTestMode.UNIAXIAL_TENSION,
            x_quantity="strain.engineering",
            x_unit="1",
            y_quantity=(
                "stress.nominal.residual" if stage is CurveStage.RESIDUAL else "stress.nominal"
            ),
            y_unit="Pa",
            x=(0.0, 0.1, 0.2),
            y=(0.0, 1_000_000.0, 2_000_000.0),
        )
        for stage in HYPERELASTIC_CURVE_STAGES
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
                role=NeutralDatasetRole.CALIBRATION,
                test_mode=NeutralTestMode.UNIAXIAL_TENSION,
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


def test_metal_neutral_material_round_trip_preserves_selected_hardening_evidence() -> None:
    source = _document()
    dataset = source.source_datasets[0].dataset
    metal = replace(
        source,
        calibration_plan=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE,
            "The selected hardening curve is owned by an exact Processing Output.",
        ),
        scientific_profile=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE,
            "No calibration scientific profile was used for processing selection.",
        ),
        source_datasets=(
            replace(
                source.source_datasets[0],
                role=NeutralDatasetRole.PROCESSING_INPUT,
                test_mode=NeutralTestMode.UNIAXIAL_TENSION,
                source_kind=NeutralDatasetKind.TEST_DATA_DOCUMENT,
            ),
        ),
        curves=tuple(
            NeutralCurve(
                stage=stage,
                dataset_revision_id=dataset.revision_id,
                test_mode=NeutralTestMode.UNIAXIAL_TENSION,
                x_quantity="strain.true_plastic",
                x_unit="1",
                y_quantity="stress.true",
                y_unit="Pa",
                x=(0.0, 0.1, 0.25),
                y=(450e6, 650e6, 790e6),
            )
            for stage in (
                CurveStage.NORMALIZED,
                CurveStage.PROCESSED,
                CurveStage.FITTED,
                CurveStage.EXTRAPOLATED,
            )
        ),
        selection=NeutralProcessingSelection(
            processing_output=_reference(17),
            processing_output_sha256=DIGEST_B,
            reason="Reviewed Voce-Swift blend with bounded post-necking extension.",
            selected_series="stress.hardening.selected",
            candidate_families=("voce", "swift", "hockett_sherby", "ghosh"),
            primary_family="voce",
            secondary_family="swift",
            primary_weight=0.7,
            warnings=("post_necking_approximation",),
        ),
        material_model_ir=NeutralElastoplasticIR(
            model=_reference(20),
            schema_id="urn:cmp:modeling:reference-processed-tabulated-plasticity:1.2.0",
            schema_version="1.2.0",
            model_schema_digest="d" * 64,
            density_kg_per_m3=7850.0,
            youngs_modulus_pa=210e9,
            poisson_ratio=0.3,
            initial_yield_stress_pa=450e6,
            hardening_curve=NeutralArtifactReference(
                IDS[22], DIGEST_C, "urn:cmp:modeling:hardening-curve:1.0.0", 101
            ),
            candidate_families=("voce", "swift", "hockett_sherby", "ghosh"),
            primary_family="voce",
            secondary_family="swift",
            primary_weight=0.7,
            characterized_max_true_plastic_strain=0.18,
            extension_max_true_plastic_strain=0.4,
            extrapolation_policy="selected_fitted_bounded_extrapolation",
            approximation_acknowledged=True,
        ),
        applicable_strain_min=0.0,
        applicable_strain_max=0.4,
    )

    decoded = neutral_material_from_json_bytes(metal.to_json_bytes())

    assert decoded == metal
    assert decoded.material_model_ir.family.value == "isotropic_tabulated_plasticity"
    Draft202012Validator(NEUTRAL_SCHEMA).validate(metal.canonical())


def test_polymer_neutral_material_round_trip_preserves_generalized_maxwell_terms() -> None:
    source = _document()
    dataset = source.source_datasets[0].dataset
    polymer = replace(
        source,
        source_datasets=(
            replace(
                source.source_datasets[0],
                role=NeutralDatasetRole.CALIBRATION,
                test_mode=NeutralTestMode.STRESS_RELAXATION,
                source_kind=NeutralDatasetKind.SHEAR_RELAXATION_DATASET,
            ),
        ),
        curves=tuple(
            NeutralCurve(
                stage=stage,
                dataset_revision_id=dataset.revision_id,
                test_mode=NeutralTestMode.STRESS_RELAXATION,
                x_quantity="time",
                x_unit="s",
                y_quantity="modulus.shear.relaxation",
                y_unit="Pa",
                x=(0.1, 1.0, 10.0),
                y=(1.2e9, 0.9e9, 0.7e9),
            )
            for stage in HYPERELASTIC_CURVE_STAGES
        ),
        material_model_ir=NeutralLinearViscoelasticIR(
            model=_reference(20),
            schema_id="urn:cmp:modeling:reference-isotropic-linear-viscoelastic-prony:1.1.0",
            schema_version="1.1.0",
            model_schema_digest="d" * 64,
            density_kg_per_m3=1180.0,
            youngs_modulus_pa=2.4e9,
            poisson_ratio=0.38,
            bulk_relaxation_status="not_characterized",
            terms=(
                NeutralPronyTerm(1, 0.2, 0.0, 0.5),
                NeutralPronyTerm(2, 0.3, 0.0, 12.0),
            ),
            reference_temperature_k=296.15,
        ),
        applicable_strain_min=None,
        applicable_strain_max=None,
        applicable_time_min_s=0.1,
        applicable_time_max_s=10.0,
    )

    decoded = neutral_material_from_json_bytes(polymer.to_json_bytes())

    assert decoded == polymer
    assert decoded.material_model_ir.family.value == "generalized_maxwell"
    Draft202012Validator(NEUTRAL_SCHEMA).validate(polymer.canonical())


def test_hyperelastic_neutral_material_can_pin_an_exact_prony_overlay() -> None:
    source = _document()
    hyperelastic_ir = cast(NeutralHyperelasticIR, source.material_model_ir)
    overlaid = replace(
        source,
        material_model_ir=replace(
            hyperelastic_ir,
            prony_overlay=NeutralPronyOverlay(
                EvidenceStatus.EXACT_REVISION,
                "Reviewed shear relaxation overlay.",
                (NeutralPronyTerm(1, 0.25, 0.0, 2.0),),
                _reference(0),
            ),
        ),
    )

    assert neutral_material_from_json_bytes(overlaid.to_json_bytes()) == overlaid
    Draft202012Validator(NEUTRAL_SCHEMA).validate(overlaid.canonical())


def test_metal_processing_output_is_split_into_observed_and_extrapolated_evidence() -> None:
    stages = [
        {
            "series": [
                {"quantity": "strain.engineering", "values": [0.0, 0.1, 0.2]},
                {"quantity": "stress.engineering", "values": [0.0, 400e6, 500e6]},
            ]
        },
        {
            "series": [
                {"quantity": "strain.true_plastic", "values": [0.0, 0.08, 0.16]},
                {"quantity": "stress.true", "values": [350e6, 480e6, 600e6]},
            ]
        },
        {
            "series": [
                {"quantity": "strain.true_plastic", "values": [0.0, 0.1, 0.2, 0.3]},
                {
                    "quantity": "stress.hardening.selected",
                    "values": [350e6, 520e6, 650e6, 720e6],
                },
            ]
        },
    ]
    value = json.dumps({"result": {"stages": stages}}).encode()

    curves = _metal_curves(
        value,
        dataset_revision_id=IDS[4],
        characterized_maximum=0.2,
    )

    assert tuple(item.stage for item in curves) == (
        CurveStage.NORMALIZED,
        CurveStage.PROCESSED,
        CurveStage.FITTED,
        CurveStage.EXTRAPOLATED,
    )
    assert curves[2].x == (0.0, 0.1, 0.2)
    assert curves[3].x == (0.3,)


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
    assert card.canonical()["family"] == family.value
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
    capabilities = cast(list[object], manifest["capabilities"])

    assert len(capabilities) == 8
    assert len(str(manifest["manifest_sha256"])) == 64

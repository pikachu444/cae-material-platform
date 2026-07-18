"""Promote an exact metal Processing Output to tabulated-plasticity IR 1.2.

Revision ID: 20260902_067_t55m_projection
Revises: 20260901_066_t54_batch

Traceability: T-55M.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260902_067_t55m_projection"
down_revision: str | None = "20260901_066_t54_batch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_TABULATED = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_VOCE = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
_PROCESSED = "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0"
_PRONY = "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
_OGDEN = "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0"

_LINEAR_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
_TABULATED_DIGEST = "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f"
_VOCE_DIGEST = "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd"
_PROCESSED_DIGEST = "60f4a0806126ccf7c918f664a97b4d49da593f1da9dacab4a843987b34a0c62f"
_PRONY_DIGEST = "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353"
_OGDEN_DIGEST = "545ef081fd6b702d99710aa2ba1a253d0ef6961b8084647d157fac03cca29f2f"

_PROCESSED_PROFILE = "urn:cmp:modeling:processing-selected-hardening-projection:1.0.0"
_PROCESSED_PROFILE_DIGEST = "7db4025177c75ecc1a820da2730ecc402844e6677180ecebf415fed07f615b50"
_CONSTANT_EXTENSION_POLICY = "approved_constant_true_stress"
_PROCESSED_EXTENSION_POLICY = "selected_fitted_bounded_extrapolation"
_TENSILE_PROFILE = "urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0"
_TENSILE_PROFILE_DIGEST = "309b38a58988f0c26a1dfeca702e91283abe025370471def0bf50f257c5e15bf"
_VOCE_PROFILE = "urn:cmp:modeling:reference-voce-fixed-grid-projection:1.0.0"
_VOCE_PROFILE_DIGEST = "64a54f24a263c863682643c5b36621275bcc355254655bdf0aae819b661a0d5d"
_SUPPORTED_FAMILIES = "'voce','swift','hockett_sherby','ghosh'"

_LINEAR_CONTRACT = (
    "exporter_id='cmp.reference.openradioss-elast' AND exporter_version='1.0.0' "
    "AND exporter_digest='65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20' "
    f"AND target_solver='openradioss' AND model_schema_digest='{_LINEAR_DIGEST}' "
    "AND material_name IS NULL AND hardening_curve_artifact_id IS NULL "
    "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
    "AND extension_max_true_plastic_strain IS NULL "
    "AND post_necking_extension_policy IS NULL "
    "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL"
)
_PLASTIC_REQUIRED = (
    "material_name IS NOT NULL AND source_yield_stress_pa IS NOT NULL "
    "AND hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL "
    "AND hardening_curve_point_count IS NOT NULL "
    "AND extension_max_true_plastic_strain IS NOT NULL "
    "AND post_necking_extension_policy IS NOT NULL "
    "AND hardening_curve_mapping_status IS NOT NULL AND extension_mapping_status IS NOT NULL "
    "AND density_mapping_status='exact' AND youngs_modulus_mapping_status='exact' "
    "AND poisson_ratio_mapping_status='exact' AND source_yield_mapping_status='transformed' "
    "AND hardening_curve_mapping_status='transformed' "
    "AND extension_mapping_status='approximated' "
    "AND temperature_applicability_mapping_status='not_applicable' "
    "AND strain_rate_applicability_mapping_status='not_applicable'"
)
_PRONY_CONTRACT = (
    "exporter_id='cmp.reference.abaqus-linear-prony' AND exporter_version='1.0.0' "
    "AND exporter_digest='3645e19c99d6030f5438d43407e05e5422f1f7413a4fd9650a2d786e5b343a5e' "
    f"AND target_solver='abaqus' AND model_schema_digest='{_PRONY_DIGEST}' "
    "AND material_name IS NOT NULL AND source_yield_stress_pa IS NULL "
    "AND hardening_curve_artifact_id IS NULL AND hardening_curve_sha256 IS NULL "
    "AND hardening_curve_point_count IS NULL AND extension_max_true_plastic_strain IS NULL "
    "AND post_necking_extension_policy IS NULL AND hardening_curve_mapping_status IS NULL "
    "AND extension_mapping_status IS NULL AND density_mapping_status='exact' "
    "AND youngs_modulus_mapping_status='exact' AND poisson_ratio_mapping_status='exact' "
    "AND source_yield_mapping_status='not_applicable' "
    "AND temperature_applicability_mapping_status='not_applicable' "
    "AND strain_rate_applicability_mapping_status='not_applicable' "
    "AND unit_system_mapping_status='transformed'"
)


def _ogden_contract(exporter_id: str, digest: str, solver: str, poisson: str) -> str:
    return (
        f"exporter_id='{exporter_id}' AND exporter_version='1.0.0' "
        f"AND exporter_digest='{digest}' AND target_solver='{solver}' "
        f"AND model_schema_digest='{_OGDEN_DIGEST}' AND material_name IS NOT NULL "
        "AND source_yield_stress_pa IS NULL AND hardening_curve_artifact_id IS NULL "
        "AND hardening_curve_sha256 IS NULL AND hardening_curve_point_count IS NULL "
        "AND extension_max_true_plastic_strain IS NULL "
        "AND post_necking_extension_policy IS NULL "
        "AND hardening_curve_mapping_status IS NULL AND extension_mapping_status IS NULL "
        "AND density_mapping_status='exact' AND youngs_modulus_mapping_status='exact' "
        f"AND poisson_ratio_mapping_status='{poisson}' "
        "AND source_yield_mapping_status='not_applicable' "
        "AND temperature_applicability_mapping_status='not_applicable' "
        "AND strain_rate_applicability_mapping_status='not_applicable' "
        "AND unit_system_mapping_status='transformed'"
    )


def _replace_export_constraints(*, include_processed: bool) -> None:
    plastic_digests = f"'{_TABULATED_DIGEST}','{_VOCE_DIGEST}'"
    all_digests = f"'{_LINEAR_DIGEST}',{plastic_digests},'{_PRONY_DIGEST}','{_OGDEN_DIGEST}'"
    if include_processed:
        plastic_digests += f",'{_PROCESSED_DIGEST}'"
        all_digests += f",'{_PROCESSED_DIGEST}'"
    law36 = (
        "exporter_id='cmp.reference.openradioss-law36' AND exporter_version='1.0.0' "
        "AND exporter_digest='713da51619eedfeda972205426fe86ae25e0d9f75d85554183f35bca76f73be2' "
        f"AND target_solver='openradioss' AND model_schema_digest IN ({plastic_digests}) "
        f"AND unit_system_mapping_status='exact' AND {_PLASTIC_REQUIRED}"
    )
    abaqus = (
        "exporter_id='cmp.reference.abaqus-isotropic-plasticity' "
        "AND exporter_version='1.0.0' "
        "AND exporter_digest='0585a5dbf0898fcea74009120045b29bf52fef6c428e1285c6603aaee5dd05ad' "
        f"AND target_solver='abaqus' AND model_schema_digest IN ({plastic_digests}) "
        f"AND unit_system_mapping_status='transformed' AND {_PLASTIC_REQUIRED}"
    )
    ogden_abaqus = _ogden_contract(
        "cmp.reference.abaqus-ogden-prony",
        "1e092e39a8c08c912ba7bcd9838cc9fa8a2a960cb912b44478c94835a557444b",
        "abaqus",
        "exact",
    )
    ogden_radioss = _ogden_contract(
        "cmp.reference.openradioss-law62",
        "1ade1f1f59f00d94c0888802d5f07ddac3c0e11b376f2e4652c33e581f9e5174",
        "openradioss",
        "approximated",
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_model_digest, "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_exporter_contract"
    )
    op.execute(
        "ALTER TABLE exporting.solver_card_revision ADD CONSTRAINT "
        f"ck_exporting_solver_card_model_digest CHECK (model_schema_digest IN ({all_digests})), "
        "ADD CONSTRAINT ck_exporting_solver_card_exporter_contract CHECK ("
        f"({_LINEAR_CONTRACT}) OR ({law36}) OR ({abaqus}) OR ({_PRONY_CONTRACT}) "
        f"OR ({ogden_abaqus}) OR ({ogden_radioss}))"
    )
    extension_policies = f"'{_CONSTANT_EXTENSION_POLICY}'"
    if include_processed:
        extension_policies += f",'{_PROCESSED_EXTENSION_POLICY}'"
    op.execute(
        "ALTER TABLE exporting.solver_card_revision "
        "DROP CONSTRAINT IF EXISTS ck_exporting_solver_card_extension, "
        "ADD CONSTRAINT ck_exporting_solver_card_extension CHECK ("
        "post_necking_extension_policy IS NULL OR "
        f"post_necking_extension_policy IN ({extension_policies}))"
    )


def _replace_evidence_constraints(*, include_processing: bool) -> None:
    kinds = (
        "'manual_catalog_projection','reference_candidate_selection',"
        "'reference_prony_candidate_selection','reference_ogden_candidate_selection'"
    )
    processing_shape = ""
    if include_processing:
        kinds += ",'processing_recipe_selection'"
        processing_shape = """
            OR (calibration_evidence_kind='processing_recipe_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
        """
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_shape, "
        "DROP CONSTRAINT IF EXISTS ck_modeling_material_model_calibration_evidence_kind"
    )
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_kind CHECK
            (calibration_evidence_kind IN ({kinds})),
          ADD CONSTRAINT ck_modeling_material_model_calibration_evidence_shape CHECK (
            (calibration_evidence_kind='manual_catalog_projection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
            OR (calibration_evidence_kind='reference_candidate_selection'
             AND calibration_selection_id IS NOT NULL
             AND calibration_selection_revision_id IS NOT NULL
             AND calibration_run_id IS NOT NULL AND calibration_candidate_id IS NOT NULL
             AND calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND calibration_diagnostics_artifact_id IS NOT NULL
             AND calibration_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$'
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
            OR (calibration_evidence_kind='reference_prony_candidate_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NOT NULL AND prony_selection_revision_id IS NOT NULL
             AND prony_calibration_run_id IS NOT NULL
             AND prony_calibration_candidate_id IS NOT NULL
             AND prony_calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
             AND prony_diagnostics_artifact_id IS NOT NULL
             AND prony_diagnostics_sha256 ~ '^[0-9a-f]{{64}}$')
            OR (calibration_evidence_kind='reference_ogden_candidate_selection'
             AND calibration_selection_id IS NULL
             AND calibration_selection_revision_id IS NULL
             AND calibration_run_id IS NULL AND calibration_candidate_id IS NULL
             AND calibration_candidate_sha256 IS NULL
             AND calibration_diagnostics_artifact_id IS NULL
             AND calibration_diagnostics_sha256 IS NULL
             AND prony_selection_id IS NULL AND prony_selection_revision_id IS NULL
             AND prony_calibration_run_id IS NULL
             AND prony_calibration_candidate_id IS NULL
             AND prony_calibration_candidate_sha256 IS NULL
             AND prony_diagnostics_artifact_id IS NULL
             AND prony_diagnostics_sha256 IS NULL)
            {processing_shape})
        """
    )


def _replace_model_constraints(*, include_processed: bool) -> None:
    for constraint in (
        "ck_modeling_material_model_family",
        "ck_modeling_material_model_family_digest",
        "ck_modeling_material_model_plastic_payload",
        "ck_modeling_material_model_plastic_profile",
        "ck_modeling_material_model_plastic_ranges",
    ):
        op.execute(
            f"ALTER TABLE modeling.material_model_revision DROP CONSTRAINT IF EXISTS {constraint}"
        )
    families = f"'{_LINEAR}','{_TABULATED}','{_VOCE}','{_PRONY}','{_OGDEN}'"
    digests = (
        f"(model_family_id='{_LINEAR}' AND model_schema_digest='{_LINEAR_DIGEST}') OR "
        f"(model_family_id='{_TABULATED}' AND model_schema_digest='{_TABULATED_DIGEST}') OR "
        f"(model_family_id='{_VOCE}' AND model_schema_digest='{_VOCE_DIGEST}') OR "
        f"(model_family_id='{_PRONY}' AND model_schema_digest='{_PRONY_DIGEST}') OR "
        f"(model_family_id='{_OGDEN}' AND model_schema_digest='{_OGDEN_DIGEST}')"
    )
    processed_payload = ""
    processed_profile = ""
    processed_range = ""
    if include_processed:
        families += f",'{_PROCESSED}'"
        digests += (
            f" OR (model_family_id='{_PROCESSED}' AND model_schema_digest='{_PROCESSED_DIGEST}')"
        )
        processed_payload = f"""
            OR (model_family_id='{_PROCESSED}'
              AND source_dataset_id IS NULL AND source_dataset_revision_id IS NULL
              AND voce_calibration_candidate_id IS NULL
              AND processing_output_id IS NOT NULL
              AND processing_output_revision_id IS NOT NULL
              AND processing_output_sha256 ~ '^[0-9a-f]{{64}}$'
              AND processing_source_document_id IS NOT NULL
              AND processing_source_document_revision_id IS NOT NULL
              AND processing_mapping_profile_id IS NOT NULL
              AND processing_mapping_profile_revision_id IS NOT NULL
              AND jsonb_typeof(hardening_candidate_families)='array'
              AND jsonb_array_length(hardening_candidate_families) BETWEEN 2 AND 4
              AND hardening_primary_family IN ({_SUPPORTED_FAMILIES})
              AND hardening_secondary_family IN ({_SUPPORTED_FAMILIES})
              AND hardening_candidate_families ? hardening_primary_family
              AND hardening_candidate_families ? hardening_secondary_family
              AND hardening_primary_weight BETWEEN 0 AND 1
              AND hardening_fit_minimum_strain >= 0
              AND hardening_curve_artifact_id IS NOT NULL
              AND hardening_curve_sha256 ~ '^[0-9a-f]{{64}}$'
              AND hardening_curve_point_count BETWEEN 21 AND 501
              AND source_yield_stress_pa > 0
              AND post_necking_approximation_acknowledged IS TRUE)
        """
        processed_profile = f"""
            OR (model_family_id='{_PROCESSED}'
              AND transformation_profile_id='{_PROCESSED_PROFILE}'
              AND transformation_profile_version='1.0.0'
              AND transformation_profile_digest='{_PROCESSED_PROFILE_DIGEST}')
        """
        processed_range = f"""
            OR (model_family_id='{_PROCESSED}' AND necking_engineering_strain IS NULL
              AND hardening_fit_minimum_strain >= 0
              AND characterized_max_true_plastic_strain > hardening_fit_minimum_strain
              AND extension_max_true_plastic_strain
                  > characterized_max_true_plastic_strain
              AND extension_max_true_plastic_strain <= 5)
        """
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          ADD CONSTRAINT ck_modeling_material_model_family
            CHECK (model_family_id IN ({families})),
          ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ({digests}),
          ADD CONSTRAINT ck_modeling_material_model_plastic_payload CHECK (
            (model_family_id IN ('{_LINEAR}','{_PRONY}','{_OGDEN}')
              AND hardening_curve_artifact_id IS NULL
              AND source_dataset_id IS NULL AND voce_calibration_candidate_id IS NULL
              AND processing_output_id IS NULL)
            OR (model_family_id='{_TABULATED}' AND source_dataset_id IS NOT NULL
              AND source_dataset_revision_id IS NOT NULL
              AND hardening_curve_artifact_id IS NOT NULL
              AND source_point_count IS NOT NULL AND voce_calibration_candidate_id IS NULL
              AND processing_output_id IS NULL)
            OR (model_family_id='{_VOCE}' AND source_dataset_id IS NULL
              AND source_dataset_revision_id IS NULL AND source_point_count IS NULL
              AND pre_yield_excluded_point_count IS NULL
              AND post_necking_excluded_point_count IS NULL
              AND necking_source_point_index IS NULL AND necking_engineering_strain IS NULL
              AND hardening_curve_artifact_id IS NOT NULL
              AND hardening_curve_sha256 IS NOT NULL
              AND hardening_curve_point_count IS NOT NULL
              AND calibration_input_scope_id IS NOT NULL
              AND calibration_input_scope_revision_id IS NOT NULL
              AND voce_calibration_plan_id IS NOT NULL
              AND voce_calibration_plan_revision_id IS NOT NULL
              AND voce_calibration_run_id IS NOT NULL
              AND voce_calibration_candidate_id IS NOT NULL
              AND voce_calibration_candidate_sha256 ~ '^[0-9a-f]{{64}}$'
              AND voce_candidate_selection_id IS NOT NULL
              AND voce_candidate_selection_revision_id IS NOT NULL
              AND voce_sampling_point_count BETWEEN 21 AND 501
              AND hardening_curve_point_count=voce_sampling_point_count+1
              AND voce_q_pa > 0 AND voce_b > 0 AND source_yield_stress_pa > 0
              AND characterized_max_true_plastic_strain > 0
              AND extension_max_true_plastic_strain
                  > characterized_max_true_plastic_strain
              AND post_necking_approximation_acknowledged IS TRUE
              AND processing_output_id IS NULL)
            {processed_payload}),
          ADD CONSTRAINT ck_modeling_material_model_plastic_profile CHECK (
            transformation_profile_id IS NULL OR
            (model_family_id='{_TABULATED}'
              AND transformation_profile_id='{_TENSILE_PROFILE}'
              AND transformation_profile_version='1.0.0'
              AND transformation_profile_digest='{_TENSILE_PROFILE_DIGEST}') OR
            (model_family_id='{_VOCE}'
              AND transformation_profile_id='{_VOCE_PROFILE}'
              AND transformation_profile_version='1.0.0'
              AND transformation_profile_digest='{_VOCE_PROFILE_DIGEST}')
            {processed_profile}),
          ADD CONSTRAINT ck_modeling_material_model_plastic_ranges CHECK (
            model_family_id IN ('{_LINEAR}','{_PRONY}','{_OGDEN}') OR
            (model_family_id='{_TABULATED}' AND necking_engineering_strain >= 0
              AND characterized_max_true_plastic_strain >= 0
              AND extension_max_true_plastic_strain
                  > characterized_max_true_plastic_strain) OR
            (model_family_id='{_VOCE}' AND necking_engineering_strain IS NULL
              AND characterized_max_true_plastic_strain > 0
              AND extension_max_true_plastic_strain
                  > characterized_max_true_plastic_strain)
            {processed_range})
        """
    )


def _replace_artifact_guard(*, include_processed: bool) -> None:
    families = f"'{_TABULATED}','{_VOCE}'"
    if include_processed:
        families += f",'{_PROCESSED}'"
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION modeling.validate_reference_hardening_artifact()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE artifact_kind text; DECLARE artifact_role text;
        DECLARE artifact_schema text; DECLARE artifact_digest text;
        BEGIN
          IF NEW.model_family_id NOT IN ({families}) THEN RETURN NEW; END IF;
          SELECT a.artifact_kind,a.artifact_role,a.schema_ref,a.sha256
            INTO artifact_kind,artifact_role,artifact_schema,artifact_digest
          FROM artifact.artifact a WHERE a.organization_id=NEW.organization_id
            AND a.project_id=NEW.project_id AND a.classification=NEW.classification
            AND a.id=NEW.hardening_curve_artifact_id;
          IF artifact_kind IS DISTINCT FROM 'derived'
             OR artifact_role IS DISTINCT FROM 'modeling.hardening_curve'
             OR artifact_schema IS DISTINCT FROM
               'urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0'
             OR artifact_digest IS DISTINCT FROM NEW.hardening_curve_sha256 THEN
            RAISE EXCEPTION 'hardening curve Artifact contract is invalid'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$
        """
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modeling.material_model_revision
          ADD COLUMN processing_output_id uuid NULL,
          ADD COLUMN processing_output_revision_id uuid NULL,
          ADD COLUMN processing_output_sha256 char(64) COLLATE "C" NULL,
          ADD COLUMN processing_source_document_id uuid NULL,
          ADD COLUMN processing_source_document_revision_id uuid NULL,
          ADD COLUMN processing_mapping_profile_id uuid NULL,
          ADD COLUMN processing_mapping_profile_revision_id uuid NULL,
          ADD COLUMN hardening_candidate_families jsonb NULL,
          ADD COLUMN hardening_primary_family varchar(32) NULL,
          ADD COLUMN hardening_secondary_family varchar(32) NULL,
          ADD COLUMN hardening_primary_weight float8 NULL,
          ADD COLUMN hardening_fit_minimum_strain float8 NULL,
          ADD CONSTRAINT fk_mdl_model_processing_output_exact FOREIGN KEY
            (organization_id, project_id, classification, processing_output_id,
             processing_output_revision_id) REFERENCES
            processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_processing_source_exact FOREIGN KEY
            (organization_id, project_id, classification,
             processing_source_document_id, processing_source_document_revision_id)
            REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_mdl_model_processing_profile_exact FOREIGN KEY
            (organization_id, project_id, classification,
             processing_mapping_profile_id, processing_mapping_profile_revision_id)
            REFERENCES processing.mapping_profile_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    _replace_model_constraints(include_processed=True)
    _replace_evidence_constraints(include_processing=True)
    _replace_artifact_guard(include_processed=True)
    _replace_export_constraints(include_processed=True)
    op.execute(
        """
        CREATE FUNCTION modeling.guard_processed_plasticity_projection_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE output_row record; DECLARE final_step record;
        BEGIN
          IF NEW.model_family_id <> 'urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0'
          THEN RETURN NEW; END IF;
          SELECT * INTO output_row
          FROM processing.common_processing_output_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification
            AND aggregate_id=NEW.processing_output_id
            AND id=NEW.processing_output_revision_id;
          SELECT * INTO final_step FROM processing.common_processing_output_step
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND classification=NEW.classification
            AND output_id=NEW.processing_output_id
            AND output_revision_id=NEW.processing_output_revision_id
            AND ordinal=output_row.step_count-1;
          IF output_row.output_sha256 IS DISTINCT FROM NEW.processing_output_sha256
             OR output_row.source_document_id IS DISTINCT FROM
                NEW.processing_source_document_id
             OR output_row.source_document_revision_id IS DISTINCT FROM
                NEW.processing_source_document_revision_id
             OR output_row.mapping_profile_id IS DISTINCT FROM
                NEW.processing_mapping_profile_id
             OR output_row.mapping_profile_revision_id IS DISTINCT FROM
                NEW.processing_mapping_profile_revision_id
             OR final_step.method_id IS DISTINCT FROM
                'metal.hardening_fit_extrapolate'
             OR final_step.method_version IS DISTINCT FROM '1.0.0' THEN
            RAISE EXCEPTION
              'processed plasticity IR differs from its exact Processing Output lineage'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_processed_plasticity_projection_guard
          BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.guard_processed_plasticity_projection_insert();
        CREATE INDEX ix_mdl_model_processing_output ON
          modeling.material_model_revision
          (organization_id, project_id, processing_output_revision_id)
          WHERE processing_output_revision_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS modeling_processed_plasticity_projection_guard "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_processed_plasticity_projection_insert()")
    op.execute("DROP INDEX IF EXISTS modeling.ix_mdl_model_processing_output")
    _replace_export_constraints(include_processed=False)
    _replace_artifact_guard(include_processed=False)
    _replace_evidence_constraints(include_processing=False)
    _replace_model_constraints(include_processed=False)
    op.execute(
        """
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT IF EXISTS fk_mdl_model_processing_profile_exact,
          DROP CONSTRAINT IF EXISTS fk_mdl_model_processing_source_exact,
          DROP CONSTRAINT IF EXISTS fk_mdl_model_processing_output_exact,
          DROP COLUMN IF EXISTS hardening_fit_minimum_strain,
          DROP COLUMN IF EXISTS hardening_primary_weight,
          DROP COLUMN IF EXISTS hardening_secondary_family,
          DROP COLUMN IF EXISTS hardening_primary_family,
          DROP COLUMN IF EXISTS hardening_candidate_families,
          DROP COLUMN IF EXISTS processing_mapping_profile_revision_id,
          DROP COLUMN IF EXISTS processing_mapping_profile_id,
          DROP COLUMN IF EXISTS processing_source_document_revision_id,
          DROP COLUMN IF EXISTS processing_source_document_id,
          DROP COLUMN IF EXISTS processing_output_sha256,
          DROP COLUMN IF EXISTS processing_output_revision_id,
          DROP COLUMN IF EXISTS processing_output_id
        """
    )

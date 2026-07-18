"""Promote reviewed one-to-ten-term polymer Processing Outputs.

Revision ID: 20260914_079_t67_polymer
Revises: 20260913_078_t65_binding_rls

Traceability: ADR-0031, T-67.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260914_079_t67_polymer"
down_revision: str | None = "20260913_078_t65_binding_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEAR = "urn:cmp:reference:isotropic-linear-elasticity:1.0.0"
_TABULATED = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_VOCE = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"
_PROCESSED = "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0"
_PRONY = "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0"
_OGDEN = "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0"

_DIGESTS = {
    _LINEAR: "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6",
    _TABULATED: "18fd736897f26e6472443a5acf50bf899f8eb8f510ae0eca80dada81047a706f",
    _VOCE: "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd",
    _PROCESSED: "60f4a0806126ccf7c918f664a97b4d49da593f1da9dacab4a843987b34a0c62f",
    _PRONY: "84f948444441bf8ead0c3e3a067d78a68335f2160c6d8d5c59348250ff492353",
    _OGDEN: "545ef081fd6b702d99710aa2ba1a253d0ef6961b8084647d157fac03cca29f2f",
}
_PROCESSING_PRONY_DIGEST = "16c70b294290c62d97e7eb42c5af56a4663af19c2b2e139d2fee898f1802889e"


def _secure(table: str) -> None:
    for operation in ("select", "insert"):
        permission = "modeling.read" if operation == "select" else "modeling.write"
        predicate = "USING" if operation == "select" else "WITH CHECK"
        op.execute(
            f"CREATE POLICY modeling_{table}_{operation} ON modeling.{table} "
            f"FOR {operation.upper()} {predicate} "
            "(access_control.can_access_row(organization_id, project_id, "
            f"classification, '{permission}'))"
        )


def _family_digest_constraint(*, include_processing: bool) -> str:
    clauses = [
        f"(model_family_id='{family}' AND model_schema_digest='{digest}')"
        for family, digest in _DIGESTS.items()
    ]
    if include_processing:
        clauses.append(
            f"(model_family_id='{_PRONY}' AND "
            f"model_schema_digest='{_PROCESSING_PRONY_DIGEST}')"
        )
    return " OR ".join(clauses)


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE modeling.material_model_revision
          DROP CONSTRAINT ck_modeling_material_model_family_digest,
          ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK
            ({_family_digest_constraint(include_processing=True)});

        ALTER TABLE modeling.linear_viscoelastic_revision
          ADD COLUMN promotion_kind varchar(32) NOT NULL DEFAULT 'manual';
        UPDATE modeling.linear_viscoelastic_revision s
          SET promotion_kind='candidate_selection'
          FROM modeling.material_model_revision r
          WHERE r.organization_id=s.organization_id AND r.project_id=s.project_id
            AND r.aggregate_id=s.material_model_id
            AND r.id=s.material_model_revision_id
            AND r.calibration_evidence_kind='reference_prony_candidate_selection';
        ALTER TABLE modeling.linear_viscoelastic_revision
          ALTER COLUMN promotion_kind DROP DEFAULT,
          ADD CONSTRAINT ck_modeling_linear_viscoelastic_promotion_kind CHECK
            (promotion_kind IN ('manual','candidate_selection','processing_output')),
          DROP CONSTRAINT ck_modeling_linear_viscoelastic_term_count,
          ADD CONSTRAINT ck_modeling_linear_viscoelastic_term_count CHECK
            (term_count BETWEEN 1 AND 10);
        ALTER TABLE modeling.linear_viscoelastic_prony_term
          DROP CONSTRAINT ck_modeling_linear_viscoelastic_ordinal,
          ADD CONSTRAINT ck_modeling_linear_viscoelastic_ordinal CHECK
            (ordinal BETWEEN 1 AND 10);

        ALTER TABLE modeling.neutral_material_revision
          DROP CONSTRAINT ck_modeling_neutral_material_selection_kind,
          ADD COLUMN prony_selection_mode varchar(32),
          ADD COLUMN prony_selected_term_count integer,
          ADD COLUMN prony_normalized_rmse float8,
          ADD COLUMN prony_bic float8,
          ADD COLUMN prony_fitted_g0_pa float8,
          ADD COLUMN prony_catalog_g0_pa float8,
          ADD COLUMN prony_relative_mismatch float8,
          ADD COLUMN prony_acknowledged_max_mismatch float8,
          ADD CONSTRAINT ck_modeling_neutral_material_selection_kind CHECK
          ((selection_kind='candidate' AND calibration_run_id IS NOT NULL AND
            family_candidate_id IS NOT NULL AND candidate_sha256 IS NOT NULL AND
            diagnostics_artifact_id IS NOT NULL AND diagnostics_sha256 IS NOT NULL AND
            processing_output_id IS NULL AND processing_output_revision_id IS NULL AND
            processing_output_sha256 IS NULL AND prony_selection_mode IS NULL) OR
           (selection_kind='processing_output' AND calibration_run_id IS NULL AND
            family_candidate_id IS NULL AND candidate_sha256 IS NULL AND
            diagnostics_artifact_id IS NULL AND diagnostics_sha256 IS NULL AND
            processing_output_id IS NOT NULL AND processing_output_revision_id IS NOT NULL AND
            processing_output_sha256 IS NOT NULL AND prony_selection_mode IS NULL) OR
           (selection_kind='prony_processing_output' AND model_family='generalized_maxwell' AND
            calibration_run_id IS NULL AND family_candidate_id IS NULL AND
            candidate_sha256 IS NULL AND diagnostics_artifact_id IS NULL AND
            diagnostics_sha256 IS NULL AND processing_output_id IS NOT NULL AND
            processing_output_revision_id IS NOT NULL AND processing_output_sha256 IS NOT NULL AND
            selected_series='modulus.prony.selected' AND candidate_families IS NULL AND
            primary_family IS NULL AND secondary_family IS NULL AND primary_weight IS NULL AND
            prony_selection_mode IN ('automatic_bic','manual') AND
            prony_selected_term_count BETWEEN 1 AND 10 AND
            prony_normalized_rmse >= 0 AND prony_normalized_rmse < 'Infinity'::float8 AND
            prony_bic > '-Infinity'::float8 AND prony_bic < 'Infinity'::float8 AND
            prony_fitted_g0_pa > 0 AND prony_catalog_g0_pa > 0 AND
            prony_relative_mismatch >= 0 AND
            prony_relative_mismatch <= prony_acknowledged_max_mismatch AND
            prony_acknowledged_max_mismatch BETWEEN 0 AND 1));

        CREATE TABLE modeling.linear_viscoelastic_processing_evidence (
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          material_model_id uuid NOT NULL,
          material_model_revision_id uuid NOT NULL,
          processing_output_id uuid NOT NULL,
          processing_output_revision_id uuid NOT NULL,
          processing_output_sha256 char(64) COLLATE "C" NOT NULL,
          source_test_data_id uuid NOT NULL,
          source_test_data_revision_id uuid NOT NULL,
          mapping_profile_id uuid NOT NULL,
          mapping_profile_revision_id uuid NOT NULL,
          selection_mode varchar(32) NOT NULL,
          selected_term_count integer NOT NULL,
          normalized_rmse float8 NOT NULL,
          bic float8 NOT NULL,
          fitted_instantaneous_shear_modulus_pa float8 NOT NULL,
          catalog_instantaneous_shear_modulus_pa float8 NOT NULL,
          instantaneous_modulus_relative_mismatch float8 NOT NULL,
          acknowledged_maximum_relative_mismatch float8 NOT NULL,
          CONSTRAINT pk_modeling_linear_prony_processing_evidence PRIMARY KEY
            (organization_id, project_id, material_model_revision_id),
          CONSTRAINT uq_modeling_linear_prony_processing_output UNIQUE
            (organization_id, project_id, processing_output_revision_id),
          CONSTRAINT fk_modeling_linear_prony_processing_owner FOREIGN KEY
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id) REFERENCES modeling.linear_viscoelastic_revision
            (organization_id, project_id, classification, material_model_id,
             material_model_revision_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_linear_prony_processing_output FOREIGN KEY
            (organization_id, project_id, classification, processing_output_id,
             processing_output_revision_id) REFERENCES
            processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_linear_prony_processing_source FOREIGN KEY
            (organization_id, project_id, classification, source_test_data_id,
             source_test_data_revision_id) REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_modeling_linear_prony_processing_profile FOREIGN KEY
            (organization_id, project_id, classification, mapping_profile_id,
             mapping_profile_revision_id) REFERENCES processing.mapping_profile_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT ck_modeling_linear_prony_processing_digest CHECK
            (processing_output_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_modeling_linear_prony_processing_selection CHECK
            (selection_mode IN ('automatic_bic','manual') AND
             selected_term_count BETWEEN 1 AND 10),
          CONSTRAINT ck_modeling_linear_prony_processing_metrics CHECK
            (normalized_rmse >= 0 AND normalized_rmse < 'Infinity'::float8 AND
             bic > '-Infinity'::float8 AND bic < 'Infinity'::float8 AND
             fitted_instantaneous_shear_modulus_pa > 0 AND
             fitted_instantaneous_shear_modulus_pa < 'Infinity'::float8 AND
             catalog_instantaneous_shear_modulus_pa > 0 AND
             catalog_instantaneous_shear_modulus_pa < 'Infinity'::float8 AND
             instantaneous_modulus_relative_mismatch >= 0 AND
             instantaneous_modulus_relative_mismatch <=
               acknowledged_maximum_relative_mismatch AND
             acknowledged_maximum_relative_mismatch BETWEEN 0 AND 1)
        );
        CREATE INDEX ix_mdl_linear_prony_processing_source ON
          modeling.linear_viscoelastic_processing_evidence
          (organization_id, project_id, source_test_data_revision_id);
        ALTER TABLE modeling.linear_viscoelastic_processing_evidence ENABLE ROW LEVEL SECURITY;
        ALTER TABLE modeling.linear_viscoelastic_processing_evidence FORCE ROW LEVEL SECURITY;
        """
    )
    _secure("linear_viscoelastic_processing_evidence")
    op.execute(
        """
        CREATE TRIGGER modeling_linear_viscoelastic_processing_evidence_immutable
          BEFORE UPDATE OR DELETE ON modeling.linear_viscoelastic_processing_evidence
          FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();

        CREATE FUNCTION modeling.validate_linear_prony_processing_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE summary record; DECLARE evidence record;
        DECLARE output_row record; DECLARE final_step record;
        DECLARE evidence_count integer;
        BEGIN
          SELECT * INTO summary FROM modeling.linear_viscoelastic_revision
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND material_model_revision_id=NEW.material_model_revision_id;
          SELECT count(*) INTO evidence_count
          FROM modeling.linear_viscoelastic_processing_evidence
          WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
            AND material_model_revision_id=NEW.material_model_revision_id;
          IF summary.promotion_kind='processing_output' THEN
            SELECT * INTO evidence
            FROM modeling.linear_viscoelastic_processing_evidence
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND material_model_revision_id=NEW.material_model_revision_id;
            SELECT * INTO output_row FROM processing.common_processing_output_revision
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND classification=NEW.classification
              AND aggregate_id=evidence.processing_output_id
              AND id=evidence.processing_output_revision_id;
            SELECT * INTO final_step FROM processing.common_processing_output_step
            WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
              AND classification=NEW.classification
              AND output_id=evidence.processing_output_id
              AND output_revision_id=evidence.processing_output_revision_id
              AND ordinal=output_row.step_count-1;
            IF evidence_count <> 1 OR output_row.output_sha256 IS DISTINCT FROM
                 evidence.processing_output_sha256
               OR output_row.source_document_id IS DISTINCT FROM evidence.source_test_data_id
               OR output_row.source_document_revision_id IS DISTINCT FROM
                 evidence.source_test_data_revision_id
               OR output_row.mapping_profile_id IS DISTINCT FROM evidence.mapping_profile_id
               OR output_row.mapping_profile_revision_id IS DISTINCT FROM
                 evidence.mapping_profile_revision_id
               OR final_step.method_id IS DISTINCT FROM 'polymer.prony_fit_compare'
               OR final_step.method_version IS DISTINCT FROM '1.0.0'
               OR summary.term_count IS DISTINCT FROM evidence.selected_term_count THEN
              RAISE EXCEPTION 'linear Prony IR differs from exact Processing Output evidence'
                USING ERRCODE='23514';
            END IF;
          ELSIF evidence_count <> 0 THEN
            RAISE EXCEPTION 'non-processing linear Prony revision has Processing evidence'
              USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE CONSTRAINT TRIGGER modeling_linear_prony_processing_summary_validate
          AFTER INSERT ON modeling.linear_viscoelastic_revision
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_linear_prony_processing_evidence();
        CREATE CONSTRAINT TRIGGER modeling_linear_prony_processing_evidence_validate
          AFTER INSERT ON modeling.linear_viscoelastic_processing_evidence
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_linear_prony_processing_evidence();

        CREATE OR REPLACE FUNCTION modeling.validate_neutral_material_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.model_family='hyperelastic' THEN
            IF NOT EXISTS (
              SELECT 1 FROM modeling.ogden_calibration_plan_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.calibration_plan_id
                 AND r.id=NEW.calibration_plan_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.scientific_profile_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.scientific_profile_id
                 AND r.id=NEW.scientific_profile_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.hyperelastic_family_candidate r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification AND r.id=NEW.family_candidate_id
                 AND r.calibration_run_id=NEW.calibration_run_id
                 AND r.candidate_sha256=NEW.candidate_sha256
            ) THEN RAISE EXCEPTION 'exact hyperelastic Neutral evidence is not visible';
            END IF;
          ELSIF NEW.model_family='generalized_maxwell' AND
                NEW.selection_kind='candidate' THEN
            IF NOT EXISTS (
              SELECT 1 FROM modeling.prony_calibration_plan_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.calibration_plan_id
                 AND r.id=NEW.calibration_plan_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.prony_calibration_candidate r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification AND r.id=NEW.family_candidate_id
                 AND r.calibration_run_id=NEW.calibration_run_id
                 AND r.candidate_sha256=NEW.candidate_sha256
            ) THEN RAISE EXCEPTION 'exact generalized-Maxwell Candidate is not visible';
            END IF;
          ELSIF NEW.model_family='generalized_maxwell' AND
                NEW.selection_kind='prony_processing_output' THEN
            IF NOT EXISTS (
              SELECT 1 FROM processing.common_processing_output_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.processing_output_id
                 AND r.id=NEW.processing_output_revision_id
                 AND r.output_sha256=NEW.processing_output_sha256
                 AND r.mapping_profile_id=NEW.mapping_profile_id
                 AND r.mapping_profile_revision_id=NEW.mapping_profile_revision_id
            ) THEN RAISE EXCEPTION 'exact generalized-Maxwell Processing evidence is not visible';
            END IF;
          ELSIF NEW.model_family='isotropic_tabulated_plasticity' AND
                (NEW.calibration_plan_id IS NOT NULL OR NEW.scientific_profile_id IS NOT NULL)
          THEN RAISE EXCEPTION 'metal Processing selection forbids calibration evidence';
          END IF;
          RETURN NEW;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM modeling.linear_viscoelastic_processing_evidence) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable polymer processing evidence exists';
          END IF;
          IF EXISTS (
            SELECT 1 FROM modeling.neutral_material_revision
             WHERE selection_kind='prony_processing_output'
          ) THEN
            RAISE EXCEPTION 'cannot downgrade while immutable polymer Neutral evidence exists';
          END IF;
        END $$;
        DROP TRIGGER modeling_linear_prony_processing_evidence_validate
          ON modeling.linear_viscoelastic_processing_evidence;
        DROP TRIGGER modeling_linear_prony_processing_summary_validate
          ON modeling.linear_viscoelastic_revision;
        DROP FUNCTION modeling.validate_linear_prony_processing_evidence();
        DROP TABLE modeling.linear_viscoelastic_processing_evidence;
        DROP INDEX IF EXISTS modeling.ix_mdl_linear_prony_processing_source;
        ALTER TABLE modeling.neutral_material_revision
          DROP CONSTRAINT ck_modeling_neutral_material_selection_kind,
          DROP COLUMN prony_acknowledged_max_mismatch,
          DROP COLUMN prony_relative_mismatch,
          DROP COLUMN prony_catalog_g0_pa,
          DROP COLUMN prony_fitted_g0_pa,
          DROP COLUMN prony_bic,
          DROP COLUMN prony_normalized_rmse,
          DROP COLUMN prony_selected_term_count,
          DROP COLUMN prony_selection_mode,
          ADD CONSTRAINT ck_modeling_neutral_material_selection_kind CHECK
          ((selection_kind='candidate' AND calibration_run_id IS NOT NULL AND
            family_candidate_id IS NOT NULL AND candidate_sha256 IS NOT NULL AND
            diagnostics_artifact_id IS NOT NULL AND diagnostics_sha256 IS NOT NULL AND
            processing_output_id IS NULL AND processing_output_revision_id IS NULL AND
            processing_output_sha256 IS NULL) OR
           (selection_kind='processing_output' AND calibration_run_id IS NULL AND
            family_candidate_id IS NULL AND candidate_sha256 IS NULL AND
            diagnostics_artifact_id IS NULL AND diagnostics_sha256 IS NULL AND
            processing_output_id IS NOT NULL AND processing_output_revision_id IS NOT NULL AND
            processing_output_sha256 IS NOT NULL));
        CREATE OR REPLACE FUNCTION modeling.validate_neutral_material_evidence()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.model_family='hyperelastic' THEN
            IF NOT EXISTS (
              SELECT 1 FROM modeling.ogden_calibration_plan_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.calibration_plan_id
                 AND r.id=NEW.calibration_plan_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.scientific_profile_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.scientific_profile_id
                 AND r.id=NEW.scientific_profile_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.hyperelastic_family_candidate r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification AND r.id=NEW.family_candidate_id
                 AND r.calibration_run_id=NEW.calibration_run_id
                 AND r.candidate_sha256=NEW.candidate_sha256
            ) THEN RAISE EXCEPTION 'exact hyperelastic Neutral evidence is not visible';
            END IF;
          ELSIF NEW.model_family='generalized_maxwell' THEN
            IF NOT EXISTS (
              SELECT 1 FROM modeling.prony_calibration_plan_revision r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification
                 AND r.aggregate_id=NEW.calibration_plan_id
                 AND r.id=NEW.calibration_plan_revision_id
            ) OR NOT EXISTS (
              SELECT 1 FROM modeling.prony_calibration_candidate r
               WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
                 AND r.classification=NEW.classification AND r.id=NEW.family_candidate_id
                 AND r.calibration_run_id=NEW.calibration_run_id
                 AND r.candidate_sha256=NEW.candidate_sha256
            ) THEN RAISE EXCEPTION 'exact generalized-Maxwell Neutral evidence is not visible';
            END IF;
          ELSIF NEW.model_family='isotropic_tabulated_plasticity' AND
                (NEW.calibration_plan_id IS NOT NULL OR NEW.scientific_profile_id IS NOT NULL)
          THEN RAISE EXCEPTION 'metal Processing selection forbids calibration evidence';
          END IF;
          RETURN NEW;
        END $$;
        ALTER TABLE modeling.linear_viscoelastic_prony_term
          DROP CONSTRAINT ck_modeling_linear_viscoelastic_ordinal,
          ADD CONSTRAINT ck_modeling_linear_viscoelastic_ordinal CHECK
            (ordinal BETWEEN 1 AND 5);
        ALTER TABLE modeling.linear_viscoelastic_revision
          DROP CONSTRAINT ck_modeling_linear_viscoelastic_term_count,
          DROP CONSTRAINT ck_modeling_linear_viscoelastic_promotion_kind,
          DROP COLUMN promotion_kind,
          ADD CONSTRAINT ck_modeling_linear_viscoelastic_term_count CHECK
            (term_count BETWEEN 1 AND 5);
        """
    )
    op.execute(
        "ALTER TABLE modeling.material_model_revision "
        "DROP CONSTRAINT ck_modeling_material_model_family_digest, "
        "ADD CONSTRAINT ck_modeling_material_model_family_digest CHECK ("
        + _family_digest_constraint(include_processing=False)
        + ")"
    )

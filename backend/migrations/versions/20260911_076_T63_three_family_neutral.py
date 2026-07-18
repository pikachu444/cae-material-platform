"""Generalize canonical Neutral Material persistence to three closed model families.

Revision ID: 20260911_076_t63_neutral
Revises: 20260910_075_t62_binding

Traceability: T-63.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_076_t63_neutral"
down_revision: str | None = "20260910_075_t62_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modeling.neutral_material_revision
          DROP CONSTRAINT uq_modeling_neutral_material_candidate,
          DROP CONSTRAINT ck_modeling_neutral_material_family_parameters,
          DROP CONSTRAINT ck_modeling_neutral_material_applicability,
          DROP CONSTRAINT fk_modeling_neutral_material_plan,
          DROP CONSTRAINT fk_modeling_neutral_material_profile,
          DROP CONSTRAINT fk_modeling_neutral_material_candidate;

        ALTER TABLE modeling.neutral_material_revision
          ALTER COLUMN calibration_plan_id DROP NOT NULL,
          ALTER COLUMN calibration_plan_revision_id DROP NOT NULL,
          ALTER COLUMN scientific_profile_id DROP NOT NULL,
          ALTER COLUMN scientific_profile_revision_id DROP NOT NULL,
          ALTER COLUMN calibration_run_id DROP NOT NULL,
          ALTER COLUMN family_candidate_id DROP NOT NULL,
          ALTER COLUMN candidate_sha256 DROP NOT NULL,
          ALTER COLUMN diagnostics_artifact_id DROP NOT NULL,
          ALTER COLUMN diagnostics_sha256 DROP NOT NULL,
          ALTER COLUMN applicable_strain_min DROP NOT NULL,
          ALTER COLUMN applicable_strain_max DROP NOT NULL;

        ALTER TABLE modeling.neutral_material_revision
          ADD COLUMN model_family varchar(64) NOT NULL DEFAULT 'hyperelastic',
          ADD COLUMN selection_kind varchar(64) NOT NULL DEFAULT 'candidate',
          ADD COLUMN processing_output_id uuid,
          ADD COLUMN processing_output_revision_id uuid,
          ADD COLUMN processing_output_sha256 char(64),
          ADD COLUMN selected_series varchar(160),
          ADD COLUMN candidate_families text[],
          ADD COLUMN primary_family varchar(64),
          ADD COLUMN secondary_family varchar(64),
          ADD COLUMN primary_weight double precision,
          ADD COLUMN youngs_modulus_pa double precision,
          ADD COLUMN poisson_ratio double precision,
          ADD COLUMN initial_yield_stress_pa double precision,
          ADD COLUMN hardening_curve_artifact_id uuid,
          ADD COLUMN hardening_curve_sha256 char(64),
          ADD COLUMN hardening_curve_schema_ref varchar(255),
          ADD COLUMN hardening_curve_point_count integer,
          ADD COLUMN characterized_strain_max double precision,
          ADD COLUMN extension_strain_max double precision,
          ADD COLUMN extrapolation_policy varchar(255),
          ADD COLUMN approximation_acknowledged boolean,
          ADD COLUMN bulk_relaxation_status varchar(64),
          ADD COLUMN reference_temperature_k double precision,
          ADD COLUMN applicable_time_min_s double precision,
          ADD COLUMN applicable_time_max_s double precision,
          ADD COLUMN prony_overlay_status varchar(32),
          ADD COLUMN prony_overlay_reason varchar(500),
          ADD COLUMN prony_overlay_model_id uuid,
          ADD COLUMN prony_overlay_model_revision_id uuid;

        ALTER TABLE modeling.neutral_material_revision
          ALTER COLUMN model_family DROP DEFAULT,
          ALTER COLUMN selection_kind DROP DEFAULT;

        ALTER TABLE modeling.neutral_material_revision ADD CONSTRAINT
          uq_modeling_neutral_material_candidate UNIQUE
          (organization_id, project_id, family_candidate_id),
          ADD CONSTRAINT uq_modeling_neutral_material_processing_output UNIQUE
          (organization_id, project_id, processing_output_revision_id),
          ADD CONSTRAINT ck_modeling_neutral_material_model_family CHECK
          (model_family IN ('hyperelastic','isotropic_tabulated_plasticity',
                            'generalized_maxwell')),
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
            processing_output_sha256 IS NOT NULL)),
          ADD CONSTRAINT ck_modeling_neutral_material_family_parameters CHECK
          ((model_family='hyperelastic' AND
             ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND
               c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND
               c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND
               c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND
               c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)) AND
             youngs_modulus_pa IS NULL AND hardening_curve_artifact_id IS NULL AND
             bulk_relaxation_status IS NULL) OR
           (model_family='isotropic_tabulated_plasticity' AND
             family='isotropic_tabulated_plasticity' AND youngs_modulus_pa>0 AND
             poisson_ratio>-1 AND poisson_ratio<0.5 AND initial_yield_stress_pa>0 AND
             hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 IS NOT NULL AND
             hardening_curve_point_count BETWEEN 1 AND 50000 AND
             cardinality(candidate_families) BETWEEN 2 AND 4 AND
             primary_family=ANY(candidate_families) AND secondary_family=ANY(candidate_families) AND
             primary_weight BETWEEN 0 AND 1 AND characterized_strain_max>0 AND
             extension_strain_max>characterized_strain_max AND approximation_acknowledged AND
             c10_pa IS NULL AND ogden_mu_pa IS NULL AND bulk_relaxation_status IS NULL) OR
           (model_family='generalized_maxwell' AND family='generalized_maxwell' AND
             youngs_modulus_pa>0 AND poisson_ratio>-1 AND poisson_ratio<0.5 AND
             bulk_relaxation_status IN ('characterized','not_characterized') AND
             reference_temperature_k>0 AND hardening_curve_artifact_id IS NULL AND
             c10_pa IS NULL AND ogden_mu_pa IS NULL)),
          ADD CONSTRAINT ck_modeling_neutral_material_applicability CHECK
          (density_kg_per_m3>0 AND
           ((model_family='generalized_maxwell' AND applicable_strain_min IS NULL AND
             applicable_strain_max IS NULL AND applicable_time_min_s>=0 AND
             applicable_time_max_s>applicable_time_min_s) OR
            (model_family<>'generalized_maxwell' AND applicable_time_min_s IS NULL AND
             applicable_time_max_s IS NULL AND applicable_strain_min>=0 AND
             applicable_strain_max>applicable_strain_min))),
          ADD CONSTRAINT ck_modeling_neutral_material_prony_overlay CHECK
          ((model_family<>'hyperelastic' AND prony_overlay_status IS NULL AND
            prony_overlay_reason IS NULL AND prony_overlay_model_id IS NULL AND
            prony_overlay_model_revision_id IS NULL) OR
           (model_family='hyperelastic' AND
             ((prony_overlay_status IS NULL AND prony_overlay_reason IS NULL AND
               prony_overlay_model_id IS NULL AND prony_overlay_model_revision_id IS NULL) OR
              (prony_overlay_status='not_applicable' AND prony_overlay_reason IS NOT NULL AND
               prony_overlay_model_id IS NULL AND prony_overlay_model_revision_id IS NULL) OR
              (prony_overlay_status='exact_revision' AND prony_overlay_reason IS NOT NULL AND
               prony_overlay_model_id IS NOT NULL AND
               prony_overlay_model_revision_id IS NOT NULL)))),
          ADD CONSTRAINT fk_modeling_neutral_material_processing_output FOREIGN KEY
          (organization_id, project_id, classification, processing_output_id,
           processing_output_revision_id) REFERENCES
          processing.common_processing_output_revision
          (organization_id, project_id, classification, aggregate_id, id),
          ADD CONSTRAINT fk_modeling_neutral_material_hardening_artifact FOREIGN KEY
          (organization_id, project_id, classification, hardening_curve_artifact_id) REFERENCES
          artifact.artifact (organization_id, project_id, classification, id),
          ADD CONSTRAINT fk_modeling_neutral_material_overlay_model FOREIGN KEY
          (organization_id, project_id, classification, prony_overlay_model_id,
           prony_overlay_model_revision_id) REFERENCES modeling.material_model_revision
          (organization_id, project_id, classification, aggregate_id, id);

        CREATE TABLE modeling.neutral_material_prony_term (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, neutral_material_id uuid NOT NULL,
          neutral_material_revision_id uuid NOT NULL,
          usage varchar(16) NOT NULL CHECK (usage IN ('linear','overlay')),
          ordinal smallint NOT NULL CHECK (ordinal BETWEEN 1 AND 10),
          g_ratio double precision NOT NULL CHECK (g_ratio>=0 AND g_ratio<1),
          k_ratio double precision NOT NULL CHECK (k_ratio>=0 AND k_ratio<1),
          relaxation_time_s double precision NOT NULL CHECK (relaxation_time_s>0),
          CONSTRAINT pk_modeling_neutral_material_prony_term PRIMARY KEY
          (organization_id, project_id, neutral_material_revision_id, usage, ordinal),
          CONSTRAINT fk_modeling_neutral_material_prony_owner FOREIGN KEY
          (organization_id, project_id, classification, neutral_material_id,
           neutral_material_revision_id) REFERENCES modeling.neutral_material_revision
          (organization_id, project_id, classification, aggregate_id, id)
        );
        CREATE TRIGGER modeling_neutral_material_prony_immutable BEFORE UPDATE OR DELETE
          ON modeling.neutral_material_prony_term FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        ALTER TABLE modeling.neutral_material_prony_term ENABLE ROW LEVEL SECURITY;
        ALTER TABLE modeling.neutral_material_prony_term FORCE ROW LEVEL SECURITY;
        CREATE POLICY modeling_neutral_material_prony_select
          ON modeling.neutral_material_prony_term FOR SELECT USING
          (access_control.can_access_row(organization_id, project_id, classification,
                                         'modeling.read'));
        CREATE POLICY modeling_neutral_material_prony_insert
          ON modeling.neutral_material_prony_term FOR INSERT WITH CHECK
          (access_control.can_access_row(organization_id, project_id, classification,
                                         'modeling.write'));

        ALTER TABLE modeling.neutral_material_source_dataset
          DROP CONSTRAINT fk_modeling_neutral_material_source_dataset,
          DROP CONSTRAINT neutral_material_source_dataset_role_check,
          DROP CONSTRAINT neutral_material_source_dataset_test_mode_check,
          ADD COLUMN source_kind varchar(64) NOT NULL DEFAULT 'governed_dataset',
          ADD CONSTRAINT ck_modeling_neutral_material_source_kind CHECK
          (source_kind IN ('governed_dataset','test_data_document',
                           'shear_relaxation_dataset')),
          ADD CONSTRAINT ck_modeling_neutral_material_source_role CHECK
          (role IN ('calibration','holdout','processing_input')),
          ADD CONSTRAINT ck_modeling_neutral_material_source_test_mode CHECK
          (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension',
                         'stress_relaxation'));
        ALTER TABLE modeling.neutral_material_source_dataset
          ALTER COLUMN source_kind DROP DEFAULT;

        CREATE OR REPLACE FUNCTION modeling.validate_neutral_material_source()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.source_kind='governed_dataset' AND NOT EXISTS (
            SELECT 1 FROM datasets.governed_dataset_revision r
             WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
               AND r.classification=NEW.classification AND r.aggregate_id=NEW.dataset_id
               AND r.id=NEW.dataset_revision_id
          ) THEN RAISE EXCEPTION 'exact governed Dataset revision is not visible';
          ELSIF NEW.source_kind='test_data_document' AND NOT EXISTS (
            SELECT 1 FROM datasets.test_data_document_revision r
             WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
               AND r.classification=NEW.classification AND r.aggregate_id=NEW.dataset_id
               AND r.id=NEW.dataset_revision_id
          ) THEN RAISE EXCEPTION 'exact Test Data revision is not visible';
          ELSIF NEW.source_kind='shear_relaxation_dataset' AND NOT EXISTS (
            SELECT 1 FROM datasets.shear_relaxation_dataset_revision r
             WHERE r.organization_id=NEW.organization_id AND r.project_id=NEW.project_id
               AND r.classification=NEW.classification AND r.aggregate_id=NEW.dataset_id
               AND r.id=NEW.dataset_revision_id
          ) THEN RAISE EXCEPTION 'exact relaxation Dataset revision is not visible';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER modeling_neutral_material_source_exact BEFORE INSERT
          ON modeling.neutral_material_source_dataset FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_neutral_material_source();

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
        CREATE TRIGGER modeling_neutral_material_evidence_exact BEFORE INSERT
          ON modeling.neutral_material_revision FOR EACH ROW
          EXECUTE FUNCTION modeling.validate_neutral_material_evidence();

        CREATE INDEX ix_modeling_neutral_material_model_family
          ON modeling.neutral_material_revision
          (organization_id, project_id, model_family, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX modeling.ix_modeling_neutral_material_model_family;
        DROP TRIGGER modeling_neutral_material_source_exact
          ON modeling.neutral_material_source_dataset;
        DROP FUNCTION modeling.validate_neutral_material_source();
        DROP TRIGGER IF EXISTS modeling_neutral_material_evidence_exact
          ON modeling.neutral_material_revision;
        DROP FUNCTION IF EXISTS modeling.validate_neutral_material_evidence();
        ALTER TABLE modeling.neutral_material_source_dataset
          DROP CONSTRAINT ck_modeling_neutral_material_source_kind,
          DROP CONSTRAINT ck_modeling_neutral_material_source_role,
          DROP CONSTRAINT ck_modeling_neutral_material_source_test_mode,
          DROP COLUMN source_kind,
          ADD CONSTRAINT neutral_material_source_dataset_role_check
            CHECK (role IN ('calibration','holdout')),
          ADD CONSTRAINT neutral_material_source_dataset_test_mode_check
            CHECK (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension')),
          ADD CONSTRAINT fk_modeling_neutral_material_source_dataset FOREIGN KEY
          (organization_id, project_id, classification, dataset_id, dataset_revision_id)
          REFERENCES datasets.governed_dataset_revision
          (organization_id, project_id, classification, aggregate_id, id);
        DROP TABLE modeling.neutral_material_prony_term;
        ALTER TABLE modeling.neutral_material_revision
          DROP CONSTRAINT fk_modeling_neutral_material_overlay_model,
          DROP CONSTRAINT fk_modeling_neutral_material_hardening_artifact,
          DROP CONSTRAINT fk_modeling_neutral_material_processing_output,
          DROP CONSTRAINT ck_modeling_neutral_material_prony_overlay,
          DROP CONSTRAINT ck_modeling_neutral_material_applicability,
          DROP CONSTRAINT ck_modeling_neutral_material_family_parameters,
          DROP CONSTRAINT ck_modeling_neutral_material_selection_kind,
          DROP CONSTRAINT ck_modeling_neutral_material_model_family,
          DROP CONSTRAINT uq_modeling_neutral_material_processing_output,
          DROP CONSTRAINT uq_modeling_neutral_material_candidate;
        ALTER TABLE modeling.neutral_material_revision
          DROP COLUMN prony_overlay_model_revision_id,
          DROP COLUMN prony_overlay_model_id,
          DROP COLUMN prony_overlay_reason,
          DROP COLUMN prony_overlay_status,
          DROP COLUMN applicable_time_max_s,
          DROP COLUMN applicable_time_min_s,
          DROP COLUMN reference_temperature_k,
          DROP COLUMN bulk_relaxation_status,
          DROP COLUMN approximation_acknowledged,
          DROP COLUMN extrapolation_policy,
          DROP COLUMN extension_strain_max,
          DROP COLUMN characterized_strain_max,
          DROP COLUMN hardening_curve_point_count,
          DROP COLUMN hardening_curve_schema_ref,
          DROP COLUMN hardening_curve_sha256,
          DROP COLUMN hardening_curve_artifact_id,
          DROP COLUMN initial_yield_stress_pa,
          DROP COLUMN poisson_ratio,
          DROP COLUMN youngs_modulus_pa,
          DROP COLUMN primary_weight,
          DROP COLUMN secondary_family,
          DROP COLUMN primary_family,
          DROP COLUMN candidate_families,
          DROP COLUMN selected_series,
          DROP COLUMN processing_output_sha256,
          DROP COLUMN processing_output_revision_id,
          DROP COLUMN processing_output_id,
          DROP COLUMN selection_kind,
          DROP COLUMN model_family;
        ALTER TABLE modeling.neutral_material_revision
          ALTER COLUMN calibration_plan_id SET NOT NULL,
          ALTER COLUMN calibration_plan_revision_id SET NOT NULL,
          ALTER COLUMN scientific_profile_id SET NOT NULL,
          ALTER COLUMN scientific_profile_revision_id SET NOT NULL,
          ALTER COLUMN calibration_run_id SET NOT NULL,
          ALTER COLUMN family_candidate_id SET NOT NULL,
          ALTER COLUMN candidate_sha256 SET NOT NULL,
          ALTER COLUMN diagnostics_artifact_id SET NOT NULL,
          ALTER COLUMN diagnostics_sha256 SET NOT NULL,
          ALTER COLUMN applicable_strain_min SET NOT NULL,
          ALTER COLUMN applicable_strain_max SET NOT NULL;
        ALTER TABLE modeling.neutral_material_revision
          ADD CONSTRAINT uq_modeling_neutral_material_candidate UNIQUE
          (organization_id, project_id, family_candidate_id),
          ADD CONSTRAINT ck_modeling_neutral_material_family_parameters CHECK
          ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND
            c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
           (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND
            c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
           (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND
            c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
           (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND
            c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)),
          ADD CONSTRAINT ck_modeling_neutral_material_applicability CHECK
          (density_kg_per_m3>0 AND applicable_strain_min>=0 AND
           applicable_strain_max>applicable_strain_min),
          ADD CONSTRAINT fk_modeling_neutral_material_plan FOREIGN KEY
          (organization_id, project_id, classification, calibration_plan_id,
           calibration_plan_revision_id) REFERENCES modeling.ogden_calibration_plan_revision
          (organization_id, project_id, classification, aggregate_id, id),
          ADD CONSTRAINT fk_modeling_neutral_material_profile FOREIGN KEY
          (organization_id, project_id, classification, scientific_profile_id,
           scientific_profile_revision_id) REFERENCES modeling.scientific_profile_revision
          (organization_id, project_id, classification, aggregate_id, id),
          ADD CONSTRAINT fk_modeling_neutral_material_candidate FOREIGN KEY
          (organization_id, project_id, classification, family_candidate_id) REFERENCES
          modeling.hyperelastic_family_candidate
          (organization_id, project_id, classification, id);
        """
    )

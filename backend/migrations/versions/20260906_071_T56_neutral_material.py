"""Persist canonical Neutral Material JSON and its typed hyperelastic IR projection.

Revision ID: 20260906_071_t56_neutral
Revises: 20260905_070_t55e_diagnostics

Traceability: T-56.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_071_t56_neutral"
down_revision: str | None = "20260905_070_t55e_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str, *, identity: bool = False) -> None:
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY modeling_{table}_select ON modeling.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'modeling.read'))"
    )
    op.execute(
        f"CREATE POLICY modeling_{table}_insert ON modeling.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'modeling.write'))"
    )
    if identity:
        op.execute(
            f"CREATE POLICY modeling_{table}_update ON modeling.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'modeling.write')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'modeling.write'))"
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE modeling.neutral_material (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, material_state_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_modeling_neutral_material PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_neutral_material_scope UNIQUE
            (organization_id, project_id, classification, id)
        );

        CREATE TABLE modeling.neutral_material_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          document_artifact_id uuid NOT NULL,
          document_artifact_sha256 char(64) NOT NULL,
          document_content_sha256 char(64) NOT NULL,
          material_id uuid NOT NULL, material_revision_id uuid NOT NULL,
          material_state_id uuid NOT NULL, material_state_revision_id uuid NOT NULL,
          property_set_id uuid NOT NULL, property_set_revision_id uuid NOT NULL,
          calibration_plan_id uuid NOT NULL, calibration_plan_revision_id uuid NOT NULL,
          scientific_profile_id uuid NOT NULL, scientific_profile_revision_id uuid NOT NULL,
          mapping_profile_status varchar(32) NOT NULL,
          mapping_profile_reason varchar(500) NOT NULL,
          mapping_profile_id uuid, mapping_profile_revision_id uuid,
          processing_recipe_status varchar(32) NOT NULL,
          processing_recipe_reason varchar(500) NOT NULL,
          processing_recipe_id uuid, processing_recipe_revision_id uuid,
          calibration_run_id uuid NOT NULL, family_candidate_id uuid NOT NULL,
          candidate_sha256 char(64) NOT NULL, selection_reason text NOT NULL,
          diagnostics_artifact_id uuid NOT NULL, diagnostics_sha256 char(64) NOT NULL,
          family varchar(32) NOT NULL,
          c10_pa double precision, c01_pa double precision,
          c20_pa double precision, c30_pa double precision,
          ogden_mu_pa double precision, ogden_alpha double precision,
          density_kg_per_m3 double precision NOT NULL,
          applicable_strain_min double precision NOT NULL,
          applicable_strain_max double precision NOT NULL,
          validation_status varchar(160) NOT NULL,
          model_schema_digest char(64) NOT NULL,
          maturity varchar(32) NOT NULL, non_production boolean NOT NULL,

          CONSTRAINT pk_modeling_neutral_material_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_neutral_material_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_modeling_neutral_material_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_modeling_neutral_material_candidate UNIQUE
            (organization_id, project_id, family_candidate_id),
          CONSTRAINT ck_modeling_neutral_material_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_modeling_neutral_material_revision_hashes CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             document_artifact_sha256 ~ '^[0-9a-f]{64}$' AND
             document_content_sha256 ~ '^[0-9a-f]{64}$' AND
             candidate_sha256 ~ '^[0-9a-f]{64}$' AND
             diagnostics_sha256 ~ '^[0-9a-f]{64}$' AND
             model_schema_digest ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_modeling_neutral_material_revision_text CHECK
            (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(selection_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_modeling_neutral_material_optional_mapping CHECK
            ((mapping_profile_status='exact_revision' AND mapping_profile_id IS NOT NULL AND
              mapping_profile_revision_id IS NOT NULL) OR
             (mapping_profile_status='not_applicable' AND mapping_profile_id IS NULL AND
              mapping_profile_revision_id IS NULL)),
          CONSTRAINT ck_modeling_neutral_material_optional_recipe CHECK
            ((processing_recipe_status='exact_revision' AND processing_recipe_id IS NOT NULL AND
              processing_recipe_revision_id IS NOT NULL) OR
             (processing_recipe_status='not_applicable' AND processing_recipe_id IS NULL AND
              processing_recipe_revision_id IS NULL)),
          CONSTRAINT ck_modeling_neutral_material_family_parameters CHECK
            ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND
              c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)),
          CONSTRAINT ck_modeling_neutral_material_applicability CHECK
            (density_kg_per_m3>0 AND applicable_strain_min>=0 AND
             applicable_strain_max>applicable_strain_min),
          CONSTRAINT ck_modeling_neutral_material_reference_status CHECK
            (maturity='reference' AND non_production),
          CONSTRAINT fk_modeling_neutral_material_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            modeling.neutral_material
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            modeling.neutral_material_revision
            (organization_id, project_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_material FOREIGN KEY
            (organization_id, project_id, classification, material_id,
             material_revision_id) REFERENCES catalog.material_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_state FOREIGN KEY
            (organization_id, project_id, classification, material_state_id,
             material_state_revision_id) REFERENCES catalog.material_state_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_property_set FOREIGN KEY
            (organization_id, project_id, classification, property_set_id,
             property_set_revision_id) REFERENCES catalog.property_set_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_plan FOREIGN KEY
            (organization_id, project_id, classification, calibration_plan_id,
             calibration_plan_revision_id) REFERENCES modeling.ogden_calibration_plan_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_profile FOREIGN KEY
            (organization_id, project_id, classification, scientific_profile_id,
             scientific_profile_revision_id) REFERENCES modeling.scientific_profile_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_candidate FOREIGN KEY
            (organization_id, project_id, classification, family_candidate_id) REFERENCES
            modeling.hyperelastic_family_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_document_artifact FOREIGN KEY
            (organization_id, project_id, classification, document_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_diagnostics FOREIGN KEY
            (organization_id, project_id, classification, diagnostics_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id)
            ON DELETE RESTRICT
        );

        CREATE TABLE modeling.neutral_material_source_dataset (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          neutral_material_id uuid NOT NULL, neutral_material_revision_id uuid NOT NULL,
          ordinal smallint NOT NULL CHECK (ordinal BETWEEN 0 AND 23),
          dataset_id uuid NOT NULL, dataset_revision_id uuid NOT NULL,
          role varchar(32) NOT NULL CHECK (role IN ('calibration','holdout')),
          test_mode varchar(64) NOT NULL CHECK
            (test_mode IN ('uniaxial_tension','planar_tension','biaxial_tension')),
          normalized_artifact_id uuid NOT NULL,
          normalized_artifact_sha256 char(64) NOT NULL CHECK
            (normalized_artifact_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT pk_modeling_neutral_material_source_dataset PRIMARY KEY
            (organization_id, project_id, neutral_material_revision_id, ordinal),
          CONSTRAINT uq_modeling_neutral_material_source_revision UNIQUE
            (organization_id, project_id, neutral_material_revision_id, dataset_revision_id),
          CONSTRAINT fk_modeling_neutral_material_source_owner FOREIGN KEY
            (organization_id, project_id, classification, neutral_material_id,
             neutral_material_revision_id) REFERENCES modeling.neutral_material_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_source_dataset FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_neutral_material_source_artifact FOREIGN KEY
            (organization_id, project_id, classification, normalized_artifact_id)
            REFERENCES artifact.artifact
            (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        ALTER TABLE modeling.neutral_material ADD CONSTRAINT
          fk_modeling_neutral_material_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          modeling.neutral_material_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_modeling_neutral_material_state ON modeling.neutral_material
          (organization_id, project_id, material_state_id, updated_at DESC);
        CREATE INDEX ix_modeling_neutral_material_family ON modeling.neutral_material_revision
          (organization_id, project_id, family, created_at DESC);
        CREATE INDEX ix_modeling_neutral_material_source_dataset_lookup
          ON modeling.neutral_material_source_dataset
          (organization_id, project_id, dataset_id, dataset_revision_id);

        CREATE TRIGGER modeling_neutral_material_head_only BEFORE UPDATE OR DELETE
          ON modeling.neutral_material FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        CREATE TRIGGER modeling_neutral_material_revision_immutable BEFORE UPDATE OR DELETE
          ON modeling.neutral_material_revision FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER modeling_neutral_material_source_dataset_immutable
          BEFORE UPDATE OR DELETE ON modeling.neutral_material_source_dataset FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _rls("neutral_material", identity=True)
    _rls("neutral_material_revision")
    _rls("neutral_material_source_dataset")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE modeling.neutral_material DROP CONSTRAINT fk_modeling_neutral_material_current"
    )
    op.execute("DROP TABLE modeling.neutral_material_source_dataset")
    op.execute("DROP TABLE modeling.neutral_material_revision")
    op.execute("DROP TABLE modeling.neutral_material")

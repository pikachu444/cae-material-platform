"""Generalize Neutral solver cards across the three closed Neutral families.

Revision ID: 20260912_077_t64_export
Revises: 20260911_076_t63_neutral

Traceability: T-64.
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260912_077_t64_export"
down_revision: str | None = "20260911_076_t63_neutral"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE exporting.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE exporting.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY exporting_{table}_select ON exporting.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'export.read'))"
    )
    op.execute(
        f"CREATE POLICY exporting_{table}_insert ON exporting.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'export.execute'))"
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE exporting.neutral_solver_card_revision
          ADD COLUMN model_family varchar(64),
          ADD COLUMN model_schema_digest char(64),
          ADD COLUMN youngs_modulus_pa double precision,
          ADD COLUMN poisson_ratio double precision,
          ADD COLUMN initial_yield_stress_pa double precision,
          ADD COLUMN hardening_curve_artifact_id uuid,
          ADD COLUMN hardening_curve_sha256 char(64),
          ADD COLUMN hardening_curve_schema_ref varchar(255),
          ADD COLUMN hardening_curve_point_count integer,
          ADD COLUMN bulk_relaxation_status varchar(32),
          ADD COLUMN reference_temperature_k double precision,
          ADD COLUMN applicable_time_min_s double precision,
          ADD COLUMN applicable_time_max_s double precision;

        ALTER TABLE exporting.neutral_solver_card_revision
          ALTER COLUMN applicable_strain_min DROP NOT NULL,
          ALTER COLUMN applicable_strain_max DROP NOT NULL,
          DROP CONSTRAINT ck_exporting_neutral_solver_card_family_parameters,
          DROP CONSTRAINT ck_exporting_neutral_solver_card_applicability;

        ALTER TABLE exporting.neutral_solver_card_revision
          ADD CONSTRAINT ck_exporting_neutral_solver_card_family_parameters CHECK (
            (model_family IS NULL AND
             ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0))) OR
            (model_family='hyperelastic' AND family IN ('neo_hookean','mooney_rivlin','yeoh','ogden_1') AND model_schema_digest ~ '^[0-9a-f]{64}$' AND
             ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
              (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)) AND
             youngs_modulus_pa IS NULL AND hardening_curve_artifact_id IS NULL AND bulk_relaxation_status IS NULL) OR
            (model_family='isotropic_tabulated_plasticity' AND family='isotropic_tabulated_plasticity' AND model_schema_digest ~ '^[0-9a-f]{64}$' AND
             c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL AND
             youngs_modulus_pa>0 AND poisson_ratio>-1 AND poisson_ratio<0.5 AND initial_yield_stress_pa>0 AND
             hardening_curve_artifact_id IS NOT NULL AND hardening_curve_sha256 ~ '^[0-9a-f]{64}$' AND
             length(btrim(hardening_curve_schema_ref)) BETWEEN 1 AND 255 AND hardening_curve_point_count BETWEEN 2 AND 50000 AND bulk_relaxation_status IS NULL) OR
            (model_family='generalized_maxwell' AND family='generalized_maxwell' AND model_schema_digest ~ '^[0-9a-f]{64}$' AND
             c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL AND
             youngs_modulus_pa>0 AND poisson_ratio>-1 AND poisson_ratio<0.5 AND initial_yield_stress_pa IS NULL AND
             hardening_curve_artifact_id IS NULL AND bulk_relaxation_status IN ('characterized','not_characterized') AND reference_temperature_k>0)
          ),
          ADD CONSTRAINT ck_exporting_neutral_solver_card_applicability CHECK (
            density_kg_per_m3>0 AND
            ((applicable_strain_min IS NULL AND applicable_strain_max IS NULL) OR
             (applicable_strain_min>=0 AND applicable_strain_max>applicable_strain_min)) AND
            ((applicable_time_min_s IS NULL AND applicable_time_max_s IS NULL) OR
             (applicable_time_min_s>=0 AND applicable_time_max_s>applicable_time_min_s)) AND
            (model_family IS NULL OR
             (model_family IN ('hyperelastic','isotropic_tabulated_plasticity') AND applicable_strain_min IS NOT NULL) OR
             (model_family='generalized_maxwell' AND applicable_time_min_s IS NOT NULL))
          );

        CREATE TABLE exporting.neutral_solver_card_mapping_item (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL, ordinal smallint NOT NULL,
          name varchar(80) NOT NULL, status varchar(32) NOT NULL,
          CONSTRAINT pk_exporting_neutral_solver_card_mapping_item PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id, ordinal),
          CONSTRAINT uq_exporting_neutral_solver_card_mapping_name UNIQUE
            (organization_id, project_id, solver_card_revision_id, name),
          CONSTRAINT ck_exporting_neutral_solver_card_mapping_item CHECK
            (ordinal BETWEEN 1 AND 32 AND length(btrim(name)) BETWEEN 1 AND 80 AND
             status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable')),
          CONSTRAINT fk_exporting_neutral_solver_card_mapping_revision FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id, solver_card_revision_id)
            REFERENCES exporting.neutral_solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        );

        CREATE TABLE exporting.neutral_solver_card_prony_term (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, solver_card_id uuid NOT NULL,
          solver_card_revision_id uuid NOT NULL, ordinal smallint NOT NULL,
          g_ratio double precision NOT NULL, k_ratio double precision NOT NULL,
          relaxation_time_s double precision NOT NULL,
          CONSTRAINT pk_exporting_neutral_solver_card_prony_term PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id, ordinal),
          CONSTRAINT ck_exporting_neutral_solver_card_prony_term CHECK
            (ordinal BETWEEN 1 AND 10 AND g_ratio>=0 AND g_ratio<1 AND
             k_ratio>=0 AND k_ratio<1 AND relaxation_time_s>0),
          CONSTRAINT fk_exporting_neutral_solver_card_prony_revision FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id, solver_card_revision_id)
            REFERENCES exporting.neutral_solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id) ON DELETE RESTRICT
        );

        CREATE INDEX ix_exporting_neutral_solver_card_model_family
          ON exporting.neutral_solver_card_revision
          (organization_id, project_id, model_family, target_solver, created_at DESC);
        CREATE INDEX ix_exporting_neutral_solver_card_mapping_status
          ON exporting.neutral_solver_card_mapping_item
          (organization_id, project_id, status, name);

        CREATE TRIGGER exporting_neutral_solver_card_mapping_immutable BEFORE UPDATE OR DELETE
          ON exporting.neutral_solver_card_mapping_item FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER exporting_neutral_solver_card_prony_immutable BEFORE UPDATE OR DELETE
          ON exporting.neutral_solver_card_prony_term FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _rls("neutral_solver_card_mapping_item")
    _rls("neutral_solver_card_prony_term")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM exporting.neutral_solver_card_revision WHERE model_family IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'cannot downgrade T-64 while family-neutral solver cards exist';
          END IF;
        END $$;

        DROP TABLE exporting.neutral_solver_card_prony_term;
        DROP TABLE exporting.neutral_solver_card_mapping_item;
        DROP INDEX exporting.ix_exporting_neutral_solver_card_model_family;

        ALTER TABLE exporting.neutral_solver_card_revision
          DROP CONSTRAINT ck_exporting_neutral_solver_card_family_parameters,
          DROP CONSTRAINT ck_exporting_neutral_solver_card_applicability,
          ALTER COLUMN applicable_strain_min SET NOT NULL,
          ALTER COLUMN applicable_strain_max SET NOT NULL,
          ADD CONSTRAINT ck_exporting_neutral_solver_card_family_parameters CHECK
            ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)),
          ADD CONSTRAINT ck_exporting_neutral_solver_card_applicability CHECK
            (density_kg_per_m3>0 AND applicable_strain_min>=0 AND applicable_strain_max>applicable_strain_min),
          DROP COLUMN applicable_time_max_s,
          DROP COLUMN applicable_time_min_s,
          DROP COLUMN reference_temperature_k,
          DROP COLUMN bulk_relaxation_status,
          DROP COLUMN hardening_curve_point_count,
          DROP COLUMN hardening_curve_schema_ref,
          DROP COLUMN hardening_curve_sha256,
          DROP COLUMN hardening_curve_artifact_id,
          DROP COLUMN initial_yield_stress_pa,
          DROP COLUMN poisson_ratio,
          DROP COLUMN youngs_modulus_pa,
          DROP COLUMN model_schema_digest,
          DROP COLUMN model_family;
        """
    )

"""Add typed model-family scientific calibration profiles.

Revision ID: 20260819_053_t43_profiles
Revises: 20260818_052_t42

Traceability: T-43, FR-CAL-002/003/007, ADR-0025.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260819_053_t43_profiles"
down_revision: str | None = "20260818_052_t42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
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
        CREATE TABLE modeling.scientific_profile (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_label varchar(160) NOT NULL,
          family varchar(64) NOT NULL CHECK (family IN
            ('steel_voce','polymer_linear_prony','elastomer_ogden_prony')),
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_modeling_scientific_profile PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_scientific_profile_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_scientific_profile_label UNIQUE
            (organization_id, project_id, classification, family, profile_label)
        );

        CREATE TABLE modeling.scientific_profile_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no > 0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL CHECK (schema_version='1.0.0'),
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          profile_label varchar(160) NOT NULL,
          family varchar(64) NOT NULL CHECK (family IN
            ('steel_voce','polymer_linear_prony','elastomer_ogden_prony')),
          model_family_id varchar(255) NOT NULL,
          approval_status varchar(32) NOT NULL CHECK
            (approval_status IN ('reference_unapproved','domain_approved')),
          optimizer varchar(64) NOT NULL CHECK (optimizer='scipy_least_squares_trf'),
          residual_definition varchar(64) NOT NULL CHECK
            (residual_definition='normalized_weighted_least_squares'),
          aggregation_order varchar(64) NOT NULL CHECK
            (aggregation_order='point_then_curve_then_mode'),
          missing_data_policy varchar(32) NOT NULL CHECK (missing_data_policy='reject'),
          holdout_policy varchar(32) NOT NULL CHECK (holdout_policy='explicit_disjoint'),
          uncertainty_policy varchar(64) NOT NULL CHECK
            (uncertainty_policy='jacobian_covariance_or_not_estimable'),
          multistart_count integer NOT NULL CHECK (multistart_count BETWEEN 1 AND 32),
          seed integer NOT NULL CHECK (seed BETWEEN 0 AND 2147483647),
          status_note varchar(500) NOT NULL CHECK
            (length(btrim(status_note)) BETWEEN 1 AND 500),

          voce_sigma0_initial_pa double precision,
          voce_sigma0_lower_pa double precision,
          voce_sigma0_upper_pa double precision,
          voce_sigma0_scale_pa double precision,
          voce_q_initial_pa double precision,
          voce_q_lower_pa double precision,
          voce_q_upper_pa double precision,
          voce_q_scale_pa double precision,
          voce_b_initial double precision,
          voce_b_lower double precision,
          voce_b_upper double precision,
          voce_b_scale double precision,

          prony_term_count_min integer,
          prony_term_count_max integer,
          prony_total_shear_ratio_upper double precision,
          prony_relaxation_time_lower_s double precision,
          prony_relaxation_time_upper_s double precision,

          ogden_mu_initial_pa double precision,
          ogden_mu_lower_pa double precision,
          ogden_mu_upper_pa double precision,
          ogden_mu_scale_pa double precision,
          ogden_alpha_initial double precision,
          ogden_alpha_lower double precision,
          ogden_alpha_upper double precision,
          ogden_alpha_scale double precision,
          ogden_uniaxial_weight double precision,
          ogden_planar_weight double precision,
          ogden_biaxial_weight double precision,

          CONSTRAINT pk_modeling_scientific_profile_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_scientific_profile_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_modeling_scientific_profile_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_modeling_scientific_profile_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id)
            REFERENCES modeling.scientific_profile
            (organization_id, project_id, classification, id) ON DELETE RESTRICT,
          CONSTRAINT fk_modeling_scientific_profile_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id)
            REFERENCES modeling.scientific_profile_revision
            (organization_id, project_id, id) ON DELETE RESTRICT,
          CONSTRAINT ck_modeling_scientific_profile_family_id CHECK (
            (family='steel_voce' AND
             model_family_id='urn:cmp:reference:voce-saturation-hardening:1.0.0') OR
            (family='polymer_linear_prony' AND
             model_family_id='urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0') OR
            (family='elastomer_ogden_prony' AND
             model_family_id='urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0')),
          CONSTRAINT ck_modeling_scientific_profile_parameter_family CHECK (
            (family='steel_voce' AND
             voce_sigma0_initial_pa IS NOT NULL AND voce_sigma0_lower_pa IS NOT NULL AND
             voce_sigma0_upper_pa IS NOT NULL AND voce_sigma0_scale_pa IS NOT NULL AND
             voce_q_initial_pa IS NOT NULL AND voce_q_lower_pa IS NOT NULL AND
             voce_q_upper_pa IS NOT NULL AND voce_q_scale_pa IS NOT NULL AND
             voce_b_initial IS NOT NULL AND voce_b_lower IS NOT NULL AND
             voce_b_upper IS NOT NULL AND voce_b_scale IS NOT NULL AND
             prony_term_count_min IS NULL AND prony_term_count_max IS NULL AND
             prony_total_shear_ratio_upper IS NULL AND
             prony_relaxation_time_lower_s IS NULL AND
             prony_relaxation_time_upper_s IS NULL AND
             ogden_mu_initial_pa IS NULL AND ogden_mu_lower_pa IS NULL AND
             ogden_mu_upper_pa IS NULL AND ogden_mu_scale_pa IS NULL AND
             ogden_alpha_initial IS NULL AND ogden_alpha_lower IS NULL AND
             ogden_alpha_upper IS NULL AND ogden_alpha_scale IS NULL AND
             ogden_uniaxial_weight IS NULL AND ogden_planar_weight IS NULL AND
             ogden_biaxial_weight IS NULL) OR
            (family='polymer_linear_prony' AND
             prony_term_count_min IS NOT NULL AND prony_term_count_max IS NOT NULL AND
             prony_total_shear_ratio_upper IS NOT NULL AND
             prony_relaxation_time_lower_s IS NOT NULL AND
             prony_relaxation_time_upper_s IS NOT NULL AND
             voce_sigma0_initial_pa IS NULL AND voce_sigma0_lower_pa IS NULL AND
             voce_sigma0_upper_pa IS NULL AND voce_sigma0_scale_pa IS NULL AND
             voce_q_initial_pa IS NULL AND voce_q_lower_pa IS NULL AND
             voce_q_upper_pa IS NULL AND voce_q_scale_pa IS NULL AND
             voce_b_initial IS NULL AND voce_b_lower IS NULL AND
             voce_b_upper IS NULL AND voce_b_scale IS NULL AND
             ogden_mu_initial_pa IS NULL AND ogden_mu_lower_pa IS NULL AND
             ogden_mu_upper_pa IS NULL AND ogden_mu_scale_pa IS NULL AND
             ogden_alpha_initial IS NULL AND ogden_alpha_lower IS NULL AND
             ogden_alpha_upper IS NULL AND ogden_alpha_scale IS NULL AND
             ogden_uniaxial_weight IS NULL AND ogden_planar_weight IS NULL AND
             ogden_biaxial_weight IS NULL) OR
            (family='elastomer_ogden_prony' AND
             ogden_mu_initial_pa IS NOT NULL AND ogden_mu_lower_pa IS NOT NULL AND
             ogden_mu_upper_pa IS NOT NULL AND ogden_mu_scale_pa IS NOT NULL AND
             ogden_alpha_initial IS NOT NULL AND ogden_alpha_lower IS NOT NULL AND
             ogden_alpha_upper IS NOT NULL AND ogden_alpha_scale IS NOT NULL AND
             ogden_uniaxial_weight IS NOT NULL AND ogden_planar_weight IS NOT NULL AND
             ogden_biaxial_weight IS NOT NULL AND
             voce_sigma0_initial_pa IS NULL AND voce_sigma0_lower_pa IS NULL AND
             voce_sigma0_upper_pa IS NULL AND voce_sigma0_scale_pa IS NULL AND
             voce_q_initial_pa IS NULL AND voce_q_lower_pa IS NULL AND
             voce_q_upper_pa IS NULL AND voce_q_scale_pa IS NULL AND
             voce_b_initial IS NULL AND voce_b_lower IS NULL AND
             voce_b_upper IS NULL AND voce_b_scale IS NULL AND
             prony_term_count_min IS NULL AND prony_term_count_max IS NULL AND
             prony_total_shear_ratio_upper IS NULL AND
             prony_relaxation_time_lower_s IS NULL AND
             prony_relaxation_time_upper_s IS NULL)),
          CONSTRAINT ck_modeling_scientific_profile_voce_bounds CHECK (
            family<>'steel_voce' OR
            (voce_sigma0_lower_pa>0 AND voce_sigma0_lower_pa<voce_sigma0_initial_pa AND
             voce_sigma0_initial_pa<voce_sigma0_upper_pa AND voce_sigma0_scale_pa>0 AND
             voce_q_lower_pa>0 AND voce_q_lower_pa<voce_q_initial_pa AND
             voce_q_initial_pa<voce_q_upper_pa AND voce_q_scale_pa>0 AND
             voce_b_lower>0 AND voce_b_lower<voce_b_initial AND
             voce_b_initial<voce_b_upper AND voce_b_scale>0)),
          CONSTRAINT ck_modeling_scientific_profile_prony_bounds CHECK (
            family<>'polymer_linear_prony' OR
            (prony_term_count_min BETWEEN 1 AND 10 AND
             prony_term_count_max BETWEEN prony_term_count_min AND 10 AND
             prony_total_shear_ratio_upper>0 AND prony_total_shear_ratio_upper<1 AND
             prony_relaxation_time_lower_s>0 AND
             prony_relaxation_time_lower_s<prony_relaxation_time_upper_s)),
          CONSTRAINT ck_modeling_scientific_profile_ogden_bounds CHECK (
            family<>'elastomer_ogden_prony' OR
            (ogden_mu_lower_pa>0 AND ogden_mu_lower_pa<ogden_mu_initial_pa AND
             ogden_mu_initial_pa<ogden_mu_upper_pa AND ogden_mu_scale_pa>0 AND
             ogden_alpha_lower>0 AND ogden_alpha_lower<ogden_alpha_initial AND
             ogden_alpha_initial<ogden_alpha_upper AND ogden_alpha_scale>0 AND
             ogden_uniaxial_weight>0 AND ogden_planar_weight>0 AND ogden_biaxial_weight>0))
        );

        ALTER TABLE modeling.scientific_profile
          ADD CONSTRAINT fk_modeling_scientific_profile_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES modeling.scientific_profile_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_modeling_scientific_profile_family
          ON modeling.scientific_profile
          (organization_id, project_id, family, profile_label);
        CREATE INDEX ix_modeling_scientific_profile_revision_status
          ON modeling.scientific_profile_revision
          (organization_id, project_id, family, approval_status, created_at DESC);

        CREATE TRIGGER modeling_scientific_profile_head_only BEFORE UPDATE OR DELETE
          ON modeling.scientific_profile FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        CREATE TRIGGER modeling_scientific_profile_revision_immutable BEFORE UPDATE OR DELETE
          ON modeling.scientific_profile_revision FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _rls("scientific_profile")
    _rls("scientific_profile_revision")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE modeling.scientific_profile "
        "DROP CONSTRAINT fk_modeling_scientific_profile_current"
    )
    op.execute("DROP TABLE modeling.scientific_profile_revision")
    op.execute("DROP TABLE modeling.scientific_profile")

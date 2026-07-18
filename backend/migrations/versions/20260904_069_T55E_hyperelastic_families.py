"""Persist explicit hyperelastic family comparison candidates.

Revision ID: 20260904_069_t55e_families
Revises: 20260903_068_t55p_arrhenius

Traceability: T-55E.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260904_069_t55e_families"
down_revision: str | None = "20260903_068_t55p_arrhenius"
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
        "'calibration.execute'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE modeling.hyperelastic_family_candidate (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, calibration_run_id uuid NOT NULL,
          family varchar(32) NOT NULL CHECK
            (family IN ('neo_hookean','mooney_rivlin','yeoh','ogden_1')),
          candidate_sha256 char(64) NOT NULL CHECK (candidate_sha256 ~ '^[0-9a-f]{64}$'),
          c10_pa double precision, c01_pa double precision,
          c20_pa double precision, c30_pa double precision,
          ogden_mu_pa double precision, ogden_alpha double precision,
          objective_total double precision NOT NULL CHECK
            (objective_total>=0 AND objective_total<'Infinity'::double precision),
          uniaxial_objective double precision NOT NULL CHECK
            (uniaxial_objective>=0 AND uniaxial_objective<'Infinity'::double precision),
          planar_objective double precision NOT NULL CHECK
            (planar_objective>=0 AND planar_objective<'Infinity'::double precision),
          biaxial_objective double precision NOT NULL CHECK
            (biaxial_objective>=0 AND biaxial_objective<'Infinity'::double precision),
          calibration_normalized_rmse double precision NOT NULL CHECK
            (calibration_normalized_rmse>=0 AND
             calibration_normalized_rmse<'Infinity'::double precision),
          holdout_normalized_rmse double precision CHECK
            (holdout_normalized_rmse>=0 AND
             holdout_normalized_rmse<'Infinity'::double precision),
          function_evaluations integer NOT NULL CHECK (function_evaluations>0),
          convergence_reason varchar(255) NOT NULL CHECK
            (length(btrim(convergence_reason)) BETWEEN 1 AND 255),
          stability_status varchar(48) NOT NULL CHECK
            (stability_status IN ('monotonic_on_fitted_domain','nonmonotonic')),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          CONSTRAINT pk_modeling_hyperelastic_family_candidate PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_modeling_hyperelastic_family_candidate_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_modeling_hyperelastic_family_candidate_run_family UNIQUE
            (organization_id, project_id, calibration_run_id, family),
          CONSTRAINT ck_modeling_hyperelastic_family_candidate_parameters CHECK
            ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND
              c20_pa IS NULL AND c30_pa IS NULL AND
              ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND
              c20_pa IS NULL AND c30_pa IS NULL AND
              ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='yeoh' AND c10_pa>0 AND c20_pa IS NOT NULL AND c30_pa IS NOT NULL AND
              c01_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='ogden_1' AND ogden_mu_pa>0 AND ogden_alpha>0 AND
              c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND c30_pa IS NULL)),
          CONSTRAINT fk_modeling_hyperelastic_family_candidate_run FOREIGN KEY
            (organization_id, project_id, classification, calibration_run_id) REFERENCES
            modeling.ogden_calibration_run
            (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        CREATE TABLE modeling.hyperelastic_family_candidate_warning (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, candidate_id uuid NOT NULL,
          ordinal smallint NOT NULL CHECK (ordinal BETWEEN 0 AND 15),
          warning_code varchar(64) NOT NULL CHECK
            (length(btrim(warning_code)) BETWEEN 1 AND 64),
          CONSTRAINT pk_modeling_hyperelastic_family_candidate_warning PRIMARY KEY
            (organization_id, project_id, candidate_id, ordinal),
          CONSTRAINT fk_modeling_hyperelastic_family_candidate_warning_candidate FOREIGN KEY
            (organization_id, project_id, classification, candidate_id) REFERENCES
            modeling.hyperelastic_family_candidate
            (organization_id, project_id, classification, id) ON DELETE RESTRICT
        );

        CREATE INDEX ix_modeling_hyperelastic_family_candidate_objective
          ON modeling.hyperelastic_family_candidate
          (organization_id, project_id, calibration_run_id, objective_total);

        CREATE TRIGGER modeling_hyperelastic_family_candidate_immutable
          BEFORE UPDATE OR DELETE ON modeling.hyperelastic_family_candidate
          FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        CREATE TRIGGER modeling_hyperelastic_family_candidate_warning_immutable
          BEFORE UPDATE OR DELETE ON modeling.hyperelastic_family_candidate_warning
          FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _rls("hyperelastic_family_candidate")
    _rls("hyperelastic_family_candidate_warning")


def downgrade() -> None:
    op.execute("DROP TABLE modeling.hyperelastic_family_candidate_warning")
    op.execute("DROP TABLE modeling.hyperelastic_family_candidate")

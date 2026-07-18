"""Persist native cards generated from exact Neutral Material revisions.

Revision ID: 20260907_072_t57_cards
Revises: 20260906_071_t56_neutral

Traceability: T-57.
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260907_072_t57_cards"
down_revision: str | None = "20260906_071_t56_neutral"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str, *, identity: bool = False) -> None:
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
    if identity:
        op.execute(
            f"CREATE POLICY exporting_{table}_update ON exporting.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'export.execute')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, classification, "
            "'export.execute'))"
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE exporting.neutral_solver_card (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, neutral_material_id uuid NOT NULL,
          target_solver varchar(64) NOT NULL, target_version varchar(64) NOT NULL,
          target_unit_system varchar(64) NOT NULL, solver_material_id bigint NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_exporting_neutral_solver_card PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_exporting_neutral_solver_card_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_exporting_neutral_solver_card_target UNIQUE
            (organization_id, project_id, classification, id, neutral_material_id,
             target_solver, target_version, target_unit_system, solver_material_id),
          CONSTRAINT ck_exporting_neutral_solver_card_target CHECK
            (target_solver IN ('abaqus','openradioss') AND target_version='2025' AND
             target_unit_system='kg_m_s' AND solver_material_id BETWEEN 1 AND 9999999999),
          CONSTRAINT fk_exporting_neutral_solver_card_source FOREIGN KEY
            (organization_id, project_id, classification, neutral_material_id) REFERENCES
            modeling.neutral_material (organization_id, project_id, classification, id)
            ON DELETE RESTRICT
        );

        CREATE TABLE exporting.neutral_solver_card_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, revision_no bigint NOT NULL,
          based_on_revision_id uuid, schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL, content_hash char(64) NOT NULL,
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL, request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          neutral_material_id uuid NOT NULL, neutral_material_revision_id uuid NOT NULL,
          neutral_material_sha256 char(64) NOT NULL,
          family varchar(32) NOT NULL,
          c10_pa double precision, c01_pa double precision,
          c20_pa double precision, c30_pa double precision,
          ogden_mu_pa double precision, ogden_alpha double precision,
          density_kg_per_m3 double precision NOT NULL,
          applicable_strain_min double precision NOT NULL,
          applicable_strain_max double precision NOT NULL,
          target_solver varchar(64) NOT NULL, target_version varchar(64) NOT NULL,
          target_unit_system varchar(64) NOT NULL, solver_material_id bigint NOT NULL,
          material_name varchar(80) NOT NULL,
          density_mapping_status varchar(32) NOT NULL,
          constitutive_mapping_status varchar(32) NOT NULL,
          volumetric_mapping_status varchar(32) NOT NULL,
          applicability_mapping_status varchar(32) NOT NULL,
          calibration_mapping_status varchar(32) NOT NULL,
          unit_system_mapping_status varchar(32) NOT NULL,
          mapping_report_sha256 char(64) NOT NULL,
          card_text text NOT NULL, card_sha256 char(64) NOT NULL,
          exporter_id varchar(255) NOT NULL, exporter_version varchar(64) NOT NULL,
          exporter_digest char(64) NOT NULL, non_production boolean NOT NULL,
          CONSTRAINT pk_exporting_neutral_solver_card_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_exporting_neutral_solver_card_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_exporting_neutral_solver_card_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT ck_exporting_neutral_solver_card_revision_base CHECK
            ((revision_no=1 AND based_on_revision_id IS NULL) OR
             (revision_no>1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_exporting_neutral_solver_card_hashes CHECK
            (content_hash ~ '^[0-9a-f]{64}$' AND
             neutral_material_sha256 ~ '^[0-9a-f]{64}$' AND
             mapping_report_sha256 ~ '^[0-9a-f]{64}$' AND
             card_sha256 ~ '^[0-9a-f]{64}$' AND
             exporter_digest ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_exporting_neutral_solver_card_text CHECK
            (length(btrim(change_reason)) BETWEEN 1 AND 2000 AND
             length(btrim(trace_id)) BETWEEN 1 AND 255 AND
             material_name ~ '^[A-Za-z][A-Za-z0-9_-]{0,79}$' AND
             length(card_text)>0),
          CONSTRAINT ck_exporting_neutral_solver_card_family_parameters CHECK
            ((family='neo_hookean' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='mooney_rivlin' AND c10_pa>0 AND c01_pa>=0 AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='yeoh' AND c10_pa>0 AND c01_pa IS NULL AND c20_pa IS NOT NULL AND
              c30_pa IS NOT NULL AND ogden_mu_pa IS NULL AND ogden_alpha IS NULL) OR
             (family='ogden_1' AND c10_pa IS NULL AND c01_pa IS NULL AND c20_pa IS NULL AND
              c30_pa IS NULL AND ogden_mu_pa>0 AND ogden_alpha>0)),
          CONSTRAINT ck_exporting_neutral_solver_card_applicability CHECK
            (density_kg_per_m3>0 AND applicable_strain_min>=0 AND
             applicable_strain_max>applicable_strain_min),
          CONSTRAINT ck_exporting_neutral_solver_card_target CHECK
            (target_solver IN ('abaqus','openradioss') AND target_version='2025' AND
             target_unit_system='kg_m_s' AND solver_material_id BETWEEN 1 AND 9999999999),
          CONSTRAINT ck_exporting_neutral_solver_card_statuses CHECK
            (density_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable') AND
             constitutive_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable') AND
             volumetric_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable') AND
             applicability_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable') AND
             calibration_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable') AND
             unit_system_mapping_status IN ('exact','transformed','approximated','ignored','unsupported','not_applicable')),
          CONSTRAINT ck_exporting_neutral_solver_card_reference CHECK (non_production),
          CONSTRAINT fk_exporting_neutral_solver_card_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id,
             neutral_material_id, target_solver, target_version, target_unit_system,
             solver_material_id) REFERENCES exporting.neutral_solver_card
            (organization_id, project_id, classification, id, neutral_material_id,
             target_solver, target_version, target_unit_system, solver_material_id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_exporting_neutral_solver_card_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            exporting.neutral_solver_card_revision (organization_id, project_id, id)
            ON DELETE RESTRICT,
          CONSTRAINT fk_exporting_neutral_solver_card_revision_source FOREIGN KEY
            (organization_id, project_id, classification, neutral_material_id,
             neutral_material_revision_id) REFERENCES modeling.neutral_material_revision
            (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT
        );

        ALTER TABLE exporting.neutral_solver_card ADD CONSTRAINT
          fk_exporting_neutral_solver_card_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          exporting.neutral_solver_card_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_exporting_neutral_solver_card_source
          ON exporting.neutral_solver_card
          (organization_id, project_id, neutral_material_id, updated_at DESC);
        CREATE INDEX ix_exporting_neutral_solver_card_family_target
          ON exporting.neutral_solver_card_revision
          (organization_id, project_id, family, target_solver, created_at DESC);
        CREATE INDEX ix_exporting_neutral_solver_card_report
          ON exporting.neutral_solver_card_revision
          (organization_id, project_id, mapping_report_sha256);

        CREATE TRIGGER exporting_neutral_solver_card_head_only BEFORE UPDATE OR DELETE
          ON exporting.neutral_solver_card FOR EACH ROW
          EXECUTE FUNCTION revisioning.guard_identity_head_update();
        CREATE TRIGGER exporting_neutral_solver_card_revision_immutable BEFORE UPDATE OR DELETE
          ON exporting.neutral_solver_card_revision FOR EACH ROW
          EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )
    _rls("neutral_solver_card", identity=True)
    _rls("neutral_solver_card_revision")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE exporting.neutral_solver_card DROP CONSTRAINT "
        "fk_exporting_neutral_solver_card_current"
    )
    op.execute("DROP TABLE exporting.neutral_solver_card_revision")
    op.execute("DROP TABLE exporting.neutral_solver_card")

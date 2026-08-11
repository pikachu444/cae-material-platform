"""Issue #205 common CAE units and immutable Unit Profile revisions.

Revision ID: 20260926_095_issue205_units
Revises: 20260925_094_issue160
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260926_095_issue205_units"
down_revision: str | None = "20260925_094_issue160"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "unit_profile",
    "unit_profile_revision",
    "unit_profile_selection",
)


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE units.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE units.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY units_{table}_select ON units.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'units.read'))"
    )
    op.execute(
        f"CREATE POLICY units_{table}_insert ON units.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'units.write'))"
    )
    op.execute(
        f"CREATE POLICY units_{table}_update ON units.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'units.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'units.write'))"
    )


def _processing_rls(table: str) -> None:
    op.execute(f"ALTER TABLE processing.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE processing.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY processing_{table}_select ON processing.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'processing.read'))"
    )
    op.execute(
        f"CREATE POLICY processing_{table}_insert ON processing.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'processing.execute'))"
    )


def _exporting_rls(table: str) -> None:
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
    op.execute("CREATE SCHEMA units")
    op.execute(
        """
        CREATE TABLE units.unit_profile (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_key varchar(160) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_units_unit_profile PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_units_unit_profile_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_units_unit_profile_key UNIQUE
            (organization_id, project_id, profile_key),
          CONSTRAINT ck_units_unit_profile_key CHECK
            (profile_key ~ '^[a-z][a-z0-9_-]{0,159}$')
        );

        CREATE TABLE units.unit_profile_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no > 0),
          based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL
            CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          profile_key varchar(160) NOT NULL,
          label varchar(200) NOT NULL,
          description text,
          non_production boolean NOT NULL,
          selection_count integer NOT NULL CHECK (selection_count BETWEEN 1 AND 128),
          CONSTRAINT pk_units_unit_profile_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_units_unit_profile_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_units_unit_profile_revision_exact_hash UNIQUE
            (organization_id, project_id, classification, aggregate_id, id, content_hash),
          CONSTRAINT uq_units_unit_profile_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_units_unit_profile_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            units.unit_profile (organization_id, project_id, classification, id),
          CONSTRAINT fk_units_unit_profile_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            units.unit_profile_revision (organization_id, project_id, id),
          CONSTRAINT ck_units_unit_profile_revision_key CHECK
            (profile_key ~ '^[a-z][a-z0-9_-]{0,159}$'),
          CONSTRAINT ck_units_unit_profile_revision_label CHECK
            (length(btrim(label)) BETWEEN 1 AND 200),
          CONSTRAINT ck_units_unit_profile_revision_description CHECK
            (description IS NULL OR length(btrim(description)) BETWEEN 1 AND 1000)
        );

        ALTER TABLE units.unit_profile ADD CONSTRAINT fk_units_unit_profile_current
          FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          units.unit_profile_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX ix_units_unit_profile_label
          ON units.unit_profile_revision (organization_id, project_id, lower(label));

        CREATE TABLE units.unit_profile_selection (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          profile_id uuid NOT NULL, profile_revision_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          quantity_semantics varchar(160) NOT NULL,
          dimension varchar(64) NOT NULL,
          input_unit_id varchar(64) NOT NULL,
          display_unit_id varchar(64) NOT NULL,
          solver_export_unit_id varchar(64),
          CONSTRAINT pk_units_unit_profile_selection PRIMARY KEY
            (organization_id, project_id, profile_revision_id, ordinal),
          CONSTRAINT uq_units_unit_profile_selection_semantics UNIQUE
            (organization_id, project_id, profile_revision_id, quantity_semantics),
          CONSTRAINT fk_units_unit_profile_selection_revision FOREIGN KEY
            (organization_id, project_id, classification, profile_id, profile_revision_id)
            REFERENCES units.unit_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_units_unit_profile_selection_semantics CHECK
            (quantity_semantics ~ '^[a-z][a-z0-9_.-]{0,159}$'),
          CONSTRAINT ck_units_unit_profile_selection_dimension CHECK
            (dimension IN ('force_per_area','length','time','force','mass',
                           'mass_per_volume','temperature','strain')),
          CONSTRAINT ck_units_unit_profile_selection_input CHECK (
            (dimension = 'force_per_area' AND input_unit_id IN ('Pa','kPa','MPa','GPa')) OR
            (dimension = 'length' AND input_unit_id IN ('m','cm','mm','um')) OR
            (dimension = 'time' AND input_unit_id IN ('s','ms','min','h')) OR
            (dimension = 'force' AND input_unit_id IN ('N','kN')) OR
            (dimension = 'mass' AND input_unit_id IN ('kg','g','mg')) OR
            (dimension = 'mass_per_volume' AND input_unit_id IN ('kg/m3','g/cm3')) OR
            (dimension = 'temperature' AND input_unit_id IN ('K','Cel')) OR
            (dimension = 'strain' AND input_unit_id IN ('1','%'))
          ),
          CONSTRAINT ck_units_unit_profile_selection_display CHECK (
            (dimension = 'force_per_area' AND display_unit_id IN ('Pa','kPa','MPa','GPa')) OR
            (dimension = 'length' AND display_unit_id IN ('m','cm','mm','um')) OR
            (dimension = 'time' AND display_unit_id IN ('s','ms','min','h')) OR
            (dimension = 'force' AND display_unit_id IN ('N','kN')) OR
            (dimension = 'mass' AND display_unit_id IN ('kg','g','mg')) OR
            (dimension = 'mass_per_volume' AND display_unit_id IN ('kg/m3','g/cm3')) OR
            (dimension = 'temperature' AND display_unit_id IN ('K','Cel')) OR
            (dimension = 'strain' AND display_unit_id IN ('1','%'))
          ),
          CONSTRAINT ck_units_unit_profile_selection_solver CHECK (
            solver_export_unit_id IS NULL OR
            (dimension = 'force_per_area' AND solver_export_unit_id IN ('Pa','kPa','MPa','GPa')) OR
            (dimension = 'length' AND solver_export_unit_id IN ('m','cm','mm','um')) OR
            (dimension = 'time' AND solver_export_unit_id IN ('s','ms','min','h')) OR
            (dimension = 'force' AND solver_export_unit_id IN ('N','kN')) OR
            (dimension = 'mass' AND solver_export_unit_id IN ('kg','g','mg')) OR
            (dimension = 'mass_per_volume' AND solver_export_unit_id IN ('kg/m3','g/cm3')) OR
            (dimension = 'temperature' AND solver_export_unit_id IN ('K','Cel')) OR
            (dimension = 'strain' AND solver_export_unit_id IN ('1','%'))
          ),
          CONSTRAINT ck_units_unit_profile_temperature_semantics CHECK (
            dimension <> 'temperature' OR quantity_semantics IN
              ('temperature.absolute','temperature.test','temperature.difference')
          )
        );

        ALTER TABLE processing.common_processing_output_revision
          ADD COLUMN unit_profile_id uuid,
          ADD COLUMN unit_profile_revision_id uuid,
          ADD COLUMN unit_profile_sha256 char(64),
          ADD CONSTRAINT ck_processing_output_unit_profile_pin CHECK (
            (unit_profile_id IS NULL AND unit_profile_revision_id IS NULL
             AND unit_profile_sha256 IS NULL) OR
            (unit_profile_id IS NOT NULL AND unit_profile_revision_id IS NOT NULL
             AND unit_profile_sha256 ~ '^[0-9a-f]{64}$')
          ),
          ADD CONSTRAINT fk_processing_output_unit_profile_exact FOREIGN KEY
            (organization_id, project_id, classification, unit_profile_id,
             unit_profile_revision_id, unit_profile_sha256)
            REFERENCES units.unit_profile_revision
            (organization_id, project_id, classification, aggregate_id, id, content_hash);

        CREATE TABLE processing.common_processing_output_unit_application (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          output_id uuid NOT NULL, output_revision_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          location varchar(255) NOT NULL,
          application_role varchar(32) NOT NULL
            CHECK (application_role IN ('input','display','solver_export')),
          quantity_semantics varchar(160) NOT NULL,
          dimension varchar(64) NOT NULL,
          unit_id varchar(64) NOT NULL,
          CONSTRAINT pk_processing_output_unit_application PRIMARY KEY
            (organization_id, project_id, output_revision_id, ordinal),
          CONSTRAINT uq_processing_output_unit_application_location UNIQUE
            (organization_id, project_id, output_revision_id, location, application_role),
          CONSTRAINT fk_processing_output_unit_application_revision FOREIGN KEY
            (organization_id, project_id, classification, output_id, output_revision_id)
            REFERENCES processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_output_unit_application_semantics CHECK
            (quantity_semantics ~ '^[a-z][a-z0-9_.-]{0,159}$'),
          CONSTRAINT ck_processing_output_unit_application_dimension CHECK
            (dimension IN ('force_per_area','length','time','force','mass',
                           'mass_per_volume','temperature','strain')),
          CONSTRAINT ck_processing_output_unit_application_unit CHECK (
            (dimension = 'force_per_area' AND unit_id IN ('Pa','kPa','MPa','GPa')) OR
            (dimension = 'length' AND unit_id IN ('m','cm','mm','um')) OR
            (dimension = 'time' AND unit_id IN ('s','ms','min','h')) OR
            (dimension = 'force' AND unit_id IN ('N','kN')) OR
            (dimension = 'mass' AND unit_id IN ('kg','g','mg')) OR
            (dimension = 'mass_per_volume' AND unit_id IN ('kg/m3','g/cm3')) OR
            (dimension = 'temperature' AND unit_id IN ('K','Cel')) OR
            (dimension = 'strain' AND unit_id IN ('1','%'))
          )
        );

        ALTER TABLE processing.metal_fit_run
          ADD COLUMN unit_profile_id uuid,
          ADD COLUMN unit_profile_revision_id uuid,
          ADD COLUMN unit_profile_sha256 char(64),
          ADD CONSTRAINT ck_processing_metal_fit_unit_profile_pin CHECK (
            (unit_profile_id IS NULL AND unit_profile_revision_id IS NULL
             AND unit_profile_sha256 IS NULL) OR
            (unit_profile_id IS NOT NULL AND unit_profile_revision_id IS NOT NULL
             AND unit_profile_sha256 ~ '^[0-9a-f]{64}$')
          ),
          ADD CONSTRAINT fk_processing_metal_fit_unit_profile_exact FOREIGN KEY
            (organization_id, project_id, classification, unit_profile_id,
             unit_profile_revision_id, unit_profile_sha256)
            REFERENCES units.unit_profile_revision
            (organization_id, project_id, classification, aggregate_id, id, content_hash);

        CREATE TABLE processing.metal_fit_run_unit_application (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          run_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          location varchar(255) NOT NULL,
          application_role varchar(32) NOT NULL
            CHECK (application_role IN ('input','display','solver_export')),
          quantity_semantics varchar(160) NOT NULL,
          dimension varchar(64) NOT NULL,
          unit_id varchar(64) NOT NULL,
          CONSTRAINT pk_processing_metal_fit_unit_application PRIMARY KEY
            (organization_id, project_id, run_id, ordinal),
          CONSTRAINT uq_processing_metal_fit_unit_application_location UNIQUE
            (organization_id, project_id, run_id, location, application_role),
          CONSTRAINT fk_processing_metal_fit_unit_application_run FOREIGN KEY
            (organization_id, project_id, classification, run_id)
            REFERENCES processing.metal_fit_run
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_metal_fit_unit_application_semantics CHECK
            (quantity_semantics ~ '^[a-z][a-z0-9_.-]{0,159}$'),
          CONSTRAINT ck_processing_metal_fit_unit_application_dimension CHECK
            (dimension IN ('force_per_area','length','time','force','mass',
                           'mass_per_volume','temperature','strain')),
          CONSTRAINT ck_processing_metal_fit_unit_application_unit CHECK (
            (dimension = 'force_per_area' AND unit_id IN ('Pa','kPa','MPa','GPa')) OR
            (dimension = 'length' AND unit_id IN ('m','cm','mm','um')) OR
            (dimension = 'time' AND unit_id IN ('s','ms','min','h')) OR
            (dimension = 'force' AND unit_id IN ('N','kN')) OR
            (dimension = 'mass' AND unit_id IN ('kg','g','mg')) OR
            (dimension = 'mass_per_volume' AND unit_id IN ('kg/m3','g/cm3')) OR
            (dimension = 'temperature' AND unit_id IN ('K','Cel')) OR
            (dimension = 'strain' AND unit_id IN ('1','%'))
          )
        );

        CREATE TABLE exporting.neutral_solver_card_unit_profile (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          solver_card_id uuid NOT NULL, solver_card_revision_id uuid NOT NULL,
          unit_profile_id uuid NOT NULL, unit_profile_revision_id uuid NOT NULL,
          unit_profile_sha256 char(64) NOT NULL
            CHECK (unit_profile_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT pk_exporting_neutral_card_unit_profile PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id),
          CONSTRAINT uq_exporting_neutral_card_unit_profile_scope UNIQUE
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id),
          CONSTRAINT fk_exporting_neutral_card_unit_profile_card FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            REFERENCES exporting.neutral_solver_card_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_exporting_neutral_card_unit_profile_exact FOREIGN KEY
            (organization_id, project_id, classification, unit_profile_id,
             unit_profile_revision_id, unit_profile_sha256)
            REFERENCES units.unit_profile_revision
            (organization_id, project_id, classification, aggregate_id, id, content_hash)
        );

        CREATE TABLE exporting.neutral_solver_card_unit_application (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          solver_card_id uuid NOT NULL, solver_card_revision_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          location varchar(255) NOT NULL,
          application_role varchar(32) NOT NULL CHECK (application_role = 'solver_export'),
          quantity_semantics varchar(160) NOT NULL,
          dimension varchar(64) NOT NULL,
          unit_id varchar(64) NOT NULL,
          CONSTRAINT pk_exporting_neutral_card_unit_application PRIMARY KEY
            (organization_id, project_id, solver_card_revision_id, ordinal),
          CONSTRAINT uq_exporting_neutral_card_unit_application_location UNIQUE
            (organization_id, project_id, solver_card_revision_id, location, application_role),
          CONSTRAINT fk_exporting_neutral_card_unit_application_profile FOREIGN KEY
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id)
            REFERENCES exporting.neutral_solver_card_unit_profile
            (organization_id, project_id, classification, solver_card_id,
             solver_card_revision_id),
          CONSTRAINT ck_exporting_neutral_card_unit_application_semantics CHECK
            (quantity_semantics ~ '^[a-z][a-z0-9_.-]{0,159}$'),
          CONSTRAINT ck_exporting_neutral_card_unit_application_kg_m_s CHECK (
            (dimension = 'force_per_area' AND unit_id = 'Pa') OR
            (dimension = 'length' AND unit_id = 'm') OR
            (dimension = 'time' AND unit_id = 's') OR
            (dimension = 'force' AND unit_id = 'N') OR
            (dimension = 'mass' AND unit_id = 'kg') OR
            (dimension = 'mass_per_volume' AND unit_id = 'kg/m3') OR
            (dimension = 'temperature' AND unit_id = 'K') OR
            (dimension = 'strain' AND unit_id = '1')
          )
        );

        ALTER TABLE exporting.solver_card_delivery_receipt
          ADD COLUMN unit_profile_id uuid,
          ADD COLUMN unit_profile_revision_id uuid,
          ADD COLUMN unit_profile_sha256 char(64),
          ADD CONSTRAINT uq_exporting_delivery_receipt_scope UNIQUE
            (organization_id, project_id, classification, receipt_id),
          ADD CONSTRAINT ck_exporting_delivery_unit_profile_pin CHECK (
            (unit_profile_id IS NULL AND unit_profile_revision_id IS NULL
             AND unit_profile_sha256 IS NULL) OR
            (unit_profile_id IS NOT NULL AND unit_profile_revision_id IS NOT NULL
             AND unit_profile_sha256 ~ '^[0-9a-f]{64}$')
          ),
          ADD CONSTRAINT fk_exporting_delivery_unit_profile_exact FOREIGN KEY
            (organization_id, project_id, classification, unit_profile_id,
             unit_profile_revision_id, unit_profile_sha256)
            REFERENCES units.unit_profile_revision
            (organization_id, project_id, classification, aggregate_id, id, content_hash);

        CREATE TABLE exporting.solver_card_delivery_unit_application (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, receipt_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          location varchar(255) NOT NULL,
          application_role varchar(32) NOT NULL CHECK (application_role = 'solver_export'),
          quantity_semantics varchar(160) NOT NULL,
          dimension varchar(64) NOT NULL, unit_id varchar(64) NOT NULL,
          CONSTRAINT pk_exporting_delivery_unit_application PRIMARY KEY
            (organization_id, project_id, receipt_id, ordinal),
          CONSTRAINT uq_exporting_delivery_unit_application_location UNIQUE
            (organization_id, project_id, receipt_id, location, application_role),
          CONSTRAINT fk_exporting_delivery_unit_application_receipt FOREIGN KEY
            (organization_id, project_id, classification, receipt_id)
            REFERENCES exporting.solver_card_delivery_receipt
            (organization_id, project_id, classification, receipt_id),
          CONSTRAINT ck_exporting_delivery_unit_application_semantics CHECK
            (quantity_semantics ~ '^[a-z][a-z0-9_.-]{0,159}$'),
          CONSTRAINT ck_exporting_delivery_unit_application_kg_m_s CHECK (
            (dimension = 'force_per_area' AND unit_id = 'Pa') OR
            (dimension = 'length' AND unit_id = 'm') OR
            (dimension = 'time' AND unit_id = 's') OR
            (dimension = 'force' AND unit_id = 'N') OR
            (dimension = 'mass' AND unit_id = 'kg') OR
            (dimension = 'mass_per_volume' AND unit_id = 'kg/m3') OR
            (dimension = 'temperature' AND unit_id = 'K') OR
            (dimension = 'strain' AND unit_id = '1')
          )
        );
        """
    )
    op.execute(
        "CREATE TRIGGER units_unit_profile_head_only BEFORE UPDATE OR DELETE "
        "ON units.unit_profile FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    for table in _TABLES[1:]:
        op.execute(
            f"CREATE TRIGGER units_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON units.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in _TABLES:
        _rls(table)
    op.execute(
        "CREATE TRIGGER processing_common_processing_output_unit_application_immutable "
        "BEFORE UPDATE OR DELETE ON processing.common_processing_output_unit_application "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    _processing_rls("common_processing_output_unit_application")
    op.execute(
        "CREATE TRIGGER processing_metal_fit_run_unit_application_immutable "
        "BEFORE UPDATE OR DELETE ON processing.metal_fit_run_unit_application "
        "FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
    )
    _processing_rls("metal_fit_run_unit_application")
    for table in (
        "neutral_solver_card_unit_profile",
        "neutral_solver_card_unit_application",
        "solver_card_delivery_unit_application",
    ):
        op.execute(
            f"CREATE TRIGGER exporting_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON exporting.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
        _exporting_rls(table)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM units.unit_profile) THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'issue #205 downgrade requires empty Unit Profile history';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        "ALTER TABLE units.unit_profile DROP CONSTRAINT fk_units_unit_profile_current"
    )
    op.execute("DROP TABLE exporting.solver_card_delivery_unit_application")
    op.execute(
        "ALTER TABLE exporting.solver_card_delivery_receipt "
        "DROP CONSTRAINT fk_exporting_delivery_unit_profile_exact, "
        "DROP CONSTRAINT ck_exporting_delivery_unit_profile_pin, "
        "DROP CONSTRAINT uq_exporting_delivery_receipt_scope, "
        "DROP COLUMN unit_profile_sha256, "
        "DROP COLUMN unit_profile_revision_id, "
        "DROP COLUMN unit_profile_id"
    )
    op.execute("DROP TABLE exporting.neutral_solver_card_unit_application")
    op.execute("DROP TABLE exporting.neutral_solver_card_unit_profile")
    op.execute("DROP TABLE processing.metal_fit_run_unit_application")
    op.execute(
        "ALTER TABLE processing.metal_fit_run "
        "DROP CONSTRAINT fk_processing_metal_fit_unit_profile_exact, "
        "DROP CONSTRAINT ck_processing_metal_fit_unit_profile_pin, "
        "DROP COLUMN unit_profile_sha256, "
        "DROP COLUMN unit_profile_revision_id, "
        "DROP COLUMN unit_profile_id"
    )
    op.execute("DROP TABLE processing.common_processing_output_unit_application")
    op.execute(
        "ALTER TABLE processing.common_processing_output_revision "
        "DROP CONSTRAINT fk_processing_output_unit_profile_exact, "
        "DROP CONSTRAINT ck_processing_output_unit_profile_pin, "
        "DROP COLUMN unit_profile_sha256, "
        "DROP COLUMN unit_profile_revision_id, "
        "DROP COLUMN unit_profile_id"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE units.{table}")
    op.execute("DROP SCHEMA units")

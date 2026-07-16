"""Add governed tabular Import Profiles, Runs, and Datasets.

Revision ID: 20260817_051_governed_import
Revises: 20260816_050_test_context

Traceability: T-41, FR-TST-001/002/003, FR-DAT-001/002/003, NFR-SEC-003/006.
"""

# ruff: noqa: E501 -- SQL constraint clauses remain aligned with their database objects.

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260817_051_governed_import"
down_revision: str | None = "20260816_050_test_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IDENTITIES = ("import_profile", "governed_dataset")
_IMMUTABLE = (
    "import_profile_revision",
    "import_profile_channel",
    "governed_dataset_revision",
    "governed_dataset_channel",
    "tabular_preview_report",
    "tabular_preview_column",
    "tabular_import_row_error",
)
_TABLES = (
    *_IDENTITIES,
    *_IMMUTABLE,
    "tabular_import_run",
)


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE datasets.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE datasets.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY datasets_{table}_select ON datasets.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'dataset.read'))"
    )
    op.execute(
        f"CREATE POLICY datasets_{table}_insert ON datasets.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'dataset.write'))"
    )
    op.execute(
        f"CREATE POLICY datasets_{table}_update ON datasets.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'dataset.write')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'dataset.write'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE datasets.import_profile (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_label varchar(160) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_import_profile PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_import_profile_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_datasets_import_profile_label UNIQUE
            (organization_id, project_id, classification, profile_label)
        );
        CREATE TABLE datasets.import_profile_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no > 0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          profile_label varchar(160) NOT NULL,
          data_schema varchar(64) NOT NULL CHECK (data_schema IN
            ('monotonic_tension','monotonic_compression','planar_tension','biaxial_tension',
             'simple_shear','shear_relaxation')),
          file_format varchar(16) NOT NULL CHECK (file_format IN ('csv','tsv','xlsx')),
          sheet_name varchar(255), header_row integer NOT NULL CHECK (header_row BETWEEN 1 AND 100),
          encoding varchar(32) NOT NULL CHECK (encoding IN ('utf-8','utf-8-sig','binary')),
          delimiter varchar(1), decimal_separator varchar(1) NOT NULL
            CHECK (decimal_separator IN ('.',',')),
          initial_gauge_length_m double precision CHECK (initial_gauge_length_m > 0),
          initial_cross_section_area_m2 double precision CHECK (initial_cross_section_area_m2 > 0),
          approval_kind varchar(32) NOT NULL CHECK (approval_kind='human_confirmed'),
          CONSTRAINT pk_datasets_import_profile_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_import_profile_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_import_profile_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_datasets_import_profile_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            datasets.import_profile (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_import_profile_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            datasets.import_profile_revision (organization_id, project_id, id),
          CONSTRAINT ck_datasets_import_profile_format CHECK (
            (file_format='xlsx' AND sheet_name IS NOT NULL AND encoding='binary' AND delimiter IS NULL)
            OR (file_format='csv' AND sheet_name IS NULL AND encoding IN ('utf-8','utf-8-sig')
                AND delimiter IN (',',';') AND delimiter<>decimal_separator)
            OR (file_format='tsv' AND sheet_name IS NULL AND encoding IN ('utf-8','utf-8-sig')
                AND delimiter=E'\\t' AND decimal_separator<>E'\\t'))
        );
        ALTER TABLE datasets.import_profile ADD CONSTRAINT fk_datasets_import_profile_current
          FOREIGN KEY (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES datasets.import_profile_revision
            (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_import_profile_schema
          ON datasets.import_profile_revision (organization_id, project_id, data_schema, file_format);

        CREATE TABLE datasets.import_profile_channel (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, import_profile_id uuid NOT NULL,
          import_profile_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal IN (0,1)),
          source_column varchar(255) NOT NULL, source_quantity varchar(64) NOT NULL CHECK
            (source_quantity IN ('engineering_strain','engineering_stress','shear_strain',
             'shear_stress','time','shear_modulus','displacement','force')),
          original_unit varchar(32) NOT NULL, normalized_quantity varchar(64) NOT NULL,
          normalized_unit varchar(32) NOT NULL, axis_role varchar(32) NOT NULL
            CHECK (axis_role IN ('independent','dependent')),
          CONSTRAINT pk_datasets_import_profile_channel PRIMARY KEY
            (organization_id, project_id, import_profile_revision_id, ordinal),
          CONSTRAINT uq_datasets_import_profile_source_column UNIQUE
            (organization_id, project_id, import_profile_revision_id, source_column),
          CONSTRAINT fk_datasets_import_profile_channel_revision FOREIGN KEY
            (organization_id, project_id, classification, import_profile_id,
             import_profile_revision_id) REFERENCES datasets.import_profile_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );

        CREATE TABLE datasets.tabular_preview_report (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL, raw_sha256 char(64) NOT NULL
            CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'), file_format varchar(16) NOT NULL
            CHECK (file_format IN ('csv','tsv','xlsx')), selected_sheet_name varchar(255),
          header_row integer NOT NULL CHECK (header_row BETWEEN 1 AND 100),
          encoding varchar(32) NOT NULL, delimiter varchar(1), decimal_separator varchar(1) NOT NULL,
          status varchar(32) NOT NULL CHECK (status='needs_input'),
          report_sha256 char(64) NOT NULL CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_datasets_tabular_preview PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_tabular_preview_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_tabular_preview_raw FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id) REFERENCES artifact.raw_asset
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_tabular_preview_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id) REFERENCES artifact.artifact
            (organization_id, project_id, classification, id)
        );
        CREATE INDEX ix_datasets_tabular_preview_raw
          ON datasets.tabular_preview_report (organization_id, project_id, raw_asset_id, created_at DESC);
        CREATE TABLE datasets.tabular_preview_column (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, preview_report_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 511),
          column_name varchar(255) NOT NULL,
          CONSTRAINT pk_datasets_tabular_preview_column PRIMARY KEY
            (organization_id, project_id, preview_report_id, ordinal),
          CONSTRAINT uq_datasets_tabular_preview_column_name UNIQUE
            (organization_id, project_id, preview_report_id, column_name),
          CONSTRAINT fk_datasets_tabular_preview_column_report FOREIGN KEY
            (organization_id, project_id, classification, preview_report_id) REFERENCES
            datasets.tabular_preview_report (organization_id, project_id, classification, id)
        );

        CREATE TABLE datasets.governed_dataset (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, test_run_id uuid NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_governed_dataset PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_governed_dataset_scope UNIQUE
            (organization_id, project_id, classification, id)
        );
        CREATE TABLE datasets.governed_dataset_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no>0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          test_run_id uuid NOT NULL, test_run_revision_id uuid NOT NULL,
          raw_asset_id uuid NOT NULL, raw_artifact_id uuid NOT NULL,
          import_profile_id uuid NOT NULL, import_profile_revision_id uuid NOT NULL,
          representation varchar(32) NOT NULL CHECK (representation IN ('raw','normalized')),
          data_schema varchar(64) NOT NULL, data_artifact_id uuid NOT NULL,
          data_sha256 char(64) NOT NULL CHECK (data_sha256 ~ '^[0-9a-f]{64}$'),
          source_dataset_revision_id uuid, row_count integer NOT NULL CHECK (row_count BETWEEN 2 AND 100000),
          CONSTRAINT pk_datasets_governed_dataset_revision PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_datasets_governed_dataset_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_governed_dataset_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_datasets_governed_dataset_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            datasets.governed_dataset (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_governed_dataset_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            datasets.governed_dataset_revision (organization_id, project_id, id),
          CONSTRAINT fk_datasets_governed_dataset_test_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_datasets_governed_dataset_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id) REFERENCES artifact.raw_asset
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_governed_dataset_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id) REFERENCES artifact.artifact
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_governed_dataset_data_artifact FOREIGN KEY
            (organization_id, project_id, classification, data_artifact_id) REFERENCES artifact.artifact
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_governed_dataset_profile FOREIGN KEY
            (organization_id, project_id, classification, import_profile_id,
             import_profile_revision_id) REFERENCES datasets.import_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_datasets_governed_dataset_source FOREIGN KEY
            (organization_id, project_id, source_dataset_revision_id) REFERENCES
            datasets.governed_dataset_revision (organization_id, project_id, id),
          CONSTRAINT ck_datasets_governed_dataset_representation CHECK
            ((representation='raw' AND source_dataset_revision_id IS NULL
              AND data_artifact_id=raw_artifact_id)
             OR (representation='normalized' AND source_dataset_revision_id IS NOT NULL
                 AND data_artifact_id<>raw_artifact_id))
        );
        ALTER TABLE datasets.governed_dataset ADD CONSTRAINT fk_datasets_governed_dataset_current
          FOREIGN KEY (organization_id, project_id, classification, id, current_revision_id)
          REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_governed_dataset_test_run
          ON datasets.governed_dataset_revision
            (organization_id, project_id, test_run_id, representation);
        CREATE TABLE datasets.governed_dataset_channel (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, dataset_id uuid NOT NULL,
          dataset_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal IN (0,1)),
          source_column varchar(255) NOT NULL, source_quantity varchar(64) NOT NULL,
          original_unit varchar(32) NOT NULL, normalized_quantity varchar(64) NOT NULL,
          normalized_unit varchar(32) NOT NULL, axis_role varchar(32) NOT NULL,
          CONSTRAINT pk_datasets_governed_dataset_channel PRIMARY KEY
            (organization_id, project_id, dataset_revision_id, ordinal),
          CONSTRAINT fk_datasets_governed_dataset_channel_revision FOREIGN KEY
            (organization_id, project_id, classification, dataset_id, dataset_revision_id)
            REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );

        CREATE TABLE datasets.tabular_import_run (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, test_run_id uuid NOT NULL,
          test_run_revision_id uuid NOT NULL, raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL, import_profile_id uuid NOT NULL,
          import_profile_revision_id uuid NOT NULL, profile_sha256 char(64) NOT NULL,
          importer_id varchar(255) NOT NULL, importer_version varchar(64) NOT NULL,
          status varchar(32) NOT NULL CHECK (status IN ('executing','succeeded','failed')),
          started_at timestamptz NOT NULL, finished_at timestamptz,
          started_by uuid NOT NULL, request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          raw_dataset_id uuid, raw_dataset_revision_id uuid,
          normalized_dataset_id uuid, normalized_dataset_revision_id uuid,
          row_count integer CHECK (row_count BETWEEN 2 AND 100000),
          failure_code varchar(100), failure_detail text,
          CONSTRAINT pk_datasets_tabular_import_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_tabular_import_run_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_tabular_import_run_test FOREIGN KEY
            (organization_id, project_id, classification, test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_datasets_tabular_import_run_profile FOREIGN KEY
            (organization_id, project_id, classification, import_profile_id,
             import_profile_revision_id) REFERENCES datasets.import_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_datasets_tabular_import_run_raw FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id) REFERENCES artifact.raw_asset
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_tabular_import_run_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id) REFERENCES artifact.artifact
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_tabular_import_run_raw_output FOREIGN KEY
            (organization_id, project_id, classification, raw_dataset_id, raw_dataset_revision_id)
            REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_datasets_tabular_import_run_normalized_output FOREIGN KEY
            (organization_id, project_id, classification, normalized_dataset_id,
             normalized_dataset_revision_id) REFERENCES datasets.governed_dataset_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_datasets_tabular_import_run_terminal CHECK
            ((status='executing' AND finished_at IS NULL AND raw_dataset_id IS NULL
              AND normalized_dataset_id IS NULL AND row_count IS NULL
              AND failure_code IS NULL AND failure_detail IS NULL)
             OR (status='succeeded' AND finished_at IS NOT NULL AND raw_dataset_id IS NOT NULL
                 AND raw_dataset_revision_id IS NOT NULL AND normalized_dataset_id IS NOT NULL
                 AND normalized_dataset_revision_id IS NOT NULL AND row_count IS NOT NULL
                 AND failure_code IS NULL AND failure_detail IS NULL)
             OR (status='failed' AND finished_at IS NOT NULL AND raw_dataset_id IS NULL
                 AND normalized_dataset_id IS NULL AND row_count IS NULL
                 AND failure_code IS NOT NULL AND failure_detail IS NOT NULL))
        );
        CREATE INDEX ix_datasets_tabular_import_run_source
          ON datasets.tabular_import_run
            (organization_id, project_id, raw_asset_id, started_at DESC);
        CREATE TABLE datasets.tabular_import_row_error (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, import_run_id uuid NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 99), row_number integer,
          error_code varchar(100) NOT NULL, error_detail text NOT NULL,
          CONSTRAINT pk_datasets_tabular_import_row_error PRIMARY KEY
            (organization_id, project_id, import_run_id, ordinal),
          CONSTRAINT fk_datasets_tabular_import_row_error_run FOREIGN KEY
            (organization_id, project_id, classification, import_run_id) REFERENCES
            datasets.tabular_import_run (organization_id, project_id, classification, id)
        );

        CREATE FUNCTION datasets.guard_tabular_import_run_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' OR OLD.status<>'executing' THEN
            RAISE EXCEPTION 'terminal tabular Import Runs are immutable';
          END IF;
          IF NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id OR
             NEW.project_id<>OLD.project_id OR NEW.classification<>OLD.classification OR
             NEW.test_run_id<>OLD.test_run_id OR NEW.test_run_revision_id<>OLD.test_run_revision_id OR
             NEW.raw_asset_id<>OLD.raw_asset_id OR NEW.raw_artifact_id<>OLD.raw_artifact_id OR
             NEW.import_profile_id<>OLD.import_profile_id OR
             NEW.import_profile_revision_id<>OLD.import_profile_revision_id OR
             NEW.profile_sha256<>OLD.profile_sha256 OR NEW.importer_id<>OLD.importer_id OR
             NEW.importer_version<>OLD.importer_version OR NEW.started_at<>OLD.started_at OR
             NEW.started_by<>OLD.started_by OR NEW.request_id<>OLD.request_id OR
             NEW.trace_id<>OLD.trace_id OR NEW.status='executing' THEN
            RAISE EXCEPTION 'tabular Import Run immutable inputs cannot change';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER datasets_tabular_import_run_guard BEFORE UPDATE OR DELETE
          ON datasets.tabular_import_run FOR EACH ROW
          EXECUTE FUNCTION datasets.guard_tabular_import_run_mutation();
        """
    )
    for identity in _IDENTITIES:
        op.execute(
            f"CREATE TRIGGER datasets_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON datasets.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for table in _IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER datasets_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON datasets.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in _TABLES:
        _rls(table)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS datasets.guard_tabular_import_run_mutation() CASCADE")
    op.execute(
        "ALTER TABLE datasets.governed_dataset DROP CONSTRAINT fk_datasets_governed_dataset_current"
    )
    op.execute(
        "ALTER TABLE datasets.import_profile DROP CONSTRAINT fk_datasets_import_profile_current"
    )
    for table in (
        "tabular_import_row_error",
        "tabular_import_run",
        "governed_dataset_channel",
        "governed_dataset_revision",
        "governed_dataset",
        "tabular_preview_column",
        "tabular_preview_report",
        "import_profile_channel",
        "import_profile_revision",
        "import_profile",
    ):
        op.execute(f"DROP TABLE datasets.{table}")

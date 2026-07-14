"""Add immutable reference import detection, mapping, and orchestration records.

Revision ID: 20260718_020_t11
Revises: 20260717_019_t21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260718_020_t11"
down_revision: str | None = "20260717_019_t21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_IMPORTER_ID = "urn:cmp:testing:synthetic-csv-header-importer:1.0.0"
_IMPORTER_VERSION = "1.0.0"
_MAPPING_SCHEMA = "urn:cmp:testing:reference-import-mapping:1.0.0"
_IMPORT_KIND = "reference_uniaxial_tensile_csv"
_EXECUTION_MODE = "reference_inline"


def _secure(schema: str, table: str, read_permission: str, write_permission: str) -> None:
    for operation, predicate, permission in (
        ("select", "USING", read_permission),
        ("insert", "WITH CHECK", write_permission),
    ):
        op.execute(
            f"CREATE POLICY {schema}_{table}_{operation} ON {schema}.{table} "
            f"FOR {operation.upper()} {predicate} (access_control.can_access_row("
            f"organization_id, project_id, classification, '{permission}'))"
        )
    op.execute(
        f"CREATE POLICY {schema}_{table}_update ON {schema}.{table} FOR UPDATE "
        "USING (access_control.can_access_row(organization_id, project_id, classification, "
        f"'{write_permission}')) WITH CHECK (access_control.can_access_row(organization_id, "
        f"project_id, classification, '{write_permission}'))"
    )


def _create_tables() -> None:
    op.execute(
        f"""
        CREATE TABLE testing.import_detection_report (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          raw_sha256 char(64) COLLATE "C" NOT NULL,
          importer_id varchar(255) NOT NULL,
          importer_version varchar(64) NOT NULL,
          status varchar(32) NOT NULL,
          header_columns varchar(255)[] NOT NULL,
          suggested_strain_column varchar(255) NULL,
          suggested_strain_unit varchar(16) NULL,
          strain_confidence varchar(16) NOT NULL,
          suggested_stress_column varchar(255) NULL,
          suggested_stress_unit varchar(16) NULL,
          stress_confidence varchar(16) NOT NULL,
          report_sha256 char(64) COLLATE "C" NOT NULL,
          reference_only boolean NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_testing_import_detection_report
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_import_detection_report_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_testing_import_detection_report_nonzero_ids CHECK (
            id <> {_ZERO} AND raw_asset_id <> {_ZERO} AND raw_artifact_id <> {_ZERO}
            AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_testing_import_detection_report_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_testing_import_detection_report_digest CHECK (
            raw_sha256 ~ '^[0-9a-f]{{64}}$' AND report_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_testing_import_detection_report_importer CHECK (
            importer_id = '{_IMPORTER_ID}' AND importer_version = '{_IMPORTER_VERSION}'),
          CONSTRAINT ck_testing_import_detection_report_status CHECK (status = 'needs_input'),
          CONSTRAINT ck_testing_import_detection_report_headers CHECK (
            cardinality(header_columns) BETWEEN 1 AND 512),
          CONSTRAINT ck_testing_import_detection_report_strain_suggestion CHECK (
            (strain_confidence = 'none' AND suggested_strain_column IS NULL
             AND suggested_strain_unit IS NULL) OR
            (strain_confidence = 'low' AND suggested_strain_column = ANY(header_columns)
             AND suggested_strain_unit IN ('1', '%'))),
          CONSTRAINT ck_testing_import_detection_report_stress_suggestion CHECK (
            (stress_confidence = 'none' AND suggested_stress_column IS NULL
             AND suggested_stress_unit IS NULL) OR
            (stress_confidence = 'low' AND suggested_stress_column = ANY(header_columns)
             AND suggested_stress_unit IN ('Pa', 'kPa', 'MPa', 'GPa'))),
          CONSTRAINT ck_testing_import_detection_report_reference CHECK (reference_only),
          CONSTRAINT ck_testing_import_detection_report_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_testing_import_detection_report_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id)
            REFERENCES artifact.raw_asset (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_detection_report_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_asset_id)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, source_raw_asset_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_detection_report_raw_digest FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_sha256)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, sha256)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE testing.import_mapping (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          mapping_label varchar(160) NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          importer_id varchar(255) NOT NULL,
          importer_version varchar(64) NOT NULL,
          current_revision_id uuid NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          updated_at timestamptz NOT NULL,
          CONSTRAINT pk_testing_import_mapping PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_import_mapping_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT uq_testing_import_mapping_source_label
            UNIQUE (organization_id, project_id, classification, raw_asset_id,
                    raw_artifact_id, mapping_label),
          CONSTRAINT uq_testing_import_mapping_identity_source
            UNIQUE (organization_id, project_id, classification, id, raw_asset_id,
                    raw_artifact_id, importer_id, importer_version),
          CONSTRAINT ck_testing_import_mapping_nonzero_ids CHECK (
            id <> {_ZERO} AND raw_asset_id <> {_ZERO} AND raw_artifact_id <> {_ZERO}
            AND current_revision_id <> {_ZERO} AND created_by <> {_ZERO}),
          CONSTRAINT ck_testing_import_mapping_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_testing_import_mapping_label CHECK (
            length(btrim(mapping_label)) BETWEEN 1 AND 160
            AND mapping_label = btrim(mapping_label)),
          CONSTRAINT ck_testing_import_mapping_importer CHECK (
            importer_id = '{_IMPORTER_ID}' AND importer_version = '{_IMPORTER_VERSION}'),
          CONSTRAINT fk_testing_import_mapping_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id)
            REFERENCES artifact.raw_asset (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_mapping_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_asset_id)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, source_raw_asset_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE testing.import_mapping_revision (
          id uuid NOT NULL,
          aggregate_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL,
          based_on_revision_id uuid NULL,
          schema_id varchar(255) NOT NULL,
          schema_version varchar(64) NOT NULL,
          content_hash char(64) COLLATE "C" NOT NULL,
          created_at timestamptz NOT NULL,
          created_by uuid NOT NULL,
          change_reason text NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          detection_report_id uuid NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          strain_column varchar(255) NOT NULL,
          stress_column varchar(255) NOT NULL,
          strain_original_unit varchar(16) NOT NULL,
          stress_original_unit varchar(16) NOT NULL,
          dataset_mapping_sha256 char(64) COLLATE "C" NOT NULL,
          importer_id varchar(255) NOT NULL,
          importer_version varchar(64) NOT NULL,
          approval_kind varchar(32) NOT NULL,
          reference_only boolean NOT NULL,
          CONSTRAINT pk_testing_import_mapping_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_testing_import_mapping_revision_scope_id
            UNIQUE (organization_id, project_id, aggregate_id, id),
          CONSTRAINT uq_testing_import_mapping_revision_scoped_ref
            UNIQUE (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_testing_import_mapping_revision_number
            UNIQUE (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT uq_testing_import_mapping_revision_classified_id
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_testing_import_mapping_revision_nonzero_ids CHECK (
            id <> {_ZERO} AND aggregate_id <> {_ZERO} AND detection_report_id <> {_ZERO}
            AND raw_asset_id <> {_ZERO} AND raw_artifact_id <> {_ZERO}
            AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_testing_import_mapping_revision_number CHECK (revision_no > 0),
          CONSTRAINT ck_testing_import_mapping_revision_base CHECK (
            (revision_no = 1 AND based_on_revision_id IS NULL)
            OR (revision_no > 1 AND based_on_revision_id IS NOT NULL)),
          CONSTRAINT ck_testing_import_mapping_revision_hash CHECK (
            content_hash ~ '^[0-9a-f]{{64}}$'
            AND dataset_mapping_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_testing_import_mapping_revision_schema CHECK (
            schema_id = '{_MAPPING_SCHEMA}' AND schema_version = '1.0.0'),
          CONSTRAINT ck_testing_import_mapping_revision_reason CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_testing_import_mapping_revision_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT ck_testing_import_mapping_revision_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_testing_import_mapping_revision_columns CHECK (
            length(btrim(strain_column)) BETWEEN 1 AND 255
            AND length(btrim(stress_column)) BETWEEN 1 AND 255
            AND strain_column <> stress_column),
          CONSTRAINT ck_testing_import_mapping_revision_units CHECK (
            strain_original_unit IN ('1', '%')
            AND stress_original_unit IN ('Pa', 'kPa', 'MPa', 'GPa')),
          CONSTRAINT ck_testing_import_mapping_revision_contract CHECK (
            importer_id = '{_IMPORTER_ID}' AND importer_version = '{_IMPORTER_VERSION}'
            AND approval_kind = 'human_confirmed' AND reference_only),
          CONSTRAINT fk_testing_import_mapping_revision_identity FOREIGN KEY
            (organization_id, project_id, aggregate_id)
            REFERENCES testing.import_mapping (organization_id, project_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_mapping_revision_identity_source FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id, raw_asset_id,
             raw_artifact_id, importer_id, importer_version)
            REFERENCES testing.import_mapping
              (organization_id, project_id, classification, id, raw_asset_id,
               raw_artifact_id, importer_id, importer_version)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_mapping_revision_detection FOREIGN KEY
            (organization_id, project_id, classification, detection_report_id)
            REFERENCES testing.import_detection_report
              (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_testing_import_mapping_revision_base FOREIGN KEY
            (organization_id, project_id, aggregate_id, based_on_revision_id)
            REFERENCES testing.import_mapping_revision
              (organization_id, project_id, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )
    op.execute(
        """
        ALTER TABLE testing.import_mapping
          ADD CONSTRAINT fk_testing_import_mapping_current_revision
          FOREIGN KEY (organization_id, project_id, id, current_revision_id)
          REFERENCES testing.import_mapping_revision
            (organization_id, project_id, aggregate_id, id)
          ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        """
    )
    op.execute(
        f"""
        CREATE TABLE processing.import_run (
          id uuid NOT NULL,
          organization_id uuid NOT NULL,
          project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          import_kind varchar(100) NOT NULL,
          execution_mode varchar(32) NOT NULL,
          test_run_id uuid NOT NULL,
          test_run_revision_id uuid NOT NULL,
          raw_asset_id uuid NOT NULL,
          raw_artifact_id uuid NOT NULL,
          import_mapping_id uuid NOT NULL,
          import_mapping_revision_id uuid NOT NULL,
          mapping_sha256 char(64) COLLATE "C" NOT NULL,
          importer_id varchar(255) NOT NULL,
          importer_version varchar(64) NOT NULL,
          status varchar(16) NOT NULL,
          output_dataset_id uuid NULL,
          output_dataset_revision_id uuid NULL,
          failure_code varchar(100) NULL,
          change_reason text NOT NULL,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NULL,
          created_by uuid NOT NULL,
          request_id uuid NOT NULL,
          trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_processing_import_run PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_import_run_scope_identity
            UNIQUE (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_import_run_nonzero_ids CHECK (
            id <> {_ZERO} AND test_run_id <> {_ZERO} AND test_run_revision_id <> {_ZERO}
            AND raw_asset_id <> {_ZERO} AND raw_artifact_id <> {_ZERO}
            AND import_mapping_id <> {_ZERO} AND import_mapping_revision_id <> {_ZERO}
            AND created_by <> {_ZERO} AND request_id <> {_ZERO}),
          CONSTRAINT ck_processing_import_run_classification CHECK (
            classification ~ '^[a-z][a-z0-9_.-]{{0,63}}$'),
          CONSTRAINT ck_processing_import_run_contract CHECK (
            import_kind = '{_IMPORT_KIND}' AND execution_mode = '{_EXECUTION_MODE}'
            AND importer_id = '{_IMPORTER_ID}' AND importer_version = '{_IMPORTER_VERSION}'),
          CONSTRAINT ck_processing_import_run_status CHECK (
            status IN ('executing', 'succeeded', 'failed')),
          CONSTRAINT ck_processing_import_run_mapping_digest CHECK (
            mapping_sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_processing_import_run_terminal_shape CHECK (
            (status = 'executing' AND ended_at IS NULL AND output_dataset_id IS NULL
             AND output_dataset_revision_id IS NULL AND failure_code IS NULL) OR
            (status = 'succeeded' AND ended_at IS NOT NULL AND output_dataset_id IS NOT NULL
             AND output_dataset_revision_id IS NOT NULL AND failure_code IS NULL) OR
            (status = 'failed' AND ended_at IS NOT NULL AND output_dataset_id IS NULL
             AND output_dataset_revision_id IS NULL
             AND length(btrim(failure_code)) BETWEEN 1 AND 100)),
          CONSTRAINT ck_processing_import_run_time CHECK (
            ended_at IS NULL OR ended_at >= started_at),
          CONSTRAINT ck_processing_import_run_reason CHECK (
            length(btrim(change_reason)) BETWEEN 1 AND 2000),
          CONSTRAINT ck_processing_import_run_trace CHECK (
            length(btrim(trace_id)) BETWEEN 1 AND 255),
          CONSTRAINT fk_processing_import_run_test_run FOREIGN KEY
            (organization_id, project_id, classification, test_run_id, test_run_revision_id)
            REFERENCES testing.test_run_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_import_run_raw_asset FOREIGN KEY
            (organization_id, project_id, classification, raw_asset_id)
            REFERENCES artifact.raw_asset (organization_id, project_id, classification, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_import_run_raw_artifact FOREIGN KEY
            (organization_id, project_id, classification, raw_artifact_id, raw_asset_id)
            REFERENCES artifact.artifact
              (organization_id, project_id, classification, id, source_raw_asset_id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_import_run_mapping FOREIGN KEY
            (organization_id, project_id, classification, import_mapping_id,
             import_mapping_revision_id)
            REFERENCES testing.import_mapping_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
          CONSTRAINT fk_processing_import_run_output_dataset FOREIGN KEY
            (organization_id, project_id, classification, output_dataset_id,
             output_dataset_revision_id)
            REFERENCES datasets.dataset_revision
              (organization_id, project_id, classification, aggregate_id, id)
            ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
        )
        """
    )


def _create_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION testing.guard_reference_import_mapping_revision_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          report testing.import_detection_report%ROWTYPE;
        BEGIN
          SELECT * INTO report
          FROM testing.import_detection_report
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.detection_report_id;
          IF NOT FOUND
             OR report.raw_asset_id <> NEW.raw_asset_id
             OR report.raw_artifact_id <> NEW.raw_artifact_id
             OR report.importer_id <> NEW.importer_id
             OR report.importer_version <> NEW.importer_version
             OR NEW.strain_column <> ALL(report.header_columns)
             OR NEW.stress_column <> ALL(report.header_columns) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Import Mapping revision must use its frozen Detection Report evidence';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION processing.guard_reference_import_run_insert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          mapping testing.import_mapping_revision%ROWTYPE;
          test_run_is_reference boolean;
          artifact_kind text;
          artifact_media_type text;
        BEGIN
          SELECT * INTO mapping
          FROM testing.import_mapping_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.import_mapping_id
            AND id = NEW.import_mapping_revision_id;
          IF NOT FOUND
             OR mapping.raw_asset_id <> NEW.raw_asset_id
             OR mapping.raw_artifact_id <> NEW.raw_artifact_id
             OR mapping.dataset_mapping_sha256 <> NEW.mapping_sha256
             OR mapping.importer_id <> NEW.importer_id
             OR mapping.importer_version <> NEW.importer_version
             OR NOT mapping.reference_only THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Import Run must use the exact approved Mapping revision snapshot';
          END IF;
          SELECT reference_only INTO test_run_is_reference
          FROM testing.test_run_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.test_run_id
            AND id = NEW.test_run_revision_id;
          IF test_run_is_reference IS DISTINCT FROM true THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference Import Run requires a reference Test Run revision';
          END IF;
          SELECT artifact_kind, media_type INTO artifact_kind, artifact_media_type
          FROM artifact.artifact
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND id = NEW.raw_artifact_id
            AND source_raw_asset_id = NEW.raw_asset_id;
          IF artifact_kind IS DISTINCT FROM 'raw'
             OR artifact_media_type IS DISTINCT FROM 'text/csv' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference Import Run requires a text/csv Raw Artifact';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION processing.guard_reference_import_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          output_representation text;
          output_test_run_id uuid;
          output_test_run_revision_id uuid;
          output_raw_asset_id uuid;
          output_raw_artifact_id uuid;
          output_mapping_sha256 text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Import Run rows are append-only and cannot be deleted';
          END IF;
          IF OLD.status <> 'executing' OR NEW.status NOT IN ('succeeded', 'failed') THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Import Run may transition only once from executing to a terminal state';
          END IF;
          IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.classification IS DISTINCT FROM OLD.classification
             OR NEW.import_kind IS DISTINCT FROM OLD.import_kind
             OR NEW.execution_mode IS DISTINCT FROM OLD.execution_mode
             OR NEW.test_run_id IS DISTINCT FROM OLD.test_run_id
             OR NEW.test_run_revision_id IS DISTINCT FROM OLD.test_run_revision_id
             OR NEW.raw_asset_id IS DISTINCT FROM OLD.raw_asset_id
             OR NEW.raw_artifact_id IS DISTINCT FROM OLD.raw_artifact_id
             OR NEW.import_mapping_id IS DISTINCT FROM OLD.import_mapping_id
             OR NEW.import_mapping_revision_id IS DISTINCT FROM OLD.import_mapping_revision_id
             OR NEW.mapping_sha256 IS DISTINCT FROM OLD.mapping_sha256
             OR NEW.importer_id IS DISTINCT FROM OLD.importer_id
             OR NEW.importer_version IS DISTINCT FROM OLD.importer_version
             OR NEW.change_reason IS DISTINCT FROM OLD.change_reason
             OR NEW.started_at IS DISTINCT FROM OLD.started_at
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.trace_id IS DISTINCT FROM OLD.trace_id THEN
            RAISE EXCEPTION USING ERRCODE = '55000',
              MESSAGE = 'Import Run input snapshot is immutable';
          END IF;
          IF NEW.status = 'succeeded' THEN
            SELECT representation, test_run_id, test_run_revision_id, raw_asset_id,
                   raw_artifact_id, mapping_sha256
            INTO output_representation, output_test_run_id, output_test_run_revision_id,
                 output_raw_asset_id, output_raw_artifact_id, output_mapping_sha256
            FROM datasets.dataset_revision
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND classification = NEW.classification
              AND aggregate_id = NEW.output_dataset_id
              AND id = NEW.output_dataset_revision_id;
            IF NOT FOUND
               OR output_representation <> 'normalized'
               OR output_test_run_id <> NEW.test_run_id
               OR output_test_run_revision_id <> NEW.test_run_revision_id
               OR output_raw_asset_id <> NEW.raw_asset_id
               OR output_raw_artifact_id <> NEW.raw_artifact_id
               OR output_mapping_sha256 <> NEW.mapping_sha256 THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'Import Run output must equal its normalized Dataset revision';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER testing_import_mapping_revision_insert_guard BEFORE INSERT "
        "ON testing.import_mapping_revision FOR EACH ROW "
        "EXECUTE FUNCTION testing.guard_reference_import_mapping_revision_insert()"
    )
    op.execute(
        "CREATE TRIGGER processing_import_run_insert_guard BEFORE INSERT "
        "ON processing.import_run FOR EACH ROW "
        "EXECUTE FUNCTION processing.guard_reference_import_run_insert()"
    )
    op.execute(
        "CREATE TRIGGER processing_import_run_transition_guard BEFORE UPDATE OR DELETE "
        "ON processing.import_run FOR EACH ROW "
        "EXECUTE FUNCTION processing.guard_reference_import_run_transition()"
    )


def upgrade() -> None:
    _create_tables()
    for schema, table, read_permission, write_permission in (
        ("testing", "import_detection_report", "testing.read", "testing.write"),
        ("testing", "import_mapping", "testing.read", "testing.write"),
        ("testing", "import_mapping_revision", "testing.read", "testing.write"),
        ("processing", "import_run", "processing.read", "processing.execute"),
    ):
        op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {schema}.{table} FORCE ROW LEVEL SECURITY")
        _secure(schema, table, read_permission, write_permission)
    op.execute(
        "CREATE TRIGGER testing_import_mapping_head_only BEFORE UPDATE OR DELETE "
        "ON testing.import_mapping FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    for table in ("import_detection_report", "import_mapping_revision"):
        op.execute(
            f"CREATE TRIGGER testing_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON testing.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    _create_guards()
    for name, schema, table, columns in (
        (
            "ix_testing_import_detection_report_raw",
            "testing",
            "import_detection_report",
            ["organization_id", "project_id", "classification", "raw_artifact_id"],
        ),
        (
            "ix_testing_import_mapping_raw",
            "testing",
            "import_mapping",
            ["organization_id", "project_id", "classification", "raw_artifact_id"],
        ),
        (
            "ix_testing_import_mapping_revision_detection",
            "testing",
            "import_mapping_revision",
            ["organization_id", "project_id", "classification", "detection_report_id"],
        ),
        (
            "ix_processing_import_run_test_run",
            "processing",
            "import_run",
            ["organization_id", "project_id", "classification", "test_run_revision_id"],
        ),
        (
            "ix_processing_import_run_mapping",
            "processing",
            "import_run",
            [
                "organization_id",
                "project_id",
                "classification",
                "import_mapping_revision_id",
            ],
        ),
    ):
        op.create_index(name, table, columns, schema=schema)


def downgrade() -> None:
    for trigger, table in (
        ("processing_import_run_transition_guard", "processing.import_run"),
        ("processing_import_run_insert_guard", "processing.import_run"),
        ("testing_import_mapping_revision_insert_guard", "testing.import_mapping_revision"),
        ("testing_import_mapping_revision_immutable", "testing.import_mapping_revision"),
        ("testing_import_detection_report_immutable", "testing.import_detection_report"),
        ("testing_import_mapping_head_only", "testing.import_mapping"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
    op.execute("DROP FUNCTION processing.guard_reference_import_run_transition()")
    op.execute("DROP FUNCTION processing.guard_reference_import_run_insert()")
    op.execute("DROP FUNCTION testing.guard_reference_import_mapping_revision_insert()")
    op.drop_table("import_run", schema="processing")
    op.drop_constraint(
        "fk_testing_import_mapping_current_revision",
        "import_mapping",
        schema="testing",
        type_="foreignkey",
    )
    op.drop_table("import_mapping_revision", schema="testing")
    op.drop_table("import_mapping", schema="testing")
    op.drop_table("import_detection_report", schema="testing")

"""Add immutable canonical Test Data JSON documents.

Revision ID: 20260828_062_test_json
Revises: 20260827_061_t51
"""

# ruff: noqa: E501 -- SQL constraint clauses remain aligned with their database objects.

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_062_test_json"
down_revision: str | None = "20260827_061_t51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "test_data_document",
    "test_data_document_revision",
    "test_data_condition",
    "test_data_channel",
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
        CREATE TABLE datasets.test_data_document (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, document_key varchar(200) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_datasets_test_data_document PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_test_data_document_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_datasets_test_data_document_key UNIQUE
            (organization_id, project_id, classification, document_key),
          CONSTRAINT ck_datasets_test_data_document_key CHECK
            (length(btrim(document_key)) BETWEEN 1 AND 200)
        );
        CREATE TABLE datasets.test_data_document_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no>0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          document_key varchar(200) NOT NULL, maker varchar(200) NOT NULL,
          grade varchar(200) NOT NULL, lot_batch varchar(200), test_date date NOT NULL,
          operator_name varchar(200) NOT NULL, laboratory varchar(200) NOT NULL,
          test_method varchar(300) NOT NULL, equipment_maker varchar(200),
          equipment_model varchar(200), specimen_key varchar(200) NOT NULL,
          specimen_description text, source_file_name varchar(255) NOT NULL,
          source_media_type varchar(255) NOT NULL, source_sha256 char(64) NOT NULL,
          canonical_artifact_id uuid NOT NULL, canonical_sha256 char(64) NOT NULL,
          normalized_artifact_id uuid NOT NULL, normalized_sha256 char(64) NOT NULL,
          point_count integer NOT NULL CHECK (point_count BETWEEN 2 AND 1000000),
          CONSTRAINT pk_datasets_test_data_document_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_datasets_test_data_document_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_datasets_test_data_document_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_datasets_test_data_document_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            datasets.test_data_document (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_test_data_document_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            datasets.test_data_document_revision (organization_id, project_id, id),
          CONSTRAINT fk_datasets_test_data_document_canonical_artifact FOREIGN KEY
            (organization_id, project_id, classification, canonical_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT fk_datasets_test_data_document_normalized_artifact FOREIGN KEY
            (organization_id, project_id, classification, normalized_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT ck_datasets_test_data_document_hashes CHECK
            (source_sha256 ~ '^[0-9a-f]{64}$' AND canonical_sha256 ~ '^[0-9a-f]{64}$'
             AND normalized_sha256 ~ '^[0-9a-f]{64}$')
        );
        ALTER TABLE datasets.test_data_document ADD CONSTRAINT
          fk_datasets_test_data_document_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          datasets.test_data_document_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_datasets_test_data_document_material
          ON datasets.test_data_document_revision
          (organization_id, project_id, maker, grade, test_date DESC);

        CREATE TABLE datasets.test_data_condition (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, document_id uuid NOT NULL,
          document_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          condition_key varchar(128) NOT NULL, quantity_semantics varchar(160) NOT NULL,
          original_value numeric NOT NULL, original_unit_string varchar(64) NOT NULL,
          normalized_value numeric NOT NULL, normalized_unit varchar(64) NOT NULL,
          CONSTRAINT pk_datasets_test_data_condition PRIMARY KEY
            (organization_id, project_id, document_revision_id, ordinal),
          CONSTRAINT uq_datasets_test_data_condition_key UNIQUE
            (organization_id, project_id, document_revision_id, condition_key),
          CONSTRAINT fk_datasets_test_data_condition_revision FOREIGN KEY
            (organization_id, project_id, classification, document_id, document_revision_id)
            REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );
        CREATE TABLE datasets.test_data_channel (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, document_id uuid NOT NULL,
          document_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 511),
          channel_key varchar(128) NOT NULL, channel_name varchar(200) NOT NULL,
          quantity_semantics varchar(160) NOT NULL,
          axis_role varchar(32) NOT NULL CHECK (axis_role IN ('independent','dependent','auxiliary')),
          original_unit_string varchar(64) NOT NULL, normalized_unit varchar(64) NOT NULL,
          normalization_scale numeric NOT NULL CHECK (normalization_scale<>0),
          normalization_offset numeric NOT NULL, point_count integer NOT NULL,
          missing_count integer NOT NULL CHECK (missing_count BETWEEN 0 AND point_count),
          CONSTRAINT pk_datasets_test_data_channel PRIMARY KEY
            (organization_id, project_id, document_revision_id, ordinal),
          CONSTRAINT uq_datasets_test_data_channel_key UNIQUE
            (organization_id, project_id, document_revision_id, channel_key),
          CONSTRAINT fk_datasets_test_data_channel_revision FOREIGN KEY
            (organization_id, project_id, classification, document_id, document_revision_id)
            REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );
        """
    )
    op.execute(
        "CREATE TRIGGER datasets_test_data_document_head_only BEFORE UPDATE OR DELETE "
        "ON datasets.test_data_document FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    for table in _TABLES[1:]:
        op.execute(
            f"CREATE TRIGGER datasets_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON datasets.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in _TABLES:
        _rls(table)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE datasets.test_data_document DROP CONSTRAINT "
        "fk_datasets_test_data_document_current"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE datasets.{table}")

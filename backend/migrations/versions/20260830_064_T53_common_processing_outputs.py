"""Add exact-input immutable common Processing Outputs.

Revision ID: 20260830_064_t53_output
Revises: 20260829_063_t53_map
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260830_064_t53_output"
down_revision: str | None = "20260829_063_t53_map"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "common_processing_output",
    "common_processing_output_revision",
    "common_processing_output_step",
)


def _rls(table: str) -> None:
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
    op.execute(
        f"CREATE POLICY processing_{table}_update ON processing.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'processing.execute')) WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'processing.execute'))"
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE processing.common_processing_output (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, label varchar(200) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_processing_common_output PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_common_output_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_common_output_label CHECK
            (length(btrim(label)) BETWEEN 1 AND 200)
        );
        CREATE TABLE processing.common_processing_output_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no=1), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          label varchar(200) NOT NULL, source_document_id uuid NOT NULL,
          source_document_revision_id uuid NOT NULL, source_document_sha256 char(64) NOT NULL,
          source_canonical_artifact_sha256 char(64) NOT NULL,
          mapping_profile_id uuid NOT NULL, mapping_profile_revision_id uuid NOT NULL,
          mapping_profile_sha256 char(64) NOT NULL, independent_quantity varchar(160) NOT NULL,
          step_count integer NOT NULL CHECK (step_count BETWEEN 1 AND 32),
          stage_count integer NOT NULL CHECK (stage_count=step_count+1),
          final_point_count integer NOT NULL CHECK (final_point_count BETWEEN 2 AND 100000),
          output_artifact_id uuid NOT NULL, output_sha256 char(64) NOT NULL,
          CONSTRAINT pk_processing_common_output_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_common_output_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_processing_common_output_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_processing_common_output_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            processing.common_processing_output (organization_id, project_id, classification, id),
          CONSTRAINT fk_processing_common_output_source_exact FOREIGN KEY
            (organization_id, project_id, classification, source_document_id,
             source_document_revision_id) REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_processing_common_output_profile_exact FOREIGN KEY
            (organization_id, project_id, classification, mapping_profile_id,
             mapping_profile_revision_id) REFERENCES processing.mapping_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_processing_common_output_artifact FOREIGN KEY
            (organization_id, project_id, classification, output_artifact_id) REFERENCES
            artifact.artifact (organization_id, project_id, classification, id),
          CONSTRAINT ck_processing_common_output_hashes CHECK
            (source_document_sha256 ~ '^[0-9a-f]{64}$' AND
             source_canonical_artifact_sha256 ~ '^[0-9a-f]{64}$' AND
             mapping_profile_sha256 ~ '^[0-9a-f]{64}$' AND
             output_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT ck_processing_common_output_no_base CHECK (based_on_revision_id IS NULL)
        );
        ALTER TABLE processing.common_processing_output ADD CONSTRAINT
          fk_processing_common_output_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          processing.common_processing_output_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_processing_common_output_source ON
          processing.common_processing_output_revision
          (organization_id, project_id, source_document_revision_id, created_at DESC);
        CREATE INDEX ix_processing_common_output_profile ON
          processing.common_processing_output_revision
          (organization_id, project_id, mapping_profile_revision_id, created_at DESC);

        CREATE TABLE processing.common_processing_output_step (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, output_id uuid NOT NULL,
          output_revision_id uuid NOT NULL, ordinal integer NOT NULL
            CHECK (ordinal BETWEEN 0 AND 31),
          method_id varchar(160) NOT NULL, method_version varchar(64) NOT NULL,
          options_sha256 char(64) NOT NULL CHECK (options_sha256 ~ '^[0-9a-f]{64}$'),
          options jsonb NOT NULL CHECK (jsonb_typeof(options)='object'),
          CONSTRAINT pk_processing_common_output_step PRIMARY KEY
            (organization_id, project_id, output_revision_id, ordinal),
          CONSTRAINT fk_processing_common_output_step_revision FOREIGN KEY
            (organization_id, project_id, classification, output_id, output_revision_id)
            REFERENCES processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );
        """
    )
    op.execute(
        "CREATE TRIGGER processing_common_output_head_only BEFORE UPDATE OR DELETE "
        "ON processing.common_processing_output FOR EACH ROW "
        "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
    )
    for table in _TABLES[1:]:
        op.execute(
            f"CREATE TRIGGER processing_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON processing.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in _TABLES:
        _rls(table)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE processing.common_processing_output DROP CONSTRAINT "
        "fk_processing_common_output_current"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE processing.{table}")

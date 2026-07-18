"""Add exact-selection Processing Batch members and append-only attempts.

Revision ID: 20260901_066_t54_batch
Revises: 20260831_065_t54_recipe
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260901_066_t54_batch"
down_revision: str | None = "20260831_065_t54_recipe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "common_processing_batch",
    "common_processing_batch_member",
    "common_processing_batch_attempt",
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


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE processing.common_processing_batch (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, label varchar(200) NOT NULL,
          recipe_id uuid NOT NULL, recipe_revision_id uuid NOT NULL,
          recipe_sha256 char(64) NOT NULL CHECK (recipe_sha256 ~ '^[0-9a-f]{64}$'),
          member_count integer NOT NULL CHECK (member_count BETWEEN 1 AND 500),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          CONSTRAINT pk_processing_common_batch PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_common_batch_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_processing_common_batch_recipe_exact FOREIGN KEY
            (organization_id, project_id, classification, recipe_id, recipe_revision_id)
            REFERENCES processing.common_processing_recipe_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_common_batch_label CHECK
            (length(btrim(label)) BETWEEN 1 AND 200)
        );
        CREATE INDEX ix_processing_common_batch_recipe ON
          processing.common_processing_batch
          (organization_id, project_id, recipe_revision_id, created_at DESC);

        CREATE TABLE processing.common_processing_batch_member (
          id uuid NOT NULL, batch_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 499),
          source_document_id uuid NOT NULL, source_document_revision_id uuid NOT NULL,
          source_document_sha256 char(64) NOT NULL
            CHECK (source_document_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT pk_processing_common_batch_member PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_common_batch_member_scope UNIQUE
            (organization_id, project_id, classification, batch_id, id),
          CONSTRAINT uq_processing_common_batch_member_ordinal UNIQUE
            (organization_id, project_id, batch_id, ordinal),
          CONSTRAINT uq_processing_common_batch_member_source UNIQUE
            (organization_id, project_id, batch_id, source_document_id,
             source_document_revision_id),
          CONSTRAINT fk_processing_common_batch_member_batch FOREIGN KEY
            (organization_id, project_id, classification, batch_id) REFERENCES
            processing.common_processing_batch
            (organization_id, project_id, classification, id),
          CONSTRAINT fk_processing_common_batch_member_source_exact FOREIGN KEY
            (organization_id, project_id, classification, source_document_id,
             source_document_revision_id) REFERENCES datasets.test_data_document_revision
            (organization_id, project_id, classification, aggregate_id, id)
        );
        CREATE INDEX ix_processing_common_batch_member_source ON
          processing.common_processing_batch_member
          (organization_id, project_id, source_document_revision_id);

        CREATE TABLE processing.common_processing_batch_attempt (
          id uuid NOT NULL, batch_id uuid NOT NULL, member_id uuid NOT NULL,
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL,
          attempt_no integer NOT NULL CHECK (attempt_no >= 1),
          status varchar(32) NOT NULL CHECK (status IN ('succeeded','failed')),
          output_id uuid, output_revision_id uuid,
          error_code varchar(160), error_detail text,
          started_at timestamptz NOT NULL, completed_at timestamptz NOT NULL,
          CONSTRAINT pk_processing_common_batch_attempt PRIMARY KEY
            (organization_id, project_id, id),
          CONSTRAINT uq_processing_common_batch_attempt_no UNIQUE
            (organization_id, project_id, member_id, attempt_no),
          CONSTRAINT fk_processing_common_batch_attempt_member FOREIGN KEY
            (organization_id, project_id, classification, batch_id, member_id) REFERENCES
            processing.common_processing_batch_member
            (organization_id, project_id, classification, batch_id, id),
          CONSTRAINT fk_processing_common_batch_attempt_output_exact FOREIGN KEY
            (organization_id, project_id, classification, output_id, output_revision_id)
            REFERENCES processing.common_processing_output_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_common_batch_attempt_result CHECK (
            (status='succeeded' AND output_id IS NOT NULL AND output_revision_id IS NOT NULL
              AND error_code IS NULL AND error_detail IS NULL)
            OR
            (status='failed' AND output_id IS NULL AND output_revision_id IS NULL
              AND error_code IS NOT NULL AND length(btrim(error_code)) BETWEEN 1 AND 160
              AND error_detail IS NOT NULL AND length(btrim(error_detail)) BETWEEN 1 AND 2000)
          ),
          CONSTRAINT ck_processing_common_batch_attempt_time CHECK
            (completed_at >= started_at)
        );
        CREATE INDEX ix_processing_common_batch_attempt_latest ON
          processing.common_processing_batch_attempt
          (organization_id, project_id, batch_id, member_id, attempt_no DESC);
        """
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER processing_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON processing.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
        _rls(table)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE processing.{table}")

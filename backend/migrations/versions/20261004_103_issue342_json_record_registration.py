"""Issue #342 Task 1B exact-format JSON Record registration persistence.

Revision ID: 20261004_103_issue342_json
Revises: 20261003_102_issue246_units

The preview token is a durable command envelope.  It is the only mutable row in this
slice (open -> committed); package/component/provenance and batch-state event rows are
append-only evidence.  A batch's source state is derived from its latest state event.
No raw JSON is promoted to a business JSONB authority.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261004_103_issue342_json"
down_revision: str | None = "20261003_102_issue246_units"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_uuid = postgresql.UUID(as_uuid=True)


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY catalog_{table}_read ON catalog.{table} FOR SELECT USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'catalog.read'))"
    )
    op.execute(
        f"CREATE POLICY catalog_{table}_write ON catalog.{table} FOR INSERT WITH CHECK "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'catalog.write'))"
    )
    op.execute(
        f"CREATE POLICY catalog_{table}_update ON catalog.{table} FOR UPDATE USING "
        "(access_control.can_access_row(organization_id, project_id, classification, "
        "'catalog.write')) WITH CHECK (access_control.can_access_row(organization_id, project_id, "
        "classification, 'catalog.write'))"
    )


def upgrade() -> None:
    op.create_table(
        "json_record_registration_preview",
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("principal_id", _uuid, nullable=False),
        sa.Column("token_digest", sa.CHAR(64), nullable=False),
        sa.Column("format_id", _uuid, nullable=False),
        sa.Column("format_revision_id", _uuid, nullable=False),
        sa.Column("application_id", _uuid, nullable=False),
        sa.Column("application_revision_id", _uuid, nullable=False),
        sa.Column("schema_artifact_id", _uuid, nullable=False),
        sa.Column("schema_sha256", sa.CHAR(64), nullable=False),
        sa.Column("table_id", _uuid, nullable=False),
        sa.Column("table_revision_id", _uuid, nullable=False),
        sa.Column("package_artifact_id", _uuid, nullable=True),
        sa.Column("package_sha256", sa.CHAR(64), nullable=False),
        sa.Column("package_media_type", sa.String(64), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reference_pins", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("domain_bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="open"),
        sa.Column("batch_id", _uuid, nullable=True),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_json_registration_preview"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "token_digest",
            name="uq_catalog_json_registration_preview_token",
        ),
        sa.CheckConstraint(
            "state IN ('open', 'committed')",
            name="ck_catalog_json_registration_preview_state",
        ),
        sa.CheckConstraint(
            "package_media_type IN ('application/json', 'application/zip')",
            name="ck_catalog_json_registration_preview_media_type",
        ),
        sa.CheckConstraint(
            "package_sha256 ~ '^[0-9a-f]{64}$' AND schema_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_json_registration_preview_digests",
        ),
        schema="catalog",
    )
    op.create_table(
        "json_record_registration_batch",
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("preview_id", _uuid, nullable=False),
        sa.Column("token_digest", sa.CHAR(64), nullable=False),
        sa.Column("format_id", _uuid, nullable=False),
        sa.Column("format_revision_id", _uuid, nullable=False),
        sa.Column("package_artifact_id", _uuid, nullable=True),
        sa.Column("package_sha256", sa.CHAR(64), nullable=False),
        sa.Column(
            "source_state", sa.String(32), nullable=False, server_default="ready"
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("request_id", _uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_json_registration_batch"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "token_digest",
            name="uq_catalog_json_registration_batch_token",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_json_registration_batch_classified_reference",
        ),
        sa.CheckConstraint(
            "source_state IN ('artifacts_pending', 'ready', 'reconciliation_failed')",
            name="ck_catalog_json_registration_batch_source_state",
        ),
        sa.CheckConstraint(
            "package_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_json_registration_batch_digest",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "preview_id"],
            [
                "catalog.json_record_registration_preview.organization_id",
                "catalog.json_record_registration_preview.project_id",
                "catalog.json_record_registration_preview.id",
            ],
            name="fk_catalog_json_registration_batch_preview",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_table(
        "json_record_registration_curve_artifact",
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("batch_id", _uuid, nullable=False),
        sa.Column("component_ordinal", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("json_pointer", sa.String(2000), nullable=False),
        sa.Column("artifact_id", _uuid, nullable=False),
        sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "batch_id",
            "component_ordinal",
            "json_pointer",
            name="pk_catalog_json_registration_curve_artifact",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "batch_id",
            "original_filename",
            "json_pointer",
            name="uq_catalog_json_registration_curve_artifact_component",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "artifact_id",
            name="uq_catalog_json_registration_curve_artifact_artifact",
        ),
        sa.CheckConstraint(
            "component_ordinal BETWEEN 1 AND 100 AND length(btrim(original_filename)) > 0 "
            "AND original_filename = btrim(original_filename) "
            "AND left(json_pointer, 1) = '/'",
            name="ck_catalog_json_registration_curve_artifact_component",
        ),
        sa.CheckConstraint(
            "artifact_size_bytes > 0 AND artifact_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_json_registration_curve_artifact_digest",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "batch_id"],
            [
                "catalog.json_record_registration_batch.organization_id",
                "catalog.json_record_registration_batch.project_id",
                "catalog.json_record_registration_batch.classification",
                "catalog.json_record_registration_batch.id",
            ],
            name="fk_catalog_json_registration_curve_artifact_batch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_catalog_json_registration_curve_artifact_artifact",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_table(
        "record_json_source_provenance",
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("batch_id", _uuid, nullable=False),
        sa.Column("record_id", _uuid, nullable=False),
        sa.Column("record_revision_id", _uuid, nullable=False),
        sa.Column("component_ordinal", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("source_artifact_id", _uuid, nullable=True),
        sa.Column("source_length_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_sha256", sa.CHAR(64), nullable=False),
        sa.Column("package_artifact_id", _uuid, nullable=True),
        sa.Column("package_component_path", sa.String(1000), nullable=True),
        sa.Column("package_sha256", sa.CHAR(64), nullable=False),
        sa.Column("format_id", _uuid, nullable=False),
        sa.Column("format_revision_id", _uuid, nullable=False),
        sa.Column("application_id", _uuid, nullable=False),
        sa.Column("application_revision_id", _uuid, nullable=False),
        sa.Column("schema_artifact_id", _uuid, nullable=False),
        sa.Column("schema_file", sa.String(1000), nullable=False),
        sa.Column("schema_pointer", sa.String(2000), nullable=False),
        sa.Column("schema_sha256", sa.CHAR(64), nullable=False),
        sa.Column("table_id", _uuid, nullable=False),
        sa.Column("table_revision_id", _uuid, nullable=False),
        sa.Column("table_source_file", sa.String(1000), nullable=False),
        sa.Column("table_source_pointer", sa.String(2000), nullable=False),
        sa.Column("table_source_sha256", sa.CHAR(64), nullable=False),
        sa.Column("pointer_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unit_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "record_id",
            "record_revision_id",
            name="pk_catalog_record_json_source_provenance",
        ),
        sa.CheckConstraint(
            "media_type = 'application/json' AND source_sha256 ~ '^[0-9a-f]{64}$' "
            "AND package_sha256 ~ '^[0-9a-f]{64}$' AND schema_sha256 ~ '^[0-9a-f]{64}$' "
            "AND table_source_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_record_json_source_provenance_digests",
        ),
        sa.CheckConstraint(
            "source_length_bytes > 0 AND component_ordinal BETWEEN 1 AND 100",
            name="ck_catalog_record_json_source_provenance_size",
        ),
        sa.CheckConstraint(
            "(source_artifact_id IS NOT NULL AND package_artifact_id IS NULL "
            "AND package_component_path IS NULL) OR "
            "(source_artifact_id IS NULL AND package_artifact_id IS NOT NULL "
            "AND package_component_path IS NOT NULL)",
            name="ck_catalog_record_json_source_provenance_container_pin",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "batch_id"],
            [
                "catalog.json_record_registration_batch.organization_id",
                "catalog.json_record_registration_batch.project_id",
                "catalog.json_record_registration_batch.id",
            ],
            name="fk_catalog_record_json_source_provenance_batch",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_table(
        "json_record_registration_batch_state_event",
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("batch_id", _uuid, nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("request_id", _uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "id",
            name="pk_catalog_json_registration_batch_state_event",
        ),
        sa.CheckConstraint(
            "state IN ('artifacts_pending', 'ready', 'reconciliation_failed')",
            name="ck_catalog_json_registration_batch_state_event_state",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_catalog_json_registration_batch_state_event_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "batch_id"],
            [
                "catalog.json_record_registration_batch.organization_id",
                "catalog.json_record_registration_batch.project_id",
                "catalog.json_record_registration_batch.id",
            ],
            name="fk_catalog_json_registration_batch_state_event_batch",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )

    for table in (
        "json_record_registration_preview",
        "json_record_registration_batch",
        "json_record_registration_curve_artifact",
        "json_record_registration_batch_state_event",
        "record_json_source_provenance",
    ):
        _rls(table)
    for immutable in (
        "json_record_registration_batch",
        "json_record_registration_curve_artifact",
        "json_record_registration_batch_state_event",
        "record_json_source_provenance",
    ):
        op.execute(
            f"CREATE TRIGGER catalog_{immutable}_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{immutable} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )

    # JSON preview resolves cross-module pins while running under the Catalog read
    # decision.  The application role intentionally cannot SELECT every governed
    # module's revision table directly, so expose one boolean-only, closed-kind
    # check from the already runtime-granted access_control schema.  The first
    # predicate is evaluated with the transaction-local authorization settings;
    # only that authorized scope may reach the SECURITY DEFINER target checks.
    op.execute(
        """
        CREATE FUNCTION access_control.catalog_domain_revision_exists(
          p_organization_id uuid,
          p_project_id uuid,
          p_classification text,
          p_domain_kind text,
          p_domain_object_id uuid,
          p_domain_revision_id uuid
        ) RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $$
        DECLARE
          target_exists boolean := false;
        BEGIN
          IF NOT access_control.can_access_row(
            p_organization_id,
            p_project_id,
            p_classification,
            'catalog.read'
          ) THEN
            RETURN false;
          END IF;

          IF p_domain_kind = 'material' THEN
            SELECT EXISTS (
              SELECT 1
                FROM catalog.material_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'material_state' THEN
            SELECT EXISTS (
              SELECT 1
                FROM catalog.material_state_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'specimen' THEN
            SELECT EXISTS (
              SELECT 1
                FROM testing.specimen_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'test_run' THEN
            SELECT EXISTS (
              SELECT 1
                FROM testing.test_run_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'test_data' THEN
            SELECT EXISTS (
              SELECT 1
                FROM datasets.test_data_document_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'processing_output' THEN
            SELECT EXISTS (
              SELECT 1
                FROM processing.common_processing_output_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'material_model' THEN
            SELECT EXISTS (
              SELECT 1
                FROM modeling.material_model_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'neutral_material' THEN
            SELECT EXISTS (
              SELECT 1
                FROM modeling.neutral_material_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'solver_card' THEN
            SELECT EXISTS (
              SELECT 1
                FROM exporting.solver_card_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'neutral_solver_card' THEN
            SELECT EXISTS (
              SELECT 1
                FROM exporting.neutral_solver_card_revision AS r
               WHERE (r.organization_id, r.project_id, r.classification,
                      r.aggregate_id, r.id) =
                     (p_organization_id, p_project_id, p_classification,
                      p_domain_object_id, p_domain_revision_id)
            ) INTO target_exists;
          ELSIF p_domain_kind = 'release' THEN
            SELECT EXISTS (
              SELECT 1
                FROM governance.release_manifest AS r
               WHERE r.organization_id = p_organization_id
                 AND r.project_id = p_project_id
                 AND r.classification = p_classification
                 AND r.release_id = p_domain_object_id
                 AND r.id = p_domain_revision_id
            ) INTO target_exists;
          END IF;

          RETURN target_exists;
        END
        $$;
        REVOKE ALL ON FUNCTION access_control.catalog_domain_revision_exists(
          uuid, uuid, text, text, uuid, uuid
        ) FROM PUBLIC;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP FUNCTION access_control.catalog_domain_revision_exists(
          uuid, uuid, text, text, uuid, uuid
        )
        """
    )
    for table in (
        "record_json_source_provenance",
        "json_record_registration_curve_artifact",
        "json_record_registration_batch_state_event",
        "json_record_registration_batch",
        "json_record_registration_preview",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS catalog_{table}_immutable ON catalog.{table}")
        op.execute(f"DROP POLICY IF EXISTS catalog_{table}_read ON catalog.{table}")
        op.execute(f"DROP POLICY IF EXISTS catalog_{table}_write ON catalog.{table}")
        op.execute(f"DROP POLICY IF EXISTS catalog_{table}_update ON catalog.{table}")
        op.drop_table(table, schema="catalog")

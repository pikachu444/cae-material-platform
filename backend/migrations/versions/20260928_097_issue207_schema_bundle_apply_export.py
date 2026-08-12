"""Issue #207 atomic Schema Definition Bundle apply/export authority.

Revision ID: 20260928_097_issue207_bundle
Revises: 20260927_096_issue206_curve
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_097_issue207_bundle"
down_revision: str | None = "20260927_096_issue206_curve"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSIFICATIONS = "'internal', 'confidential', 'restricted', 'export_controlled'"
_TARGET_TYPES = (
    "'database', 'profile', 'table', 'attribute', 'layout', 'profile_table_placement', 'link_type'"
)
_DISPOSITIONS = "'create', 'update', 'no-op'"


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "schema_definition_bundle",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("bundle_key", sa.String(64, collation="C"), nullable=False),
        sa.Column("current_application_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_schema_bundle"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_schema_bundle_classified",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "bundle_key",
            name="uq_catalog_schema_bundle_key",
        ),
        sa.CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS}) "
            "AND bundle_key ~ '^[a-z][a-z0-9_]{0,62}[a-z0-9]$|^[a-z]$' "
            "AND updated_at >= created_at",
            name="ck_catalog_schema_bundle_values",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_catalog_schema_bundle_creator",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_table(
        "schema_definition_bundle_version",
        sa.Column("id", uuid, nullable=False),
        sa.Column("bundle_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("bundle_version", sa.String(64, collation="C"), nullable=False),
        sa.Column("canonical_bundle_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("first_source_artifact_id", uuid, nullable=False),
        sa.Column("first_source_artifact_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_schema_bundle_version"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "bundle_id",
            "bundle_version",
            name="uq_catalog_schema_bundle_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "bundle_id",
            "id",
            name="uq_catalog_schema_bundle_version_identity",
        ),
        sa.CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS}) "
            "AND bundle_version ~ '^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$' "
            "AND canonical_bundle_sha256 ~ '^[0-9a-f]{64}$' "
            "AND first_source_artifact_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_catalog_schema_bundle_version_values",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "bundle_id"],
            [
                "catalog.schema_definition_bundle.organization_id",
                "catalog.schema_definition_bundle.project_id",
                "catalog.schema_definition_bundle.classification",
                "catalog.schema_definition_bundle.id",
            ],
            name="fk_catalog_schema_bundle_version_bundle",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "first_source_artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_catalog_schema_bundle_version_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_catalog_schema_bundle_version_creator",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_table(
        "schema_definition_bundle_application",
        sa.Column("id", uuid, nullable=False),
        sa.Column("bundle_id", uuid, nullable=False),
        sa.Column("bundle_version_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("source_artifact_id", uuid, nullable=False),
        sa.Column("source_artifact_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("plan_fingerprint", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("before_snapshot_fingerprint", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("after_snapshot_fingerprint", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("idempotency_key", sa.String(255, collation="C"), nullable=False),
        sa.Column("request_digest", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("mutations_applied", sa.Boolean(), nullable=False),
        sa.Column("delete_missing", sa.Boolean(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_catalog_schema_bundle_application"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "idempotency_key",
            name="uq_catalog_schema_bundle_application_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "bundle_id",
            "id",
            name="uq_catalog_schema_bundle_application_bundle",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_catalog_schema_bundle_application_classified",
        ),
        sa.CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS}) "
            "AND source_artifact_sha256 ~ '^[0-9a-f]{64}$' "
            "AND plan_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND before_snapshot_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND after_snapshot_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND request_digest ~ '^[0-9a-f]{64}$' "
            "AND idempotency_key ~ '^[!-~]{1,255}$' "
            "AND delete_missing = false "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255 AND trace_id = btrim(trace_id)",
            name="ck_catalog_schema_bundle_application_values",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "bundle_id"],
            [
                "catalog.schema_definition_bundle.organization_id",
                "catalog.schema_definition_bundle.project_id",
                "catalog.schema_definition_bundle.classification",
                "catalog.schema_definition_bundle.id",
            ],
            name="fk_catalog_schema_bundle_application_bundle",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "bundle_id", "bundle_version_id"],
            [
                "catalog.schema_definition_bundle_version.organization_id",
                "catalog.schema_definition_bundle_version.project_id",
                "catalog.schema_definition_bundle_version.bundle_id",
                "catalog.schema_definition_bundle_version.id",
            ],
            name="fk_catalog_schema_bundle_application_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "source_artifact_id"],
            [
                "artifact.artifact.organization_id",
                "artifact.artifact.project_id",
                "artifact.artifact.classification",
                "artifact.artifact.id",
            ],
            name="fk_catalog_schema_bundle_application_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["applied_by"],
            ["identity.principal.id"],
            name="fk_catalog_schema_bundle_application_actor",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_schema_bundle_current_application",
        "schema_definition_bundle",
        "schema_definition_bundle_application",
        ["organization_id", "project_id", "id", "current_application_id"],
        ["organization_id", "project_id", "bundle_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "schema_definition_bundle_binding",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("application_id", uuid, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("external_key", sa.String(255, collation="C"), nullable=False),
        sa.Column("parent_external_key", sa.String(255, collation="C"), nullable=True),
        sa.Column("aggregate_id", uuid, nullable=True),
        sa.Column("revision_id", uuid, nullable=True),
        sa.Column("content_hash", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("source_schema_id", sa.String(500), nullable=False),
        sa.Column("source_schema_version", sa.String(64), nullable=False),
        sa.Column("source_pointer", sa.String(2000), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "application_id",
            "sequence",
            name="pk_catalog_schema_bundle_binding",
        ),
        sa.CheckConstraint(
            f"classification IN ({_CLASSIFICATIONS}) "
            f"AND disposition IN ({_DISPOSITIONS}) "
            f"AND target_type IN ({_TARGET_TYPES}) "
            "AND sequence >= 0 AND content_hash ~ '^[0-9a-f]{64}$' "
            "AND length(external_key) BETWEEN 1 AND 255 "
            "AND length(source_schema_id) BETWEEN 1 AND 500 "
            "AND source_schema_version ~ '^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$' "
            "AND length(source_pointer) BETWEEN 1 AND 2000 "
            "AND ((target_type = 'profile_table_placement' AND aggregate_id IS NULL "
            "AND revision_id IS NULL AND published = false) OR "
            "(target_type <> 'profile_table_placement' AND aggregate_id IS NOT NULL "
            "AND revision_id IS NOT NULL AND published = true))",
            name="ck_catalog_schema_bundle_binding_values",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "application_id"],
            [
                "catalog.schema_definition_bundle_application.organization_id",
                "catalog.schema_definition_bundle_application.project_id",
                "catalog.schema_definition_bundle_application.classification",
                "catalog.schema_definition_bundle_application.id",
            ],
            name="fk_catalog_schema_bundle_binding_application",
            ondelete="RESTRICT",
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_schema_bundle_binding_target",
        "schema_definition_bundle_binding",
        ["organization_id", "project_id", "target_type", "aggregate_id"],
        schema="catalog",
    )

    for table in (
        "schema_definition_bundle_version",
        "schema_definition_bundle_application",
        "schema_definition_bundle_binding",
    ):
        op.execute(
            f"CREATE TRIGGER catalog_{table}_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{table} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION catalog.guard_schema_definition_bundle_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Schema Definition Bundle stable identity is immutable'
              USING ERRCODE = '55000';
          END IF;
          IF NEW.id <> OLD.id
             OR NEW.organization_id <> OLD.organization_id
             OR NEW.project_id <> OLD.project_id
             OR NEW.classification <> OLD.classification
             OR NEW.bundle_key <> OLD.bundle_key
             OR NEW.created_at <> OLD.created_at
             OR NEW.created_by <> OLD.created_by
             OR NEW.updated_at < OLD.updated_at THEN
            RAISE EXCEPTION 'Schema Definition Bundle stable identity is immutable'
              USING ERRCODE = '55000';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER catalog_schema_definition_bundle_guard BEFORE UPDATE OR DELETE "
        "ON catalog.schema_definition_bundle FOR EACH ROW "
        "EXECUTE FUNCTION catalog.guard_schema_definition_bundle_update()"
    )

    for table in (
        "schema_definition_bundle",
        "schema_definition_bundle_version",
        "schema_definition_bundle_application",
        "schema_definition_bundle_binding",
    ):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY catalog_{table}_read ON catalog.{table} FOR SELECT USING "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.read'))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_apply_insert ON catalog.{table} "
            "FOR INSERT WITH CHECK (access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.schema.apply'))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_apply_update ON catalog.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.schema.apply')) WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.schema.apply'))"
        )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM catalog.schema_definition_bundle_application) THEN
            RAISE EXCEPTION
              'Issue #207 downgrade refused: immutable Schema Bundle applications exist';
          END IF;
        END
        $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS catalog_schema_definition_bundle_guard "
        "ON catalog.schema_definition_bundle"
    )
    op.execute("DROP FUNCTION IF EXISTS catalog.guard_schema_definition_bundle_update()")
    op.drop_constraint(
        "fk_catalog_schema_bundle_current_application",
        "schema_definition_bundle",
        schema="catalog",
        type_="foreignkey",
    )
    for table in (
        "schema_definition_bundle_binding",
        "schema_definition_bundle_application",
        "schema_definition_bundle_version",
        "schema_definition_bundle",
    ):
        op.drop_table(table, schema="catalog")

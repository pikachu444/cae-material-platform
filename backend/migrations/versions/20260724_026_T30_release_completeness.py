"""T-30 digest-fixed reference Release, Manifest, and package channel."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_026_t30"
down_revision: str | None = "20260723_025_t29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"
_SHA = "'^[0-9a-f]{64}$'"


def _secure(table: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {table}_immutable
        BEFORE UPDATE OR DELETE ON governance.{table}
        FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
        """
    )
    op.execute(f"ALTER TABLE governance.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE governance.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_authorized_select
        ON governance.{table}
        FOR SELECT
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'release.read'
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_authorized_insert
        ON governance.{table}
        FOR INSERT
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'release.publish'
          )
        )
        """
    )


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "release",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("release_code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND organization_id <> "
            + _ZERO
            + " AND project_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name="ck_governance_release_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_governance_release_classification",
        ),
        sa.CheckConstraint(
            "release_code ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_governance_release_code",
        ),
        sa.CheckConstraint("channel = 'reference'", name="ck_governance_release_channel"),
        sa.CheckConstraint("state = 'released'", name="ck_governance_release_state"),
        sa.CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 255 AND length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_governance_release_text",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_governance_release"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_governance_release_scope_identity",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "release_code",
            name="uq_governance_release_code",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_release_tenant_created",
        "release",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="governance",
    )

    op.create_table(
        "release_manifest",
        sa.Column("id", uuid, nullable=False),
        sa.Column("release_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("package_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("package_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("package_media_type", sa.String(128), nullable=False),
        sa.Column("material_id", uuid, nullable=False),
        sa.Column("material_revision_id", uuid, nullable=False),
        sa.Column("material_state_id", uuid, nullable=False),
        sa.Column("material_state_revision_id", uuid, nullable=False),
        sa.Column("property_set_id", uuid, nullable=False),
        sa.Column("property_set_revision_id", uuid, nullable=False),
        sa.Column("material_model_id", uuid, nullable=False),
        sa.Column("material_model_revision_id", uuid, nullable=False),
        sa.Column("material_model_content_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("solver_card_id", uuid, nullable=False),
        sa.Column("solver_card_revision_id", uuid, nullable=False),
        sa.Column("solver_card_content_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("mapping_report_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("card_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("validation_result_id", uuid, nullable=False),
        sa.Column("validation_result_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("review_request_id", uuid, nullable=False),
        sa.Column("review_manifest_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("provenance_snapshot_sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND release_id <> "
            + _ZERO
            + " AND organization_id <> "
            + _ZERO
            + " AND project_id <> "
            + _ZERO
            + " AND material_id <> "
            + _ZERO
            + " AND material_revision_id <> "
            + _ZERO
            + " AND material_state_id <> "
            + _ZERO
            + " AND material_state_revision_id <> "
            + _ZERO
            + " AND property_set_id <> "
            + _ZERO
            + " AND property_set_revision_id <> "
            + _ZERO
            + " AND material_model_id <> "
            + _ZERO
            + " AND material_model_revision_id <> "
            + _ZERO
            + " AND solver_card_id <> "
            + _ZERO
            + " AND solver_card_revision_id <> "
            + _ZERO
            + " AND validation_result_id <> "
            + _ZERO
            + " AND review_request_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO,
            name="ck_governance_release_manifest_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$'",
            name="ck_governance_release_manifest_classification",
        ),
        sa.CheckConstraint(
            "manifest_sha256 ~ "
            + _SHA
            + " AND package_sha256 ~ "
            + _SHA
            + " AND material_model_content_sha256 ~ "
            + _SHA
            + " AND solver_card_content_sha256 ~ "
            + _SHA
            + " AND mapping_report_sha256 ~ "
            + _SHA
            + " AND card_sha256 ~ "
            + _SHA
            + " AND validation_result_sha256 ~ "
            + _SHA
            + " AND review_manifest_sha256 ~ "
            + _SHA
            + " AND provenance_snapshot_sha256 ~ "
            + _SHA,
            name="ck_governance_release_manifest_hashes",
        ),
        sa.CheckConstraint(
            "package_size_bytes > 0", name="ck_governance_release_manifest_package_size"
        ),
        sa.CheckConstraint(
            "package_media_type = 'application/vnd.cmp.release-manifest+json'",
            name="ck_governance_release_manifest_media_type",
        ),
        sa.CheckConstraint(
            "state = 'released' AND length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_governance_release_manifest_state_reason",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_governance_release_manifest"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "release_id",
            name="uq_governance_release_manifest_release",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_governance_release_manifest_scope_identity",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_governance_release_manifest_release",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_model_id",
                "material_model_revision_id",
            ],
            [
                "modeling.material_model_revision.organization_id",
                "modeling.material_model_revision.project_id",
                "modeling.material_model_revision.classification",
                "modeling.material_model_revision.aggregate_id",
                "modeling.material_model_revision.id",
            ],
            name="fk_governance_release_manifest_model_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "solver_card_id",
                "solver_card_revision_id",
            ],
            [
                "exporting.solver_card_revision.organization_id",
                "exporting.solver_card_revision.project_id",
                "exporting.solver_card_revision.classification",
                "exporting.solver_card_revision.aggregate_id",
                "exporting.solver_card_revision.id",
            ],
            name="fk_governance_release_manifest_card_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "validation_result_id"],
            [
                "validation.validation_result.organization_id",
                "validation.validation_result.project_id",
                "validation.validation_result.classification",
                "validation.validation_result.id",
            ],
            name="fk_governance_release_manifest_validation_result",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "review_request_id"],
            [
                "governance.review_request.organization_id",
                "governance.review_request.project_id",
                "governance.review_request.id",
            ],
            name="fk_governance_release_manifest_review_request",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_release_manifest_tenant_created",
        "release_manifest",
        ["organization_id", "project_id", "classification", "created_at"],
        schema="governance",
    )
    op.create_index(
        "ix_governance_release_manifest_review",
        "release_manifest",
        ["organization_id", "project_id", "review_request_id"],
        schema="governance",
    )

    op.create_table(
        "release_artifact",
        sa.Column("id", uuid, nullable=False),
        sa.Column("release_id", uuid, nullable=False),
        sa.Column("release_manifest_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("sha256", sa.CHAR(64, collation="C"), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "id <> "
            + _ZERO
            + " AND release_id <> "
            + _ZERO
            + " AND release_manifest_id <> "
            + _ZERO
            + " AND organization_id <> "
            + _ZERO
            + " AND project_id <> "
            + _ZERO
            + " AND created_by <> "
            + _ZERO
            + " AND request_id <> "
            + _ZERO,
            name="ck_governance_release_artifact_nonzero_ids",
        ),
        sa.CheckConstraint(
            "classification ~ '^[a-z][a-z0-9_.-]{0,63}$' AND media_type = "
            "'application/vnd.cmp.release-manifest+json'",
            name="ck_governance_release_artifact_classification_media",
        ),
        sa.CheckConstraint(
            "sha256 ~ " + _SHA + " AND size_bytes > 0 AND length(btrim(content_text)) > 0",
            name="ck_governance_release_artifact_content",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_governance_release_artifact"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "release_manifest_id",
            name="uq_governance_release_artifact_manifest",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_id"],
            [
                "governance.release.organization_id",
                "governance.release.project_id",
                "governance.release.id",
            ],
            name="fk_governance_release_artifact_release",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "release_manifest_id"],
            [
                "governance.release_manifest.organization_id",
                "governance.release_manifest.project_id",
                "governance.release_manifest.id",
            ],
            name="fk_governance_release_artifact_manifest",
            ondelete="RESTRICT",
        ),
        schema="governance",
    )
    _secure("release")
    _secure("release_manifest")
    _secure("release_artifact")


def downgrade() -> None:
    for table in ("release_artifact", "release_manifest", "release"):
        op.execute(f"DROP TRIGGER {table}_immutable ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_insert ON governance.{table}")
        op.execute(f"DROP POLICY {table}_authorized_select ON governance.{table}")
    op.drop_table("release_artifact", schema="governance")
    op.drop_index(
        "ix_governance_release_manifest_review",
        table_name="release_manifest",
        schema="governance",
    )
    op.drop_index(
        "ix_governance_release_manifest_tenant_created",
        table_name="release_manifest",
        schema="governance",
    )
    op.drop_table("release_manifest", schema="governance")
    op.drop_index(
        "ix_governance_release_tenant_created",
        table_name="release",
        schema="governance",
    )
    op.drop_table("release", schema="governance")

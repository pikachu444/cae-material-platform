"""Catalog administration identities and append-only publication markers (Issue #159 task 2).

Database/Profile keep stable identities separate from immutable revisions.  Publication is a
separate append-only marker so an administrator can continue drafting without changing the
published projection consumed by Materials search.
"""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_092_uxc08"
down_revision: str | None = "20260922_091_uxc07_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity(name: str, key_column: str) -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        name,
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", uuid, nullable=False),
        sa.Column(key_column, sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name=f"pk_catalog_{name}"),
        sa.UniqueConstraint(
            "organization_id", "project_id", key_column, name=f"uq_catalog_{name}_key"
        ),
        schema="catalog",
    )
    op.create_table(
        f"{name}_revision",
        sa.Column("id", uuid, nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", uuid, nullable=True),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        sa.Column(key_column, sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name=f"pk_catalog_{name}_revision"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "id",
            name=f"uq_catalog_{name}_revision_aggregate_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "aggregate_id",
            "id",
            name=f"uq_catalog_{name}_revision_scope_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_id",
            "revision_no",
            name=f"uq_catalog_{name}_revision_number",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "aggregate_id"],
            [f"catalog.{name}.organization_id", f"catalog.{name}.project_id", f"catalog.{name}.id"],
            name=f"fk_catalog_{name}_revision_identity",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="catalog",
    )
    op.create_foreign_key(
        f"fk_catalog_{name}_current_revision",
        name,
        f"{name}_revision",
        ["organization_id", "project_id", "id", "current_revision_id"],
        ["organization_id", "project_id", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def upgrade() -> None:
    _identity("database", "database_key")
    _identity("profile", "profile_key")
    op.add_column(
        "profile_revision",
        sa.Column("database_id", postgresql.UUID(as_uuid=True), nullable=False),
        schema="catalog",
    )
    op.add_column(
        "profile_revision",
        sa.Column("database_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_catalog_profile_revision_database",
        "profile_revision",
        "database_revision",
        ["organization_id", "project_id", "classification", "database_id", "database_revision_id"],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )

    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "publication_marker",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", uuid, nullable=False),
        sa.Column("revision_id", uuid, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            name="pk_catalog_publication_marker",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "aggregate_type",
            "aggregate_id",
            "revision_id",
            name="uq_catalog_publication_marker_revision",
        ),
        schema="catalog",
    )
    # A Table is placed under one exact Profile revision.  It is intentionally
    # a separate append-only relation: changing a profile must never rewrite a
    # Table revision (or its content hash).
    op.create_table(
        "table_profile_placement",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("table_id", uuid, nullable=False),
        sa.Column("table_revision_id", uuid, nullable=False),
        sa.Column("profile_id", uuid, nullable=False),
        sa.Column("profile_revision_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "table_id", "table_revision_id",
            name="pk_catalog_table_profile_placement",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "table_id", "table_revision_id"],
            ["catalog.schema_table_revision.organization_id", "catalog.schema_table_revision.project_id", "catalog.schema_table_revision.classification", "catalog.schema_table_revision.aggregate_id", "catalog.schema_table_revision.id"],
            name="fk_catalog_table_profile_placement_table", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "profile_id", "profile_revision_id"],
            ["catalog.profile_revision.organization_id", "catalog.profile_revision.project_id", "catalog.profile_revision.classification", "catalog.profile_revision.aggregate_id", "catalog.profile_revision.id"],
            name="fk_catalog_table_profile_placement_profile", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED",
        ),
        schema="catalog",
    )
    # The preview is durable across workers, but never stores uploaded raw
    # bytes.  Rows/mapping/errors are the user-editable normalized projection;
    # the immutable artifact (when used) remains in the artifact service.
    op.create_table(
        "record_registration_preview",
        sa.Column("id", uuid, nullable=False),
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("principal_id", uuid, nullable=False),
        sa.Column("token_digest", sa.CHAR(64), nullable=False),
        sa.Column("table_id", uuid, nullable=False),
        sa.Column("table_revision_id", uuid, nullable=False),
        sa.Column("source_artifact_id", uuid, nullable=True),
        sa.Column("source_digest", sa.CHAR(64), nullable=False),
        sa.Column("source_format", sa.String(16), nullable=False),
        sa.Column("sheet_name", sa.String(255), nullable=True),
        sa.Column("has_header", sa.Boolean(), nullable=False),
        sa.Column("encoding", sa.String(64), nullable=True),
        sa.Column("delimiter", sa.String(8), nullable=True),
        sa.Column("decimal_separator", sa.String(1), nullable=True),
        sa.Column("unit_mapping_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("rows", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_selection", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by", uuid, nullable=True),
        sa.PrimaryKeyConstraint("organization_id", "project_id", "id", name="pk_catalog_record_registration_preview"),
        sa.UniqueConstraint("organization_id", "project_id", "token_digest", name="uq_catalog_registration_preview_token"),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "table_id", "table_revision_id"],
            ["catalog.schema_table_revision.organization_id", "catalog.schema_table_revision.project_id", "catalog.schema_table_revision.classification", "catalog.schema_table_revision.aggregate_id", "catalog.schema_table_revision.id"],
            name="fk_catalog_registration_preview_table", ondelete="RESTRICT",
            deferrable=True, initially="DEFERRED",
        ),
        schema="catalog",
    )
    # Existing reader-visible heads remain searchable after the publication boundary is added.
    for source, aggregate_type in (
        ("schema_table", "catalog.configurable_table"),
        ("attribute_definition", "catalog.attribute_definition"),
        ("layout", "catalog.layout"),
        ("subset", "catalog.subset"),
        ("folder", "catalog.folder"),
        ("catalog_record", "catalog.configurable_record"),
        ("link_type", "catalog.link_type"),
        ("record_link", "catalog.record_link"),
    ):
        op.execute(
            f"INSERT INTO catalog.publication_marker "
            "(organization_id, project_id, classification, aggregate_type, aggregate_id, "
            "revision_id, published_at, published_by) "
            f"SELECT organization_id, project_id, classification, '{aggregate_type}', id, "
            f"current_revision_id, now(), created_by FROM catalog.{source}"
        )
    # Preserve the old one-level catalog hierarchy without changing Table
    # content.  The deterministic v5-like ids are scoped so independently
    # migrated tenants never share an identity.
    op.execute(
        """
        INSERT INTO catalog.database
          (id, organization_id, project_id, classification, current_revision_id, database_key,
           created_at, created_by, updated_at)
        SELECT md5('database:' || organization_id::text || ':' || project_id::text || ':' || classification)::uuid,
               organization_id, project_id, classification,
               md5('database-revision:' || organization_id::text || ':' || project_id::text || ':' || classification)::uuid,
               'materials_catalog', now(), min(created_by::text)::uuid, now()
          FROM catalog.schema_table
         GROUP BY organization_id, project_id, classification
        """
    )
    op.execute(
        """
        INSERT INTO catalog.database_revision
          (id, aggregate_id, organization_id, project_id, classification, revision_no,
           based_on_revision_id, schema_id, schema_version, content_hash, created_at, created_by,
           change_reason, request_id, trace_id, database_key, name, description)
        SELECT current_revision_id, id, organization_id, project_id, classification, 1, NULL,
               'urn:cmp:catalog:database:1.0.0', '1.0.0',
               encode(sha256(convert_to(
                 'materials_catalog:' || organization_id::text || ':' || project_id::text || ':' || classification,
                 'UTF8'
               )), 'hex'),
               created_at, created_by, 'Compatibility catalog hierarchy',
               '00000000-0000-0000-0000-000000000000'::uuid, 'migration-092',
               database_key, 'Materials catalog', 'Compatibility container for existing catalog tables.'
          FROM catalog.database
        """
    )
    op.execute(
        """
        INSERT INTO catalog.profile
          (id, organization_id, project_id, classification, current_revision_id, profile_key,
           created_at, created_by, updated_at)
        SELECT md5('profile:' || organization_id::text || ':' || project_id::text || ':' || classification)::uuid,
               organization_id, project_id, classification,
               md5('profile-revision:' || organization_id::text || ':' || project_id::text || ':' || classification)::uuid,
               'general', created_at, created_by, now()
          FROM catalog.database
        """
    )
    op.execute(
        """
        INSERT INTO catalog.profile_revision
          (id, aggregate_id, organization_id, project_id, classification, revision_no,
           based_on_revision_id, schema_id, schema_version, content_hash, created_at, created_by,
           change_reason, request_id, trace_id, profile_key, name, description, database_id, database_revision_id)
        SELECT p.current_revision_id, p.id, p.organization_id, p.project_id, p.classification, 1, NULL,
               'urn:cmp:catalog:profile:1.0.0', '1.0.0',
               encode(sha256(convert_to(
                 'general:' || p.organization_id::text || ':' || p.project_id::text || ':' || p.classification,
                 'UTF8'
               )), 'hex'),
               p.created_at, p.created_by, 'Compatibility catalog hierarchy',
               '00000000-0000-0000-0000-000000000000'::uuid, 'migration-092',
               p.profile_key, 'General', 'Compatibility profile for existing catalog tables.',
               d.id, d.current_revision_id
          FROM catalog.profile p
          JOIN catalog.database d USING (organization_id, project_id, classification)
        """
    )
    op.execute(
        """
        INSERT INTO catalog.table_profile_placement
          (organization_id, project_id, classification, table_id, table_revision_id,
           profile_id, profile_revision_id, created_at, created_by)
        SELECT t.organization_id, t.project_id, t.classification, t.id, t.current_revision_id,
               p.id, p.current_revision_id, now(), t.created_by
          FROM catalog.schema_table t
          JOIN catalog.profile p USING (organization_id, project_id, classification)
        """
    )
    for source, aggregate_type in (("database", "catalog.database"), ("profile", "catalog.profile")):
        op.execute(
            f"INSERT INTO catalog.publication_marker "
            "(organization_id, project_id, classification, aggregate_type, aggregate_id, "
            "revision_id, published_at, published_by) "
            f"SELECT organization_id, project_id, classification, '{aggregate_type}', id, "
            "current_revision_id, now(), created_by FROM catalog." + source
        )
    # The compatibility rows use deferred circular identity/revision foreign keys.
    # Flush those checks before ALTER TABLE below; PostgreSQL otherwise reports
    # pending trigger events when upgrading a populated catalog in one transaction.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    for identity in ("database", "profile"):
        op.execute(
            f"CREATE TRIGGER catalog_{identity}_head_only BEFORE UPDATE OR DELETE "
            f"ON catalog.{identity} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.guard_identity_head_update()"
        )
    for immutable in (
        "database_revision",
        "profile_revision",
        "publication_marker",
        "table_profile_placement",
    ):
        op.execute(
            f"CREATE TRIGGER catalog_{immutable}_immutable BEFORE UPDATE OR DELETE "
            f"ON catalog.{immutable} FOR EACH ROW "
            "EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()"
        )
    for table in (
        "database",
        "database_revision",
        "profile",
        "profile_revision",
        "publication_marker",
        "table_profile_placement",
        "record_registration_preview",
    ):
        op.execute(f"ALTER TABLE catalog.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE catalog.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY catalog_{table}_read ON catalog.{table} FOR SELECT USING "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.read'))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_write ON catalog.{table} FOR INSERT WITH CHECK "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.write'))"
        )
        op.execute(
            f"CREATE POLICY catalog_{table}_update ON catalog.{table} FOR UPDATE USING "
            "(access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.write')) "
            "WITH CHECK (access_control.can_access_row(organization_id, project_id, "
            "classification, 'catalog.write'))"
        )
    op.execute(
        """
        CREATE FUNCTION catalog.guard_catalog_record_external_key()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.external_key IS NULL THEN RETURN NEW; END IF;
          IF EXISTS (
            SELECT 1
              FROM catalog.catalog_record identity_row
              JOIN catalog.catalog_record_revision head
                ON head.organization_id = identity_row.organization_id
               AND head.project_id = identity_row.project_id
               AND head.classification = identity_row.classification
               AND head.aggregate_id = identity_row.id
               AND head.id = identity_row.current_revision_id
             WHERE identity_row.organization_id = NEW.organization_id
               AND identity_row.project_id = NEW.project_id
               AND identity_row.classification = NEW.classification
               AND identity_row.id <> NEW.aggregate_id
               AND head.table_id = NEW.table_id
               AND lower(btrim(head.external_key)) = lower(btrim(NEW.external_key))
          ) THEN
            RAISE EXCEPTION 'duplicate Catalog Record code' USING ERRCODE = '23505';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER catalog_record_external_key_guard BEFORE INSERT "
        "ON catalog.catalog_record_revision FOR EACH ROW "
        "EXECUTE FUNCTION catalog.guard_catalog_record_external_key()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS catalog_record_external_key_guard "
        "ON catalog.catalog_record_revision"
    )
    op.execute("DROP FUNCTION IF EXISTS catalog.guard_catalog_record_external_key()")
    op.drop_constraint(
        "fk_catalog_profile_revision_database",
        "profile_revision",
        schema="catalog",
        type_="foreignkey",
    )
    for identity in ("profile", "database"):
        op.drop_constraint(
            f"fk_catalog_{identity}_current_revision",
            identity,
            schema="catalog",
            type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_catalog_{identity}_revision_identity",
            f"{identity}_revision",
            schema="catalog",
            type_="foreignkey",
        )
    for table in (
        "record_registration_preview",
        "table_profile_placement",
        "publication_marker",
        "profile_revision",
        "profile",
        "database_revision",
        "database",
    ):
        op.drop_table(table, schema="catalog")

"""T-17 immutable plugin manifest/package/schema registry.

Traceability: T-17, NFR-MOD-002, NFR-SEC-002/003/005/006, ADR-001/002/004.
Package, signature, and SBOM artifact UUID/digest references intentionally have no artifact FK
until T-10 owns the immutable artifact table and transfer verification boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_005_t17"
down_revision: str | None = "20260711_004_t15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSIFICATIONS = (
    "internal",
    "confidential",
    "restricted",
    "export_controlled",
)
_EXTENSION_TYPES = (
    "importer",
    "processor",
    "statistical_analyzer",
    "material_model",
    "calibrator",
    "validator",
    "solver_exporter",
)
_PACKAGE_STATES = (
    "contract_validated",
    "eligible",
    "rejected",
    "revoked",
    "unavailable",
)
_SCHEMA_ROLES = ("config", "input", "output", "evidence")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_definition_and_package() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "definition",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("plugin_id", sa.String(length=255, collation="C"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", uuid, nullable=False),
        sa.CheckConstraint(
            "organization_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plugin_definition_nonzero_organization",
        ),
        sa.CheckConstraint(
            "project_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plugin_definition_nonzero_project",
        ),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plugin_definition_nonzero_id",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_plugin_definition_classification",
        ),
        sa.CheckConstraint(
            "plugin_id ~ '^[a-z0-9]+([._-][a-z0-9]+)+$'",
            name="ck_plugin_definition_identifier",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_plugin_definition"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_plugin_definition_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "plugin_id",
            name="uq_plugin_definition_identifier",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.principal.id"],
            name="fk_plugin_definition_created_by",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )

    op.create_table(
        "package",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("definition_id", uuid, nullable=False),
        sa.Column("plugin_version", sa.String(length=64, collation="C"), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("package_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manifest_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("contract_api", sa.String(length=100, collation="C"), nullable=False),
        sa.Column("network_policy", sa.String(length=32), nullable=False),
        sa.Column("requested_cpu", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("requested_memory_mb", sa.Integer(), nullable=False),
        sa.Column("requested_gpu", sa.Integer(), nullable=False),
        sa.Column("requested_timeout_s", sa.Integer(), nullable=False),
        sa.Column("non_production", sa.Boolean(), nullable=False),
        sa.Column("package_artifact_id", uuid, nullable=False),
        sa.Column("package_artifact_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("package_artifact_size", sa.BigInteger(), nullable=False),
        sa.Column("package_artifact_media_type", sa.String(length=255), nullable=False),
        sa.Column("signature_artifact_id", uuid, nullable=False),
        sa.Column("signature_artifact_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("signature_artifact_size", sa.BigInteger(), nullable=False),
        sa.Column("signature_artifact_media_type", sa.String(length=255), nullable=False),
        sa.Column("sbom_artifact_id", uuid, nullable=False),
        sa.Column("sbom_artifact_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("sbom_artifact_size", sa.BigInteger(), nullable=False),
        sa.Column("sbom_artifact_media_type", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255, collation="C"), nullable=False),
        sa.Column("submission_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_by", uuid, nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND package_artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND signature_artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND sbom_artifact_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND submitted_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plugin_package_nonzero_id",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_plugin_package_classification",
        ),
        sa.CheckConstraint(
            "plugin_version ~ '^[0-9]+\\.[0-9]+\\.[0-9]+$'",
            name="ck_plugin_package_version",
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) BETWEEN 1 AND 200",
            name="ck_plugin_package_display_name",
        ),
        sa.CheckConstraint(
            "package_digest ~ '^[0-9a-f]{64}$' "
            "AND manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND package_artifact_digest ~ '^[0-9a-f]{64}$' "
            "AND signature_artifact_digest ~ '^[0-9a-f]{64}$' "
            "AND sbom_artifact_digest ~ '^[0-9a-f]{64}$'",
            name="ck_plugin_package_digests",
        ),
        sa.CheckConstraint(
            "package_artifact_digest = package_digest",
            name="ck_plugin_package_artifact_digest",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(manifest) = 'object' "
            "AND manifest->>'manifest_version' = '1.0' "
            "AND manifest->>'plugin_version' = plugin_version "
            "AND manifest->>'display_name' = display_name "
            "AND manifest->>'package_digest' = 'sha256:' || package_digest "
            "AND manifest->>'contract_api' = contract_api",
            name="ck_plugin_package_manifest_projection",
        ),
        sa.CheckConstraint(
            "network_policy = 'none' AND (manifest->'permissions'->>'network') = 'none'",
            name="ck_plugin_package_network_deny",
        ),
        sa.CheckConstraint(
            "requested_cpu > 0 AND requested_memory_mb >= 64 "
            "AND requested_gpu >= 0 AND requested_timeout_s > 0 "
            "AND (manifest->'resources'->>'cpu')::numeric = requested_cpu "
            "AND (manifest->'resources'->>'memory_mb')::integer = requested_memory_mb "
            "AND (manifest->'resources'->>'gpu')::integer = requested_gpu "
            "AND (manifest->'resources'->>'timeout_s')::integer = requested_timeout_s",
            name="ck_plugin_package_resources",
        ),
        sa.CheckConstraint(
            "non_production AND (manifest->>'non_production')::boolean",
            name="ck_plugin_package_non_production",
        ),
        sa.CheckConstraint(
            "package_artifact_id <> signature_artifact_id "
            "AND package_artifact_id <> sbom_artifact_id "
            "AND signature_artifact_id <> sbom_artifact_id",
            name="ck_plugin_package_distinct_artifacts",
        ),
        sa.CheckConstraint(
            "package_artifact_size > 0 AND signature_artifact_size > 0 "
            "AND sbom_artifact_size > 0",
            name="ck_plugin_package_artifact_sizes",
        ),
        sa.CheckConstraint(
            "length(btrim(package_artifact_media_type)) BETWEEN 1 AND 255 "
            "AND length(btrim(signature_artifact_media_type)) BETWEEN 1 AND 255 "
            "AND length(btrim(sbom_artifact_media_type)) BETWEEN 1 AND 255",
            name="ck_plugin_package_media_types",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 255 "
            "AND submission_digest ~ '^[0-9a-f]{64}$' "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_plugin_package_idempotency",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_plugin_package"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_plugin_package_classified_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "definition_id",
            "plugin_version",
            name="uq_plugin_package_definition_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "package_digest",
            name="uq_plugin_package_digest",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "idempotency_key",
            name="uq_plugin_package_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "definition_id"],
            [
                "plugin.definition.organization_id",
                "plugin.definition.project_id",
                "plugin.definition.classification",
                "plugin.definition.id",
            ],
            name="fk_plugin_package_definition",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["identity.principal.id"],
            name="fk_plugin_package_submitted_by",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_index(
        "ix_plugin_package_definition",
        "package",
        ["organization_id", "project_id", "definition_id", "plugin_version"],
        schema="plugin",
    )


def _create_package_contract_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    package_fk_local = ["organization_id", "project_id", "classification", "package_id"]
    package_fk_remote = [
        "plugin.package.organization_id",
        "plugin.package.project_id",
        "plugin.package.classification",
        "plugin.package.id",
    ]
    op.create_table(
        "extension",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("extension_type", sa.String(length=64), nullable=False),
        sa.Column("entrypoint", sa.String(length=500), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_plugin_extension_ordinal"),
        sa.CheckConstraint(
            f"extension_type IN ({_quoted(_EXTENSION_TYPES)})",
            name="ck_plugin_extension_type",
        ),
        sa.CheckConstraint(
            "length(btrim(entrypoint)) BETWEEN 1 AND 500",
            name="ck_plugin_extension_entrypoint",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "package_id",
            "ordinal",
            name="pk_plugin_extension",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "package_id",
            "ordinal",
            name="uq_plugin_extension_classified_reference",
        ),
        sa.ForeignKeyConstraint(
            package_fk_local,
            package_fk_remote,
            name="fk_plugin_extension_package",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_table(
        "capability",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("extension_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("capability", sa.String(length=100, collation="C"), nullable=False),
        sa.CheckConstraint(
            "capability ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name="ck_plugin_capability_identifier",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "package_id",
            "extension_ordinal",
            "capability",
            name="pk_plugin_capability",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "package_id",
                "extension_ordinal",
            ],
            [
                "plugin.extension.organization_id",
                "plugin.extension.project_id",
                "plugin.extension.classification",
                "plugin.extension.package_id",
                "plugin.extension.ordinal",
            ],
            name="fk_plugin_capability_extension",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_table(
        "schema",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("extension_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("schema_role", sa.String(length=32), nullable=False),
        sa.Column("schema_id", sa.String(length=500, collation="C"), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document_digest", sa.CHAR(length=64, collation="C"), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            f"AND schema_role IN ({_quoted(_SCHEMA_ROLES)})",
            name="ck_plugin_schema_role",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(document) = 'object' "
            "AND length(btrim(schema_id)) BETWEEN 1 AND 500 "
            "AND document->>'$id' = schema_id "
            "AND document->>'$schema' = 'https://json-schema.org/draft/2020-12/schema'",
            name="ck_plugin_schema_identity",
        ),
        sa.CheckConstraint(
            "document_digest ~ '^[0-9a-f]{64}$'",
            name="ck_plugin_schema_digest",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_plugin_schema"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "package_id",
            "schema_id",
            name="uq_plugin_schema_identifier",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "package_id",
                "extension_ordinal",
            ],
            [
                "plugin.extension.organization_id",
                "plugin.extension.project_id",
                "plugin.extension.classification",
                "plugin.extension.package_id",
                "plugin.extension.ordinal",
            ],
            name="fk_plugin_schema_extension",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_table(
        "artifact_role",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("role_name", sa.String(length=100, collation="C"), nullable=False),
        sa.CheckConstraint(
            "direction IN ('read', 'write')", name="ck_plugin_artifact_role_direction"
        ),
        sa.CheckConstraint(
            "length(btrim(role_name)) BETWEEN 1 AND 100",
            name="ck_plugin_artifact_role_name",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "package_id",
            "direction",
            "role_name",
            name="pk_plugin_artifact_role",
        ),
        sa.ForeignKeyConstraint(
            package_fk_local,
            package_fk_remote,
            name="fk_plugin_artifact_role_package",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )


def _create_state_and_activation_tables() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "package_state_event",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", uuid, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name="ck_plugin_state_event_sequence"),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND actor_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plugin_state_event_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"to_state IN ({_quoted(_PACKAGE_STATES)}) "
            f"AND (from_state IS NULL OR from_state IN ({_quoted(_PACKAGE_STATES)}))",
            name="ck_plugin_state_event_states",
        ),
        sa.CheckConstraint(
            "(sequence_no = 1 AND from_state IS NULL AND to_state = 'contract_validated') "
            "OR (sequence_no > 1 AND from_state IS NOT NULL)",
            name="ck_plugin_state_event_initial",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_plugin_state_event_reason",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_plugin_state_event"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "package_id",
            "id",
            name="uq_plugin_state_event_scoped_reference",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "package_id",
            "sequence_no",
            name="uq_plugin_state_event_sequence",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "package_id"],
            [
                "plugin.package.organization_id",
                "plugin.package.project_id",
                "plugin.package.classification",
                "plugin.package.id",
            ],
            name="fk_plugin_state_event_package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["identity.principal.id"],
            name="fk_plugin_state_event_actor",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_index(
        "ix_plugin_state_event_package",
        "package_state_event",
        ["organization_id", "project_id", "package_id", "sequence_no"],
        schema="plugin",
    )
    op.create_table(
        "package_state_projection",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("last_event_id", uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"state IN ({_quoted(_PACKAGE_STATES)})", name="ck_plugin_state_projection_state"
        ),
        sa.CheckConstraint(
            "sequence_no > 0", name="ck_plugin_state_projection_sequence"
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "package_id",
            name="pk_plugin_state_projection",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "package_id"],
            [
                "plugin.package.organization_id",
                "plugin.package.project_id",
                "plugin.package.classification",
                "plugin.package.id",
            ],
            name="fk_plugin_state_projection_package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "package_id",
                "last_event_id",
            ],
            [
                "plugin.package_state_event.organization_id",
                "plugin.package_state_event.project_id",
                "plugin.package_state_event.classification",
                "plugin.package_state_event.package_id",
                "plugin.package_state_event.id",
            ],
            name="fk_plugin_state_projection_last_event",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )
    op.create_index(
        "ix_plugin_state_projection_state",
        "package_state_projection",
        ["organization_id", "project_id", "state", "package_id"],
        schema="plugin",
    )
    op.create_table(
        "activation",
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("package_id", uuid, nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", uuid, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND activated_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND length(btrim(reason)) BETWEEN 1 AND 2000 "
            "AND length(btrim(trace_id)) BETWEEN 1 AND 255",
            name="ck_plugin_activation_reason",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_plugin_activation"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "package_id",
            name="uq_plugin_activation_package",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "package_id"],
            [
                "plugin.package.organization_id",
                "plugin.package.project_id",
                "plugin.package.classification",
                "plugin.package.id",
            ],
            name="fk_plugin_activation_package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["activated_by"],
            ["identity.principal.id"],
            name="fk_plugin_activation_actor",
            ondelete="RESTRICT",
        ),
        schema="plugin",
    )


def _create_guards() -> None:
    immutable_tables = (
        "definition",
        "package",
        "extension",
        "capability",
        "schema",
        "artifact_role",
        "package_state_event",
        "activation",
    )
    for table in immutable_tables:
        op.execute(
            f"""
            CREATE TRIGGER {table}_immutable
            BEFORE UPDATE OR DELETE ON plugin.{table}
            FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
            """
        )
    op.execute(
        """
        CREATE FUNCTION plugin.require_matching_definition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          stable_plugin_id text;
        BEGIN
          SELECT definition.plugin_id
          INTO stable_plugin_id
          FROM plugin.definition definition
          WHERE definition.organization_id = NEW.organization_id
            AND definition.project_id = NEW.project_id
            AND definition.classification = NEW.classification
            AND definition.id = NEW.definition_id;
          IF NOT FOUND OR NEW.manifest->>'plugin_id' <> stable_plugin_id THEN
            RAISE EXCEPTION USING
              ERRCODE = '23514',
              MESSAGE = 'plugin package manifest does not match its stable definition';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER package_definition_guard
        BEFORE INSERT ON plugin.package
        FOR EACH ROW EXECUTE FUNCTION plugin.require_matching_definition()
        """
    )
    op.execute(
        """
        CREATE FUNCTION plugin.require_initial_package_projection()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM plugin.package_state_projection projection
            JOIN plugin.package_state_event event
              ON event.organization_id = projection.organization_id
             AND event.project_id = projection.project_id
             AND event.classification = projection.classification
             AND event.package_id = projection.package_id
             AND event.id = projection.last_event_id
            WHERE projection.organization_id = NEW.organization_id
              AND projection.project_id = NEW.project_id
              AND projection.classification = NEW.classification
              AND projection.package_id = NEW.id
              AND projection.sequence_no = 1
              AND projection.state = 'contract_validated'
              AND event.sequence_no = 1
              AND event.from_state IS NULL
              AND event.to_state = 'contract_validated'
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package registration must commit its initial state projection';
          END IF;
          RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER package_initial_projection
        AFTER INSERT ON plugin.package
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION plugin.require_initial_package_projection()
        """
    )
    op.execute(
        """
        CREATE FUNCTION plugin.require_unsealed_package()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM plugin.package_state_projection projection
            WHERE projection.organization_id = NEW.organization_id
              AND projection.project_id = NEW.project_id
              AND projection.package_id = NEW.package_id
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'sealed plugin package contract rows are immutable';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    for table in ("extension", "capability", "schema", "artifact_role"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_sealed_package_guard
            BEFORE INSERT ON plugin.{table}
            FOR EACH ROW EXECUTE FUNCTION plugin.require_unsealed_package()
            """
        )
    op.execute(
        """
        CREATE FUNCTION plugin.guard_package_state_event_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          current_state text;
          current_sequence bigint;
          transition_allowed boolean;
        BEGIN
          IF NEW.sequence_no = 1 THEN
            IF EXISTS (
              SELECT 1
              FROM plugin.package_state_event event
              WHERE event.organization_id = NEW.organization_id
                AND event.project_id = NEW.project_id
                AND event.package_id = NEW.package_id
            ) OR EXISTS (
              SELECT 1
              FROM plugin.package_state_projection projection
              WHERE projection.organization_id = NEW.organization_id
                AND projection.project_id = NEW.project_id
                AND projection.package_id = NEW.package_id
            ) THEN
              RAISE EXCEPTION USING
                ERRCODE = '23505',
                MESSAGE = 'plugin package already has an initial state event';
            END IF;
            RETURN NEW;
          END IF;

          SELECT projection.state, projection.sequence_no
          INTO current_state, current_sequence
          FROM plugin.package_state_projection projection
          WHERE projection.organization_id = NEW.organization_id
            AND projection.project_id = NEW.project_id
            AND projection.package_id = NEW.package_id
          FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package state projection is missing';
          END IF;
          IF NEW.sequence_no <> current_sequence + 1
             OR NEW.from_state IS DISTINCT FROM current_state THEN
            RAISE EXCEPTION USING
              ERRCODE = '40001',
              MESSAGE = 'plugin package event does not advance the current projection';
          END IF;
          transition_allowed := CASE current_state
            WHEN 'contract_validated' THEN NEW.to_state IN ('eligible', 'rejected', 'revoked')
            WHEN 'eligible' THEN NEW.to_state IN ('revoked', 'unavailable')
            WHEN 'unavailable' THEN NEW.to_state = 'revoked'
            ELSE false
          END;
          IF NOT COALESCE(transition_allowed, false) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                'invalid plugin package transition %s -> %s',
                current_state,
                NEW.to_state
              );
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER package_state_event_guard
        BEFORE INSERT ON plugin.package_state_event
        FOR EACH ROW EXECUTE FUNCTION plugin.guard_package_state_event_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION plugin.require_state_event_projection()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM plugin.package_state_projection projection
            WHERE projection.organization_id = NEW.organization_id
              AND projection.project_id = NEW.project_id
              AND projection.classification = NEW.classification
              AND projection.package_id = NEW.package_id
              AND projection.sequence_no = NEW.sequence_no
              AND projection.last_event_id = NEW.id
              AND projection.state = NEW.to_state
              AND projection.updated_at = NEW.occurred_at
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package state event must be projected in the same transaction';
          END IF;
          RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER package_state_event_projected
        AFTER INSERT ON plugin.package_state_event
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION plugin.require_state_event_projection()
        """
    )
    op.execute(
        """
        CREATE FUNCTION plugin.guard_package_state_projection()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          transition_allowed boolean;
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NOT EXISTS (
              SELECT 1
              FROM plugin.package_state_event event
              WHERE event.organization_id = NEW.organization_id
                AND event.project_id = NEW.project_id
                AND event.classification = NEW.classification
                AND event.package_id = NEW.package_id
                AND event.id = NEW.last_event_id
                AND event.sequence_no = NEW.sequence_no
                AND event.from_state IS NULL
                AND event.to_state = NEW.state
                AND event.occurred_at = NEW.updated_at
            ) THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'initial plugin package projection requires its matching event';
            END IF;
            RETURN NEW;
          END IF;
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'plugin package state projections cannot be deleted';
          END IF;
          IF (to_jsonb(NEW) - ARRAY['state', 'sequence_no', 'last_event_id', 'updated_at'])
             IS DISTINCT FROM
             (to_jsonb(OLD) - ARRAY['state', 'sequence_no', 'last_event_id', 'updated_at']) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000', MESSAGE = 'plugin package state identity is immutable';
          END IF;
          IF NEW.sequence_no <> OLD.sequence_no + 1 OR NEW.updated_at < OLD.updated_at THEN
            RAISE EXCEPTION USING
              ERRCODE = '40001', MESSAGE = 'plugin package state sequence must advance once';
          END IF;
          transition_allowed := CASE OLD.state
            WHEN 'contract_validated' THEN NEW.state IN ('eligible', 'rejected', 'revoked')
            WHEN 'eligible' THEN NEW.state IN ('revoked', 'unavailable')
            WHEN 'unavailable' THEN NEW.state = 'revoked'
            ELSE false
          END;
          IF NOT COALESCE(transition_allowed, false) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = format(
                'invalid plugin package transition %s -> %s', OLD.state, NEW.state
              );
          END IF;
          IF NOT EXISTS (
            SELECT 1
            FROM plugin.package_state_event event
            WHERE event.organization_id = NEW.organization_id
              AND event.project_id = NEW.project_id
              AND event.classification = NEW.classification
              AND event.package_id = NEW.package_id
              AND event.id = NEW.last_event_id
              AND event.sequence_no = NEW.sequence_no
              AND event.from_state = OLD.state
              AND event.to_state = NEW.state
              AND event.occurred_at = NEW.updated_at
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package projection update requires its matching event';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER package_state_projection_guard
        BEFORE INSERT OR UPDATE OR DELETE ON plugin.package_state_projection
        FOR EACH ROW EXECUTE FUNCTION plugin.guard_package_state_projection()
        """
    )
    op.execute(
        """
        CREATE FUNCTION plugin.require_eligible_activation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          current_state text;
          manifest_document jsonb;
          stable_plugin_id text;
          extension_row record;
          manifest_extension jsonb;
          actual_capabilities text[];
          expected_capabilities text[];
          actual_roles text[];
          expected_roles text[];
          extension_count integer := 0;
        BEGIN
          SELECT projection.state
          INTO current_state
          FROM plugin.package_state_projection projection
          WHERE projection.organization_id = NEW.organization_id
            AND projection.project_id = NEW.project_id
            AND projection.package_id = NEW.package_id
          FOR UPDATE;
          IF NOT FOUND OR current_state <> 'eligible' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'only an eligible plugin package can be activated';
          END IF;

          SELECT package.manifest, definition.plugin_id
          INTO manifest_document, stable_plugin_id
          FROM plugin.package package
          JOIN plugin.definition definition
            ON definition.organization_id = package.organization_id
           AND definition.project_id = package.project_id
           AND definition.id = package.definition_id
          WHERE package.organization_id = NEW.organization_id
            AND package.project_id = NEW.project_id
            AND package.id = NEW.package_id;
          IF NOT FOUND OR manifest_document->>'plugin_id' <> stable_plugin_id THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package does not match its stable definition';
          END IF;
          IF jsonb_typeof(manifest_document->'extensions') <> 'array'
             OR jsonb_typeof(manifest_document->'permissions'->'artifact_read_roles') <> 'array'
             OR jsonb_typeof(
               manifest_document->'permissions'->'artifact_write_roles'
             ) <> 'array' THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'plugin package manifest contract is incomplete';
          END IF;

          FOR extension_row IN
            SELECT extension.ordinal, extension.extension_type, extension.entrypoint
            FROM plugin.extension extension
            WHERE extension.organization_id = NEW.organization_id
              AND extension.project_id = NEW.project_id
              AND extension.package_id = NEW.package_id
            ORDER BY extension.ordinal
          LOOP
            extension_count := extension_count + 1;
            manifest_extension := manifest_document->'extensions'->(extension_row.ordinal - 1);
            IF jsonb_typeof(manifest_extension) <> 'object'
               OR manifest_extension->>'type' <> extension_row.extension_type
               OR manifest_extension->>'entrypoint' <> extension_row.entrypoint
               OR jsonb_typeof(manifest_extension->'capabilities') <> 'array' THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'registered extension does not match the immutable manifest';
            END IF;
            SELECT array_agg(capability.capability ORDER BY capability.capability)
            INTO actual_capabilities
            FROM plugin.capability capability
            WHERE capability.organization_id = NEW.organization_id
              AND capability.project_id = NEW.project_id
              AND capability.package_id = NEW.package_id
              AND capability.extension_ordinal = extension_row.ordinal;
            SELECT array_agg(value ORDER BY value)
            INTO expected_capabilities
            FROM jsonb_array_elements_text(
              manifest_extension->'capabilities'
            ) AS declared(value);
            IF actual_capabilities IS NULL
               OR actual_capabilities IS DISTINCT FROM expected_capabilities THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'every extension requires its exact declared capabilities';
            END IF;
            IF NOT EXISTS (
              SELECT 1
              FROM plugin.schema registered_schema
              WHERE registered_schema.organization_id = NEW.organization_id
                AND registered_schema.project_id = NEW.project_id
                AND registered_schema.package_id = NEW.package_id
                AND registered_schema.extension_ordinal = extension_row.ordinal
            ) THEN
              RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'every extension requires at least one registered schema';
            END IF;
          END LOOP;
          IF extension_count = 0
             OR extension_count <> jsonb_array_length(manifest_document->'extensions') THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'registered extensions do not match the immutable manifest';
          END IF;

          SELECT array_agg(role.role_name ORDER BY role.role_name)
          INTO actual_roles
          FROM plugin.artifact_role role
          WHERE role.organization_id = NEW.organization_id
            AND role.project_id = NEW.project_id
            AND role.package_id = NEW.package_id
            AND role.direction = 'read';
          SELECT array_agg(value ORDER BY value)
          INTO expected_roles
          FROM jsonb_array_elements_text(
            manifest_document->'permissions'->'artifact_read_roles'
          ) AS declared(value);
          IF COALESCE(actual_roles, ARRAY[]::text[])
             IS DISTINCT FROM COALESCE(expected_roles, ARRAY[]::text[]) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'registered read roles do not match the immutable manifest';
          END IF;

          SELECT array_agg(role.role_name ORDER BY role.role_name)
          INTO actual_roles
          FROM plugin.artifact_role role
          WHERE role.organization_id = NEW.organization_id
            AND role.project_id = NEW.project_id
            AND role.package_id = NEW.package_id
            AND role.direction = 'write';
          SELECT array_agg(value ORDER BY value)
          INTO expected_roles
          FROM jsonb_array_elements_text(
            manifest_document->'permissions'->'artifact_write_roles'
          ) AS declared(value);
          IF COALESCE(actual_roles, ARRAY[]::text[])
             IS DISTINCT FROM COALESCE(expected_roles, ARRAY[]::text[]) THEN
            RAISE EXCEPTION USING
              ERRCODE = '55000',
              MESSAGE = 'registered write roles do not match the immutable manifest';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER activation_eligibility_guard
        BEFORE INSERT ON plugin.activation
        FOR EACH ROW EXECUTE FUNCTION plugin.require_eligible_activation()
        """
    )


def _secure_tables() -> None:
    tables = (
        "definition",
        "package",
        "extension",
        "capability",
        "schema",
        "artifact_role",
        "package_state_event",
        "package_state_projection",
        "activation",
    )
    for table in tables:
        op.execute(f"ALTER TABLE plugin.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE plugin.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON plugin.{table} FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'plugin.read'
              )
            )
            """
        )

    submit_tables = (
        "definition",
        "package",
        "extension",
        "capability",
        "schema",
        "artifact_role",
    )
    for table in submit_tables:
        actor_check = ""
        if table == "definition":
            actor_check = "AND created_by = access_control.current_principal_id()"
        elif table == "package":
            actor_check = "AND submitted_by = access_control.current_principal_id()"
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_insert
            ON plugin.{table} FOR INSERT
            WITH CHECK (
              access_control.can_access_row(
                organization_id, project_id, classification, 'plugin.submit'
              )
              {actor_check}
            )
            """
        )
    op.execute(
        """
        CREATE POLICY package_state_event_authorized_insert
        ON plugin.package_state_event FOR INSERT
        WITH CHECK (
          actor_id = access_control.current_principal_id()
          AND (
            (
              sequence_no = 1
              AND to_state = 'contract_validated'
              AND access_control.can_access_row(
                organization_id, project_id, classification, 'plugin.submit'
              )
            )
            OR (
              sequence_no > 1
              AND access_control.can_access_row(
                organization_id, project_id, classification, 'plugin.activate'
              )
            )
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY package_state_projection_authorized_insert
        ON plugin.package_state_projection FOR INSERT
        WITH CHECK (
          state = 'contract_validated'
          AND sequence_no = 1
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'plugin.submit'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY package_state_projection_authorized_update
        ON plugin.package_state_projection FOR UPDATE
        USING (
          access_control.can_access_row(
            organization_id, project_id, classification, 'plugin.activate'
          )
        )
        WITH CHECK (
          access_control.can_access_row(
            organization_id, project_id, classification, 'plugin.activate'
          )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY activation_authorized_insert
        ON plugin.activation FOR INSERT
        WITH CHECK (
          activated_by = access_control.current_principal_id()
          AND access_control.can_access_row(
            organization_id, project_id, classification, 'plugin.activate'
          )
        )
        """
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA plugin")
    _create_definition_and_package()
    _create_package_contract_tables()
    _create_state_and_activation_tables()
    _create_guards()
    _secure_tables()


def downgrade() -> None:
    op.execute("DROP FUNCTION plugin.require_eligible_activation() CASCADE")
    op.execute("DROP FUNCTION plugin.guard_package_state_projection() CASCADE")
    op.execute("DROP FUNCTION plugin.require_state_event_projection() CASCADE")
    op.execute("DROP FUNCTION plugin.guard_package_state_event_insert() CASCADE")
    op.execute("DROP FUNCTION plugin.require_unsealed_package() CASCADE")
    op.execute("DROP FUNCTION plugin.require_initial_package_projection() CASCADE")
    op.execute("DROP FUNCTION plugin.require_matching_definition() CASCADE")
    op.drop_table("activation", schema="plugin")
    op.drop_index(
        "ix_plugin_state_projection_state",
        table_name="package_state_projection",
        schema="plugin",
    )
    op.drop_table("package_state_projection", schema="plugin")
    op.drop_index(
        "ix_plugin_state_event_package",
        table_name="package_state_event",
        schema="plugin",
    )
    op.drop_table("package_state_event", schema="plugin")
    op.drop_table("artifact_role", schema="plugin")
    op.drop_table("schema", schema="plugin")
    op.drop_table("capability", schema="plugin")
    op.drop_table("extension", schema="plugin")
    op.drop_index(
        "ix_plugin_package_definition", table_name="package", schema="plugin"
    )
    op.drop_table("package", schema="plugin")
    op.drop_table("definition", schema="plugin")
    op.execute("DROP SCHEMA plugin")

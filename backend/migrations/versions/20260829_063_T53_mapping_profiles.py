"""Add immutable Mapping Profiles with typed channel and Attribute bindings.

Revision ID: 20260829_063_t53_map
Revises: 20260828_062_test_json
"""

# ruff: noqa: E501 -- SQL constraints remain aligned with their database objects.

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_063_t53_map"
down_revision: str | None = "20260828_062_test_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "mapping_profile",
    "mapping_profile_revision",
    "mapping_profile_channel_binding",
    "mapping_profile_attribute_binding",
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
        CREATE TABLE processing.mapping_profile (
          id uuid NOT NULL, organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_key varchar(160) NOT NULL,
          current_revision_id uuid NOT NULL, created_at timestamptz NOT NULL,
          created_by uuid NOT NULL, updated_at timestamptz NOT NULL,
          CONSTRAINT pk_processing_mapping_profile PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_mapping_profile_scope UNIQUE
            (organization_id, project_id, classification, id),
          CONSTRAINT uq_processing_mapping_profile_key UNIQUE
            (organization_id, project_id, profile_key),
          CONSTRAINT ck_processing_mapping_profile_key CHECK
            (length(btrim(profile_key)) BETWEEN 1 AND 160)
        );
        CREATE TABLE processing.mapping_profile_revision (
          id uuid NOT NULL, aggregate_id uuid NOT NULL, organization_id uuid NOT NULL,
          project_id uuid NOT NULL, classification varchar(64) NOT NULL,
          revision_no bigint NOT NULL CHECK (revision_no>0), based_on_revision_id uuid,
          schema_id varchar(255) NOT NULL, schema_version varchar(64) NOT NULL,
          content_hash char(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL, created_by uuid NOT NULL,
          change_reason text NOT NULL CHECK (length(btrim(change_reason)) BETWEEN 1 AND 2000),
          request_id uuid NOT NULL, trace_id varchar(255) NOT NULL,
          profile_key varchar(160) NOT NULL, label varchar(200) NOT NULL,
          independent_quantity varchar(160) NOT NULL,
          missing_data_policy varchar(32) NOT NULL
            CHECK (missing_data_policy IN ('reject','drop_any')),
          channel_binding_count integer NOT NULL CHECK (channel_binding_count BETWEEN 2 AND 128),
          attribute_binding_count integer NOT NULL CHECK (attribute_binding_count BETWEEN 0 AND 128),
          CONSTRAINT pk_processing_mapping_profile_revision
            PRIMARY KEY (organization_id, project_id, id),
          CONSTRAINT uq_processing_mapping_profile_revision_scope UNIQUE
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT uq_processing_mapping_profile_revision_no UNIQUE
            (organization_id, project_id, aggregate_id, revision_no),
          CONSTRAINT fk_processing_mapping_profile_revision_identity FOREIGN KEY
            (organization_id, project_id, classification, aggregate_id) REFERENCES
            processing.mapping_profile (organization_id, project_id, classification, id),
          CONSTRAINT fk_processing_mapping_profile_revision_base FOREIGN KEY
            (organization_id, project_id, based_on_revision_id) REFERENCES
            processing.mapping_profile_revision (organization_id, project_id, id),
          CONSTRAINT ck_processing_mapping_profile_revision_key CHECK
            (length(btrim(profile_key)) BETWEEN 1 AND 160),
          CONSTRAINT ck_processing_mapping_profile_revision_label CHECK
            (length(btrim(label)) BETWEEN 1 AND 200)
        );
        ALTER TABLE processing.mapping_profile ADD CONSTRAINT
          fk_processing_mapping_profile_current FOREIGN KEY
          (organization_id, project_id, classification, id, current_revision_id) REFERENCES
          processing.mapping_profile_revision
          (organization_id, project_id, classification, aggregate_id, id)
          DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_processing_mapping_profile_label
          ON processing.mapping_profile_revision (organization_id, project_id, lower(label));

        CREATE TABLE processing.mapping_profile_channel_binding (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_id uuid NOT NULL,
          profile_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          channel_key varchar(160) NOT NULL, target_quantity varchar(160) NOT NULL,
          accepted_normalized_units varchar(160)[] NOT NULL,
          required boolean NOT NULL, value_scale double precision NOT NULL
            CHECK (value_scale > '-Infinity'::float8 AND value_scale < 'Infinity'::float8
                   AND value_scale<>0),
          value_offset double precision NOT NULL
            CHECK (value_offset > '-Infinity'::float8 AND value_offset < 'Infinity'::float8),
          CONSTRAINT pk_processing_mapping_profile_channel_binding PRIMARY KEY
            (organization_id, project_id, profile_revision_id, ordinal),
          CONSTRAINT uq_processing_mapping_profile_channel_source UNIQUE
            (organization_id, project_id, profile_revision_id, channel_key),
          CONSTRAINT uq_processing_mapping_profile_channel_target UNIQUE
            (organization_id, project_id, profile_revision_id, target_quantity),
          CONSTRAINT fk_processing_mapping_profile_channel_revision FOREIGN KEY
            (organization_id, project_id, classification, profile_id, profile_revision_id)
            REFERENCES processing.mapping_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_mapping_profile_channel_units CHECK
            (cardinality(accepted_normalized_units) BETWEEN 1 AND 32)
        );

        CREATE TABLE processing.mapping_profile_attribute_binding (
          organization_id uuid NOT NULL, project_id uuid NOT NULL,
          classification varchar(64) NOT NULL, profile_id uuid NOT NULL,
          profile_revision_id uuid NOT NULL, ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 127),
          attribute_definition_id uuid NOT NULL, attribute_definition_revision_id uuid NOT NULL,
          target_quantity varchar(160) NOT NULL,
          accepted_normalized_units varchar(160)[] NOT NULL, required boolean NOT NULL,
          CONSTRAINT pk_processing_mapping_profile_attribute_binding PRIMARY KEY
            (organization_id, project_id, profile_revision_id, ordinal),
          CONSTRAINT uq_processing_mapping_profile_attribute_source UNIQUE
            (organization_id, project_id, profile_revision_id, attribute_definition_revision_id),
          CONSTRAINT uq_processing_mapping_profile_attribute_target UNIQUE
            (organization_id, project_id, profile_revision_id, target_quantity),
          CONSTRAINT fk_processing_mapping_profile_attribute_profile_revision FOREIGN KEY
            (organization_id, project_id, classification, profile_id, profile_revision_id)
            REFERENCES processing.mapping_profile_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT fk_processing_mapping_profile_attribute_exact_revision FOREIGN KEY
            (organization_id, project_id, classification, attribute_definition_id,
             attribute_definition_revision_id) REFERENCES catalog.attribute_definition_revision
            (organization_id, project_id, classification, aggregate_id, id),
          CONSTRAINT ck_processing_mapping_profile_attribute_units CHECK
            (cardinality(accepted_normalized_units) BETWEEN 1 AND 32)
        );
        """
    )
    op.execute(
        "CREATE TRIGGER processing_mapping_profile_head_only BEFORE UPDATE OR DELETE "
        "ON processing.mapping_profile FOR EACH ROW "
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
        "ALTER TABLE processing.mapping_profile DROP CONSTRAINT "
        "fk_processing_mapping_profile_current"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE processing.{table}")

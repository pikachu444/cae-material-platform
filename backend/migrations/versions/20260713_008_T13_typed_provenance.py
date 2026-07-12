"""T-13 typed provenance nodes, relations, completeness, cycles, and RLS.

Revision ID: 20260713_008_t13
Revises: 20260712_007_t10
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260713_008_t13"
down_revision = "20260712_007_t10"
branch_labels = None
depends_on = None

_CLASSIFICATIONS = ("internal", "confidential", "restricted", "export_controlled")
_ENTITY_REFERENCE_KINDS = ("raw_asset", "artifact", "revision")
_GENERATION_REQUIREMENTS = ("none", "primary")
_ACTIVITY_STATUSES = ("succeeded", "failed", "cancelled")
_AGENT_TYPES = ("user", "service", "plugin_package", "organization")


def _quoted(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _scope_columns() -> tuple[sa.Column[object], ...]:
    uuid = postgresql.UUID(as_uuid=True)
    return (
        sa.Column("organization_id", uuid, nullable=False),
        sa.Column("project_id", uuid, nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
    )


def _recording_columns() -> tuple[sa.Column[object], ...]:
    uuid = postgresql.UUID(as_uuid=True)
    return (
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid, nullable=False),
    )


def _classified_reference(name: str, table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", "project_id", "classification", column],
        [
            f"provenance.{table}.organization_id",
            f"provenance.{table}.project_id",
            f"provenance.{table}.classification",
            f"provenance.{table}.id",
        ],
        name=name,
        ondelete="RESTRICT",
    )


def _recorded_by_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["recorded_by"],
        ["identity.principal.id"],
        name=name,
        ondelete="RESTRICT",
    )


def _create_nodes() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    namespaced = r"^[a-z][a-z0-9]*([._-][a-z0-9]+)+$"

    op.create_table(
        "entity",
        *_scope_columns(),
        sa.Column("id", uuid, nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("reference_kind", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=100), nullable=False),
        sa.Column("reference_id", uuid, nullable=False),
        sa.Column("content_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("generation_requirement", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_recording_columns(),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND reference_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND recorded_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_provenance_entity_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_provenance_entity_classification",
        ),
        sa.CheckConstraint(
            f"entity_type ~ '{namespaced}' AND reference_type ~ '{namespaced}'",
            name="ck_provenance_entity_types",
        ),
        sa.CheckConstraint(
            f"reference_kind IN ({_quoted(_ENTITY_REFERENCE_KINDS)})",
            name="ck_provenance_entity_reference_kind",
        ),
        sa.CheckConstraint(
            f"generation_requirement IN ({_quoted(_GENERATION_REQUIREMENTS)})",
            name="ck_provenance_entity_generation_requirement",
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_provenance_entity_digest",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255 AND trace_id = btrim(trace_id)",
            name="ck_provenance_entity_trace",
        ),
        sa.CheckConstraint(
            "(reference_kind = 'raw_asset' "
            "AND reference_type = 'artifact.raw_asset' "
            "AND generation_requirement = 'none') OR "
            "(reference_kind = 'artifact' "
            "AND reference_type = 'artifact.artifact' "
            "AND generation_requirement = 'primary') OR "
            "(reference_kind = 'revision' "
            "AND reference_type NOT IN ('aggregate.head', 'aggregate.latest') "
            "AND generation_requirement = 'primary')",
            name="ck_provenance_entity_immutable_reference",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_provenance_entity"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_provenance_entity_classified_ref",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "reference_kind",
            "reference_type",
            "reference_id",
            name="uq_provenance_entity_domain_ref",
        ),
        _recorded_by_fk("fk_provenance_entity_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_entity_digest",
        "entity",
        ["organization_id", "project_id", "content_sha256"],
        schema="provenance",
    )

    op.create_table(
        "activity",
        *_scope_columns(),
        sa.Column("id", uuid, nullable=False),
        sa.Column("activity_type", sa.String(length=100), nullable=False),
        sa.Column("domain_run_type", sa.String(length=100), nullable=False),
        sa.Column("domain_run_id", uuid, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_required", sa.Boolean(), nullable=False),
        sa.Column("output_required", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submission_digest", sa.CHAR(length=64), nullable=False),
        *_recording_columns(),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND domain_run_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND recorded_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_provenance_activity_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_provenance_activity_classification",
        ),
        sa.CheckConstraint(
            f"activity_type ~ '{namespaced}' AND domain_run_type ~ '{namespaced}'",
            name="ck_provenance_activity_types",
        ),
        sa.CheckConstraint(
            f"status IN ({_quoted(_ACTIVITY_STATUSES)})",
            name="ck_provenance_activity_status",
        ),
        sa.CheckConstraint(
            "ended_at >= started_at",
            name="ck_provenance_activity_time",
        ),
        sa.CheckConstraint(
            "submission_digest ~ '^[0-9a-f]{64}$'",
            name="ck_provenance_activity_submission_digest",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255 AND trace_id = btrim(trace_id)",
            name="ck_provenance_activity_trace",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_provenance_activity"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_provenance_activity_classified_ref",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "domain_run_type",
            "domain_run_id",
            name="uq_provenance_activity_domain_run",
        ),
        _recorded_by_fk("fk_provenance_activity_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_activity_type_time",
        "activity",
        ["organization_id", "project_id", "activity_type", "started_at"],
        schema="provenance",
    )

    op.create_table(
        "agent",
        *_scope_columns(),
        sa.Column("id", uuid, nullable=False),
        sa.Column("agent_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", uuid, nullable=False),
        *_recording_columns(),
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND organization_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND reference_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND recorded_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND request_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_provenance_agent_nonzero_ids",
        ),
        sa.CheckConstraint(
            f"classification IN ({_quoted(_CLASSIFICATIONS)})",
            name="ck_provenance_agent_classification",
        ),
        sa.CheckConstraint(
            f"agent_type IN ({_quoted(_AGENT_TYPES)})",
            name="ck_provenance_agent_type",
        ),
        sa.CheckConstraint(
            "length(btrim(trace_id)) BETWEEN 1 AND 255 AND trace_id = btrim(trace_id)",
            name="ck_provenance_agent_trace",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "id", name="pk_provenance_agent"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "id",
            name="uq_provenance_agent_classified_ref",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "classification",
            "agent_type",
            "reference_id",
            name="uq_provenance_agent_reference",
        ),
        _recorded_by_fk("fk_provenance_agent_recorded_by"),
        schema="provenance",
    )


def _create_relations() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    token_check = "^[a-z][a-z0-9_.-]{0,99}$"

    op.create_table(
        "usage",
        *_scope_columns(),
        sa.Column("activity_id", uuid, nullable=False),
        sa.Column("entity_id", uuid, nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        *_recording_columns(),
        sa.CheckConstraint("role ~ '" + token_check + "'", name="ck_provenance_usage_role"),
        sa.CheckConstraint("ordinal >= 0", name="ck_provenance_usage_ordinal"),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "activity_id",
            "entity_id",
            "role",
            name="pk_provenance_usage",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "activity_id",
            "role",
            "ordinal",
            name="uq_provenance_usage_position",
        ),
        _classified_reference(
            "fk_provenance_usage_activity", "activity", "activity_id"
        ),
        _classified_reference("fk_provenance_usage_entity", "entity", "entity_id"),
        _recorded_by_fk("fk_provenance_usage_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_usage_entity",
        "usage",
        ["organization_id", "project_id", "entity_id", "activity_id"],
        schema="provenance",
    )

    op.create_table(
        "generation",
        *_scope_columns(),
        sa.Column("entity_id", uuid, nullable=False),
        sa.Column("activity_id", uuid, nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        *_recording_columns(),
        sa.CheckConstraint(
            "role ~ '" + token_check + "'", name="ck_provenance_generation_role"
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "entity_id",
            name="pk_provenance_generation",
        ),
        _classified_reference(
            "fk_provenance_generation_entity", "entity", "entity_id"
        ),
        _classified_reference(
            "fk_provenance_generation_activity", "activity", "activity_id"
        ),
        _recorded_by_fk("fk_provenance_generation_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_generation_activity",
        "generation",
        ["organization_id", "project_id", "activity_id", "entity_id"],
        schema="provenance",
    )

    op.create_table(
        "derivation",
        *_scope_columns(),
        sa.Column("generated_entity_id", uuid, nullable=False),
        sa.Column("used_entity_id", uuid, nullable=False),
        sa.Column("activity_id", uuid, nullable=True),
        sa.Column("derivation_kind", sa.String(length=100), nullable=False),
        *_recording_columns(),
        sa.CheckConstraint(
            "generated_entity_id <> used_entity_id",
            name="ck_provenance_derivation_distinct",
        ),
        sa.CheckConstraint(
            "derivation_kind ~ '" + token_check + "'",
            name="ck_provenance_derivation_kind",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "generated_entity_id",
            "used_entity_id",
            "derivation_kind",
            name="pk_provenance_derivation",
        ),
        _classified_reference(
            "fk_provenance_derivation_generated", "entity", "generated_entity_id"
        ),
        _classified_reference(
            "fk_provenance_derivation_used", "entity", "used_entity_id"
        ),
        _classified_reference(
            "fk_provenance_derivation_activity", "activity", "activity_id"
        ),
        _recorded_by_fk("fk_provenance_derivation_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_derivation_used",
        "derivation",
        ["organization_id", "project_id", "used_entity_id", "generated_entity_id"],
        schema="provenance",
    )

    op.create_table(
        "association",
        *_scope_columns(),
        sa.Column("activity_id", uuid, nullable=False),
        sa.Column("agent_id", uuid, nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("plan_entity_id", uuid, nullable=True),
        *_recording_columns(),
        sa.CheckConstraint(
            "role ~ '" + token_check + "'", name="ck_provenance_association_role"
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "activity_id",
            "agent_id",
            "role",
            name="pk_provenance_association",
        ),
        _classified_reference(
            "fk_provenance_association_activity", "activity", "activity_id"
        ),
        _classified_reference("fk_provenance_association_agent", "agent", "agent_id"),
        _classified_reference(
            "fk_provenance_association_plan", "entity", "plan_entity_id"
        ),
        _recorded_by_fk("fk_provenance_association_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_association_agent",
        "association",
        ["organization_id", "project_id", "agent_id", "activity_id"],
        schema="provenance",
    )

    op.create_table(
        "revision",
        *_scope_columns(),
        sa.Column("newer_entity_id", uuid, nullable=False),
        sa.Column("prior_entity_id", uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        *_recording_columns(),
        sa.CheckConstraint(
            "newer_entity_id <> prior_entity_id",
            name="ck_provenance_revision_distinct",
        ),
        sa.CheckConstraint(
            "length(btrim(change_reason)) BETWEEN 1 AND 2000 "
            "AND change_reason = btrim(change_reason)",
            name="ck_provenance_revision_reason",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "newer_entity_id",
            name="pk_provenance_revision",
        ),
        _classified_reference(
            "fk_provenance_revision_newer", "entity", "newer_entity_id"
        ),
        _classified_reference(
            "fk_provenance_revision_prior", "entity", "prior_entity_id"
        ),
        _recorded_by_fk("fk_provenance_revision_recorded_by"),
        schema="provenance",
    )
    op.create_index(
        "ix_provenance_revision_prior",
        "revision",
        ["organization_id", "project_id", "prior_entity_id", "newer_entity_id"],
        schema="provenance",
    )

    op.create_table(
        "attribution",
        *_scope_columns(),
        sa.Column("entity_id", uuid, nullable=False),
        sa.Column("agent_id", uuid, nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        *_recording_columns(),
        sa.CheckConstraint(
            "role ~ '" + token_check + "'", name="ck_provenance_attribution_role"
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "entity_id",
            "agent_id",
            "role",
            name="pk_provenance_attribution",
        ),
        _classified_reference(
            "fk_provenance_attribution_entity", "entity", "entity_id"
        ),
        _classified_reference(
            "fk_provenance_attribution_agent", "agent", "agent_id"
        ),
        _recorded_by_fk("fk_provenance_attribution_recorded_by"),
        schema="provenance",
    )


def _create_reference_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION provenance.guard_entity_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.reference_kind = 'raw_asset' AND NOT EXISTS (
            SELECT 1
            FROM artifact.raw_asset AS source
            WHERE source.organization_id = NEW.organization_id
              AND source.project_id = NEW.project_id
              AND source.classification = NEW.classification
              AND source.id = NEW.reference_id
              AND source.sha256 = NEW.content_sha256
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23503',
              MESSAGE = 'provenance Raw Asset reference is absent or differs from immutable facts';
          ELSIF NEW.reference_kind = 'artifact' AND NOT EXISTS (
            SELECT 1
            FROM artifact.artifact AS source
            WHERE source.organization_id = NEW.organization_id
              AND source.project_id = NEW.project_id
              AND source.classification = NEW.classification
              AND source.id = NEW.reference_id
              AND source.sha256 = NEW.content_sha256
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23503',
              MESSAGE = 'provenance Artifact reference is absent or differs from immutable facts';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_entity_insert_guard
        BEFORE INSERT ON provenance.entity
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_entity_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_agent_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.agent_type IN ('user', 'service') AND NOT EXISTS (
            SELECT 1
            FROM identity.principal AS principal
            WHERE principal.id = NEW.reference_id
              AND principal.principal_type = NEW.agent_type
              AND principal.active
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23503',
              MESSAGE = 'provenance principal Agent is absent, inactive, or has another type';
          ELSIF NEW.agent_type = 'plugin_package' AND NOT EXISTS (
            SELECT 1
            FROM plugin.package AS package
            WHERE package.organization_id = NEW.organization_id
              AND package.project_id = NEW.project_id
              AND package.classification = NEW.classification
              AND package.id = NEW.reference_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23503',
              MESSAGE = 'provenance Plugin Package Agent is absent or outside scope';
          ELSIF NEW.agent_type = 'organization'
             AND NEW.reference_id <> NEW.organization_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'organization Agent must reference the owning organization';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_agent_insert_guard
        BEFORE INSERT ON provenance.agent
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_agent_insert()
        """
    )


def _create_cycle_and_relation_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION provenance.entity_depends_on(
          p_organization_id uuid,
          p_project_id uuid,
          p_start_entity_id uuid,
          p_target_entity_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
          WITH RECURSIVE edges(child_id, parent_id) AS (
            SELECT generated_entity_id, used_entity_id
            FROM provenance.derivation
            WHERE organization_id = p_organization_id
              AND project_id = p_project_id
            UNION
            SELECT generation.entity_id, usage.entity_id
            FROM provenance.generation AS generation
            JOIN provenance.usage AS usage
              ON usage.organization_id = generation.organization_id
             AND usage.project_id = generation.project_id
             AND usage.classification = generation.classification
             AND usage.activity_id = generation.activity_id
            WHERE generation.organization_id = p_organization_id
              AND generation.project_id = p_project_id
            UNION
            SELECT newer_entity_id, prior_entity_id
            FROM provenance.revision
            WHERE organization_id = p_organization_id
              AND project_id = p_project_id
          ), walk(entity_id) AS (
            SELECT p_start_entity_id
            UNION
            SELECT edges.parent_id
            FROM walk
            JOIN edges ON edges.child_id = walk.entity_id
          )
          SELECT EXISTS(
            SELECT 1 FROM walk WHERE entity_id = p_target_entity_id
          )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_usage_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          output_id uuid;
        BEGIN
          FOR output_id IN
            SELECT entity_id
            FROM provenance.generation
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.activity_id
          LOOP
            IF provenance.entity_depends_on(
              NEW.organization_id, NEW.project_id, NEW.entity_id, output_id
            ) THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'usage-generation relation would create a provenance cycle';
            END IF;
          END LOOP;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_usage_insert_guard
        BEFORE INSERT ON provenance.usage
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_usage_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_generation_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          input_id uuid;
          activity_start timestamptz;
          activity_end timestamptz;
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM provenance.entity
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND id = NEW.entity_id
              AND generation_requirement = 'primary'
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'primary generation requires a generated immutable Entity';
          END IF;
          SELECT started_at, ended_at INTO activity_start, activity_end
          FROM provenance.activity
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.activity_id;
          IF NEW.generated_at < activity_start OR NEW.generated_at > activity_end THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'generation time must fall within the Activity interval';
          END IF;
          FOR input_id IN
            SELECT entity_id
            FROM provenance.usage
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.activity_id
          LOOP
            IF provenance.entity_depends_on(
              NEW.organization_id, NEW.project_id, input_id, NEW.entity_id
            ) THEN
              RAISE EXCEPTION USING ERRCODE = '23514',
                MESSAGE = 'usage-generation relation would create a provenance cycle';
            END IF;
          END LOOP;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_generation_insert_guard
        BEFORE INSERT ON provenance.generation
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_generation_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_derivation_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF provenance.entity_depends_on(
            NEW.organization_id,
            NEW.project_id,
            NEW.used_entity_id,
            NEW.generated_entity_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'derivation relation would create a provenance cycle';
          END IF;
          IF NEW.activity_id IS NOT NULL AND (
            NOT EXISTS (
              SELECT 1 FROM provenance.generation
              WHERE organization_id = NEW.organization_id
                AND project_id = NEW.project_id
                AND activity_id = NEW.activity_id
                AND entity_id = NEW.generated_entity_id
            ) OR NOT EXISTS (
              SELECT 1 FROM provenance.usage
              WHERE organization_id = NEW.organization_id
                AND project_id = NEW.project_id
                AND activity_id = NEW.activity_id
                AND entity_id = NEW.used_entity_id
            )
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Activity derivation requires matching usage and generation';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_derivation_insert_guard
        BEFORE INSERT ON provenance.derivation
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_derivation_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_revision_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          newer_type text;
          prior_type text;
          generation_activity_id uuid;
        BEGIN
          SELECT reference_type INTO newer_type
          FROM provenance.entity
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.newer_entity_id
            AND reference_kind = 'revision';
          SELECT reference_type INTO prior_type
          FROM provenance.entity
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND id = NEW.prior_entity_id
            AND reference_kind = 'revision';
          IF newer_type IS NULL OR prior_type IS NULL OR newer_type <> prior_type THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'wasRevisionOf requires two immutable revisions of one type';
          END IF;
          IF provenance.entity_depends_on(
            NEW.organization_id,
            NEW.project_id,
            NEW.prior_entity_id,
            NEW.newer_entity_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'revision relation would create a provenance cycle';
          END IF;
          SELECT activity_id INTO generation_activity_id
          FROM provenance.generation
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND entity_id = NEW.newer_entity_id;
          IF generation_activity_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM provenance.usage
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = generation_activity_id
              AND entity_id = NEW.prior_entity_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'revision relation requires generation that used the prior revision';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_revision_insert_guard
        BEFORE INSERT ON provenance.revision
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_revision_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.guard_association_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.plan_entity_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM provenance.usage
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.activity_id
              AND entity_id = NEW.plan_entity_id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'association plan Entity must be used by the Activity';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER provenance_association_insert_guard
        BEFORE INSERT ON provenance.association
        FOR EACH ROW EXECUTE FUNCTION provenance.guard_association_insert()
        """
    )


def _create_completeness_and_immutability() -> None:
    op.execute(
        """
        CREATE FUNCTION provenance.assert_entity_complete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.generation_requirement = 'primary' AND NOT EXISTS (
            SELECT 1 FROM provenance.generation
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND entity_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'generated Entity requires exactly one primary generation';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER provenance_entity_completeness
        AFTER INSERT ON provenance.entity
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION provenance.assert_entity_complete()
        """
    )
    op.execute(
        """
        CREATE FUNCTION provenance.assert_activity_complete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.input_required AND NOT EXISTS (
            SELECT 1 FROM provenance.usage
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Activity requires at least one immutable input usage';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM provenance.association
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'Activity requires at least one responsible Agent';
          END IF;
          IF NEW.output_required AND NOT EXISTS (
            SELECT 1 FROM provenance.generation
            WHERE organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND activity_id = NEW.id
          ) THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'successful Activity requires a generated output';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER provenance_activity_completeness
        AFTER INSERT ON provenance.activity
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION provenance.assert_activity_complete()
        """
    )
    for table in (
        "entity",
        "activity",
        "agent",
        "usage",
        "generation",
        "derivation",
        "association",
        "revision",
        "attribution",
    ):
        op.execute(
            f"""
            CREATE TRIGGER provenance_{table}_immutable
            BEFORE UPDATE OR DELETE ON provenance.{table}
            FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation()
            """
        )


def _secure_tables() -> None:
    for table in (
        "entity",
        "activity",
        "agent",
        "usage",
        "generation",
        "derivation",
        "association",
        "revision",
        "attribution",
    ):
        op.execute(f"ALTER TABLE provenance.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE provenance.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_select
            ON provenance.{table} FOR SELECT
            USING (
              access_control.can_access_row(
                organization_id, project_id, classification, 'provenance.read'
              )
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_authorized_insert
            ON provenance.{table} FOR INSERT
            WITH CHECK (
              recorded_by = access_control.current_principal_id()
              AND access_control.can_access_row(
                organization_id, project_id, classification, 'provenance.write'
              )
            )
            """
        )


def upgrade() -> None:
    op.execute("CREATE SCHEMA provenance")
    _create_nodes()
    _create_relations()
    _create_reference_guards()
    _create_cycle_and_relation_guards()
    _create_completeness_and_immutability()
    _secure_tables()


def downgrade() -> None:
    op.execute("DROP FUNCTION provenance.assert_activity_complete() CASCADE")
    op.execute("DROP FUNCTION provenance.assert_entity_complete() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_association_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_revision_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_derivation_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_generation_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_usage_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.entity_depends_on(uuid, uuid, uuid, uuid) CASCADE")
    op.execute("DROP FUNCTION provenance.guard_agent_insert() CASCADE")
    op.execute("DROP FUNCTION provenance.guard_entity_insert() CASCADE")
    op.drop_table("attribution", schema="provenance")
    op.drop_table("revision", schema="provenance")
    op.drop_table("association", schema="provenance")
    op.drop_table("derivation", schema="provenance")
    op.drop_table("generation", schema="provenance")
    op.drop_table("usage", schema="provenance")
    op.drop_table("agent", schema="provenance")
    op.drop_table("activity", schema="provenance")
    op.drop_table("entity", schema="provenance")
    op.execute("DROP SCHEMA provenance")

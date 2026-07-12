"""T-14 security-invoker lineage and completeness read models.

Revision ID: 20260713_009_t14
Revises: 20260713_008_t13
Create Date: 2026-07-13
"""

from __future__ import annotations

from alembic import op

revision = "20260713_009_t14"
down_revision = "20260713_008_t13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW provenance.dependency_edge
        WITH (security_barrier = true, security_invoker = true)
        AS
          SELECT
            derivation.organization_id,
            derivation.project_id,
            derivation.classification,
            derivation.generated_entity_id AS child_entity_id,
            derivation.used_entity_id AS parent_entity_id,
            'derivation'::text AS relation,
            derivation.activity_id
          FROM provenance.derivation
        UNION
          SELECT
            generation.organization_id,
            generation.project_id,
            generation.classification,
            generation.entity_id AS child_entity_id,
            usage.entity_id AS parent_entity_id,
            'usage_generation'::text AS relation,
            generation.activity_id
          FROM provenance.generation
          JOIN provenance.usage
            ON usage.organization_id = generation.organization_id
           AND usage.project_id = generation.project_id
           AND usage.classification = generation.classification
           AND usage.activity_id = generation.activity_id
        UNION
          SELECT
            revision.organization_id,
            revision.project_id,
            revision.classification,
            revision.newer_entity_id AS child_entity_id,
            revision.prior_entity_id AS parent_entity_id,
            'revision'::text AS relation,
            generation.activity_id
          FROM provenance.revision
          JOIN provenance.generation
            ON generation.organization_id = revision.organization_id
           AND generation.project_id = revision.project_id
           AND generation.classification = revision.classification
           AND generation.entity_id = revision.newer_entity_id
        """
    )
    op.execute(
        """
        CREATE VIEW provenance.entity_completeness
        WITH (security_barrier = true, security_invoker = true)
        AS
          SELECT
            entity.organization_id,
            entity.project_id,
            entity.classification,
            entity.id AS entity_id,
            entity.generation_requirement,
            generation.activity_id AS generation_activity_id,
            (
              entity.generation_requirement = 'none'
              OR generation.activity_id IS NOT NULL
            ) AS generation_complete
          FROM provenance.entity
          LEFT JOIN provenance.generation
            ON generation.organization_id = entity.organization_id
           AND generation.project_id = entity.project_id
           AND generation.classification = entity.classification
           AND generation.entity_id = entity.id
        """
    )
    op.execute(
        """
        CREATE VIEW provenance.activity_completeness
        WITH (security_barrier = true, security_invoker = true)
        AS
          SELECT
            activity.organization_id,
            activity.project_id,
            activity.classification,
            activity.id AS activity_id,
            (
              NOT activity.input_required
              OR EXISTS (
                SELECT 1 FROM provenance.usage
                WHERE usage.organization_id = activity.organization_id
                  AND usage.project_id = activity.project_id
                  AND usage.classification = activity.classification
                  AND usage.activity_id = activity.id
              )
            ) AS input_complete,
            EXISTS (
              SELECT 1 FROM provenance.association
              WHERE association.organization_id = activity.organization_id
                AND association.project_id = activity.project_id
                AND association.classification = activity.classification
                AND association.activity_id = activity.id
            ) AS agent_complete,
            (
              NOT activity.output_required
              OR EXISTS (
                SELECT 1 FROM provenance.generation
                WHERE generation.organization_id = activity.organization_id
                  AND generation.project_id = activity.project_id
                  AND generation.classification = activity.classification
                  AND generation.activity_id = activity.id
              )
            ) AS output_complete
          FROM provenance.activity
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW provenance.activity_completeness")
    op.execute("DROP VIEW provenance.entity_completeness")
    op.execute("DROP VIEW provenance.dependency_edge")

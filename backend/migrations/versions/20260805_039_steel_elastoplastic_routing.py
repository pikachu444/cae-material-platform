"""Require metal-classified source revisions for reference plasticity IRs.

Revision ID: 20260805_039_steel
Revises: 20260804_038_catalog
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260805_039_steel"
down_revision: str | None = "20260804_038_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABULATED_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
_VOCE_TABULATED_FAMILY = "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION modeling.guard_metal_plasticity_source() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE source_class text;
        BEGIN
          IF NEW.model_family_id NOT IN ('{_TABULATED_FAMILY}', '{_VOCE_TABULATED_FAMILY}') THEN
            RETURN NEW;
          END IF;
          SELECT COALESCE(material_class, 'unclassified') INTO source_class
          FROM catalog.material_revision
          WHERE organization_id = NEW.organization_id
            AND project_id = NEW.project_id
            AND classification = NEW.classification
            AND aggregate_id = NEW.material_id
            AND id = NEW.material_revision_id;
          IF source_class IS DISTINCT FROM 'metal' THEN
            RAISE EXCEPTION USING ERRCODE = '23514',
              MESSAGE = 'reference plasticity IR requires a metal-classified Material revision';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER modeling_material_model_metal_plasticity_guard "
        "BEFORE INSERT ON modeling.material_model_revision FOR EACH ROW "
        "EXECUTE FUNCTION modeling.guard_metal_plasticity_source()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS modeling_material_model_metal_plasticity_guard "
        "ON modeling.material_model_revision"
    )
    op.execute("DROP FUNCTION IF EXISTS modeling.guard_metal_plasticity_source()")

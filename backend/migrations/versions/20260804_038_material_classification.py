"""Add governed Material classification without rewriting legacy revisions.

Revision ID: 20260804_038_catalog
Revises: 20260803_037_p1
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_038_catalog"
down_revision: str | None = "20260803_037_p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASSES = (
    "unclassified",
    "metal",
    "polymer",
    "elastomer",
    "composite",
    "ceramic",
    "other",
)


def upgrade() -> None:
    op.add_column(
        "material_revision",
        sa.Column("material_class", sa.String(length=32), nullable=True),
        schema="catalog",
    )
    allowed = ",".join(f"'{value}'" for value in _CLASSES)
    op.create_check_constraint(
        "ck_catalog_material_revision_schema_class",
        "material_revision",
        "(schema_version <> '2.0.0' AND material_class IS NULL) OR "
        f"(schema_version = '2.0.0' AND material_class IN ({allowed}))",
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_material_revision_class",
        "material_revision",
        ["organization_id", "project_id", "classification", "material_class", "created_at"],
        schema="catalog",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM catalog.material_revision WHERE schema_version = '2.0.0'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade Material classification while immutable schema v2 revisions exist';
          END IF;
        END $$
        """
    )
    op.drop_index(
        "ix_catalog_material_revision_class",
        table_name="material_revision",
        schema="catalog",
    )
    op.drop_constraint(
        "ck_catalog_material_revision_schema_class",
        "material_revision",
        schema="catalog",
        type_="check",
    )
    op.drop_column("material_revision", "material_class", schema="catalog")

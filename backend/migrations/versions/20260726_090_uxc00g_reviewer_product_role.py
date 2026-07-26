"""Add the fixed Reviewer product role without rewriting access history.

Revision ID: 20260726_090_uxc00g
Revises: 20260726_089_uxc06c2
"""

from __future__ import annotations

from alembic import op

revision = "20260726_090_uxc00g"
down_revision = "20260726_089_uxc06c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing User and Administrator rows are append-only history. Widen the role
    # vocabulary in place; do not backfill a Reviewer from an old feature combination.
    op.drop_constraint(
        "ck_product_access_role", "product_access_assignment", schema="identity"
    )
    op.create_check_constraint(
        "ck_product_access_role",
        "product_access_assignment",
        "product_role IN ('administrator', 'reviewer', 'user')",
        schema="identity",
    )
    op.create_check_constraint(
        "ck_product_access_reviewer_features",
        "product_access_assignment",
        "product_role <> 'reviewer' OR "
        "(NOT schema_configuration AND NOT catalog_edit "
        "AND processing_calibration AND model_approval AND solver_card_export)",
        schema="identity",
    )


def downgrade() -> None:
    # Refuse a lossy downgrade. A reviewer assignment is immutable evidence and must
    # be revoked explicitly before an operator returns to the older vocabulary.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM identity.product_access_assignment
            WHERE product_role = 'reviewer'
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade UXC-00G while Reviewer product assignments exist; revoke them explicitly first';
          END IF;
        END
        $$
        """
    )
    op.drop_constraint(
        "ck_product_access_reviewer_features",
        "product_access_assignment",
        schema="identity",
    )
    op.drop_constraint(
        "ck_product_access_role", "product_access_assignment", schema="identity"
    )
    op.create_check_constraint(
        "ck_product_access_role",
        "product_access_assignment",
        "product_role IN ('administrator', 'user')",
        schema="identity",
    )

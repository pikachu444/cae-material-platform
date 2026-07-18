"""Allow the exact-domain binding validator to inspect cross-module revisions.

Revision ID: 20260913_078_t65_binding_rls
Revises: 20260912_077_t64_export

Traceability: T-65.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260913_078_t65_binding_rls"
down_revision: str | None = "20260912_077_t64_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The function only evaluates a fully scoped equality predicate and returns no target data.
    # SECURITY DEFINER is required because a catalog.write decision deliberately does not grant
    # direct SELECT on Dataset, Processing, Modeling, Exporting, or Governance tables.
    op.execute(
        """
        ALTER FUNCTION catalog.validate_domain_record_binding() SECURITY DEFINER;
        ALTER FUNCTION catalog.validate_domain_record_binding()
          SET search_path = pg_catalog;
        REVOKE ALL ON FUNCTION catalog.validate_domain_record_binding() FROM PUBLIC;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER FUNCTION catalog.validate_domain_record_binding() SECURITY INVOKER;
        ALTER FUNCTION catalog.validate_domain_record_binding() RESET search_path;
        GRANT EXECUTE ON FUNCTION catalog.validate_domain_record_binding() TO PUBLIC;
        """
    )

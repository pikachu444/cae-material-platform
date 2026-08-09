from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/20260925_094_issue160_review_publication.py"


def test_issue160_migration_renders_review_projection_and_versioned_admin_transition() -> None:
    output = StringIO()
    command.upgrade(Config(str(ROOT / "alembic.ini"), output_buffer=output), "head", sql=True)
    sql = output.getvalue()

    for fragment in (
        "ALTER TABLE governance.review_request ADD COLUMN subject_evidence JSONB",
        "requested_by_display_name",
        "CREATE TABLE governance.review_publication_projection",
        "record_table_id uuid NOT NULL",
        "record_table_revision_id uuid NOT NULL",
        "ALTER TABLE governance.review_publication_projection FORCE ROW LEVEL SECURITY",
        "CREATE POLICY review_publication_projection_select",
        "'catalog.read'",
        "CREATE POLICY review_publication_projection_insert",
        "DROP CONSTRAINT IF EXISTS uq_catalog_domain_binding_record_revision",
        "uq_catalog_domain_binding_exact_revision",
        "ck_product_access_preset_version",
        "ck_product_access_admin_v1_legacy",
        "ck_product_access_admin_v2_corrected",
        "product_access_assignment_preset_version_guard",
        "Issue #160: corrected Administrator preset transition",
    ):
        assert fragment in sql


def test_issue160_transition_is_append_only_and_downgrade_refuses_lossy_reversal() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert text.index("ck_product_access_admin_transition") < text.index(
        'op.drop_constraint(\n        "ck_product_access_administrator_features"'
    )
    assert "revoked_at IS NOT NULL AND revoked_by IS NOT NULL" in text
    assert "revocation_reason IS NOT NULL" in text
    assert "successor := md5('issue160:administrator:v2:'" in text
    assert "DELETE FROM identity.principal" not in text
    assert "Issue #160 downgrade refused: immutable transition evidence exists" in text
    assert "Issue #160 downgrade refused: multiple domain bindings share a Record revision" in text

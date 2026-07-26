from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "backend/migrations/versions/20260909_074_T59_product_access_assignments.py"
)
REVIEWER_MIGRATION = (
    ROOT / "backend/migrations/versions/20260726_090_uxc00g_reviewer_product_role.py"
)


def test_t59_migration_uses_explicit_product_access_columns_and_rls() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260909_074_t59"' in text
    assert 'down_revision: str | None = "20260908_073_t58_bulk"' in text
    for column in (
        "product_role",
        "schema_configuration",
        "catalog_edit",
        "processing_calibration",
        "model_approval",
        "solver_card_export",
    ):
        assert column in text
    assert "postgresql.JSONB" not in text
    assert "sa.JSON" not in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_product_access_assignment_mutation" in text
    assert "product_access_own_select" in text
    assert "product_access_manager_insert" in text


def test_t59_migration_has_complete_downgrade() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "DROP POLICY IF EXISTS" in text
    assert 'op.drop_table("product_access_assignment", schema="identity")' in text
    assert "DROP FUNCTION access_control.guard_product_access_assignment_mutation()" in text


def test_uxc00g_widens_roles_and_refuses_lossy_reviewer_downgrade() -> None:
    text = REVIEWER_MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260726_090_uxc00g"' in text
    assert 'down_revision = "20260726_089_uxc06c2"' in text
    assert "'administrator', 'reviewer', 'user'" in text
    assert "ck_product_access_reviewer_features" in text
    assert "NOT schema_configuration AND NOT catalog_edit" in text
    assert "processing_calibration AND model_approval AND solver_card_export" in text
    assert "cannot downgrade UXC-00G while Reviewer product assignments exist" in text

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
MIGRATION = ROOT / "backend/migrations/versions/20260917_082_T76_current_domain_bindings.py"


def test_t76_keeps_one_catalog_identity_while_allowing_exact_revision_bindings() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "CREATE TABLE catalog.domain_record_identity_binding" in text
    assert "pk_catalog_domain_identity_binding PRIMARY KEY" in text
    assert "record_id uuid NOT NULL" in text
    assert "DROP CONSTRAINT uq_catalog_domain_binding_domain_revision" in text
    assert "fk_catalog_domain_binding_identity_target" in text
    assert "domain_record_identity_binding_immutable" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text

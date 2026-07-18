from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / (
    "backend/migrations/versions/20260913_078_T65_domain_binding_rls_validator.py"
)


def test_t65_cross_module_validator_has_a_fixed_privilege_boundary() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260913_078_t65_binding_rls"' in text
    assert 'down_revision: str | None = "20260912_077_t64_export"' in text
    assert "catalog.validate_domain_record_binding() SECURITY DEFINER" in text
    assert "SET search_path = pg_catalog" in text
    assert "REVOKE ALL ON FUNCTION catalog.validate_domain_record_binding() FROM PUBLIC" in text
    assert "SECURITY INVOKER" in text
    assert "GRANT EXECUTE ON FUNCTION catalog.validate_domain_record_binding() TO PUBLIC" in text

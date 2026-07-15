from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_ogden_prony_ir_migration_is_typed_immutable_and_tenant_scoped() -> None:
    source = (ROOT / "backend/migrations/versions/20260812_046_ogden_prony_ir.py").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE modeling.ogden_prony_revision" in source
    assert "CREATE TABLE modeling.ogden_prony_term" in source
    assert "guard_ogden_prony_source" in source
    assert "validate_ogden_prony_terms" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "reject_immutable_row_mutation" in source
    assert "material_state_id, property_set_revision_id" in source
    assert "jsonb" not in source.lower()


def test_ogden_prony_card_migration_pins_source_terms_and_mapping_status() -> None:
    source = (ROOT / "backend/migrations/versions/20260813_047_ogden_prony_cards.py").read_text(
        encoding="utf-8"
    )
    assert "CREATE TABLE exporting.ogden_prony_solver_card_revision" in source
    assert "CREATE TABLE exporting.ogden_prony_solver_card_term" in source
    assert "validate_ogden_prony_card_terms" in source
    assert "volumetric_mapping_status IN ('exact','approximated')" in source
    assert "cmp.reference.abaqus-ogden-prony" in source
    assert "cmp.reference.openradioss-law62" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "jsonb" not in source.lower()

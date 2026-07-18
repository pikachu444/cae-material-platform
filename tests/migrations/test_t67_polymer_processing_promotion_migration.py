from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / (
    "backend/migrations/versions/20260914_079_T67_polymer_processing_promotion.py"
)


def test_t67_persists_typed_exact_processing_evidence_without_json_eav() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260914_079_t67_polymer"' in text
    assert 'down_revision: str | None = "20260913_078_t65_binding_rls"' in text
    assert "CREATE TABLE modeling.linear_viscoelastic_processing_evidence" in text
    assert "fk_modeling_linear_prony_processing_output" in text
    assert "fk_modeling_linear_prony_processing_source" in text
    assert "fk_modeling_linear_prony_processing_profile" in text
    assert "processing_output_revision_id uuid NOT NULL" in text
    assert "selected_term_count integer NOT NULL" in text
    assert "jsonb" not in text.lower()
    assert "value_json" not in text.lower()


def test_t67_enforces_immutable_ten_term_and_neutral_selection_contracts() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "term_count BETWEEN 1 AND 10" in text
    assert "ordinal BETWEEN 1 AND 10" in text
    assert "selection_kind='prony_processing_output'" in text
    assert "selected_series='modulus.prony.selected'" in text
    assert "instantaneous_modulus_relative_mismatch <=" in text
    assert "DEFERRABLE INITIALLY DEFERRED" in text
    assert "polymer.prony_fit_compare" in text
    assert "revisioning.reject_immutable_row_mutation()" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text

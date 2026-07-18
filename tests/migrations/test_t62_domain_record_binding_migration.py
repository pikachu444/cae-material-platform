from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "backend/migrations/versions/20260910_075_T62_domain_record_bindings.py"
)


def test_t62_migration_is_a_closed_typed_exact_revision_binding() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260910_075_t62_binding"' in text
    assert 'down_revision: str | None = "20260909_074_t59"' in text
    assert "catalog.catalog_record_revision" in text
    for target in (
        "catalog.material_revision",
        "catalog.material_state_revision",
        "testing.specimen_revision",
        "testing.test_run_revision",
        "datasets.test_data_document_revision",
        "processing.common_processing_output_revision",
        "modeling.material_model_revision",
        "modeling.neutral_material_revision",
        "exporting.solver_card_revision",
        "exporting.neutral_solver_card_revision",
        "governance.release_manifest",
    ):
        assert target in text
    assert "jsonb" not in text.lower()
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "revisioning.reject_immutable_row_mutation" in text


def test_t62_migration_rejects_latest_aliases_and_cross_scope_targets() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "domain_revision_id uuid NOT NULL" in text
    assert "organization_id,NEW.project_id,NEW.classification" in text
    assert "domain binding target must be an exact revision in the same scope" in text
    assert "DROP TABLE catalog.domain_record_binding" in text

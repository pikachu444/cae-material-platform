from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20260930_099_issue209_dma_fld_import.py"
)


def test_issue209_migration_adds_only_typed_dma_fld_import_state() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "dma_frequency_temperature_sweep" in source
    assert "forming_limit_diagram" in source
    for quantity in (
        "temperature",
        "frequency",
        "storage_modulus",
        "loss_modulus",
        "tan_delta",
        "minor_strain",
        "major_strain",
    ):
        assert quantity in source
    assert "ordinal BETWEEN 0 AND 4" in source
    assert "idempotency_key varchar(255)" in source
    assert "request_sha256 char(64)" in source
    assert "UNIQUE (organization_id, project_id, idempotency_key)" in source
    assert "column_name varchar(255)" in source
    assert "channel_key varchar(64)" in source
    assert "recovery_hint varchar(500)" in source
    assert "ALTER COLUMN record_id DROP NOT NULL" in source
    assert "ADD COLUMN material_id uuid" in source
    assert "ADD COLUMN material_revision_id uuid" in source
    assert "ck_review_publication_material_revision_pair" in source
    assert "ck_review_publication_record_target" in source
    assert "ck_review_publication_exact_target" in source
    assert "direct governed Material review projections exist" in source
    assert "DISABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "jsonb" not in source.lower()
    assert "dma_strain_sweep" not in source


def test_issue209_migration_preserves_terminal_run_immutability() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "terminal tabular Import Runs are immutable" in source
    assert "NEW.idempotency_key<>OLD.idempotency_key" in source
    assert "NEW.request_sha256<>OLD.request_sha256" in source
    assert "datasets_tabular_import_run_guard" in source

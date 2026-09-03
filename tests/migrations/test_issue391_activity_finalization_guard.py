from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20261008_107_issue391_dma_tts_sweep_ordinal.py"
)


def _upgrade_source() -> str:
    source = MIGRATION.read_text(encoding="utf-8")
    return source[source.index("def upgrade()") : source.index("def downgrade()")]


def test_issue391_guard_retains_general_semantic_specialization() -> None:
    source = _upgrade_source()

    assert "general_semantic_specialization" in source
    assert "dma_semantic_specialization" in source
    assert "NEW.activity_type ~ '^(processing|statistics)\\\\.'" in source
    assert "NEW.activity_type <> 'processing.dma_frequency_master_curve'" in source
    assert "NEW.domain_run_type IS NOT NULL" in source
    assert "NEW.domain_run_id IS NOT NULL" in source
    assert source.count("NOT (general_semantic_specialization OR dma_semantic_specialization)") == 3
    assert "OLD.activity_type NOT IN" not in source


def test_issue391_guard_keeps_dma_branch_exact_and_facts_immutable() -> None:
    source = _upgrade_source()

    assert "NEW.activity_type = 'processing.dma_frequency_master_curve'" in source
    assert "NEW.domain_run_type = 'processing.common_processing_output'" in source
    for immutable_fact in (
        "OLD.input_required OR NOT NEW.input_required",
        "OLD.organization_id IS DISTINCT FROM NEW.organization_id",
        "OLD.project_id IS DISTINCT FROM NEW.project_id",
        "OLD.classification IS DISTINCT FROM NEW.classification",
        "OLD.id IS DISTINCT FROM NEW.id",
        "OLD.status IS DISTINCT FROM NEW.status",
        "OLD.output_required IS DISTINCT FROM NEW.output_required",
        "OLD.started_at IS DISTINCT FROM NEW.started_at",
        "OLD.ended_at IS DISTINCT FROM NEW.ended_at",
        "OLD.recorded_at IS DISTINCT FROM NEW.recorded_at",
        "OLD.recorded_by IS DISTINCT FROM NEW.recorded_by",
        "OLD.request_id IS DISTINCT FROM NEW.request_id",
        "OLD.trace_id IS DISTINCT FROM NEW.trace_id",
        "OLD.recorded_by::text IS DISTINCT FROM",
        "OLD.request_id::text IS DISTINCT FROM",
    ):
        assert immutable_fact in source

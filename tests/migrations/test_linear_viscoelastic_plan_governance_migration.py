from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/migrations/versions/20261007_106_linear_viscoelastic_plan_governance.py"


def test_issue377_migration_is_after_dma_processing_and_renders_plan_governance() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261007_106_lve_plan_governance"' in source
    assert 'down_revision: str | None = "20261006_105_dma_tts"' in source
    for fragment in (
        'sa.Column("setup_name", sa.String(length=255), nullable=True)',
        'sa.Column("material_revision_id", sa.Uuid(), nullable=True)',
        'sa.Column("material_state_revision_id", sa.Uuid(), nullable=True)',
        'sa.Column("input_mode", sa.String(length=64), nullable=True)',
        'sa.Column("based_on_plan_id", sa.Uuid(), nullable=True)',
        'sa.Column("override_reason", sa.Text(), nullable=True)',
        'postgresql.JSONB(astext_type=sa.Text())',
        'sa.Column("approval_request_id", sa.Uuid(), nullable=True)',
        'sa.Column("approval_decision_id", sa.Uuid(), nullable=True)',
        "op.create_table(",
        "linear_viscoelastic_calibration_plan_approval",
        "linear_viscoelastic_calibration_plan_usability_fact",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
        "access_control.can_access_row",
        "review.decide",
    ):
        assert fragment in source

    output = StringIO()
    command.upgrade(Config(str(ROOT / "alembic.ini"), output_buffer=output), "head", sql=True)
    sql = output.getvalue()
    for fragment in (
        "CREATE TABLE modeling.linear_viscoelastic_calibration_plan_approval",
        "CREATE TABLE modeling.linear_viscoelastic_calibration_plan_usability_fact",
        (
            "ALTER TABLE modeling.linear_viscoelastic_calibration_plan_approval "
            "FORCE ROW LEVEL SECURITY"
        ),
        "CREATE POLICY lve_plan_approval_select",
        "CREATE POLICY lve_plan_usability_fact_review_insert",
    ):
        assert fragment in sql


def test_issue377_migration_keeps_plan_approval_out_of_catalog_publication() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "review_publication_projection" not in source
    assert "publication_marker" not in source
    assert "fk_mdl_lve_approval_material_revision" in source
    assert "fk_mdl_lve_approval_material_state_revision" in source
    assert "fk_mdl_lve_approval_test_data_revision" in source
    assert "fk_mdl_lve_approval_processing_revision" in source
    assert "fk_mdl_lve_run_approval_request" in source
    assert "fk_mdl_lve_run_approval_decision" in source
    assert "cannot downgrade Issue #377 Plan governance while evidence exists" in source

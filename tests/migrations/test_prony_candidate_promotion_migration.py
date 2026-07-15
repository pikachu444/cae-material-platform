from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = PROJECT_ROOT / "backend/migrations/versions/20260811_045_prony_candidate_promotion.py"


def test_migration_renders_typed_selection_and_promotion_guards() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()
    required = {
        "modeling.prony_candidate_selection",
        "modeling.prony_candidate_selection_revision",
        "validate_prony_candidate_selection_revision",
        "validate_prony_promoted_model_revision",
        "prony_selection_revision_id",
        "prony_calibration_candidate_id",
        "reference_prony_candidate_selection",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
    }
    assert all(fragment in sql for fragment in required)


def test_migration_avoids_generic_eav_payloads() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration
    assert 'sa.Column("content"' not in migration
    assert "organization_id" in migration and "project_id" in migration

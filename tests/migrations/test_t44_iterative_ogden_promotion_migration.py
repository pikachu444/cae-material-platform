from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    PROJECT_ROOT
    / "backend/migrations/versions/20260821_055_T44_iterative_ogden_promotion.py"
)


def test_t44_migration_renders_typed_iterative_promotion_guards() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for fragment in (
        "modeling.ogden_candidate_selection_revision",
        "modeling.ogden_promotion_evidence",
        "uq_mdl_ogden_promotion_candidate",
        "promoted_from_model_revision_id",
        "reference_ogden_candidate_selection",
        "validate_ogden_candidate_selection",
        "validate_ogden_promotion_evidence",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
    ):
        assert fragment in sql


def test_t44_migration_is_explicit_and_non_eav() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "JSONB" not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration
    assert "candidate_sha256" in migration
    assert "diagnostics_sha256" in migration
    assert "cannot downgrade with immutable Ogden Selections" in migration

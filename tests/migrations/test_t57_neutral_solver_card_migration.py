from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).parents[2]


def _migration_sql() -> str:
    output = StringIO()
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "20260907_072_t57_cards"
    from alembic import command

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    return sql[sql.index("20260907_072_t57_cards") :]


def test_t57_card_projection_is_typed_and_exact_revision_pinned() -> None:
    migration = _migration_sql()

    assert "CREATE TABLE exporting.neutral_solver_card" in migration
    assert "CREATE TABLE exporting.neutral_solver_card_revision" in migration
    assert "neutral_material_revision_id uuid NOT NULL" in migration
    assert "family='neo_hookean'" in migration
    assert "family='mooney_rivlin'" in migration
    assert "family='yeoh'" in migration
    assert "family='ogden_1'" in migration
    assert "fk_exporting_neutral_solver_card_revision_source" in migration
    assert "mapping_report_sha256 char(64) NOT NULL" in migration
    assert "card_text text NOT NULL" in migration
    assert "jsonb" not in migration.lower()


def test_t57_card_rows_are_immutable_rls_scoped_and_six_state_constrained() -> None:
    migration = _migration_sql()

    assert "revisioning.guard_identity_head_update()" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    for status in (
        "exact",
        "transformed",
        "approximated",
        "ignored",
        "unsupported",
        "not_applicable",
    ):
        assert status in migration

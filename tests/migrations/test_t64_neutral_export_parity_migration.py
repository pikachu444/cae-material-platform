from io import StringIO
from pathlib import Path

from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _migration_sql() -> str:
    output = StringIO()
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    from alembic import command

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    return sql[sql.index("20260912_077_t64_export") :]


def test_t64_projects_three_neutral_families_without_json_eav() -> None:
    migration = _migration_sql()

    assert "ADD COLUMN model_family varchar(64)" in migration
    assert "model_family='isotropic_tabulated_plasticity'" in migration
    assert "model_family='generalized_maxwell'" in migration
    assert "model_family='hyperelastic'" in migration
    assert "hardening_curve_artifact_id uuid" in migration
    assert "CREATE TABLE exporting.neutral_solver_card_prony_term" in migration
    assert "CREATE TABLE exporting.neutral_solver_card_mapping_item" in migration
    assert "jsonb" not in migration.lower()
    assert "value_json" not in migration.lower()


def test_t64_mapping_and_prony_rows_are_exact_revision_pinned_and_immutable() -> None:
    migration = _migration_sql()

    assert "fk_exporting_neutral_solver_card_mapping_revision" in migration
    assert "fk_exporting_neutral_solver_card_prony_revision" in migration
    assert "REFERENCES exporting.neutral_solver_card_revision" in migration
    assert migration.count("revisioning.reject_immutable_row_mutation()") >= 2
    assert migration.count("ENABLE ROW LEVEL SECURITY") >= 2
    assert migration.count("FORCE ROW LEVEL SECURITY") >= 2
    for status in (
        "exact",
        "transformed",
        "approximated",
        "ignored",
        "unsupported",
        "not_applicable",
    ):
        assert status in migration

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_holdout_migration_has_typed_disjoint_lineage_and_no_solver_or_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "validation.voce_holdout_plan",
        "validation.voce_holdout_plan_revision",
        "validation.voce_holdout_run",
        "validation.voce_holdout_result",
        "validation.voce_holdout_comparison_point",
        "guard_voce_holdout_plan_insert",
        "holdout Dataset or Test Run overlaps calibration review scope",
        "closed_form_curve",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
        "ck_exporting_solver_card_exporter_contract",
        "60174f00940a5e371613f941649a61af20714b5664b8b95672e34e1a718251bd",
    ):
        assert value in sql
    holdout_sql = sql[sql.index("CREATE TABLE validation.voce_holdout_plan (") :]
    assert " JSON" not in holdout_sql
    assert " JSONB" not in holdout_sql
    assert "OpenRadioss" not in holdout_sql
    assert "Abaqus" not in holdout_sql

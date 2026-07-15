from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_voce_projection_migration_has_typed_selection_lineage_and_no_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "modeling.voce_candidate_selection",
        "modeling.voce_candidate_selection_revision",
        "voce_calibration_candidate_sha256 char(64)",
        "voce_sampling_point_count integer",
        "voce_q_pa float8",
        "voce_b float8",
        "fk_mdl_model_voce_scope",
        "fk_mdl_model_voce_plan",
        "fk_mdl_model_voce_candidate",
        "fk_mdl_model_voce_selection",
        "guard_voce_projected_model_insert",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
    ):
        assert value in sql
    projection_sql = sql[sql.index("CREATE TABLE modeling.voce_candidate_selection (") :]
    assert " JSON" not in projection_sql
    assert " JSONB" not in projection_sql
    assert "*PLASTIC" not in projection_sql
    assert "/MAT/LAW36" not in projection_sql

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t55e_family_diagnostics_are_exact_artifact_references() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output), "head", sql=True
    )
    sql = output.getvalue()
    migration = sql[sql.index("20260905_070_t55e_diagnostics") :]
    for value in (
        "diagnostics_artifact_id uuid",
        "diagnostics_sha256 char(64)",
        "diagnostics_point_count integer",
        "ck_modeling_hyperelastic_family_candidate_diagnostics",
        "fk_modeling_hyperelastic_family_candidate_diagnostics",
        "artifact.artifact",
        "ON DELETE RESTRICT",
    ):
        assert value in migration
    assert "jsonb" not in migration.lower()

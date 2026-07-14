from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def _configuration(output: StringIO) -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)


def test_solver_card_applicability_note_is_typed_and_bounded() -> None:
    output = StringIO()
    command.upgrade(_configuration(output), "head", sql=True)

    sql = " ".join(output.getvalue().split())
    assert (
        "ALTER TABLE exporting.solver_card_revision "
        "ADD COLUMN applicability_note text NULL"
    ) in sql
    assert "ck_exporting_solver_card_applicability_note" in sql
    assert "length(btrim(applicability_note)) BETWEEN 1 AND 2000" in sql


def test_solver_card_applicability_note_downgrade_preserves_evidence() -> None:
    output = StringIO()
    command.downgrade(
        _configuration(output),
        "20260727_029_p0:20260726_028_td03",
        sql=True,
    )

    sql = output.getvalue()
    assert "cannot downgrade while Solver Card applicability evidence exists" in sql
    assert sql.index("DROP CONSTRAINT ck_exporting_solver_card_applicability_note") < sql.index(
        "DROP COLUMN applicability_note"
    )

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_abaqus_linear_prony_card_is_typed_scoped_immutable_and_source_pinned() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    assert "exporting.linear_viscoelastic_solver_card_revision" in sql
    assert "exporting.linear_viscoelastic_solver_card_term" in sql
    assert "bulk_relaxation_status varchar(32)" in sql
    assert "prony_terms_mapping_status varchar(32)" in sql
    assert "relaxation_time_s double precision" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "reject_immutable_row_mutation" in sql
    assert "validate_linear_viscoelastic_card_terms" in sql
    assert "linear-Prony Solver Card terms differ from the exact source IR revision" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260807_041_abaqus_linear_prony_card.py"
    ).read_text(encoding="utf-8")
    assert "JSON" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

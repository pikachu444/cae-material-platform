from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t55e_family_candidates_are_explicit_typed_immutable_and_scoped() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output), "head", sql=True
    )
    sql = output.getvalue()
    start = sql.index("20260904_069_t55e_families")
    end = sql.index("20260905_070_t55e_diagnostics", start)
    migration = sql[start:end]
    for value in (
        "modeling.hyperelastic_family_candidate",
        "modeling.hyperelastic_family_candidate_warning",
        "c10_pa double precision",
        "c01_pa double precision",
        "c20_pa double precision",
        "c30_pa double precision",
        "ogden_mu_pa double precision",
        "ogden_alpha double precision",
        "ck_modeling_hyperelastic_family_candidate_parameters",
        "fk_modeling_hyperelastic_family_candidate_run",
        "FORCE ROW LEVEL SECURITY",
        "reject_immutable_row_mutation",
    ):
        assert value in migration
    assert "jsonb" not in migration.lower()
    assert "attribute_value" not in migration

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_t43_scientific_profiles_are_typed_revisioned_and_non_eav() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    assert "modeling.scientific_profile_revision" in sql
    assert "voce_sigma0_initial_pa double precision" in sql
    assert "prony_term_count_max integer" in sql
    assert "ogden_mu_initial_pa double precision" in sql
    assert "jacobian_covariance_or_not_estimable" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "guard_identity_head_update" in sql
    assert "reject_immutable_row_mutation" in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260819_053_T43_scientific_profiles.py"
    ).read_text(encoding="utf-8")
    assert "JSONB" not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration

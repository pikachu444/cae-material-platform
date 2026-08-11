from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def _config() -> tuple[Config, StringIO]:
    output = StringIO()
    return Config(str(ROOT / "alembic.ini"), output_buffer=output), output


def test_issue206_migration_widens_only_existing_typed_curve_guards() -> None:
    config, output = _config()
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()

    assert "20260927_096_issue206_curve" in sql
    assert "reference-tensile-normalized-parquet:1.0.0" in sql
    assert "reference-tensile-normalized-parquet:1.1.0" in sql
    assert "reference-tensile-processed-parquet:1.1.0" in sql
    assert "reference-tensile-pair-curve-parquet:1.1.0" in sql
    assert "reference-tensile-replicate-curve-parquet:1.1.0" in sql
    assert "CREATE OR REPLACE FUNCTION datasets.guard_reference_dataset_revision_insert" in sql
    assert "CREATE OR REPLACE FUNCTION statistics.guard_statistical_result_revision_insert" in sql

    migration = (
        ROOT
        / "backend/migrations/versions/20260927_096_issue206_curve_metadata.py"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE" not in migration
    assert "JSONB" not in migration
    assert 'sa.JSON' not in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration


def test_issue206_downgrade_refuses_immutable_current_curve_evidence() -> None:
    config, output = _config()
    command.downgrade(
        config,
        "20260927_096_issue206_curve:20260926_095_issue205_units",
        sql=True,
    )
    sql = output.getvalue()
    assert "Issue #206 downgrade refused: immutable curve schema 1.1.0 evidence exists" in sql
    assert "input_schema_ref = 'urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0'" in sql
    assert (
        "curve_output_schema_ref = "
        "'urn:cmp:statistics:reference-tensile-pair-curve-parquet:1.0.0'"
    ) in sql

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t24_migration_renders_typed_selection_promotion_evidence_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE TABLE modeling.calibration_candidate_selection",
        "CREATE TABLE modeling.calibration_candidate_selection_revision",
        "uq_modeling_calibration_candidate_selection_identity_run",
        "uq_modeling_calibration_candidate_identity_run",
        "calibration_evidence_kind",
        "calibration_selection_revision_id",
        "calibration_diagnostics_artifact_id",
        "CREATE INDEX ix_modeling_material_model_calibration_candidate",
        "CREATE FUNCTION modeling.guard_calibration_candidate_selection_revision_insert()",
        "CREATE FUNCTION modeling.guard_reference_calibrated_model_revision_insert()",
        "CREATE TRIGGER modeling_calibration_candidate_selection_revision_guard",
        "CREATE TRIGGER modeling_reference_calibrated_model_revision_guard",
        "ALTER TABLE modeling.calibration_candidate_selection FORCE ROW LEVEL SECURITY",
        "ALTER TABLE modeling.calibration_candidate_selection_revision FORCE ROW LEVEL SECURITY",
        "accepted_for_reference_ir_promotion",
        "reference_candidate_selection",
    }

    assert all(fragment in sql for fragment in required)


def test_t24_downgrade_drops_identity_head_fk_before_revision_table() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.downgrade(
        configuration,
        "20260720_022_t24:20260719_021_t23",
        sql=True,
    )

    sql = output.getvalue()
    assert sql.index(
        "DROP CONSTRAINT IF EXISTS "
        "fk_modeling_calibration_candidate_selection_current_revision"
    ) < sql.index("DROP TABLE modeling.calibration_candidate_selection_revision")

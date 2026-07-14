from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t27_migration_renders_explicit_validation_relations_guards_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    normalized_sql = " ".join(sql.split())
    required = {
        "CREATE SCHEMA validation",
        "CREATE TABLE validation.validation_template",
        "CREATE TABLE validation.validation_template_revision",
        "CREATE TABLE validation.validation_plan",
        "CREATE TABLE validation.validation_plan_revision",
        "CREATE TABLE validation.validation_run",
        "CREATE TABLE validation.validation_run_result_manifest",
        "gauge_length_m",
        "cross_section_area_m2",
        "axial_element_count",
        "solver_card_revision_id",
        "experimental_selection_revision_id",
        "deck_artifact_id",
        "stdout_artifact_id",
        "stderr_artifact_id",
        "native_result_artifact_id",
        "manifest_artifact_id",
        "CREATE FUNCTION validation.guard_validation_plan_revision_insert()",
        "CREATE FUNCTION validation.guard_validation_run_insert()",
        "CREATE FUNCTION validation.guard_validation_run_transition()",
        "CREATE FUNCTION validation.guard_validation_result_manifest_insert()",
        "CREATE TRIGGER validation_plan_revision_input_guard",
        "CREATE TRIGGER validation_run_input_guard",
        "CREATE TRIGGER validation_run_transition_guard",
        "CREATE TRIGGER validation_run_result_manifest_input_guard",
        "ALTER TABLE validation.validation_run FORCE ROW LEVEL SECURITY",
        "ALTER TABLE validation.validation_run_result_manifest FORCE ROW LEVEL SECURITY",
        "reference_inline_mock",
        "manual_attach",
    }

    assert all(fragment in sql for fragment in required)
    assert (
        "OR (execution_mode = 'manual_attach' AND external_job_reference IS NOT NULL))), "
        "CONSTRAINT fk_validation_run_result_manifest_run"
    ) in normalized_sql

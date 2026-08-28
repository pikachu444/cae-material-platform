from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_issue342_json_registration_migration_is_scoped_atomic_and_append_only() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()
    for value in (
        "catalog.json_record_registration_preview",
        "catalog.json_record_registration_batch",
        "catalog.json_record_registration_curve_artifact",
        "catalog.record_json_source_provenance",
        "package_sha256",
        "source_length_bytes",
        "source_sha256",
        "table_source_pointer",
        "pointer_evidence",
        "unit_evidence",
        "domain_bindings",
        "FORCE ROW LEVEL SECURITY",
        "revisioning.reject_immutable_row_mutation()",
        "state IN ('open', 'committed')",
        "source_state IN ('artifacts_pending', 'ready', 'reconciliation_failed')",
        "fk_catalog_json_registration_curve_artifact_batch",
        "fk_catalog_json_registration_curve_artifact_artifact",
        "catalog_json_record_registration_curve_artifact_immutable",
    ):
        assert value in sql
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20261004_103_issue342_json_record_registration.py"
    ).read_text(encoding="utf-8")
    persistence = (
        PROJECT_ROOT
        / "backend/src/cmp/modules/catalog/adapters/persistence/json_record_registration.py"
    ).read_text(encoding="utf-8")
    assert 'schema="catalog"' in migration
    assert "source_artifact_id" in migration
    assert 'server_default="ready"' in migration
    assert 'str(existing_batch["source_state"]) != "artifacts_pending"' in persistence
    assert "json_record_registration_curve_artifact" in persistence
    assert "CREATE TABLE catalog.record_json_source_provenance" in sql
    assert "catalog_record_json_source_provenance_immutable" in sql


def test_issue342_domain_pin_lookup_is_scoped_security_definer_and_closed_kind() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20261004_103_issue342_json_record_registration.py"
    ).read_text(encoding="utf-8")
    persistence = (
        PROJECT_ROOT
        / "backend/src/cmp/modules/catalog/adapters/persistence/records.py"
    ).read_text(encoding="utf-8")

    assert "CREATE FUNCTION access_control.catalog_domain_revision_exists(" in migration
    assert "RETURNS boolean" in migration
    assert "SECURITY DEFINER" in migration
    assert "SET search_path = pg_catalog" in migration
    assert (
        "REVOKE ALL ON FUNCTION access_control.catalog_domain_revision_exists("
        in migration
    )
    assert "access_control.can_access_row(" in migration
    assert "'catalog.read'" in migration
    for kind, table in (
        ("material", "catalog.material_revision"),
        ("material_state", "catalog.material_state_revision"),
        ("specimen", "testing.specimen_revision"),
        ("test_run", "testing.test_run_revision"),
        ("test_data", "datasets.test_data_document_revision"),
        ("processing_output", "processing.common_processing_output_revision"),
        ("material_model", "modeling.material_model_revision"),
        ("neutral_material", "modeling.neutral_material_revision"),
        ("solver_card", "exporting.solver_card_revision"),
        ("neutral_solver_card", "exporting.neutral_solver_card_revision"),
        ("release", "governance.release_manifest"),
    ):
        assert f"p_domain_kind = '{kind}'" in migration
        assert f"FROM {table}" in migration
    assert "RETURN target_exists;" in migration
    assert "sa.func.access_control.catalog_domain_revision_exists" in persistence
    assert "sa.select(sa.literal(True)).select_from(table)" not in persistence

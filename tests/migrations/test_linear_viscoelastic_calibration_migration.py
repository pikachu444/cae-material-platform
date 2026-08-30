from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20261005_104_linear_viscoelastic_calibration.py"
)
DMA_PROCESSING_MIGRATION = (
    Path(__file__).parents[2]
    / "backend/migrations/versions/20261006_105_dma_frequency_master_curve.py"
)


def test_linear_viscoelastic_migration_is_typed_additive_and_has_exact_chain() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261005_104_lve_calibration"' in source
    assert 'down_revision: str | None = "20261004_103_issue342_json"' in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_plan" in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_execution_attempt" in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_numerical_attempt" in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_candidate" in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_recommendation" in source
    assert "CREATE TABLE modeling.linear_viscoelastic_calibration_selection_revision" in source
    assert "ADD COLUMN deformation_mode varchar(32)" in source
    assert "WHERE schema_version = '1.2.0' OR deformation_mode IS NOT NULL" in source
    assert "cannot downgrade linear-viscoelastic calibration while calibration rows exist" in source
    assert "CREATE POLICY" in source and "FORCE ROW LEVEL SECURITY" in source
    assert "CREATE TRIGGER" in source and "immutable" in source


def test_reference_shear_dma_method_constraints_are_reversible() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    extend_start = source.index("def _extend_reference_test_method_constraints")
    restore_start = source.index("def _restore_reference_test_method_constraints")
    upgrade_start = source.index("def upgrade()")
    downgrade_start = source.index("def downgrade()")
    forward_sql = source[extend_start:restore_start]
    reverse_sql = source[restore_start:upgrade_start]
    upgrade_body = source[upgrade_start:downgrade_start]
    downgrade_body = source[downgrade_start:]

    assert "DROP CONSTRAINT ck_testing_test_method_code" in forward_sql
    assert "DROP CONSTRAINT ck_testing_test_method_revision_declared" in forward_sql
    assert "reference_shear_dma_frequency_sweep" in forward_sql
    assert "Reference shear DMA frequency sweep" in forward_sql
    for legacy_code, legacy_name in (
        ("reference_uniaxial_tensile", "Reference uniaxial tensile CSV"),
        ("reference_planar_tension", "Reference planar tension CSV"),
        ("reference_biaxial_tension", "Reference biaxial tension CSV"),
        ("reference_shear_relaxation", "Reference shear relaxation CSV"),
    ):
        assert legacy_code in forward_sql
        assert legacy_name in forward_sql
        assert legacy_code in reverse_sql
        assert legacy_name in reverse_sql
    assert "_extend_reference_test_method_constraints()" in upgrade_body
    assert "_restore_reference_test_method_constraints()" in downgrade_body
    assert "cannot downgrade Test Method constraints" in reverse_sql


def test_dma_master_curve_migration_persists_processing_and_plan_evidence() -> None:
    source = DMA_PROCESSING_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261006_105_dma_tts"' in source
    assert 'down_revision: str | None = "20261005_104_lve_calibration"' in source
    assert "dma_temperature_sweep" in source
    assert "source_profile_kind" in source
    assert "result_artifact_id" in source
    assert "ck_common_processing_output_source_profile_xor" in source
    assert "ck_common_processing_output_result_artifact_all_or_none" in source
    assert "processing_output_revision_id" in source
    assert "processing_metadata_artifact_sha256" in source
    assert "processing_result_artifact_sha256" in source
    assert "ck_lve_calibration_processing_input_all_or_none" in source
    assert "cannot downgrade while governed DMA temperature-sweep records exist" in source

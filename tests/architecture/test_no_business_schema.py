from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_implemented_tasks_are_the_only_database_migrations() -> None:
    migrations = sorted((PROJECT_ROOT / "backend/migrations/versions").glob("*.py"))

    assert [path.name for path in migrations] == [
        "20260711_001_T06_revision_kernel.py",
        "20260711_002_T03_identity_principal.py",
        "20260711_003_T04_authorization_rls.py",
        "20260711_004_T15_job_engine.py",
        "20260711_005_T17_plugin_registry.py",
        "20260712_006_T09_streaming_upload.py",
        "20260712_007_T10_content_artifacts.py",
        "20260713_008_T13_typed_provenance.py",
        "20260713_009_T14_lineage_read_model.py",
        "20260713_010_T16_transactional_outbox.py",
        "20260713_011_T16_reconciliation_schedule.py",
        "20260713_012_T05_append_only_audit.py",
        "20260713_013_T07_material_catalog.py",
        "20260714_014_T22_reference_material_model.py",
        "20260714_015_T25_reference_openradioss_export.py",
        "20260714_016_T08_T12_reference_tensile_dataset.py",
        "20260715_017_T19_reference_processing.py",
        "20260716_018_T20_reference_statistics.py",
        "20260717_019_T21_reference_outlier_assessment.py",
        "20260718_020_T11_reference_import_orchestration.py",
        "20260719_021_T23_reference_calibration.py",
        "20260720_022_T24_candidate_selection_promotion.py",
        "20260721_023_T27_validation_template_runner.py",
        "20260722_024_T28_validation_result_interpretation.py",
        "20260723_025_T29_review_lifecycle.py",
        "20260724_026_T30_release_completeness.py",
        "20260725_027_T31_release_lifecycle.py",
        "20260726_028_TD03_reference_elastoplastic_multisolver.py",
        "20260727_029_P0_solver_card_applicability_note.py",
        "20260728_030_P0_2_multi_replicate_selection.py",
        "20260728_031_P0_2_provenance_activity_finalization.py",
        "20260729_032_P0_2_replicate_alignment.py",
        "20260730_033_P0_2_replicate_statistics.py",
        "20260731_034_P0_2_replicate_outlier_scope.py",
        "20260801_035_P1_reference_voce_calibration.py",
        "20260802_036_P1_voce_candidate_projection.py",
        "20260803_037_P1_voce_holdout_validation.py",
        "20260804_038_material_classification.py",
        "20260805_039_steel_elastoplastic_routing.py",
        "20260806_040_linear_viscoelastic_ir.py",
        "20260807_041_abaqus_linear_prony_card.py",
        "20260808_042_shear_relaxation_dataset.py",
        "20260809_043_shear_relaxation_processing.py",
        "20260810_044_reference_prony_calibration.py",
        "20260811_045_prony_candidate_promotion.py",
        "20260812_046_ogden_prony_ir.py",
        "20260813_047_ogden_prony_cards.py",
        "20260814_048_catalog_genealogy.py",
        "20260815_049_T39_process_run_genealogy.py",
        "20260816_050_T40_test_context.py",
        "20260817_051_T41_governed_tabular_import.py",
        "20260818_052_T42_viscoelastic_master_curve.py",
        "20260819_053_T43_scientific_profiles.py",
        "20260820_054_T43_ogden_calibration.py",
        "20260821_055_T44_iterative_ogden_promotion.py",
        "20260822_056_T45_bulk_export_bundle.py",
    ]


def test_t06_migration_does_not_introduce_domain_or_generic_content_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_001_T06_revision_kernel.py"
    ).read_text(encoding="utf-8")
    forbidden_table_names = (
        '"material"',
        '"test_run"',
        '"dataset"',
        '"solver_card"',
        '"aggregate_revision"',
        '"generic_revision"',
    )

    assert all(name not in migration for name in forbidden_table_names)
    assert '"content", postgresql.JSONB' not in migration


def test_t03_migration_stops_before_roles_and_business_resources() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_002_T03_identity_principal.py"
    ).read_text(encoding="utf-8")

    assert '"role_binding"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration
    assert "sa.JSON" not in migration
    assert "postgresql.JSONB" not in migration


def test_t04_migration_adds_access_control_without_business_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_003_T04_authorization_rls.py"
    ).read_text(encoding="utf-8")

    assert '"role_binding"' in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"artifact"' not in migration
    assert '"solver_card"' not in migration
    assert "sa.JSON" not in migration
    assert "postgresql.JSONB" not in migration


def test_t15_job_spec_jsonb_is_not_a_generic_eav_or_business_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_004_T15_job_engine.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 1
    assert 'sa.Column("job_spec", postgresql.JSONB' in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration


def test_t17_jsonb_is_limited_to_versioned_manifest_and_schema_contracts() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_005_T17_plugin_registry.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 2
    assert 'sa.Column("manifest", postgresql.JSONB' in migration
    assert 'sa.Column("document", postgresql.JSONB' in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration


def test_t09_uses_explicit_upload_raw_and_ingestion_relations_without_jsonb() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_006_T09_streaming_upload.py"
    ).read_text(encoding="utf-8")

    assert '"upload_session"' in migration
    assert '"upload_part"' in migration
    assert '"raw_asset"' in migration
    assert '"ingestion_event"' in migration
    assert "postgresql.JSONB" not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t10_uses_explicit_manifest_integrity_relations_without_eav_json() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_007_T10_content_artifacts.py"
    ).read_text(encoding="utf-8")

    assert '"artifact_pending"' in migration
    assert '"artifact"' in migration
    assert '"integrity_observation"' in migration
    assert '"integrity_projection"' in migration
    assert '"reconciliation_issue"' in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t13_uses_typed_provenance_relations_without_generic_edges_or_jsonb() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_008_T13_typed_provenance.py"
    ).read_text(encoding="utf-8")

    for table in (
        "entity",
        "activity",
        "agent",
        "usage",
        "generation",
        "derivation",
        "association",
        "revision",
        "attribution",
    ):
        assert f'"{table}"' in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"edge"' not in migration
    assert '"edge_type"' not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t14_adds_security_invoker_read_models_without_new_domain_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_009_T14_lineage_read_model.py"
    ).read_text(encoding="utf-8")

    assert "security_invoker = true" in migration
    assert "provenance.dependency_edge" in migration
    assert "provenance.entity_completeness" in migration
    assert "provenance.activity_completeness" in migration
    assert "op.create_table" not in migration
    assert "postgresql.JSONB" not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration


def test_t07_uses_explicit_catalog_revisions_and_typed_property_columns_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260713_013_T07_material_catalog.py"
    ).read_text(encoding="utf-8")

    for table in (
        "material",
        "material_revision",
        "material_state",
        "material_state_revision",
        "property_set",
        "property_set_revision",
    ):
        assert f'"{table}"' in migration
    for column in (
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"yield_stress_pa"',
        '"applicable_temperature_min_k"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "for table in (identity, revision_table):" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "revisioning.guard_identity_head_update()" in migration


def test_t22_uses_typed_reference_model_revisions_without_generic_model_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_014_T22_reference_material_model.py"
    ).read_text(encoding="utf-8")

    for table in ("material_model", "material_model_revision"):
        assert f'"{table}"' in migration
    for column in (
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"source_yield_stress_pa"',
        '"property_set_revision_id"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t25_uses_typed_solver_card_revisions_without_generic_card_payload() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_015_T25_reference_openradioss_export.py"
    ).read_text(encoding="utf-8")

    for table in ("solver_card", "solver_card_revision"):
        assert f'"{table}"' in migration
    for column in (
        '"material_model_revision_id"',
        '"density_kg_per_m3"',
        '"youngs_modulus_pa"',
        '"poisson_ratio"',
        '"mapping_report_sha256"',
        '"card_sha256"',
        '"card_text"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t08_t12_use_explicit_test_dataset_revisions_and_artifact_references_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260714_016_T08_T12_reference_tensile_dataset.py"
    ).read_text(encoding="utf-8")

    for table in (
        "specimen",
        "specimen_revision",
        "test_method",
        "test_method_revision",
        "test_run",
        "test_run_revision",
        "dataset",
        "dataset_revision",
    ):
        assert f'"{table}"' in migration
    for column in (
        '"material_state_revision_id"',
        '"test_run_revision_id"',
        '"raw_artifact_id"',
        '"data_artifact_id"',
        '"strain_original_unit"',
        '"stress_original_unit"',
        '"mapping_sha256"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t20_uses_explicit_statistics_qc_and_result_columns_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260716_018_T20_reference_statistics.py"
    ).read_text(encoding="utf-8")

    for table in (
        "statistical_plan",
        "statistical_plan_revision",
        "statistical_result",
        "statistical_result_revision",
        "statistical_run",
        "qc_observation",
    ):
        assert f'"{table}"' in migration
    for column in (
        '"first_selection_revision_id"',
        '"second_selection_revision_id"',
        '"first_peak_engineering_stress_pa"',
        '"sample_standard_deviation_engineering_stress_pa"',
        '"curve_artifact_id"',
        '"check_code"',
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration


def test_t11_uses_explicit_detection_mapping_and_import_run_records_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260718_020_T11_reference_import_orchestration.py"
    ).read_text(encoding="utf-8")

    for table in (
        "testing.import_detection_report",
        "testing.import_mapping",
        "testing.import_mapping_revision",
        "processing.import_run",
    ):
        assert table in migration
    for column in (
        "header_columns",
        "detection_report_id",
        "dataset_mapping_sha256",
        "import_mapping_revision_id",
        "mapping_sha256",
        "output_dataset_revision_id",
    ):
        assert column in migration
    assert "needs_input" in migration
    assert "human_confirmed" in migration
    assert "reference_inline" in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "revisioning.guard_identity_head_update()" in migration


def test_t24_uses_typed_candidate_selection_and_ir_promotion_evidence_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260720_022_T24_candidate_selection_promotion.py"
    ).read_text(encoding="utf-8")

    for table in (
        "calibration_candidate_selection",
        "calibration_candidate_selection_revision",
        "material_model_revision",
    ):
        assert table in migration
    for column in (
        "selection_label",
        "calibration_run_id",
        "calibration_candidate_id",
        "candidate_sha256",
        "selection_reason",
        "calibration_selection_revision_id",
        "calibration_diagnostics_artifact_id",
    ):
        assert column in migration
    assert "accepted_for_reference_ir_promotion" in migration
    assert "reference_candidate_selection" in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "guard_reference_calibrated_model_revision_insert" in migration


def test_t27_uses_explicit_template_plan_run_and_result_manifest_relations_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260721_023_T27_validation_template_runner.py"
    ).read_text(encoding="utf-8")

    for table in (
        "validation_template",
        "validation_template_revision",
        "validation_plan",
        "validation_plan_revision",
        "validation_run",
        "validation_run_result_manifest",
    ):
        assert table in migration
    for column in (
        "gauge_length_m",
        "cross_section_area_m2",
        "axial_element_count",
        "solver_card_revision_id",
        "experimental_selection_revision_id",
        "deck_artifact_id",
        "stdout_artifact_id",
        "native_result_artifact_id",
        "manifest_artifact_id",
    ):
        assert column in migration
    assert "reference_inline_mock" in migration
    assert "manual_attach" in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "guard_validation_plan_revision_insert" in migration
    assert "guard_validation_result_manifest_insert" in migration


def test_t28_uses_explicit_validation_result_interpretation_relations_without_eav() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260722_024_T28_validation_result_interpretation.py"
    ).read_text(encoding="utf-8")

    for table in (
        "validation_response_extraction",
        "validation_numerical_health_report",
        "validation_result",
        "validation_result_comparison_point",
    ):
        assert table in migration
    for column in (
        "source_native_result_artifact_id",
        "normalized_response_artifact_id",
        "health_status",
        "relative_root_mean_squared_error",
        "holdout_independence",
        "engineering_strain",
        "observed_engineering_stress_pa",
        "simulated_engineering_stress_pa",
    ):
        assert column in migration
    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "revisioning.reject_immutable_row_mutation()" in migration
    assert "guard_validation_response_extraction_insert" in migration
    assert "guard_validation_numerical_health_report_insert" in migration
    assert "guard_validation_result_insert" in migration
    assert "guard_validation_result_comparison_points" in migration


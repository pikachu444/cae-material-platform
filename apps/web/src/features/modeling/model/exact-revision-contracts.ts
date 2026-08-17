export interface CommonExactRevisionPin {
  aggregate_id: string;
  revision_id: string;
}

export interface CommonExportProvenance {
  material: CommonExactRevisionPin;
  material_state: CommonExactRevisionPin;
  test_run: CommonExactRevisionPin;
  tabular_import?: {
    raw_asset_id: string;
    raw_artifact_id: string;
    import_run_id: string;
    import_profile: CommonExactRevisionPin;
    normalized_dataset: CommonExactRevisionPin;
  } | null;
}

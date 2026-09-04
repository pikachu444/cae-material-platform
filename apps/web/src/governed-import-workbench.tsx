import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  createGovernedImportProfile,
  executeGovernedTabularImport,
  listGovernedImportProfiles,
  listTestRunsForMaterialState,
  previewGovernedTabularImport,
  uploadGovernedTabularFile,
} from "./features/test-data";
import type { MaterialStateResponse } from "./features/materials/contracts";
import type {
  GovernedChannelMapping,
  GovernedImportPreview,
  GovernedImportProfileResponse,
  GovernedImportRunResponse,
  GovernedQuantityKind,
  GovernedTabularDataSchema,
  GovernedTabularFileFormat,
  TestRunResponse,
} from "./features/test-data/contracts";
import type { DataClassification } from "./shared/model/core-contracts";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The governed tabular import could not be completed.";
}

const SCHEMAS: { value: GovernedTabularDataSchema; label: string }[] = [
  { value: "monotonic_tension", label: "Monotonic tension" },
  { value: "monotonic_compression", label: "Monotonic compression" },
  { value: "planar_tension", label: "Planar tension" },
  { value: "biaxial_tension", label: "Biaxial tension" },
  { value: "simple_shear", label: "Simple shear" },
  { value: "shear_relaxation", label: "Shear relaxation" },
];

const UNIT_OPTIONS: Record<GovernedQuantityKind, string[]> = {
  engineering_strain: ["1", "%"],
  engineering_stress: ["Pa", "kPa", "MPa", "GPa"],
  shear_strain: ["1", "%"],
  shear_stress: ["Pa", "kPa", "MPa", "GPa"],
  time: ["s", "ms", "min", "h"],
  shear_modulus: ["Pa", "kPa", "MPa", "GPa"],
  displacement: ["m", "mm", "um"],
  force: ["N", "kN"],
  temperature: ["degC", "K"],
  frequency: ["Hz"],
  storage_modulus: ["Pa", "kPa", "MPa", "GPa"],
  loss_modulus: ["Pa", "kPa", "MPa", "GPa"],
  tan_delta: ["1"],
  source_sweep_ordinal: ["1"],
  minor_strain: ["1", "%"],
  major_strain: ["1", "%"],
};

function quantities(
  schema: GovernedTabularDataSchema,
  geometrySource: boolean,
): [GovernedQuantityKind, GovernedQuantityKind] {
  if (
    geometrySource &&
    (schema === "monotonic_tension" || schema === "monotonic_compression")
  ) {
    return ["displacement", "force"];
  }
  if (schema === "simple_shear") return ["shear_strain", "shear_stress"];
  if (schema === "shear_relaxation") return ["time", "shear_modulus"];
  return ["engineering_strain", "engineering_stress"];
}

function defaultUnit(quantity: GovernedQuantityKind): string {
  if (quantity.includes("strain")) return "%";
  if (quantity === "time") return "s";
  if (quantity === "displacement") return "mm";
  if (quantity === "force") return "kN";
  return "MPa";
}

function short(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

interface Props {
  config: ApiConfig;
  state: MaterialStateResponse;
}

export function GovernedImportWorkbench({ config, state }: Props) {
  const [testRuns, setTestRuns] = useState<TestRunResponse[]>([]);
  const [profiles, setProfiles] = useState<GovernedImportProfileResponse[]>([]);
  const [testRunId, setTestRunId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileFormat, setFileFormat] = useState<GovernedTabularFileFormat>("csv");
  const [sheetName, setSheetName] = useState("Data");
  const [headerRow, setHeaderRow] = useState(1);
  const [delimiter, setDelimiter] = useState(",");
  const [decimalSeparator, setDecimalSeparator] = useState<"." | ",">(".");
  const [preview, setPreview] = useState<GovernedImportPreview | null>(null);
  const [rawAssetId, setRawAssetId] = useState("");
  const [rawArtifactId, setRawArtifactId] = useState("");
  const [schema, setSchema] = useState<GovernedTabularDataSchema>("monotonic_tension");
  const [geometrySource, setGeometrySource] = useState(false);
  const [firstColumn, setFirstColumn] = useState("");
  const [secondColumn, setSecondColumn] = useState("");
  const [firstUnit, setFirstUnit] = useState("%");
  const [secondUnit, setSecondUnit] = useState("MPa");
  const [gaugeLengthMm, setGaugeLengthMm] = useState("50");
  const [areaMm2, setAreaMm2] = useState("10");
  const [profileLabel, setProfileLabel] = useState("Approved governed import");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [run, setRun] = useState<GovernedImportRunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const selectedRun = testRuns.find((item) => item.test_run_id === testRunId) ?? null;
  const selectedProfile =
    profiles.find((item) => item.import_profile_id === selectedProfileId) ?? null;
  const channelQuantities = useMemo(
    () => quantities(schema, geometrySource),
    [schema, geometrySource],
  );

  const refresh = useCallback(async () => {
    if (!config.accessToken) return;
    try {
      const [runsResult, profilesResult] = await Promise.all([
        listTestRunsForMaterialState(config, state.material_state_id),
        listGovernedImportProfiles(config),
      ]);
      setTestRuns(runsResult.data.items);
      setProfiles(profilesResult.data);
      setTestRunId((current) => current || runsResult.data.items[0]?.test_run_id || "");
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }, [config, state.material_state_id]);

  useEffect(() => void refresh(), [refresh]);

  useEffect(() => {
    setFirstUnit(defaultUnit(channelQuantities[0]));
    setSecondUnit(defaultUnit(channelQuantities[1]));
  }, [channelQuantities]);

  async function uploadAndPreview(event: FormEvent) {
    event.preventDefault();
    if (!file || !selectedRun) {
      setError("Choose an exact Test Run and source file first.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    setRun(null);
    try {
      const uploaded = await uploadGovernedTabularFile(config, {
        file,
        file_format: fileFormat,
        classification: selectedRun.current_revision.classification as DataClassification,
        test_run_revision_id: selectedRun.current_revision.id,
      });
      const rawAsset = uploaded.data.raw_asset;
      const artifactId = uploaded.data.available_artifact_id;
      if (!rawAsset || !artifactId) throw new ApiError(409, "Upload has no verified Raw Artifact.");
      const settings = {
        raw_asset_id: rawAsset.raw_asset_id,
        raw_artifact_id: artifactId,
        file_format: fileFormat,
        sheet_name: fileFormat === "xlsx" ? sheetName.trim() : null,
        header_row: headerRow,
        encoding: fileFormat === "xlsx" ? "binary" : "utf-8",
        delimiter: fileFormat === "xlsx" ? null : fileFormat === "tsv" ? "\t" : delimiter,
        decimal_separator: decimalSeparator,
      };
      const inspected = await previewGovernedTabularImport(config, settings);
      setRawAssetId(rawAsset.raw_asset_id);
      setRawArtifactId(artifactId);
      setPreview(inspected.data);
      setFirstColumn(inspected.data.header_columns[0] ?? "");
      setSecondColumn(inspected.data.header_columns[1] ?? "");
      setNotice("Raw bytes are immutable. Header evidence remains needs_input until you approve a Profile.");
    } catch (previewError) {
      setError(errorMessage(previewError));
    } finally {
      setBusy(false);
    }
  }

  async function approveProfile(event: FormEvent) {
    event.preventDefault();
    if (!preview || !firstColumn || !secondColumn) {
      setError("Preview the source and map both required channels first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const channels: GovernedChannelMapping[] = [
        {
          ordinal: 0,
          source_column: firstColumn,
          source_quantity: channelQuantities[0],
          original_unit: firstUnit,
          axis_role: "independent",
        },
        {
          ordinal: 1,
          source_column: secondColumn,
          source_quantity: channelQuantities[1],
          original_unit: secondUnit,
          axis_role: "dependent",
        },
      ];
      const created = await createGovernedImportProfile(config, {
        classification: preview.classification,
        content: {
          profile_label: profileLabel.trim(),
          data_schema: schema,
          file_format: fileFormat,
          sheet_name: fileFormat === "xlsx" ? sheetName.trim() : null,
          header_row: headerRow,
          encoding: fileFormat === "xlsx" ? "binary" : "utf-8",
          delimiter: fileFormat === "xlsx" ? null : fileFormat === "tsv" ? "\t" : delimiter,
          decimal_separator: decimalSeparator,
          channels,
          initial_gauge_length_m: geometrySource ? Number(gaugeLengthMm) / 1000 : null,
          initial_cross_section_area_m2: geometrySource ? Number(areaMm2) / 1_000_000 : null,
          approval_kind: "human_confirmed",
        },
        change_reason: "Human-approved governed tabular mapping",
      });
      setProfiles((current) => [created.data, ...current]);
      setSelectedProfileId(created.data.import_profile_id);
      setNotice(`Profile revision ${created.data.current_revision.revision_no} approved and reusable.`);
    } catch (profileError) {
      setError(errorMessage(profileError));
    } finally {
      setBusy(false);
    }
  }

  async function executeImport() {
    if (!selectedRun || !selectedProfile || !rawAssetId || !rawArtifactId) {
      setError("Choose the exact Test Run, uploaded Raw Asset, and approved Profile revision.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await executeGovernedTabularImport(config, {
        test_run_id: selectedRun.test_run_id,
        test_run_revision_id: selectedRun.current_revision.id,
        raw_asset_id: rawAssetId,
        raw_artifact_id: rawArtifactId,
        import_profile_id: selectedProfile.import_profile_id,
        import_profile_revision_id: selectedProfile.current_revision.id,
        change_reason: "Execute approved governed tabular import",
      });
      setRun(result.data);
      setNotice(
        result.data.status === "succeeded"
          ? "Import succeeded. Raw and normalized SI Dataset revisions are separate and immutable."
          : "Import failed without altering the Raw Asset; row-level evidence was preserved.",
      );
    } catch (runError) {
      setError(errorMessage(runError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel governed-import" aria-labelledby="governed-import-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">T-41 · reusable intake</p>
          <h3 id="governed-import-title">Governed CSV / TSV / XLSX import</h3>
          <p>
            Upload immutable source bytes, inspect headers, approve quantity and unit semantics,
            then create separate raw and normalized SI Datasets.
          </p>
        </div>
        <span className="reference-chip">explicit mapping</span>
      </div>

      {error ? <p className="error-banner" role="alert">{error}</p> : null}
      {notice ? <p className="success-banner">{notice}</p> : null}

      <div className="workflow-grid">
        <form className="form-stack workflow-card" onSubmit={(event) => void uploadAndPreview(event)}>
          <h4>1. Upload and preview</h4>
          <label>
            Exact Test Run
            <select value={testRunId} onChange={(event) => setTestRunId(event.target.value)}>
              <option value="">Choose a Run</option>
              {testRuns.map((item) => (
                <option key={item.test_run_id} value={item.test_run_id}>
                  {item.current_revision.content.run_label} · r{item.current_revision.revision_no}
                </option>
              ))}
            </select>
          </label>
          <label>
            Format
            <select value={fileFormat} onChange={(event) => setFileFormat(event.target.value as GovernedTabularFileFormat)}>
              <option value="csv">CSV</option><option value="tsv">TSV</option><option value="xlsx">XLSX</option>
            </select>
          </label>
          {fileFormat === "xlsx" ? (
            <label>Worksheet name<input value={sheetName} onChange={(event) => setSheetName(event.target.value)} /></label>
          ) : fileFormat === "csv" ? (
            <label>Delimiter<select value={delimiter} onChange={(event) => setDelimiter(event.target.value)}><option value=",">comma</option><option value=";">semicolon</option></select></label>
          ) : null}
          <div className="form-grid compact-grid">
            <label>Header row<input type="number" min="1" max="100" value={headerRow} onChange={(event) => setHeaderRow(Number(event.target.value))} /></label>
            <label>Decimal<select value={decimalSeparator} onChange={(event) => setDecimalSeparator(event.target.value as "." | ",")}><option value=".">dot</option><option value=",">comma</option></select></label>
          </div>
          <label>Source file<input type="file" accept=".csv,.tsv,.xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          <button className="primary-action" disabled={busy || !selectedRun || !file}>Upload immutable bytes and preview</button>
        </form>

        <form className="form-stack workflow-card" onSubmit={(event) => void approveProfile(event)}>
          <h4>2. Approve reusable Profile</h4>
          <label>Data schema<select value={schema} onChange={(event) => setSchema(event.target.value as GovernedTabularDataSchema)}>{SCHEMAS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          {(schema === "monotonic_tension" || schema === "monotonic_compression") ? (
            <label className="checkbox-line"><input type="checkbox" checked={geometrySource} onChange={(event) => setGeometrySource(event.target.checked)} />Source is displacement / force</label>
          ) : null}
          <div className="form-grid compact-grid">
            <label>Independent column<select value={firstColumn} onChange={(event) => setFirstColumn(event.target.value)}><option value="">Choose</option>{preview?.header_columns.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label>Original unit<select value={firstUnit} onChange={(event) => setFirstUnit(event.target.value)}>{UNIT_OPTIONS[channelQuantities[0]].map((unit) => <option key={unit}>{unit}</option>)}</select></label>
            <label>Dependent column<select value={secondColumn} onChange={(event) => setSecondColumn(event.target.value)}><option value="">Choose</option>{preview?.header_columns.map((name) => <option key={name}>{name}</option>)}</select></label>
            <label>Original unit<select value={secondUnit} onChange={(event) => setSecondUnit(event.target.value)}>{UNIT_OPTIONS[channelQuantities[1]].map((unit) => <option key={unit}>{unit}</option>)}</select></label>
          </div>
          {geometrySource ? <div className="form-grid compact-grid"><label>Gauge length (mm)<input type="number" min="0.000001" value={gaugeLengthMm} onChange={(event) => setGaugeLengthMm(event.target.value)} /></label><label>Area (mm²)<input type="number" min="0.000001" value={areaMm2} onChange={(event) => setAreaMm2(event.target.value)} /></label></div> : null}
          <label>Profile label<input value={profileLabel} onChange={(event) => setProfileLabel(event.target.value)} /></label>
          <button className="secondary-action" disabled={busy || !preview}>Approve immutable Profile revision</button>
        </form>

        <div className="workflow-card form-stack">
          <h4>3. Execute exact revision</h4>
          <label>Approved Profile<select value={selectedProfileId} onChange={(event) => setSelectedProfileId(event.target.value)}><option value="">Choose</option>{profiles.map((item) => <option key={item.import_profile_id} value={item.import_profile_id}>{item.content.profile_label} · {item.content.data_schema} · r{item.current_revision.revision_no}</option>)}</select></label>
          {selectedProfile ? <p className="muted">Pinned {short(selectedProfile.current_revision.id)} · {selectedProfile.content.file_format} · {selectedProfile.content.channels.map((item) => `${item.source_column} [${item.original_unit}]`).join(" / ")}</p> : null}
          <button className="primary-action" type="button" disabled={busy || !selectedProfile || !rawAssetId} onClick={() => void executeImport()}>Create raw + normalized SI Datasets</button>
          {run ? <div className={`status-card ${run.status === "succeeded" ? "status-success" : "status-warning"}`}><strong>{run.status}</strong><span>Import Run {short(run.import_run_id)}</span>{run.row_count ? <span>{run.row_count.toLocaleString()} rows</span> : null}{run.normalized_dataset_revision_id ? <span>Normalized revision {short(run.normalized_dataset_revision_id)}</span> : null}{run.failure_detail ? <span>{run.failure_detail}</span> : null}</div> : null}
        </div>
      </div>

      {preview ? (
        <div className="preview-table-wrap">
          <div className="curve-heading"><div><p className="eyebrow">Header evidence</p><h4>{preview.status}</h4></div><span className="reference-chip">{preview.file_format} · {short(preview.report_sha256)}</span></div>
          <table className="data-table"><thead><tr>{preview.header_columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{preview.sample_rows.map((row, rowIndex) => <tr key={rowIndex}>{preview.header_columns.map((column, index) => <td key={column}>{row[index]}</td>)}</tr>)}</tbody></table>
          <p className="muted">Preview values are not a committed mapping. Formula cells, macros, external links, unsafe ZIP paths, and excessive decompression are rejected.</p>
        </div>
      ) : null}
    </section>
  );
}

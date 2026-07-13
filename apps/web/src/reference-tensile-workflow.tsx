import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createReferenceTensileTestMethod,
  createReferenceTensileTestRun,
  createSpecimen,
  importReferenceTensileDataset,
  listDatasetRevisions,
  listDatasetsForMaterialState,
  listSpecimensForMaterialState,
  listTestMethods,
  listTestRunsForMaterialState,
  previewDatasetCurve,
  uploadReferenceTensileCsv,
} from "./api";
import type {
  CurvePreview,
  DatasetResponse,
  DatasetRevision,
  MaterialStateResponse,
  ReferenceTensileMapping,
  SpecimenResponse,
  TestMethodResponse,
  TestRunResponse,
} from "./types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return "The reference tensile workflow could not be completed. Check the protected API connection and try again.";
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function defaultPerformedAt(): string {
  const now = new Date();
  const shifted = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function plotPoints(curve: CurvePreview): string {
  const width = 720;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 18;
  const bottom = 40;
  const xs = curve.points.map((point) => point.engineering_strain);
  const ys = curve.points.map((point) => point.engineering_stress);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  return curve.points
    .map((point) => {
      const x = left + ((point.engineering_strain - minX) / xSpan) * (width - left - right);
      const y = height - bottom - ((point.engineering_stress - minY) / ySpan) * (height - top - bottom);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function CurvePanel({ curve }: { curve: CurvePreview }) {
  const xValues = curve.points.map((point) => point.engineering_strain);
  const yValues = curve.points.map((point) => point.engineering_stress);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  return (
    <section className="curve-panel" aria-label={`${curve.representation} tensile curve`}>
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Curve preview</p>
          <h5>{curve.representation === "raw" ? "Original-unit raw curve" : "Normalized SI curve"}</h5>
        </div>
        <span className="reference-chip">{curve.representation}</span>
      </div>
      <p className="curve-summary">
        {curve.returned_point_count.toLocaleString()} of {curve.point_count.toLocaleString()} point
        {curve.point_count === 1 ? "" : "s"} · strain ({curve.strain_unit}) · stress ({curve.stress_unit})
        {curve.sampled ? " · deterministically sampled for this preview" : ""}
      </p>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Stress strain curve">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline points={plotPoints(curve)} />
        <text x="48" y="264">{minX.toPrecision(4)}</text>
        <text x="642" y="264">{maxX.toPrecision(4)}</text>
        <text x="4" y="236">{minY.toPrecision(4)}</text>
        <text x="4" y="26">{maxY.toPrecision(4)}</text>
        <text x="340" y="278">engineering strain ({curve.strain_unit})</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">engineering stress ({curve.stress_unit})</text>
      </svg>
    </section>
  );
}

interface ReferenceTensileWorkflowProps {
  config: ApiConfig;
  state: MaterialStateResponse;
}

export function ReferenceTensileWorkflow({ config, state }: ReferenceTensileWorkflowProps) {
  const [open, setOpen] = useState(false);
  const [specimens, setSpecimens] = useState<SpecimenResponse[]>([]);
  const [methods, setMethods] = useState<TestMethodResponse[]>([]);
  const [runs, setRuns] = useState<TestRunResponse[]>([]);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [selectedSpecimenId, setSelectedSpecimenId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [datasetRevisions, setDatasetRevisions] = useState<DatasetRevision[]>([]);
  const [selectedDatasetRevisionId, setSelectedDatasetRevisionId] = useState("");
  const [curve, setCurve] = useState<CurvePreview | null>(null);
  const [specimenCode, setSpecimenCode] = useState("");
  const [orientation, setOrientation] = useState("");
  const [specimenReason, setSpecimenReason] = useState("Register reference tensile specimen");
  const [methodReason, setMethodReason] = useState("Register reference tensile method");
  const [runLabel, setRunLabel] = useState("Tensile run 001");
  const [performedAt, setPerformedAt] = useState(defaultPerformedAt);
  const [temperatureK, setTemperatureK] = useState("");
  const [crossheadSpeed, setCrossheadSpeed] = useState("");
  const [runReason, setRunReason] = useState("Register reference tensile test run");
  const [file, setFile] = useState<File | null>(null);
  const [strainColumn, setStrainColumn] = useState("");
  const [stressColumn, setStressColumn] = useState("");
  const [strainUnit, setStrainUnit] = useState<ReferenceTensileMapping["strain_unit"]>("1");
  const [stressUnit, setStressUnit] = useState<ReferenceTensileMapping["stress_unit"]>("MPa");
  const [datasetReason, setDatasetReason] = useState("Import reference tensile CSV and normalize units");
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const matchingMethods = useMemo(
    () => methods.filter(
      (method) => method.current_revision.content.method_code === "reference_uniaxial_tensile"
        && method.current_revision.classification === state.current_revision.classification,
    ),
    [methods, state.current_revision.classification],
  );
  const selectedSpecimen = specimens.find((specimen) => specimen.specimen_id === selectedSpecimenId) ?? null;
  const selectedRun = runs.find((run) => run.test_run_id === selectedRunId) ?? null;

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSpecimens, nextMethods, nextRuns, nextDatasets] = await Promise.all([
        listSpecimensForMaterialState(config, state.material_state_id),
        listTestMethods(config),
        listTestRunsForMaterialState(config, state.material_state_id),
        listDatasetsForMaterialState(config, state.material_state_id),
      ]);
      setSpecimens(nextSpecimens.data.items);
      setMethods(nextMethods.data.items);
      setRuns(nextRuns.data.items);
      setDatasets(nextDatasets.data.items);
      setSelectedSpecimenId((current) => current || nextSpecimens.data.items[0]?.specimen_id || "");
      setSelectedRunId((current) => current || nextRuns.data.items[0]?.test_run_id || "");
      setSelectedDatasetId((current) => current || nextDatasets.data.items[0]?.dataset_id || "");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }, [config, state.material_state_id]);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    if (!open || !selectedDatasetId) {
      setDatasetRevisions([]);
      setSelectedDatasetRevisionId("");
      return;
    }
    let current = true;
    void listDatasetRevisions(config, selectedDatasetId)
      .then((result) => {
        if (!current) {
          return;
        }
        setDatasetRevisions(result.data.revisions);
        const normalized = result.data.revisions.find(
          (revision) => revision.content.representation === "normalized",
        );
        setSelectedDatasetRevisionId((selected) => selected || normalized?.id || result.data.revisions[0]?.id || "");
      })
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, open, selectedDatasetId]);

  useEffect(() => {
    if (!open || !selectedDatasetRevisionId) {
      setCurve(null);
      return;
    }
    let current = true;
    void previewDatasetCurve(config, selectedDatasetRevisionId)
      .then((result) => current && setCurve(result.data))
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, open, selectedDatasetRevisionId]);

  async function submitSpecimen(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAction("specimen");
    setError(null);
    try {
      const result = await createSpecimen(config, state.material_state_id, {
        material_state_revision_id: state.current_revision.id,
        specimen_code: specimenCode.trim(),
        orientation: optionalText(orientation),
        preparation_note: null,
        change_reason: specimenReason.trim(),
      });
      setSpecimens((current) => [result.data, ...current]);
      setSelectedSpecimenId(result.data.specimen_id);
      setSpecimenCode("");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function registerMethod(): Promise<void> {
    setAction("method");
    setError(null);
    try {
      const result = await createReferenceTensileTestMethod(config, {
        classification: state.current_revision.classification,
        change_reason: methodReason.trim(),
      });
      setMethods((current) => [result.data, ...current]);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const method = matchingMethods[0];
    if (!selectedSpecimen || !method) {
      return;
    }
    setAction("run");
    setError(null);
    try {
      const performed = new Date(performedAt);
      if (Number.isNaN(performed.getTime())) {
        throw new ApiError(422, "Provide a valid performed-at timestamp for the Test Run.");
      }
      const result = await createReferenceTensileTestRun(config, {
        specimen_id: selectedSpecimen.specimen_id,
        specimen_revision_id: selectedSpecimen.current_revision.id,
        test_method_id: method.test_method_id,
        test_method_revision_id: method.current_revision.id,
        run_label: runLabel.trim(),
        performed_at: performed.toISOString(),
        test_temperature_k: optionalNumber(temperatureK),
        crosshead_speed_mm_per_min: optionalNumber(crossheadSpeed),
        change_reason: runReason.trim(),
      });
      setRuns((current) => [result.data, ...current]);
      setSelectedRunId(result.data.test_run_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>): void {
    setFile(event.target.files?.[0] ?? null);
  }

  async function submitDataset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!file || !selectedRun) {
      return;
    }
    setAction("dataset");
    setError(null);
    try {
      const completed = await uploadReferenceTensileCsv(config, {
        file,
        classification: state.current_revision.classification,
        test_run_revision_id: selectedRun.current_revision.id,
      });
      if (!completed.data.available_artifact_id) {
        throw new ApiError(409, "The raw CSV was stored but no immutable Artifact is available for Dataset import.");
      }
      const result = await importReferenceTensileDataset(config, {
        test_run_id: selectedRun.test_run_id,
        test_run_revision_id: selectedRun.current_revision.id,
        raw_asset_id: completed.data.raw_asset.raw_asset_id,
        raw_artifact_id: completed.data.available_artifact_id,
        mapping: {
          strain_column: strainColumn.trim(),
          stress_column: stressColumn.trim(),
          strain_unit: strainUnit,
          stress_unit: stressUnit,
        },
        change_reason: datasetReason.trim(),
      });
      setDatasets((current) => [result.data, ...current.filter((item) => item.dataset_id !== result.data.dataset_id)]);
      setSelectedDatasetId(result.data.dataset_id);
      setSelectedDatasetRevisionId(result.data.current_revision.id);
      setFile(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-tensile-workflow" aria-label="Reference tensile Dataset workflow">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Test data workflow</p>
          <h4>Reference tensile CSV → Dataset revision</h4>
        </div>
        <span className="reference-chip">Reference only</span>
      </div>
      <p className="form-hint">
        Preserve the uploaded source as an immutable Raw Asset, explicitly confirm column and unit
        semantics, then view separate raw and normalized Dataset revisions.
      </p>
      <button className="text-button workflow-toggle" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? "Close test data workflow" : "Manage reference tensile data"}
      </button>
      {!open ? null : (
        <div className="workflow-stack tensile-workflow-stack">
          <div className="workflow-toolbar">
            <span>{loading ? "Loading tenant-scoped test data…" : "All records are immutable revisions."}</span>
            <button className="text-button" type="button" onClick={() => void refresh()} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <p className="error-notice" role="alert">{error}</p> : null}
          <div className="workflow-step">
            <strong>1. Register a concrete Specimen</strong>
            <form className="form-stack" onSubmit={(event) => void submitSpecimen(event)}>
              <div className="form-grid">
                <label>Specimen code<input value={specimenCode} onChange={(event) => setSpecimenCode(event.target.value)} required /></label>
                <label>Orientation (optional)<input value={orientation} onChange={(event) => setOrientation(event.target.value)} /></label>
              </div>
              <label>Change reason<input value={specimenReason} onChange={(event) => setSpecimenReason(event.target.value)} required /></label>
              <button className="button secondary" type="submit" disabled={action !== null}>
                {action === "specimen" ? "Registering specimen…" : "Register specimen"}
              </button>
            </form>
            {specimens.length ? (
              <label>
                Test Run specimen
                <select value={selectedSpecimenId} onChange={(event) => setSelectedSpecimenId(event.target.value)}>
                  {specimens.map((specimen) => <option key={specimen.specimen_id} value={specimen.specimen_id}>{specimen.current_revision.content.specimen_code} · r{specimen.current_revision.revision_no}</option>)}
                </select>
              </label>
            ) : <small className="muted">Register a Specimen before creating a Test Run.</small>}
          </div>
          <div className="workflow-step">
            <strong>2. Bind the reference tensile Test Method</strong>
            {matchingMethods.length ? (
              <p className="source-line">Reference method revision {shortId(matchingMethods[0].current_revision.id)} is available for this classification.</p>
            ) : (
              <>
                <p className="form-hint">This intentionally narrow method is a reference CSV contract, not a generic Test Method schema.</p>
                <label>Change reason<input value={methodReason} onChange={(event) => setMethodReason(event.target.value)} required /></label>
                <button className="button secondary" type="button" onClick={() => void registerMethod()} disabled={action !== null}>
                  {action === "method" ? "Registering method…" : "Register reference method"}
                </button>
              </>
            )}
          </div>
          <div className="workflow-step">
            <strong>3. Create a Test Run pinned to those revisions</strong>
            <form className="form-stack" onSubmit={(event) => void submitRun(event)}>
              <div className="form-grid">
                <label>Run label<input value={runLabel} onChange={(event) => setRunLabel(event.target.value)} required /></label>
                <label>Performed at<input type="datetime-local" value={performedAt} onChange={(event) => setPerformedAt(event.target.value)} required /></label>
                <label>Temperature (K, optional)<input type="number" min="0" step="any" value={temperatureK} onChange={(event) => setTemperatureK(event.target.value)} /></label>
                <label>Crosshead speed (mm/min, optional)<input type="number" min="0" step="any" value={crossheadSpeed} onChange={(event) => setCrossheadSpeed(event.target.value)} /></label>
              </div>
              <label>Change reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
              <button className="button secondary" type="submit" disabled={!selectedSpecimen || !matchingMethods.length || action !== null}>
                {action === "run" ? "Creating Test Run…" : "Create Test Run"}
              </button>
            </form>
            {runs.length ? (
              <label>
                Dataset source Test Run
                <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>
                  {runs.map((run) => <option key={run.test_run_id} value={run.test_run_id}>{run.current_revision.content.run_label} · r{run.current_revision.revision_no} · {shortId(run.current_revision.id)}</option>)}
                </select>
              </label>
            ) : <small className="muted">Create a Test Run before uploading a Dataset source.</small>}
          </div>
          <div className="workflow-step">
            <strong>4. Upload and explicitly map the CSV</strong>
            <p className="form-hint">Only UTF-8 CSV up to 16 MiB is accepted. Column names are never inferred; the source bytes and their raw-unit curve remain available after normalization.</p>
            <form className="form-stack" onSubmit={(event) => void submitDataset(event)}>
              <label>Reference tensile CSV<input type="file" accept=".csv,text/csv" onChange={selectFile} required /></label>
              {file ? <small className="source-line">{file.name} · {file.size.toLocaleString()} bytes</small> : null}
              <div className="form-grid">
                <label>Strain column<input value={strainColumn} onChange={(event) => setStrainColumn(event.target.value)} placeholder="e.g. engineering_strain" required /></label>
                <label>Stress column<input value={stressColumn} onChange={(event) => setStressColumn(event.target.value)} placeholder="e.g. engineering_stress" required /></label>
                <label>Source strain unit<select value={strainUnit} onChange={(event) => setStrainUnit(event.target.value as ReferenceTensileMapping["strain_unit"])}><option value="1">1</option><option value="%">%</option></select></label>
                <label>Source stress unit<select value={stressUnit} onChange={(event) => setStressUnit(event.target.value as ReferenceTensileMapping["stress_unit"])}><option value="Pa">Pa</option><option value="kPa">kPa</option><option value="MPa">MPa</option><option value="GPa">GPa</option></select></label>
              </div>
              <label>Change reason<input value={datasetReason} onChange={(event) => setDatasetReason(event.target.value)} required /></label>
              <button className="button primary" type="submit" disabled={!selectedRun || !file || action !== null}>
                {action === "dataset" ? "Uploading and normalizing…" : "Create raw and normalized Dataset revisions"}
              </button>
            </form>
          </div>
          <div className="workflow-step dataset-results">
            <strong>5. Inspect immutable raw and normalized curves</strong>
            {!datasets.length ? <p className="muted">No Dataset revision is available for this Material State yet.</p> : null}
            {datasets.length ? (
              <>
                <label>
                  Dataset
                  <select value={selectedDatasetId} onChange={(event) => { setSelectedDatasetId(event.target.value); setSelectedDatasetRevisionId(""); }}>
                    {datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{shortId(dataset.dataset_id)} · current {dataset.current_revision.content.representation} r{dataset.current_revision.revision_no}</option>)}
                  </select>
                </label>
                {datasetRevisions.length ? (
                  <label>
                    Dataset revision
                    <select value={selectedDatasetRevisionId} onChange={(event) => setSelectedDatasetRevisionId(event.target.value)}>
                      {datasetRevisions.map((revision) => <option key={revision.id} value={revision.id}>r{revision.revision_no} · {revision.content.representation} · {revision.content.point_count.toLocaleString()} points</option>)}
                    </select>
                  </label>
                ) : null}
                {curve ? <CurvePanel curve={curve} /> : <p className="muted">Select a Dataset revision to load its curve.</p>}
              </>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}

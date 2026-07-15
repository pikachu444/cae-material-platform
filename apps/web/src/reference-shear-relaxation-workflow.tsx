import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceShearRelaxationTestMethod,
  createReferenceShearRelaxationCropRecipe,
  createReferenceShearRelaxationTestRun,
  createSpecimen,
  importReferenceShearRelaxationDataset,
  executeReferenceShearRelaxationCrop,
  listShearRelaxationDatasetsForMaterialState,
  listSpecimensForMaterialState,
  listTestMethods,
  listTestRunsForMaterialState,
  previewShearRelaxationDataset,
  uploadReferenceTensileCsv,
} from "./api";
import type {
  MaterialStateResponse,
  ShearRelaxationCurvePreview,
  ShearRelaxationDatasetResponse,
  ShearRelaxationProcessingRunResponse,
  SpecimenResponse,
  TestMethodResponse,
  TestRunResponse,
} from "./types";

function message(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The shear-relaxation Dataset workflow could not be completed.";
}

function localDateTime(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

function plot(curve: ShearRelaxationCurvePreview): string {
  const times = curve.points.map((point) => Math.log10(Math.max(point.time, 1e-12)));
  const moduli = curve.points.map((point) => point.shear_modulus);
  const minX = Math.min(...times);
  const maxX = Math.max(...times);
  const minY = Math.min(...moduli);
  const maxY = Math.max(...moduli);
  return curve.points
    .map((point, index) => {
      const x = 48 + ((times[index] - minX) / (maxX - minX || 1)) * 654;
      const y = 240 - ((point.shear_modulus - minY) / (maxY - minY || 1)) * 222;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function Curve({ value }: { value: ShearRelaxationCurvePreview }) {
  return (
    <section className="curve-panel" aria-label="Normalized shear relaxation curve">
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Immutable Dataset preview</p>
          <h5>Relaxation shear modulus</h5>
        </div>
        <span className="reference-chip">{value.representation}</span>
      </div>
      <p className="curve-summary">
        {value.returned_point_count.toLocaleString()} of {value.point_count.toLocaleString()} points
        · time ({value.time_unit}) · shear modulus ({value.shear_modulus_unit})
      </p>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Shear modulus relaxation over logarithmic time">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline points={plot(value)} />
        <text x="300" y="276">time ({value.time_unit}, logarithmic axis)</text>
        <text x="14" y="164" transform="rotate(-90 14 164)">shear modulus ({value.shear_modulus_unit})</text>
      </svg>
    </section>
  );
}

export function ReferenceShearRelaxationWorkflow({
  config,
  state,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
}) {
  const [open, setOpen] = useState(false);
  const [specimens, setSpecimens] = useState<SpecimenResponse[]>([]);
  const [methods, setMethods] = useState<TestMethodResponse[]>([]);
  const [runs, setRuns] = useState<TestRunResponse[]>([]);
  const [datasets, setDatasets] = useState<ShearRelaxationDatasetResponse[]>([]);
  const [specimenId, setSpecimenId] = useState("");
  const [specimenCode, setSpecimenCode] = useState("SR-001");
  const [runId, setRunId] = useState("");
  const [runLabel, setRunLabel] = useState("Shear relaxation 001");
  const [performedAt, setPerformedAt] = useState(localDateTime);
  const [temperatureK, setTemperatureK] = useState("296.15");
  const [file, setFile] = useState<File | null>(null);
  const [timeColumn, setTimeColumn] = useState("time");
  const [modulusColumn, setModulusColumn] = useState("shear_modulus");
  const [timeUnit, setTimeUnit] = useState<"s" | "ms" | "min" | "h">("s");
  const [modulusUnit, setModulusUnit] = useState<"Pa" | "kPa" | "MPa" | "GPa">("MPa");
  const [curve, setCurve] = useState<ShearRelaxationCurvePreview | null>(null);
  const [minimumTimeS, setMinimumTimeS] = useState("0");
  const [maximumTimeS, setMaximumTimeS] = useState("100");
  const [processingRun, setProcessingRun] = useState<ShearRelaxationProcessingRunResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const shearMethods = useMemo(
    () => methods.filter((item) => (
      item.current_revision.content.method_code === "reference_shear_relaxation"
      && item.current_revision.classification === state.current_revision.classification
    )),
    [methods, state.current_revision.classification],
  );
  const shearMethodIds = useMemo(
    () => new Set(shearMethods.map((item) => item.test_method_id)),
    [shearMethods],
  );
  const shearRuns = useMemo(
    () => runs.filter((item) => shearMethodIds.has(item.test_method_id)),
    [runs, shearMethodIds],
  );

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [nextSpecimens, nextMethods, nextRuns, nextDatasets] = await Promise.all([
        listSpecimensForMaterialState(config, state.material_state_id),
        listTestMethods(config),
        listTestRunsForMaterialState(config, state.material_state_id),
        listShearRelaxationDatasetsForMaterialState(config, state.material_state_id),
      ]);
      setSpecimens(nextSpecimens.data.items);
      setMethods(nextMethods.data.items);
      setRuns(nextRuns.data.items);
      setDatasets(nextDatasets.data.items);
      setSpecimenId((current) => current || nextSpecimens.data.items[0]?.specimen_id || "");
    } catch (cause) {
      setError(message(cause));
    }
  }, [config, state.material_state_id]);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  useEffect(() => {
    if (!runId && shearRuns[0]) setRunId(shearRuns[0].test_run_id);
  }, [runId, shearRuns]);

  useEffect(() => {
    const head = datasets[0];
    if (!open || !head) {
      setCurve(null);
      return;
    }
    let active = true;
    void previewShearRelaxationDataset(config, head.dataset_id)
      .then((result) => active && setCurve(result.data))
      .catch((cause: unknown) => active && setError(message(cause)));
    return () => { active = false; };
  }, [config, datasets, open]);

  async function createNewSpecimen(): Promise<void> {
    setBusy("specimen");
    setError(null);
    try {
      const result = await createSpecimen(config, state.material_state_id, {
        material_state_revision_id: state.current_revision.id,
        specimen_code: specimenCode.trim(),
        orientation: null,
        preparation_note: "Reference shear-relaxation specimen",
        change_reason: "Register reference shear-relaxation specimen",
      });
      setSpecimenId(result.data.specimen_id);
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(null);
    }
  }

  async function createMethod(): Promise<void> {
    setBusy("method");
    setError(null);
    try {
      await createReferenceShearRelaxationTestMethod(config, {
        classification: state.current_revision.classification,
        change_reason: "Register reference shear-relaxation method",
      });
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(null);
    }
  }

  async function createRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const specimen = specimens.find((item) => item.specimen_id === specimenId);
    const method = shearMethods[0];
    if (!specimen || !method) return;
    setBusy("run");
    setError(null);
    try {
      const result = await createReferenceShearRelaxationTestRun(config, {
        specimen_id: specimen.specimen_id,
        specimen_revision_id: specimen.current_revision.id,
        test_method_id: method.test_method_id,
        test_method_revision_id: method.current_revision.id,
        run_label: runLabel.trim(),
        performed_at: new Date(performedAt).toISOString(),
        test_temperature_k: temperatureK.trim() ? Number(temperatureK) : null,
        change_reason: "Register reference shear-relaxation Test Run",
      });
      setRunId(result.data.test_run_id);
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(null);
    }
  }

  async function importCsv(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const run = shearRuns.find((item) => item.test_run_id === runId);
    if (!run || !file) return;
    setBusy("import");
    setError(null);
    try {
      const upload = await uploadReferenceTensileCsv(config, {
        file,
        classification: state.current_revision.classification,
        test_run_revision_id: run.current_revision.id,
      });
      if (!upload.data.raw_asset || !upload.data.available_artifact_id) {
        throw new ApiError(409, "The verified upload did not produce an immutable raw Artifact.");
      }
      await importReferenceShearRelaxationDataset(config, {
        test_run_id: run.test_run_id,
        test_run_revision_id: run.current_revision.id,
        raw_asset_id: upload.data.raw_asset.raw_asset_id,
        raw_artifact_id: upload.data.available_artifact_id,
        mapping: {
          time_column: timeColumn.trim(),
          shear_modulus_column: modulusColumn.trim(),
          time_unit: timeUnit,
          shear_modulus_unit: modulusUnit,
        },
        change_reason: "Import and normalize user-confirmed shear-relaxation CSV",
      });
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(null);
    }
  }

  async function processCurve(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const source = datasets.find(
      (item) => item.current_revision.content.representation === "normalized",
    );
    if (!source) return;
    setBusy("processing");
    setError(null);
    try {
      const recipe = await createReferenceShearRelaxationCropRecipe(config, {
        classification: state.current_revision.classification,
        recipe_label: `Time crop ${new Date().toISOString()}`,
        minimum_time_s: Number(minimumTimeS),
        maximum_time_s: Number(maximumTimeS),
        change_reason: "Define observed-point shear-relaxation time crop",
      });
      const result = await executeReferenceShearRelaxationCrop(config, {
        recipe_id: recipe.data.recipe_id,
        recipe_revision_id: recipe.data.current_revision.id,
        input_dataset_id: source.dataset_id,
        input_dataset_revision_id: source.current_revision.id,
        change_reason: "Commit processed shear-relaxation Dataset",
      });
      setProcessingRun(result.data);
      await refresh();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="workflow-card">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Test data · viscoelastic evidence</p>
          <h4>Shear-relaxation Dataset</h4>
        </div>
        <button className="text-button" type="button" onClick={() => setOpen((value) => !value)}>
          {open ? "Close" : "Open workflow"}
        </button>
      </div>
      <p className="form-hint">
        Preserve the original CSV, pin explicit column/unit semantics, and store a normalized SI
        curve. This evidence is not silently fitted into Prony terms.
      </p>
      {open ? (
        <div className="form-stack">
          <div className="form-grid">
            <label>
              Specimen
              <select value={specimenId} onChange={(event) => setSpecimenId(event.target.value)}>
                <option value="">Choose a specimen</option>
                {specimens.map((item) => (
                  <option key={item.specimen_id} value={item.specimen_id}>
                    {item.current_revision.content.specimen_code}
                  </option>
                ))}
              </select>
            </label>
            <label>
              New specimen code
              <input value={specimenCode} onChange={(event) => setSpecimenCode(event.target.value)} />
            </label>
          </div>
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={() => void createNewSpecimen()} disabled={busy !== null}>
              Create specimen
            </button>
            {shearMethods.length === 0 ? (
              <button type="button" className="button secondary" onClick={() => void createMethod()} disabled={busy !== null}>
                Register shear-relaxation method
              </button>
            ) : <span className="reference-chip">method ready</span>}
          </div>
          <form className="form-stack" onSubmit={createRun}>
            <div className="form-grid">
              <label>Run label<input value={runLabel} onChange={(event) => setRunLabel(event.target.value)} /></label>
              <label>Performed at<input type="datetime-local" value={performedAt} onChange={(event) => setPerformedAt(event.target.value)} /></label>
              <label>Temperature (K)<input type="number" min="0" step="any" value={temperatureK} onChange={(event) => setTemperatureK(event.target.value)} /></label>
            </div>
            <button className="button secondary" type="submit" disabled={!specimenId || shearMethods.length === 0 || busy !== null}>
              Create Test Run
            </button>
          </form>
          <form className="form-stack" onSubmit={importCsv}>
            <div className="form-grid">
              <label>
                Test Run
                <select value={runId} onChange={(event) => setRunId(event.target.value)}>
                  <option value="">Choose a shear-relaxation run</option>
                  {shearRuns.map((item) => <option key={item.test_run_id} value={item.test_run_id}>{item.current_revision.content.run_label}</option>)}
                </select>
              </label>
              <label>CSV file<input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
              <label>Time column<input value={timeColumn} onChange={(event) => setTimeColumn(event.target.value)} /></label>
              <label>Shear modulus column<input value={modulusColumn} onChange={(event) => setModulusColumn(event.target.value)} /></label>
              <label>Time unit<select value={timeUnit} onChange={(event) => setTimeUnit(event.target.value as typeof timeUnit)}>{["s", "ms", "min", "h"].map((unit) => <option key={unit}>{unit}</option>)}</select></label>
              <label>Modulus unit<select value={modulusUnit} onChange={(event) => setModulusUnit(event.target.value as typeof modulusUnit)}>{["Pa", "kPa", "MPa", "GPa"].map((unit) => <option key={unit}>{unit}</option>)}</select></label>
            </div>
            <button className="button primary" type="submit" disabled={!runId || !file || busy !== null}>
              {busy === "import" ? "Importing…" : "Upload and normalize Dataset"}
            </button>
          </form>
          <form className="form-stack" onSubmit={processCurve}>
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">Explicit processing revision</p>
                <h5>Observed-point time crop</h5>
              </div>
              <span className="reference-chip">no interpolation</span>
            </div>
            <p className="form-hint">
              Select an inclusive time window from the normalized SI curve. The source revision
              remains immutable; the result is a separate processed Dataset identity.
            </p>
            <div className="form-grid">
              <label>
                Minimum time (s)
                <input type="number" min="0" step="any" value={minimumTimeS} onChange={(event) => setMinimumTimeS(event.target.value)} />
              </label>
              <label>
                Maximum time (s)
                <input type="number" min="0" step="any" value={maximumTimeS} onChange={(event) => setMaximumTimeS(event.target.value)} />
              </label>
            </div>
            <button
              className="button secondary"
              type="submit"
              disabled={
                !datasets.some((item) => item.current_revision.content.representation === "normalized")
                || busy !== null
              }
            >
              {busy === "processing" ? "Processing…" : "Create recipe and processed Dataset"}
            </button>
            {processingRun ? (
              <p className="success-notice" role="status">
                Processing {processingRun.status}: {processingRun.output_point_count} of {processingRun.input_point_count} observed points retained.
              </p>
            ) : null}
          </form>
          {error ? <div className="error-notice" role="alert">{error}</div> : null}
          {datasets.length > 0 ? (
            <p className="curve-summary">
              {datasets.length} immutable Dataset {datasets.length === 1 ? "identity" : "identities"}; latest revision r{datasets[0].current_revision.revision_no}
            </p>
          ) : null}
          {curve ? <Curve value={curve} /> : null}
        </div>
      ) : null}
    </section>
  );
}

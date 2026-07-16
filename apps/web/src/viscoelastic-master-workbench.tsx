import { type FormEvent, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createViscoelasticMasterPlan,
  createViscoelasticSelection,
  executeViscoelasticMasterPlan,
  previewViscoelasticMasterRun,
} from "./api";
import type {
  MaterialStateResponse,
  ShearRelaxationDatasetResponse,
  TestRunResponse,
  ViscoelasticMasterPreviewResponse,
  ViscoelasticShiftMethod,
} from "./types";

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The viscoelastic master-curve workflow could not be completed.";
}

interface PlotCurve {
  id: string;
  label: string;
  points: Array<{ x: number; y: number }>;
  kind: "replicate" | "master";
}

function MasterCurveChart({ value }: { value: ViscoelasticMasterPreviewResponse }) {
  const shifts = new Map(
    value.run.shift_factors.map((item) => [item.temperature_k, item.log10_a_t]),
  );
  const curves: PlotCurve[] = [
    ...value.aligned_curves.map((curve) => ({
      id: `member-${curve.member_ordinal}`,
      label: `${curve.temperature_k.toFixed(2)} K · replicate ${curve.member_ordinal + 1}`,
      kind: "replicate" as const,
      points: curve.points.map((point) => ({
        x: Math.log10(point.time_s) - (shifts.get(curve.temperature_k) ?? 0),
        y: point.shear_modulus_pa,
      })),
    })),
    {
      id: "master",
      label: `Master · ${value.reference_temperature_k.toFixed(2)} K`,
      kind: "master" as const,
      points: value.master_curve.map((point) => ({
        x: Math.log10(point.reduced_time_s),
        y: point.mean_shear_modulus_pa,
      })),
    },
  ];
  const all = curves.flatMap((curve) => curve.points);
  const minX = Math.min(...all.map((point) => point.x));
  const maxX = Math.max(...all.map((point) => point.x));
  const minY = Math.min(...all.map((point) => point.y));
  const maxY = Math.max(...all.map((point) => point.y));
  const polyline = (curve: PlotCurve) =>
    curve.points
      .map((point) => {
        const x = 54 + ((point.x - minX) / (maxX - minX || 1)) * 642;
        const y = 242 - ((point.y - minY) / (maxY - minY || 1)) * 216;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

  return (
    <section className="curve-panel" aria-label="Shifted relaxation curves and master curve">
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Reduced time · t / aT</p>
          <h5>Shifted replicates and master curve</h5>
        </div>
        <span className="reference-chip">no extrapolation</span>
      </div>
      <svg
        className="curve-plot viscoelastic-master-plot"
        viewBox="0 0 720 280"
        role="img"
        aria-label="Shifted shear relaxation replicates with master curve"
      >
        <line x1="54" x2="696" y1="242" y2="242" />
        <line x1="54" x2="54" y1="26" y2="242" />
        {curves.map((curve) => (
          <polyline
            key={curve.id}
            className={curve.kind === "master" ? "master-curve-line" : "replicate-curve-line"}
            points={polyline(curve)}
          />
        ))}
        <text x="292" y="275">reduced time (s, logarithmic axis)</text>
        <text x="16" y="174" transform="rotate(-90 16 174)">shear modulus (Pa)</text>
      </svg>
      <div className="master-curve-legend" aria-label="Curve legend">
        {curves.map((curve) => (
          <span key={curve.id} className={curve.kind === "master" ? "master-key" : "replicate-key"}>
            {curve.label}
          </span>
        ))}
      </div>
    </section>
  );
}

export function ViscoelasticMasterWorkbench({
  config,
  state,
  datasets,
  runs,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  datasets: ShearRelaxationDatasetResponse[];
  runs: TestRunResponse[];
}) {
  const eligible = useMemo(
    () => datasets.filter((item) => item.current_revision.content.representation !== "raw"),
    [datasets],
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [method, setMethod] = useState<ViscoelasticShiftMethod>("manual");
  const [referenceTemperature, setReferenceTemperature] = useState("");
  const [manualShifts, setManualShifts] = useState<Record<string, string>>({});
  const [gridPointCount, setGridPointCount] = useState("101");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ViscoelasticMasterPreviewResponse | null>(null);

  const selectedDatasets = eligible.filter((item) => selected.includes(item.dataset_id));
  const temperatures = Array.from(
    new Set(
      selectedDatasets.flatMap((dataset) => {
        const run = runs.find(
          (item) => item.current_revision.id === dataset.current_revision.content.test_run_revision_id,
        );
        return run?.current_revision.content.test_temperature_k == null
          ? []
          : [run.current_revision.content.test_temperature_k];
      }),
    ),
  ).sort((left, right) => left - right);

  function temperatureFor(dataset: ShearRelaxationDatasetResponse): number | null {
    const run = runs.find(
      (item) => item.current_revision.id === dataset.current_revision.content.test_run_revision_id,
    );
    return run?.current_revision.content.test_temperature_k ?? null;
  }

  function toggle(datasetId: string): void {
    setSelected((current) =>
      current.includes(datasetId)
        ? current.filter((item) => item !== datasetId)
        : [...current, datasetId],
    );
    setPreview(null);
  }

  async function execute(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const reference = Number(referenceTemperature);
    if (selectedDatasets.length < 2 || temperatures.length < 2 || !temperatures.includes(reference)) {
      setError("Choose at least two curves across two temperatures and a listed reference temperature.");
      return;
    }
    if (method === "wlf_fit" && temperatures.length < 3) {
      setError("WLF fitting requires at least three distinct temperatures.");
      return;
    }
    const factors = method === "manual"
      ? temperatures.map((temperature) => ({
          temperature_k: temperature,
          log10_a_t: Number(manualShifts[String(temperature)] ?? (temperature === reference ? "0" : "")),
        }))
      : [];
    if (factors.some((item) => !Number.isFinite(item.log10_a_t))) {
      setError("Enter a finite log10(aT) for every selected temperature.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selection = await createViscoelasticSelection(config, {
        classification: state.current_revision.classification,
        selection_label: `TTS replicate set ${new Date().toISOString()}`,
        members: selectedDatasets.map((dataset) => ({
          dataset_id: dataset.dataset_id,
          dataset_revision_id: dataset.current_revision.id,
        })),
        change_reason: "Pin exact shear-relaxation replicate and temperature evidence",
      });
      const plan = await createViscoelasticMasterPlan(config, {
        classification: state.current_revision.classification,
        plan_label: `Master curve ${reference.toFixed(2)} K`,
        selection_id: selection.data.selection_id,
        selection_revision_id: selection.data.current_revision.id,
        reference_temperature_k: reference,
        grid_point_count: Number(gridPointCount),
        shift_method: method,
        manual_shift_factors: factors,
        change_reason: "Define log-time alignment, shift and no-extrapolation policy",
      });
      const run = await executeViscoelasticMasterPlan(config, {
        plan_id: plan.data.plan_id,
        plan_revision_id: plan.data.current_revision.id,
        change_reason: "Commit aligned, statistical and master-curve Dataset revisions",
      });
      const result = await previewViscoelasticMasterRun(
        config,
        run.data.processing_run_id,
      );
      setPreview(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="form-stack master-curve-workbench" onSubmit={execute}>
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Replicates · statistics · time-temperature superposition</p>
          <h5>Viscoelastic master curve</h5>
        </div>
        <span className="reference-chip">typed Dataset revisions</span>
      </div>
      <p className="form-hint">
        Keep every curve, align replicates only on their common log-time intersection, review n and
        bands, then shift by explicit factors or a fitted WLF relation. No source is overwritten.
      </p>
      <div className="selection-grid" aria-label="Eligible relaxation Dataset revisions">
        {eligible.length === 0 ? (
          <p className="empty-state">Import normalized shear-relaxation curves first.</p>
        ) : eligible.map((dataset) => {
          const temperature = temperatureFor(dataset);
          return (
            <label className="selection-card" key={dataset.dataset_id}>
              <input
                type="checkbox"
                checked={selected.includes(dataset.dataset_id)}
                onChange={() => toggle(dataset.dataset_id)}
              />
              <span>
                <strong>{temperature == null ? "Missing temperature" : `${temperature.toFixed(2)} K`}</strong>
                <small>
                  {dataset.current_revision.content.representation} · r{dataset.current_revision.revision_no}
                  {" · "}{dataset.current_revision.content.point_count} points
                </small>
              </span>
            </label>
          );
        })}
      </div>
      <div className="form-grid">
        <label>
          Shift method
          <select value={method} onChange={(event) => setMethod(event.target.value as ViscoelasticShiftMethod)}>
            <option value="manual">Manual shift factors</option>
            <option value="wlf_fit">WLF fit (3+ temperatures)</option>
          </select>
        </label>
        <label>
          Reference temperature (K)
          <select value={referenceTemperature} onChange={(event) => setReferenceTemperature(event.target.value)}>
            <option value="">Choose reference</option>
            {temperatures.map((temperature) => (
              <option key={temperature} value={temperature}>{temperature.toFixed(2)} K</option>
            ))}
          </select>
        </label>
        <label>
          Grid points
          <input type="number" min="3" max="501" value={gridPointCount} onChange={(event) => setGridPointCount(event.target.value)} />
        </label>
      </div>
      {method === "manual" && temperatures.length > 0 ? (
        <div className="form-grid" aria-label="Manual shift factors">
          {temperatures.map((temperature) => (
            <label key={temperature}>
              log10(aT) · {temperature.toFixed(2)} K
              <input
                type="number"
                min="-20"
                max="20"
                step="any"
                value={temperature === Number(referenceTemperature) ? "0" : (manualShifts[String(temperature)] ?? "")}
                disabled={temperature === Number(referenceTemperature)}
                onChange={(event) => setManualShifts((current) => ({ ...current, [String(temperature)]: event.target.value }))}
              />
            </label>
          ))}
        </div>
      ) : null}
      <button className="button primary" type="submit" disabled={busy || selectedDatasets.length < 2}>
        {busy ? "Building master curve..." : "Create Selection, process statistics and master curve"}
      </button>
      {error ? <div className="error-notice" role="alert">{error}</div> : null}
      {preview ? (
        <div className="form-stack" data-testid="viscoelastic-master-result">
          <p className="success-notice" role="status">
            Three immutable outputs committed: {preview.run.aligned_row_count} aligned rows, {preview.run.statistics_row_count} statistical rows, and {preview.run.master_row_count} master points.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Temperature</th><th>Replicates n</th><th>log10(aT)</th><th>Source</th><th>Band</th><th>Outlier</th></tr></thead>
              <tbody>
                {preview.temperature_statistics.map((statistics) => {
                  const shift = preview.run.shift_factors.find((item) => item.temperature_k === statistics.temperature_k);
                  return (
                    <tr key={statistics.temperature_k}>
                      <td>{statistics.temperature_k.toFixed(2)} K</td>
                      <td>{statistics.replicate_count}</td>
                      <td>{shift?.log10_a_t.toPrecision(5)}</td>
                      <td>{shift?.source}</td>
                      <td>min / max + {statistics.replicate_count > 1 ? "sample σ" : "σ unavailable"}</td>
                      <td>not assessed</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <MasterCurveChart value={preview} />
        </div>
      ) : null}
    </form>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createElastoplasticSolverCard,
  createTabulatedPlasticityModel,
  downloadElastoplasticSolverCard,
  getTabulatedPlasticityHardeningCurve,
  listDatasetsForMaterialState,
  listElastoplasticSolverCards,
  listTabulatedPlasticityModels,
  preflightElastoplasticMapping,
  previewElastoplasticSolverCard,
} from "./api";
import type {
  DatasetResponse,
  ElastoplasticCardResponse,
  ExportTarget,
  HardeningCurveResponse,
  MappingReport,
  MaterialStateResponse,
  PropertySetResponse,
  TabulatedPlasticityModelResponse,
} from "./types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return "The elastoplastic workflow could not be completed. Check the protected API connection.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function defaultMaterialName(state: MaterialStateResponse): string {
  const normalized = state.current_revision.content.name.replace(/[^A-Za-z0-9_-]/g, "_");
  const prefixed = /^[A-Za-z]/.test(normalized) ? normalized : `MAT_${normalized}`;
  return (prefixed || "MAT_REFERENCE").slice(0, 80);
}

function targetFor(value: "openradioss" | "abaqus"): ExportTarget {
  return { solver: value, version: "2025", unit_system: "kg_m_s" };
}

function hardeningPolyline(curve: HardeningCurveResponse): string {
  const width = 720;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 18;
  const bottom = 40;
  const xs = curve.points.map((point) => point.true_plastic_strain);
  const ys = curve.points.map((point) => point.true_yield_stress_pa / 1e6);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  return curve.points
    .map((point) => {
      const x = left + ((point.true_plastic_strain - minX) / xSpan) * (width - left - right);
      const y =
        height -
        bottom -
        ((point.true_yield_stress_pa / 1e6 - minY) / ySpan) * (height - top - bottom);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function HardeningCurvePanel({ curve }: { curve: HardeningCurveResponse }) {
  const first = curve.points[0];
  const last = curve.points.at(-1);
  return (
    <section className="curve-panel" aria-label="True stress versus true plastic strain curve">
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Derived hardening artifact</p>
          <h5>True yield stress vs. true plastic strain</h5>
        </div>
        <span className="reference-chip">{curve.points.length} points</span>
      </div>
      <p className="curve-summary">
        Yield anchor {(first.true_yield_stress_pa / 1e6).toFixed(2)} MPa · constant extension to{" "}
        {last?.true_plastic_strain.toFixed(4)} plastic strain · artifact {shortId(curve.artifact_id)}
      </p>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Hardening curve">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline points={hardeningPolyline(curve)} />
        <text x="330" y="278">true plastic strain (1)</text>
        <text x="14" y="170" transform="rotate(-90 14 170)">
          true yield stress (MPa)
        </text>
      </svg>
      <ul className="curve-origin-legend">
        <li>Catalog yield anchor</li>
        <li>Pre-necking observations</li>
        <li>Explicit constant-stress extension</li>
      </ul>
    </section>
  );
}

function MappingPanel({ report }: { report: MappingReport }) {
  return (
    <section className="mapping-report" aria-label="Elastoplastic solver mapping report">
      <div className="mapping-report-heading">
        <strong>{report.exportable ? "Exportable mapping" : "Mapping blocked"}</strong>
        <span className={report.exportable ? "mapping-status exact" : "mapping-status unsupported"}>
          {report.target.solver} 2025
        </span>
      </div>
      <small>Mapping report SHA-256: {shortId(report.mapping_report_sha256)}</small>
      <ul className="mapping-list">
        {report.items.map((item) => (
          <li key={item.name}>
            <span className={`mapping-status ${item.status}`}>{item.status.replaceAll("_", " ")}</span>
            <div>
              <strong>{item.name.replaceAll("_", " ")}</strong>
              <small>{item.detail}</small>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface Props {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
}

export function ReferenceElastoplasticWorkbench({ config, state, propertySet }: Props) {
  const [open, setOpen] = useState(false);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [models, setModels] = useState<TabulatedPlasticityModelResponse[]>([]);
  const [selectedDatasetRevisionId, setSelectedDatasetRevisionId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [curve, setCurve] = useState<HardeningCurveResponse | null>(null);
  const [cards, setCards] = useState<ElastoplasticCardResponse[]>([]);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [extension, setExtension] = useState("0.25");
  const [acknowledged, setAcknowledged] = useState(false);
  const [modelReason, setModelReason] = useState(
    "Derive reference pre-necking tabulated plasticity IR",
  );
  const [targetSolver, setTargetSolver] = useState<"openradioss" | "abaqus">("openradioss");
  const [solverMaterialId, setSolverMaterialId] = useState("101");
  const [materialName, setMaterialName] = useState(() => defaultMaterialName(state));
  const [cardReason, setCardReason] = useState("Generate reference elastoplastic solver card");
  const [preview, setPreview] = useState<string | null>(null);
  const [previewCardId, setPreviewCardId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<"model" | "preflight" | "card" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eligibleDatasets = useMemo(
    () =>
      datasets.filter((dataset) =>
        ["normalized", "processed"].includes(dataset.current_revision.content.representation),
      ),
    [datasets],
  );
  const selectedModel =
    models.find((model) => model.material_model_id === selectedModelId) ?? null;
  const target = targetFor(targetSolver);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasetResult, modelResult] = await Promise.all([
        listDatasetsForMaterialState(config, state.material_state_id),
        listTabulatedPlasticityModels(config, state.material_state_id),
      ]);
      setDatasets(datasetResult.data.items);
      setModels(modelResult.data.items);
      const eligible = datasetResult.data.items.filter((dataset) =>
        ["normalized", "processed"].includes(dataset.current_revision.content.representation),
      );
      setSelectedDatasetRevisionId((current) => current || eligible[0]?.current_revision.id || "");
      setSelectedModelId(
        (current) => current || modelResult.data.items[0]?.material_model_id || "",
      );
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
    if (!selectedModel) {
      setCurve(null);
      setCards([]);
      return;
    }
    let current = true;
    setReport(null);
    setPreview(null);
    void Promise.all([
      getTabulatedPlasticityHardeningCurve(config, selectedModel.material_model_id),
      listElastoplasticSolverCards(config, selectedModel.material_model_id),
    ])
      .then(([curveResult, cardResult]) => {
        if (current) {
          setCurve(curveResult.data);
          setCards(cardResult.data.items);
        }
      })
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, selectedModel?.material_model_id]);

  useEffect(() => {
    setReport(null);
  }, [targetSolver]);

  async function createModel(): Promise<void> {
    if (!selectedDatasetRevisionId) {
      return;
    }
    setAction("model");
    setError(null);
    try {
      const result = await createTabulatedPlasticityModel(config, state.material_state_id, {
        property_set_revision_id: propertySet.current_revision.id,
        dataset_revision_id: selectedDatasetRevisionId,
        extension_max_true_plastic_strain: Number(extension),
        acknowledge_post_necking_approximation: acknowledged,
        change_reason: modelReason.trim(),
      });
      setModels((current) => [result.data, ...current]);
      setSelectedModelId(result.data.material_model_id);
      setAcknowledged(false);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function runPreflight(): Promise<void> {
    if (!selectedModel) {
      return;
    }
    setAction("preflight");
    setError(null);
    try {
      const result = await preflightElastoplasticMapping(
        config,
        selectedModel.material_model_id,
        selectedModel.current_revision.id,
        target,
      );
      setReport(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function createCard(): Promise<void> {
    if (!selectedModel || !report) {
      return;
    }
    setAction("card");
    setError(null);
    try {
      const result = await createElastoplasticSolverCard(config, selectedModel.material_model_id, {
        material_model_revision_id: selectedModel.current_revision.id,
        target,
        expected_mapping_report_sha256: report.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        material_name: materialName.trim(),
        change_reason: cardReason.trim(),
      });
      setCards((current) => [result.data.card, ...current]);
      setPreview(null);
      setPreviewCardId(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function showPreview(card: ElastoplasticCardResponse): Promise<void> {
    setError(null);
    try {
      const result = await previewElastoplasticSolverCard(config, card.solver_card_id);
      setPreview(result.data);
      setPreviewCardId(card.solver_card_id);
    } catch (cause) {
      setError(messageFor(cause));
    }
  }

  async function download(card: ElastoplasticCardResponse): Promise<void> {
    setAction("download");
    setError(null);
    try {
      const result = await downloadElastoplasticSolverCard(config, card.solver_card_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-elastoplastic-workbench" aria-label="Elastoplastic material card workflow">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Data-to-card vertical slice</p>
          <h4>Tensile Dataset → Elastoplastic IR → Solver Card</h4>
        </div>
        <span className="reference-chip">Reference / non-production</span>
      </div>
      <p className="form-hint">
        Converts monotonic engineering tensile observations only through the first maximum stress,
        preserves the derived curve as an immutable Artifact, then renders OpenRadioss LAW36 or
        Abaqus isotropic plasticity from the same IR.
      </p>
      <button className="text-button workflow-toggle" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? "Close elastoplastic workflow" : "Build an elastoplastic Solver Card"}
      </button>
      {!open ? null : (
        <div className="workflow-stack elastoplastic-workflow-stack">
          <div className="workflow-toolbar">
            <span>{loading ? "Loading tenant-scoped revisions…" : "No source revision is modified."}</span>
            <button className="text-button" type="button" onClick={() => void refresh()} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <p className="error-notice" role="alert">{error}</p> : null}
          {propertySet.current_revision.content.yield_stress_pa === null ? (
            <p className="warning-notice" role="alert">
              Add a typed yield stress to this Property Set before deriving an elastoplastic IR.
            </p>
          ) : null}
          <div className="workflow-step">
            <strong>1. Select concrete Dataset and Property Set revisions</strong>
            <label>
              Normalized or processed tensile Dataset revision
              <select
                value={selectedDatasetRevisionId}
                onChange={(event) => setSelectedDatasetRevisionId(event.target.value)}
                disabled={!eligibleDatasets.length}
              >
                {eligibleDatasets.map((dataset) => (
                  <option key={dataset.current_revision.id} value={dataset.current_revision.id}>
                    {dataset.current_revision.content.representation} · r{dataset.current_revision.revision_no} ·{" "}
                    {shortId(dataset.current_revision.id)} · {dataset.current_revision.content.point_count} points
                  </option>
                ))}
              </select>
            </label>
            {!eligibleDatasets.length ? (
              <small className="muted">Import or process a tensile CSV in Test data workflow first.</small>
            ) : null}
            <p className="source-line">
              Property Set {shortId(propertySet.current_revision.id)} · E{" "}
              {(propertySet.current_revision.content.youngs_modulus_pa / 1e9).toFixed(3)} GPa · yield{" "}
              {propertySet.current_revision.content.yield_stress_pa === null
                ? "missing"
                : `${(propertySet.current_revision.content.yield_stress_pa / 1e6).toFixed(3)} MPa`}
            </p>
            <div className="form-grid">
              <label>
                Constant-extension maximum true plastic strain
                <input type="number" min="0" step="any" value={extension} onChange={(event) => setExtension(event.target.value)} />
              </label>
              <label>
                Change reason
                <input value={modelReason} onChange={(event) => setModelReason(event.target.value)} />
              </label>
            </div>
            <label className="acknowledgement-row">
              <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
              I acknowledge that post-necking behavior is not identified; a constant true-stress
              extension will be stored explicitly as an approximation boundary.
            </label>
            <button
              className="button primary"
              type="button"
              onClick={() => void createModel()}
              disabled={
                action !== null ||
                !selectedDatasetRevisionId ||
                !acknowledged ||
                propertySet.current_revision.content.yield_stress_pa === null
              }
            >
              {action === "model" ? "Deriving hardening curve…" : "Create elastoplastic IR"}
            </button>
          </div>
          {models.length ? (
            <div className="workflow-step">
              <strong>2. Inspect immutable IR and hardening Artifact</strong>
              <label>
                Tabulated-plasticity IR revision
                <select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)}>
                  {models.map((model) => (
                    <option key={model.material_model_id} value={model.material_model_id}>
                      r{model.current_revision.revision_no} · {shortId(model.current_revision.id)} · source Dataset{" "}
                      {model.current_revision.content.source_dataset_revision_id
                        ? shortId(model.current_revision.content.source_dataset_revision_id)
                        : "accepted Voce Candidate"}
                    </option>
                  ))}
                </select>
              </label>
              {selectedModel ? (
                <div className="transformation-facts">
                  <span>
                    {selectedModel.current_revision.content.necking_engineering_strain === null
                      ? "Origin: calibrated fixed-grid projection"
                      : `Necking cutoff: ${selectedModel.current_revision.content.necking_engineering_strain.toFixed(6)}`}
                  </span>
                  <span>
                    Source points: {selectedModel.current_revision.content.source_point_count} · pre-yield excluded: {selectedModel.current_revision.content.pre_yield_excluded_point_count}
                  </span>
                  <span>
                    Necking index: {selectedModel.current_revision.content.necking_source_point_index} · post-necking excluded: {selectedModel.current_revision.content.post_necking_excluded_point_count}
                  </span>
                  <span>
                    Characterized plastic strain: {selectedModel.current_revision.content.characterized_max_true_plastic_strain.toFixed(6)}
                  </span>
                  <span>Extension: {selectedModel.current_revision.content.extension_max_true_plastic_strain.toFixed(6)}</span>
                </div>
              ) : null}
              {curve ? <HardeningCurvePanel curve={curve} /> : null}
            </div>
          ) : null}
          {selectedModel ? (
            <div className="workflow-step">
              <strong>3. Select solver and acknowledge the explicit mapping</strong>
              <label>
                Solver target
                <select value={targetSolver} onChange={(event) => setTargetSolver(event.target.value as "openradioss" | "abaqus")}>
                  <option value="openradioss">OpenRadioss 2025 · /MAT/LAW36 + /FUNCT · kg/m/s</option>
                  <option value="abaqus">Abaqus 2025 · *DENSITY + *ELASTIC + *PLASTIC · kg/m/s</option>
                </select>
              </label>
              <button className="button secondary" type="button" onClick={() => void runPreflight()} disabled={action !== null}>
                {action === "preflight" ? "Checking mapping…" : "Run mapping preflight"}
              </button>
              {report ? <MappingPanel report={report} /> : null}
            </div>
          ) : null}
          {selectedModel && report ? (
            <div className="workflow-step">
              <strong>4. Generate, preview, and download the immutable card</strong>
              <div className="form-grid">
                <label>
                  Material name
                  <input value={materialName} pattern="[A-Za-z][A-Za-z0-9_-]{0,79}" onChange={(event) => setMaterialName(event.target.value)} />
                </label>
                <label>
                  Solver material ID
                  <input type="number" min="1" max="9999999999" value={solverMaterialId} onChange={(event) => setSolverMaterialId(event.target.value)} />
                </label>
              </div>
              <small className="form-hint">
                Abaqus uses the material name in the keyword deck; its numeric ID remains a platform identity only.
              </small>
              <label>
                Change reason
                <input value={cardReason} onChange={(event) => setCardReason(event.target.value)} />
              </label>
              <button className="button primary" type="button" onClick={() => void createCard()} disabled={!report.exportable || action !== null}>
                {action === "card" ? "Generating card…" : `Generate ${targetSolver === "abaqus" ? "Abaqus .inp" : "OpenRadioss .rad"}`}
              </button>
            </div>
          ) : null}
          <section className="solver-card-results">
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">Generated cards</p>
                <h4>{cards.length ? `${cards.length} immutable elastoplastic card${cards.length === 1 ? "" : "s"}` : "No elastoplastic card yet"}</h4>
              </div>
            </div>
            <div className="solver-card-list">
              {cards.map((card) => (
                <article className="solver-card-item" key={card.solver_card_id}>
                  <div>
                    <strong>
                      {card.target.solver === "abaqus" ? "*MATERIAL / *PLASTIC" : `/MAT/LAW36/${card.solver_material_id}`}
                    </strong>
                    <small>
                      {card.material_name} · {shortId(card.current_revision.id)} · {card.current_revision.content.hardening_curve_point_count} hardening points
                    </small>
                  </div>
                  <div className="card-actions">
                    <button className="text-button" type="button" onClick={() => void showPreview(card)}>Preview</button>
                    <button className="button secondary" type="button" onClick={() => void download(card)} disabled={action === "download"}>
                      Download {card.target.solver === "abaqus" ? ".inp" : ".rad"}
                    </button>
                  </div>
                  {previewCardId === card.solver_card_id && preview ? <pre className="solver-card-preview">{preview}</pre> : null}
                </article>
              ))}
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

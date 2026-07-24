import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createElastoplasticSolverCard,
  createTabulatedPlasticityModel,
  downloadNeutralMaterial,
  downloadElastoplasticSolverCard,
  getNeutralMaterial,
  getTabulatedPlasticityHardeningCurve,
  listBulkExportCandidates,
  listCommonProcessingOutputs,
  listDatasetsForMaterialState,
  listElastoplasticSolverCards,
  listTabulatedPlasticityModels,
  preflightElastoplasticMapping,
  previewElastoplasticSolverCard,
  promoteModelToNeutralMaterial,
  promoteProcessingOutputToTabulatedPlasticity,
} from "./api";
import type {
  DatasetResponse,
  CommonProcessingOutputResponse,
  ElastoplasticCardResponse,
  ExportTarget,
  HardeningCurveResponse,
  MappingReport,
  MaterialStateResponse,
  NeutralMaterialResponse,
  PropertySetResponse,
  TabulatedPlasticityModelResponse,
} from "./types";
import { NeutralSolverExport } from "./neutral-hyperelastic-export";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The elastoplastic workflow could not be completed. Try again in a moment.";
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

function HardeningCurvePanel({
  curve,
  policy,
}: {
  curve: HardeningCurveResponse;
  policy: string;
}) {
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
        Yield anchor {(first.true_yield_stress_pa / 1e6).toFixed(2)} MPa · bounded curve to{" "}
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
        {policy === "selected_fitted_bounded_extrapolation" ? (
          <>
            <li>Selected fitted hardening samples from an exact Processing Output revision</li>
            <li>Explicitly acknowledged bounded extrapolation domain</li>
          </>
        ) : (
          <>
            <li>Catalog yield anchor and pre-necking observations</li>
            <li>Explicit constant-stress extension</li>
          </>
        )}
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
  onNavigate?: (path: string) => void;
  embedded?: boolean;
  preferredProcessingOutputId?: string;
}

export function ReferenceElastoplasticWorkbench({
  config,
  state,
  propertySet,
  onNavigate,
  embedded = false,
  preferredProcessingOutputId,
}: Props) {
  const [open, setOpen] = useState(embedded);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [processingOutputs, setProcessingOutputs] = useState<CommonProcessingOutputResponse[]>([]);
  const [models, setModels] = useState<TabulatedPlasticityModelResponse[]>([]);
  const [selectedDatasetRevisionId, setSelectedDatasetRevisionId] = useState("");
  const [selectedProcessingOutputId, setSelectedProcessingOutputId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [curve, setCurve] = useState<HardeningCurveResponse | null>(null);
  const [cards, setCards] = useState<ElastoplasticCardResponse[]>([]);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [extension, setExtension] = useState("0.25");
  const [acknowledged, setAcknowledged] = useState(false);
  const [processingAcknowledged, setProcessingAcknowledged] = useState(false);
  const [processingReason, setProcessingReason] = useState(
    "Promote selected fitted hardening Processing Output to tabulated plasticity IR",
  );
  const [modelReason, setModelReason] = useState(
    "Derive reference pre-necking tabulated plasticity IR",
  );
  const [targetSolver, setTargetSolver] = useState<"openradioss" | "abaqus">("openradioss");
  const [solverMaterialId, setSolverMaterialId] = useState("101");
  const [materialName, setMaterialName] = useState(() => defaultMaterialName(state));
  const [cardReason, setCardReason] = useState("Generate reference elastoplastic solver card");
  const [preview, setPreview] = useState<string | null>(null);
  const [previewCardId, setPreviewCardId] = useState<string | null>(null);
  const [neutralMaterial, setNeutralMaterial] = useState<NeutralMaterialResponse | null>(null);
  const [switchingProcessingOutput, setSwitchingProcessingOutput] = useState(false);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<"model" | "neutral" | "preflight" | "card" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eligibleDatasets = useMemo(
    () =>
      datasets.filter((dataset) =>
        ["normalized", "processed"].includes(dataset.current_revision.content.representation),
      ),
    [datasets],
  );
  const eligibleProcessingOutputs = useMemo(
    () =>
      processingOutputs.filter(
        (output) => output.steps.at(-1)?.method_id === "metal.hardening_fit_extrapolate",
      ),
    [processingOutputs],
  );
  const selectedModel =
    models.find((model) => model.material_model_id === selectedModelId) ?? null;
  const target = targetFor(targetSolver);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasetResult, outputResult, modelResult] = await Promise.all([
        listDatasetsForMaterialState(config, state.material_state_id),
        listCommonProcessingOutputs(config),
        listTabulatedPlasticityModels(config, state.material_state_id),
      ]);
      setDatasets(datasetResult.data.items);
      setProcessingOutputs(outputResult.data.items);
      setModels(modelResult.data.items);
      const eligible = datasetResult.data.items.filter((dataset) =>
        ["normalized", "processed"].includes(dataset.current_revision.content.representation),
      );
      setSelectedDatasetRevisionId((current) => current || eligible[0]?.current_revision.id || "");
      const eligibleOutputs = outputResult.data.items.filter(
        (output) => output.steps.at(-1)?.method_id === "metal.hardening_fit_extrapolate",
      );
      const preferredOutput = eligibleOutputs.find(
        (output) => output.processing_output_id === preferredProcessingOutputId,
      );
      const preferredModel = preferredOutput
        ? modelResult.data.items.find(
          (model) => model.current_revision.content.processing_projection?.output_id
            === preferredOutput.processing_output_id
          && model.current_revision.content.processing_projection.output_revision_id
            === preferredOutput.current_revision.id,
        )
        : null;
      setSelectedProcessingOutputId(
        (current) => preferredOutput?.processing_output_id || current || eligibleOutputs[0]?.processing_output_id || "",
      );
      setSelectedModelId(
        (current) => preferredModel?.material_model_id
          || (preferredOutput ? "" : current || modelResult.data.items[0]?.material_model_id || ""),
      );
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }, [config, preferredProcessingOutputId, state.material_state_id]);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    setNeutralMaterial(null);
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
    let current = true;
    const evidence = selectedModel?.current_revision.content.processing_projection;
    if (!selectedModel || !evidence) {
      return () => { current = false; };
    }
    void listBulkExportCandidates(config, state.material_id)
      .then(async (candidates) => {
        const ids = candidates.data.items
          .filter((candidate) => candidate.source.kind === "neutral_material_json")
          .map((candidate) => candidate.source.neutral_material_id)
          .filter((id): id is string => typeof id === "string");
        const snapshots = await Promise.all(
          [...new Set(ids)].map((id) => getNeutralMaterial(config, id)),
        );
        const exact = snapshots.find(({ data }) =>
          data.document.sources.material_state?.id === selectedModel.material_state_id
          && data.document.sources.material_state.revision_id
            === selectedModel.current_revision.content.material_state_revision_id
          && data.document.sources.property_set?.revision_id
            === selectedModel.current_revision.content.property_set_revision_id
          && data.document.candidate_selection.processing_output?.id === evidence.output_id
          && data.document.candidate_selection.processing_output.revision_id
            === evidence.output_revision_id,
        );
        if (current && exact) setNeutralMaterial(exact.data);
      })
      .catch(() => undefined);
    return () => { current = false; };
  }, [config, selectedModel?.material_model_id, selectedModel?.current_revision.id, state.material_id]);

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

  async function promoteProcessingOutput(): Promise<void> {
    const output = eligibleProcessingOutputs.find(
      (candidate) => candidate.processing_output_id === selectedProcessingOutputId,
    );
    if (!output) return;
    setAction("model");
    setError(null);
    try {
      const result = await promoteProcessingOutputToTabulatedPlasticity(
        config,
        output.processing_output_id,
        {
          material_state_id: state.material_state_id,
          property_set_revision_id: propertySet.current_revision.id,
          processing_output_revision_id: output.current_revision.id,
          acknowledge_bounded_extrapolation: processingAcknowledged,
          change_reason: processingReason.trim(),
        },
      );
      setModels((current) => [result.data, ...current]);
      setSelectedModelId(result.data.material_model_id);
      setProcessingAcknowledged(false);
      setSwitchingProcessingOutput(false);
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

  async function promoteNeutral(): Promise<void> {
    if (!selectedModel?.current_revision.content.processing_projection) return;
    setAction("neutral");
    setError(null);
    try {
      const result = await promoteModelToNeutralMaterial(config, "metal", {
        material_model_id: selectedModel.material_model_id,
        material_model_revision_id: selectedModel.current_revision.id,
        selection_reason: "Reviewed selected hardening families and bounded extrapolation.",
        change_reason: "Promote selected metal IR to canonical Neutral Material JSON",
      });
      setNeutralMaterial(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function downloadNeutral(): Promise<void> {
    if (!neutralMaterial) return;
    const result = await downloadNeutralMaterial(config, neutralMaterial.neutral_material_id);
    const url = URL.createObjectURL(result.data.blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.data.filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
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
    <section className={`reference-elastoplastic-workbench ${embedded ? "embedded" : ""}`} aria-label="Elastoplastic material card workflow">
      {!embedded ? <><div className="section-heading compact-heading">
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
      </button></> : <div className="embedded-delivery-heading"><div><p className="eyebrow">Metal elastoplastic delivery</p><h3>Reviewed hardening → Neutral JSON → solver card</h3></div><span className="reference-chip">Reference / non-production</span></div>}
      {!open ? null : (
        <div className="workflow-stack elastoplastic-workflow-stack">
          <div className="workflow-toolbar">
            <span>{loading ? "Loading source revisions…" : "No source revision is modified."}</span>
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
          {!embedded ? <div className="workflow-step">
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
          </div> : null}
          {embedded && neutralMaterial && !switchingProcessingOutput ? <div className="workflow-step embedded-source-summary">
            <strong>1. Reviewed Processing Output</strong>
            <p className="form-hint">The exact fitted hardening output and its selection reason are already pinned by Neutral JSON r{neutralMaterial.revision_no}. No refit is performed here.</p>
            <div className="transformation-facts"><span>Output revision: exact and immutable</span><span>Curve stages: {neutralMaterial.document.curve_stages?.length ?? 0}</span><span>Model maturity: {neutralMaterial.document.material_model_ir.maturity}</span></div>
            <button className="text-button" type="button" onClick={() => setSwitchingProcessingOutput(true)}>Create from another reviewed output</button>
          </div> : <div className="workflow-step">
            <strong>1B. Promote a fitted metal Processing Output (recommended)</strong>
            <p className="form-hint">
              Select one exact immutable output whose final Recipe step compared and blended
              metal hardening candidates. These points are not refitted during promotion.
            </p>
            <label>
              Exact Processing Output revision
              <select
                value={selectedProcessingOutputId}
                onChange={(event) => setSelectedProcessingOutputId(event.target.value)}
                disabled={!eligibleProcessingOutputs.length}
              >
                {eligibleProcessingOutputs.map((output) => (
                  <option key={output.processing_output_id} value={output.processing_output_id}>
                    {output.label} · r{output.current_revision.revision_no} ·{" "}
                    {shortId(output.current_revision.id)} · {output.final_point_count} points
                  </option>
                ))}
              </select>
            </label>
            {!eligibleProcessingOutputs.length ? (
              <small className="muted">
                Save a Processing Output ending in metal.hardening_fit_extrapolate first.
              </small>
            ) : null}
            <label>
              Change reason
              <input
                value={processingReason}
                onChange={(event) => setProcessingReason(event.target.value)}
              />
            </label>
            <label className="acknowledgement-row">
              <input
                type="checkbox"
                checked={processingAcknowledged}
                onChange={(event) => setProcessingAcknowledged(event.target.checked)}
              />
              I reviewed the candidate blend and acknowledge its bounded fitted extrapolation as
              reference/non-production evidence.
            </label>
            <button
              className="button primary"
              type="button"
              onClick={() => void promoteProcessingOutput()}
              disabled={
                action !== null ||
                !selectedProcessingOutputId ||
                !processingAcknowledged ||
                propertySet.current_revision.content.yield_stress_pa === null
              }
            >
              {action === "model" ? "Promoting exact output…" : "Promote fitted output to IR"}
            </button>
          </div>}
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
                        : model.current_revision.content.processing_projection
                          ? `Processing Output ${shortId(model.current_revision.content.processing_projection.output_revision_id)}`
                          : "accepted Voce Candidate"}
                    </option>
                  ))}
                </select>
              </label>
              {selectedModel ? (
                <div className="transformation-facts">
                  <span>
                    {selectedModel.current_revision.content.processing_projection
                      ? "Origin: selected fitted hardening Processing Output"
                      : selectedModel.current_revision.content.necking_engineering_strain === null
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
                  {selectedModel.current_revision.content.processing_projection?.recipe_batch ? (
                    <>
                      <span>
                        Published Recipe revision: {shortId(selectedModel.current_revision.content.processing_projection.recipe_batch.processing_recipe.revision_id)}
                      </span>
                      <span>
                        Successful Batch attempt #{selectedModel.current_revision.content.processing_projection.recipe_batch.batch_attempt_no} · {shortId(selectedModel.current_revision.content.processing_projection.recipe_batch.batch_attempt_id)}
                      </span>
                      <a href="/datasets/processing">Open Recipe library and Batch monitor</a>
                    </>
                  ) : null}
                </div>
              ) : null}
              {curve && selectedModel && !embedded ? (
                <HardeningCurvePanel
                  curve={curve}
                  policy={selectedModel.current_revision.content.post_necking_extension_policy}
                />
              ) : null}
              {selectedModel?.current_revision.content.processing_projection ? (
                <div className="card-actions">
                  {neutralMaterial ? (
                    <>
                      <span className="status-chip success">
                        Exact Neutral JSON r{neutralMaterial.revision_no} restored
                      </span>
                    <button className="text-button" type="button" onClick={() => void downloadNeutral()}>
                      Download Neutral JSON r{neutralMaterial.revision_no}
                    </button>
                    </>
                  ) : (
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() => void promoteNeutral()}
                      disabled={action !== null}
                    >
                      {action === "neutral" ? "Creating Neutral JSON…" : "Create Neutral Material JSON"}
                    </button>
                  )}
                </div>
              ) : (
                <small className="muted">
                  Canonical metal Neutral promotion requires an IR created from a selected fitted Processing Output.
                </small>
              )}
            </div>
          ) : null}
          {neutralMaterial ? (
            <NeutralSolverExport config={config} neutralMaterial={neutralMaterial} onNavigate={onNavigate} />
          ) : null}
          {!embedded && selectedModel ? (
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
          {!embedded && selectedModel && report ? (
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
          {!embedded ? <section className="solver-card-results">
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
          </section> : null}
        </div>
      )}
    </section>
  );
}

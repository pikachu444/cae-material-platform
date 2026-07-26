import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  type ApiConfig,
  createLinearViscoelasticModel,
  getNeutralMaterial,
  listBulkExportCandidates,
  listCommonProcessingOutputs,
  listLinearViscoelasticModels,
  previewLinearViscoelasticResponse,
  promoteModelToNeutralMaterial,
  promotePronyProcessingOutput,
} from "./api";
import { NeutralSolverExport } from "./neutral-hyperelastic-export";
import { ReferenceLinearViscoelasticExport } from "./reference-linear-viscoelastic-export";
import type {
  BulkRelaxationStatus,
  CommonProcessingOutputResponse,
  LinearViscoelasticModelResponse,
  LinearViscoelasticResponse,
  MaterialStateResponse,
  NeutralMaterialResponse,
  PropertySetResponse,
} from "./types";

interface EditableTerm {
  gRatio: string;
  kRatio: string;
  timeS: string;
}

const initialTerms: EditableTerm[] = [
  { gRatio: "0.2", kRatio: "0", timeS: "0.1" },
  { gRatio: "0.3", kRatio: "0", timeS: "10" },
];

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : "The request could not be completed.";
}

function compact(value: string): string {
  return `${value.slice(0, 8)}…`;
}

function responsePath(response: LinearViscoelasticResponse): string {
  if (response.points.length < 2) return "";
  const values = response.points.map((point) => point.shear_modulus_pa);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = Math.max(maximum - minimum, 1);
  return response.points
    .map((point, index) => {
      const x = 12 + (index / (response.points.length - 1)) * 516;
      const y = 118 - ((point.shear_modulus_pa - minimum) / range) * 96;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function ReferenceLinearViscoelasticWorkbench({
  config,
  state,
  propertySet,
  onNavigate,
  embedded = false,
  preferredSourceDocumentId,
  preferredProcessingOutputId,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
  onNavigate?: (path: string) => void;
  embedded?: boolean;
  preferredSourceDocumentId?: string;
  preferredProcessingOutputId?: string;
}) {
  const [models, setModels] = useState<LinearViscoelasticModelResponse[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [response, setResponse] = useState<LinearViscoelasticResponse | null>(null);
  const [bulkStatus, setBulkStatus] = useState<BulkRelaxationStatus>("not_characterized");
  const [terms, setTerms] = useState<EditableTerm[]>(initialTerms);
  const [reason, setReason] = useState("Create manual reference Prony IR");
  const [processingOutputs, setProcessingOutputs] = useState<CommonProcessingOutputResponse[]>([]);
  const [processingOutputId, setProcessingOutputId] = useState("");
  const [maximumMismatch, setMaximumMismatch] = useState("0.05");
  const [processingReview, setProcessingReview] = useState(false);
  const [neutralMaterial, setNeutralMaterial] = useState<NeutralMaterialResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => models.find((model) => model.material_model_id === selectedId) ?? models[0],
    [models, selectedId],
  );

  async function reload(preferredId?: string): Promise<void> {
    const result = await listLinearViscoelasticModels(config, state.material_state_id);
    setModels(result.data.items);
    const sourceMatched = result.data.items.find(
      (model) => model.current_revision.content.processing_promotion_evidence
        ?.source_test_data.id === preferredSourceDocumentId,
    );
    const outputMatched = result.data.items.find(
      (model) => model.current_revision.content.processing_promotion_evidence
        ?.processing_output.id === preferredProcessingOutputId,
    );
    setSelectedId(
      preferredId
      ?? outputMatched?.material_model_id
      ?? (preferredProcessingOutputId
        ? ""
        : sourceMatched?.material_model_id ?? result.data.items[0]?.material_model_id ?? ""),
    );
  }

  useEffect(() => {
    setError(null);
    void Promise.all([reload(), listCommonProcessingOutputs(config)]).then(([, outputs]) => {
      const promotable = outputs.data.items.filter(
        (output) => [
          "polymer.prony_fit_compare",
          "polymer.dma_prony_fit_compare",
        ].includes(output.steps.at(-1)?.method_id ?? "")
          && output.fit_decision?.primary_law === "generalized_maxwell"
          && typeof output.fit_decision?.actual_term_count === "number",
      );
      setProcessingOutputs(promotable);
      setProcessingOutputId(
        promotable.find((output) => output.processing_output_id === preferredProcessingOutputId)
          ?.processing_output_id
          ?? promotable[0]?.processing_output_id
          ?? "",
      );
    }).catch((cause: unknown) => setError(message(cause)));
  }, [
    config.baseUrl,
    config.accessToken,
    preferredProcessingOutputId,
    preferredSourceDocumentId,
    state.material_state_id,
  ]);

  useEffect(() => {
    setResponse(null);
    if (!selected) return;
    void previewLinearViscoelasticResponse(config, selected.material_model_id)
      .then((result) => setResponse(result.data))
      .catch((cause: unknown) => setError(message(cause)));
  }, [config.baseUrl, config.accessToken, selected?.material_model_id]);

  useEffect(() => {
    let active = true;
    setNeutralMaterial(null);
    const evidence = selected?.current_revision.content.processing_promotion_evidence;
    if (!selected || !evidence) return () => { active = false; };
    void listBulkExportCandidates(config, state.material_id)
      .then(async (candidates) => {
        const ids = candidates.data.items
          .filter((candidate) => candidate.source.kind === "neutral_material_json")
          .map((candidate) => candidate.source.neutral_material_id)
          .filter((id): id is string => typeof id === "string");
        const snapshots = await Promise.all(
          [...new Set(ids)].map((id) => getNeutralMaterial(config, id)),
        );
        const exact = snapshots.find(({ data }) => {
          const source = data.document.sources;
          const selection = data.document.candidate_selection;
          return source.material_state?.id === selected.material_state_id
            && source.material_state.revision_id
              === selected.current_revision.content.material_state_revision_id
            && source.property_set?.revision_id
              === selected.current_revision.content.property_set_revision_id
            && selection.kind === "prony_processing_output_selection"
            && selection.processing_output?.id === evidence.processing_output.id
            && selection.processing_output.revision_id === evidence.processing_output.revision_id;
        });
        if (active && exact) setNeutralMaterial(exact.data);
      })
      // Discovery is a convenience for returning users. Promotion remains available when the
      // caller cannot read export candidates under its feature grants.
      .catch(() => undefined);
    return () => { active = false; };
  }, [
    config.baseUrl,
    config.accessToken,
    selected?.material_model_id,
    selected?.current_revision.id,
    state.material_id,
  ]);

  function updateTerm(index: number, key: keyof EditableTerm, value: string): void {
    setTerms((current) =>
      current.map((term, ordinal) => (ordinal === index ? { ...term, [key]: value } : term)),
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createLinearViscoelasticModel(config, state.material_state_id, {
        property_set_revision_id: propertySet.current_revision.id,
        bulk_relaxation_status: bulkStatus,
        terms: terms.map((term) => ({
          g_ratio: Number(term.gRatio),
          k_ratio: bulkStatus === "not_characterized" ? 0 : Number(term.kRatio),
          relaxation_time_s: Number(term.timeS),
        })),
        change_reason: reason.trim(),
      });
      await reload(created.data.material_model_id);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  async function promoteProcessing(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const output = processingOutputs.find(
      (candidate) => candidate.processing_output_id === processingOutputId,
    );
    if (!output) return;
    setBusy(true);
    setError(null);
    setNeutralMaterial(null);
    try {
      const created = await promotePronyProcessingOutput(config, output.processing_output_id, {
        material_state_id: state.material_state_id,
        property_set_revision_id: propertySet.current_revision.id,
        processing_output_revision_id: output.current_revision.id,
        acknowledged_maximum_relative_mismatch: Number(maximumMismatch),
        review_acknowledged: processingReview,
        change_reason: "Promote reviewed Prony Processing Output",
      });
      await reload(created.data.material_model_id);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  async function promoteNeutral(): Promise<void> {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const promoted = await promoteModelToNeutralMaterial(config, "linear-viscoelastic", {
        material_model_id: selected.material_model_id,
        material_model_revision_id: selected.current_revision.id,
        selection_reason: "Use the reviewed common Processing Output selection",
        change_reason: "Create reproducible Neutral Material JSON for solver export",
      });
      setNeutralMaterial(promoted.data);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  const content = selected?.current_revision.content;
  const path = response ? responsePath(response) : "";

  return (
    <section className={`reference-linear-viscoelastic-workbench ${embedded ? "embedded" : ""}`}>
      {!embedded ? <div className="section-heading">
        <div>
          <p className="eyebrow">Polymer / elastomer model</p>
          <h4>Linear Prony relaxation</h4>
          <p className="muted">
            Enter dimensionless shear and bulk ratios with relaxation time in seconds. Elastic
            moduli are interpreted as instantaneous values.
          </p>
        </div>
        <span className="revision-chip">reference · non-production</span>
      </div> : <div className="section-heading compact-heading"><div><p className="eyebrow">Polymer viscoelastic delivery</p><h4>Reviewed Prony → Neutral JSON → solver card</h4><p className="muted">The exact fitted output and its engineering selection remain pinned. No term is re-entered in the Card task.</p></div><span className="revision-chip">reference · non-production</span></div>}

      {!embedded || !content?.processing_promotion_evidence ? <form className={`viscoelastic-form ${embedded ? "embedded-promotion" : ""}`} onSubmit={promoteProcessing}>
        <div className="section-heading compact-heading">
          <div>
            <p className="eyebrow">Reviewed processing promotion</p>
            <h4>Processing Output → generalized-Maxwell IR</h4>
            <p className="muted">
              Promote the exact saved output from the Prony comparison step. Terms and fit
              metrics are read again from the immutable server artifact; they cannot be replaced
              by values from this form.
            </p>
          </div>
        </div>
        {processingOutputs.length ? (
          <>
            <div className="viscoelastic-toolbar">
              <label>
                Exact Processing Output
                <select
                  value={processingOutputId}
                  onChange={(event) => setProcessingOutputId(event.target.value)}
                >
                  {processingOutputs.map((output) => (
                    <option key={output.processing_output_id} value={output.processing_output_id}>
                      {output.label} · {compact(output.current_revision.id)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Reviewed maximum G₀ mismatch
                <input
                  aria-label="Reviewed maximum G0 mismatch"
                  type="number"
                  min="0"
                  max="1"
                  step="0.001"
                  value={maximumMismatch}
                  onChange={(event) => setMaximumMismatch(event.target.value)}
                  required
                />
              </label>
            </div>
            <label className="acknowledgement-row">
              <input
                type="checkbox"
                checked={processingReview}
                onChange={(event) => setProcessingReview(event.target.checked)}
              />
              I reviewed candidate selection, residuals, and fitted/catalog instantaneous shear
              modulus consistency. The entered limit is a case-specific review decision.
            </label>
            <button className="button primary" type="submit" disabled={busy || !processingReview}>
              Promote exact Processing Output
            </button>
          </>
        ) : (
          <p className="muted">
            No committed Processing Output ends with a relaxation or DMA Prony comparison.
            Create and commit one in the Processing Workbench first.
          </p>
        )}
      </form> : <section className="reviewed-delivery-summary" aria-label="Reviewed polymer Processing Output"><div><p className="eyebrow">1 · Reviewed Processing Output</p><h4>{content.processing_promotion_evidence.selection_mode.replaceAll("_", " ")} · {content.terms.length} Prony terms</h4><p>The exact fitted Output, residual metrics and instantaneous-modulus review are pinned by this IR.</p></div><div className="reviewed-output-facts"><span><small>Normalized RMSE</small><strong>{content.processing_promotion_evidence.normalized_rmse.toPrecision(4)}</strong></span><span><small>G₀ mismatch</small><strong>{(content.processing_promotion_evidence.instantaneous_modulus_relative_mismatch * 100).toFixed(2)}%</strong></span><span><small>IR revision</small><strong>r{selected?.current_revision.revision_no}</strong></span></div></section>}

      {!embedded ? <form className="viscoelastic-form" onSubmit={submit}>
        <div className="viscoelastic-toolbar">
          <label>
            Bulk relaxation evidence
            <select
              value={bulkStatus}
              onChange={(event) => setBulkStatus(event.target.value as BulkRelaxationStatus)}
            >
              <option value="not_characterized">Not characterized (kᵢ = 0)</option>
              <option value="characterized">Characterized</option>
            </select>
          </label>
          <button
            className="text-button"
            type="button"
            disabled={terms.length >= 5}
            onClick={() =>
              setTerms((current) => [
                ...current,
                { gRatio: "0.1", kRatio: "0", timeS: String(10 ** current.length) },
              ])
            }
          >
            + Add term
          </button>
        </div>
        <div className="prony-term-table" role="table" aria-label="Prony terms">
          <div className="prony-term-row prony-term-header" role="row">
            <span>Term</span><span>gᵢ ratio</span><span>kᵢ ratio</span><span>τᵢ (s)</span><span />
          </div>
          {terms.map((term, index) => (
            <div className="prony-term-row" role="row" key={`term-${index + 1}`}>
              <strong>{index + 1}</strong>
              <input
                aria-label={`Term ${index + 1} shear ratio`}
                type="number" min="0" max="0.999999" step="any" required
                value={term.gRatio}
                onChange={(event) => updateTerm(index, "gRatio", event.target.value)}
              />
              <input
                aria-label={`Term ${index + 1} bulk ratio`}
                type="number" min="0" max="0.999999" step="any" required
                disabled={bulkStatus === "not_characterized"}
                value={bulkStatus === "not_characterized" ? "0" : term.kRatio}
                onChange={(event) => updateTerm(index, "kRatio", event.target.value)}
              />
              <input
                aria-label={`Term ${index + 1} relaxation time`}
                type="number" min="0.000000001" step="any" required
                value={term.timeS}
                onChange={(event) => updateTerm(index, "timeS", event.target.value)}
              />
              <button
                className="icon-button" type="button" aria-label={`Remove term ${index + 1}`}
                disabled={terms.length === 1}
                onClick={() => setTerms((current) => current.filter((_, item) => item !== index))}
              >×</button>
            </div>
          ))}
        </div>
        <div className="inline-action">
          <label>
            Change reason
            <input value={reason} onChange={(event) => setReason(event.target.value)} required />
          </label>
          <button className="button primary" type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create immutable Prony IR"}
          </button>
        </div>
      </form> : null}

      {error ? <p className="error-notice">{error}</p> : null}

      {content ? (
        <section className={`viscoelastic-result ${embedded ? "embedded" : ""}`}>
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Saved Material Model IR</p>
              <h4>Revision {selected.current_revision.revision_no}</h4>
            </div>
            {models.length > 1 ? (
              <select value={selected.material_model_id} onChange={(event) => setSelectedId(event.target.value)}>
                {models.map((model) => (
                  <option key={model.material_model_id} value={model.material_model_id}>
                    {compact(model.material_model_id)} · r{model.current_revision.revision_no}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
          <div className="viscoelastic-facts">
            <span><small>Source property revision</small><strong>{compact(content.property_set_revision_id)}</strong></span>
            <span><small>Convention</small><strong>{content.elastic_moduli_convention}</strong></span>
            <span><small>Prony terms</small><strong>{content.terms.length}</strong></span>
            <span><small>Bulk status</small><strong>{content.bulk_relaxation_status.replace("_", " ")}</strong></span>
          </div>
          {content.processing_promotion_evidence ? (
            <div className="viscoelastic-form">
              <div className="viscoelastic-facts">
                <span>
                  <small>Selection</small>
                  <strong>{content.processing_promotion_evidence.selection_mode}</strong>
                </span>
                <span>
                  <small>Normalized RMSE</small>
                  <strong>{content.processing_promotion_evidence.normalized_rmse.toPrecision(4)}</strong>
                </span>
                <span>
                  <small>G₀ mismatch</small>
                  <strong>
                    {(content.processing_promotion_evidence.instantaneous_modulus_relative_mismatch * 100).toFixed(2)}%
                  </strong>
                </span>
                {content.processing_promotion_evidence.recipe_batch ? (
                  <>
                    <span>
                      <small>Published Recipe revision</small>
                      <strong>{compact(content.processing_promotion_evidence.recipe_batch.processing_recipe.revision_id)}</strong>
                    </span>
                    <span>
                      <small>Successful Batch attempt</small>
                      <strong>#{content.processing_promotion_evidence.recipe_batch.batch_attempt_no} · {compact(content.processing_promotion_evidence.recipe_batch.batch_attempt_id)}</strong>
                    </span>
                  </>
                ) : null}
              </div>
              {content.processing_promotion_evidence.recipe_batch ? (
                <p className="success-notice">
                  This IR pins the exact published Processing Recipe and successful Batch execution. <a href="/datasets/processing">Open Recipe library and Batch monitor</a>
                </p>
              ) : (
                <p className="mapping-note">Historical direct Output: no Processing Recipe or Batch execution was pinned.</p>
              )}
              {neutralMaterial ? (
                <p className="success-notice">
                  Loaded exact Neutral Material JSON r{neutralMaterial.revision_no} for this IR.
                </p>
              ) : (
                <button className="button primary" type="button" disabled={busy} onClick={() => void promoteNeutral()}>
                  Create Neutral JSON and solver mapping
                </button>
              )}
            </div>
          ) : !embedded ? (
            <ReferenceLinearViscoelasticExport config={config} model={selected} />
          ) : null}
          {neutralMaterial ? (
            <NeutralSolverExport config={config} neutralMaterial={neutralMaterial} onNavigate={onNavigate} />
          ) : null}
          {!embedded && response ? (
            <div className="relaxation-chart">
              <div><strong>Shear relaxation response</strong><small>G(t), Pa · log-spaced time preview</small></div>
              <svg viewBox="0 0 540 132" role="img" aria-label="Shear relaxation modulus curve">
                <line x1="12" y1="118" x2="528" y2="118" />
                <line x1="12" y1="20" x2="12" y2="118" />
                <path d={path} />
              </svg>
              <div className="chart-range">
                <span>G(0) {(response.points[0].shear_modulus_pa / 1e6).toFixed(1)} MPa</span>
                <span>G(end) {(response.points.at(-1)!.shear_modulus_pa / 1e6).toFixed(1)} MPa</span>
              </div>
            </div>
          ) : !embedded ? <p className="muted">Loading relaxation response…</p> : null}
        </section>
      ) : (
        <p className="muted">No Prony IR exists for this Material State yet.</p>
      )}
    </section>
  );
}

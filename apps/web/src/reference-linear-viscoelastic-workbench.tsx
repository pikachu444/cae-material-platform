import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  type ApiConfig,
  createLinearViscoelasticModel,
  listLinearViscoelasticModels,
  previewLinearViscoelasticResponse,
} from "./api";
import { ReferenceLinearViscoelasticExport } from "./reference-linear-viscoelastic-export";
import type {
  BulkRelaxationStatus,
  LinearViscoelasticModelResponse,
  LinearViscoelasticResponse,
  MaterialStateResponse,
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
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
}) {
  const [models, setModels] = useState<LinearViscoelasticModelResponse[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [response, setResponse] = useState<LinearViscoelasticResponse | null>(null);
  const [bulkStatus, setBulkStatus] = useState<BulkRelaxationStatus>("not_characterized");
  const [terms, setTerms] = useState<EditableTerm[]>(initialTerms);
  const [reason, setReason] = useState("Create manual reference Prony IR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => models.find((model) => model.material_model_id === selectedId) ?? models[0],
    [models, selectedId],
  );

  async function reload(preferredId?: string): Promise<void> {
    const result = await listLinearViscoelasticModels(config, state.material_state_id);
    setModels(result.data.items);
    setSelectedId(preferredId ?? result.data.items[0]?.material_model_id ?? "");
  }

  useEffect(() => {
    setError(null);
    void reload().catch((cause: unknown) => setError(message(cause)));
  }, [config.baseUrl, config.accessToken, state.material_state_id]);

  useEffect(() => {
    setResponse(null);
    if (!selected) return;
    void previewLinearViscoelasticResponse(config, selected.material_model_id)
      .then((result) => setResponse(result.data))
      .catch((cause: unknown) => setError(message(cause)));
  }, [config.baseUrl, config.accessToken, selected?.material_model_id]);

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

  const content = selected?.current_revision.content;
  const path = response ? responsePath(response) : "";

  return (
    <section className="reference-linear-viscoelastic-workbench">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Polymer / elastomer model</p>
          <h4>Linear Prony relaxation</h4>
          <p className="muted">
            Enter dimensionless shear and bulk ratios with relaxation time in seconds. Elastic
            moduli are interpreted as instantaneous values.
          </p>
        </div>
        <span className="revision-chip">reference · non-production</span>
      </div>

      <form className="viscoelastic-form" onSubmit={submit}>
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
      </form>

      {error ? <p className="error-notice">{error}</p> : null}

      {content ? (
        <section className="viscoelastic-result">
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
          <ReferenceLinearViscoelasticExport config={config} model={selected} />
          {response ? (
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
          ) : <p className="muted">Loading relaxation response…</p>}
        </section>
      ) : (
        <p className="muted">No Prony IR exists for this Material State yet.</p>
      )}
    </section>
  );
}

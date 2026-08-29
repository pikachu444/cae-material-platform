import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  type ApiConfig,
} from "./shared/api";
import {
  createOgdenPronyCard,
  createOgdenPronyModel,
  downloadOgdenPronyCard,
  listOgdenPronyCards,
  listOgdenPronyModels,
  preflightOgdenPronyCard,
  previewOgdenPronyCard,
} from "./features/modeling";
import type {
  MaterialStateResponse,
  PropertySetResponse,
} from "./features/materials/contracts";
import type {
  OgdenPronyCardResponse,
  OgdenPronyMappingResponse,
  OgdenPronyModelResponse,
} from "./features/modeling/contracts";
import { OgdenScientificProfilePanel } from "./scientific-profile-panel";
import { ReferenceOgdenCalibrationWorkbench } from "./reference-ogden-calibration-workbench";
import "./features/modeling/ui/modeling-viscoelastic-workbenches.css";

interface EditableTerm {
  ratio: string;
  time: string;
}

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "The Ogden-Prony workflow failed.";
}

export function ReferenceOgdenPronyWorkbench({
  config,
  state,
  propertySet,
  onNavigate,
  embedded = false,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
  onNavigate?: (path: string) => void;
  embedded?: boolean;
}) {
  const [models, setModels] = useState<OgdenPronyModelResponse[]>([]);
  const [cards, setCards] = useState<OgdenPronyCardResponse[]>([]);
  const [report, setReport] = useState<OgdenPronyMappingResponse | null>(null);
  const [solver, setSolver] = useState<"abaqus" | "openradioss">("abaqus");
  const [muMpa, setMuMpa] = useState("1.2");
  const [alpha, setAlpha] = useState("2.4");
  const [terms, setTerms] = useState<EditableTerm[]>([
    { ratio: "0.2", time: "0.1" },
    { ratio: "0.3", time: "10" },
  ]);
  const [materialName, setMaterialName] = useState("ELASTOMER_REFERENCE");
  const [solverMaterialId, setSolverMaterialId] = useState("301");
  const [preview, setPreview] = useState<string | null>(null);
  const [mappingAcknowledged, setMappingAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const model = useMemo(() => models[0], [models]);

  async function reloadModels(): Promise<void> {
    const result = await listOgdenPronyModels(config, state.material_state_id);
    setModels(result.data.items);
  }

  async function reloadCards(modelId: string): Promise<void> {
    const result = await listOgdenPronyCards(config, modelId);
    setCards(result.data.items);
  }

  useEffect(() => {
    setError(null);
    void reloadModels().catch((cause: unknown) => setError(errorMessage(cause)));
  }, [config.baseUrl, config.accessToken, state.material_state_id]);

  useEffect(() => {
    setReport(null);
    setPreview(null);
    if (!model) {
      setCards([]);
      return;
    }
    void reloadCards(model.material_model_id).catch((cause: unknown) =>
      setError(errorMessage(cause)),
    );
  }, [config.baseUrl, config.accessToken, model?.material_model_id]);

  async function createModel(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createOgdenPronyModel(config, state.material_state_id, {
        property_set_revision_id: propertySet.current_revision.id,
        ogden_mu_pa: Number(muMpa) * 1e6,
        ogden_alpha: Number(alpha),
        prony_terms: terms.map((term) => ({
          g_ratio: Number(term.ratio),
          relaxation_time_s: Number(term.time),
        })),
        change_reason: "Create manual reference Ogden-Prony IR",
      });
      await reloadModels();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function runPreflight(): Promise<void> {
    if (!model) return;
    setBusy(true);
    setError(null);
    try {
      const result = await preflightOgdenPronyCard(
        config,
        model.material_model_id,
        model.current_revision.id,
        solver,
      );
      setReport(result.data);
      setMappingAcknowledged(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function generateCard(): Promise<void> {
    if (!model || !report) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createOgdenPronyCard(config, model.material_model_id, {
        material_model_revision_id: model.current_revision.id,
        solver,
        expected_mapping_report_sha256: report.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        material_name: materialName,
        change_reason: `Generate ${solver} reference Ogden-Prony card`,
      });
      await reloadCards(model.material_model_id);
      const text = await previewOgdenPronyCard(config, result.data.solver_card_id);
      setPreview(text.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function download(card: OgdenPronyCardResponse): Promise<void> {
    const result = await downloadOgdenPronyCard(config, card.solver_card_id);
    const url = URL.createObjectURL(result.data.blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.data.filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return (
    <section className="reference-linear-viscoelastic-workbench" aria-label="Ogden Prony card workflow">
      <div className="section-heading elastomer-workbench-heading">
        <div>
          <p className="eyebrow">Elastomer engineering workbench</p>
          <h4>Test modes → model comparison → solver card</h4>
          <p className="muted">
            Compare uniaxial, planar and biaxial evidence across four public hyperelastic families,
            retain holdout results, then deliver the selected Neutral model to Abaqus or OpenRadioss.
          </p>
        </div>
        <span className="revision-chip">reference · non-production</span>
      </div>

      <details className="advanced-definition elastomer-baseline-editor" open={!embedded}>
        <summary>Baseline model and scientific policy</summary>
      <OgdenScientificProfilePanel config={config} />
      <form className="viscoelastic-form" onSubmit={createModel}>
        <div className="form-grid">
          <label>Ogden μ (MPa)<input type="number" min="0.000001" step="any" value={muMpa} onChange={(event) => setMuMpa(event.target.value)} /></label>
          <label>Ogden α<input type="number" min="0.000001" step="any" value={alpha} onChange={(event) => setAlpha(event.target.value)} /></label>
        </div>
        <div className="prony-term-table" role="table" aria-label="Ogden Prony terms">
          {terms.map((term, index) => (
            <div className="prony-term-row" role="row" key={`ogden-term-${index + 1}`}>
              <strong>{index + 1}</strong>
              <input aria-label={`Ogden term ${index + 1} ratio`} type="number" min="0.000001" max="0.999999" step="any" value={term.ratio} onChange={(event) => setTerms((current) => current.map((item, ordinal) => ordinal === index ? { ...item, ratio: event.target.value } : item))} />
              <input aria-label={`Ogden term ${index + 1} time`} type="number" min="0.000000001" step="any" value={term.time} onChange={(event) => setTerms((current) => current.map((item, ordinal) => ordinal === index ? { ...item, time: event.target.value } : item))} />
              <button className="text-button" type="button" disabled={terms.length === 1} onClick={() => setTerms((current) => current.filter((_, ordinal) => ordinal !== index))}>Remove</button>
            </div>
          ))}
        </div>
        <div className="inline-action">
          <button className="text-button" type="button" disabled={terms.length >= 5} onClick={() => setTerms((current) => [...current, { ratio: "0.1", time: String(10 ** current.length) }])}>+ Add term</button>
          <button className="button primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Create immutable Ogden–Prony IR"}</button>
        </div>
      </form>
      </details>

      {model ? (
        <>
        <ReferenceOgdenCalibrationWorkbench
          config={config}
          state={state}
          model={model}
          onNavigate={onNavigate}
          onPromoted={(promoted) => {
            setModels((current) => [
              promoted,
              ...current.filter((item) => item.material_model_id !== promoted.material_model_id),
            ]);
            setReport(null);
            setPreview(null);
            void reloadCards(promoted.material_model_id).catch((cause: unknown) =>
              setError(errorMessage(cause)),
            );
          }}
        />
        <div className="workflow-stack">
          <div className="workflow-step">
            <strong>Saved model revision {model.current_revision.revision_no}</strong>
            <div className="form-grid">
              <label>Solver<select value={solver} onChange={(event) => { setSolver(event.target.value as "abaqus" | "openradioss"); setReport(null); setMappingAcknowledged(false); }}><option value="abaqus">Abaqus 2025</option><option value="openradioss">OpenRadioss 2025 LAW62</option></select></label>
              <label>Solver material ID<input type="number" min="1" value={solverMaterialId} onChange={(event) => setSolverMaterialId(event.target.value)} /></label>
              <label>Material name<input value={materialName} pattern="[A-Za-z][A-Za-z0-9_-]{0,79}" onChange={(event) => setMaterialName(event.target.value)} /></label>
              <div className="delivery-readonly-field"><span>Target tuple</span><strong>{solver} 2025</strong><small>kg·m·s (SI) · exact supported unit system</small></div>
            </div>
            <button className="button secondary" type="button" disabled={busy} onClick={() => void runPreflight()}>Run mapping preflight</button>
          </div>
          {report ? (
            <div className="mapping-report">
              <strong>{report.exportable ? "Exportable mapping" : "Mapping blocked"}</strong>
              <ul className="mapping-list">{report.report.items.map((item) => <li key={item.name}><span className={`mapping-status ${item.status}`}>{item.status}</span><div><strong>{item.name.replaceAll("_", " ")}</strong><small>{item.detail}</small></div></li>)}</ul>
              {report.report.items.some((item) => item.status === "approximated" || item.status === "ignored") ? (
                <label className="mapping-acknowledgement">
                  <input type="checkbox" checked={mappingAcknowledged} onChange={(event) => setMappingAcknowledged(event.target.checked)} />
                  I reviewed the approximated or ignored mappings in this exact report.
                </label>
              ) : null}
              <button
                className="button primary"
                type="button"
                disabled={
                  !report.exportable ||
                  busy ||
                  (report.report.items.some((item) => item.status === "approximated" || item.status === "ignored") && !mappingAcknowledged)
                }
                onClick={() => void generateCard()}
              >
                Generate immutable {solver === "abaqus" ? ".inp" : "LAW62 .rad"} card
              </button>
            </div>
          ) : null}
        </div>
        </>
      ) : <p className="muted">No Ogden–Prony IR exists for this elastomer State yet.</p>}

      {error ? <p className="error-notice" role="alert">{error}</p> : null}
      {cards.map((card) => <article className="solver-card-item" key={card.solver_card_id}><div><strong>{card.target.solver === "abaqus" ? "Abaqus Ogden" : "OpenRadioss LAW62"}</strong><small>{card.current_revision.content.material_name}</small></div><div className="card-actions"><button className="text-button" type="button" onClick={() => void previewOgdenPronyCard(config, card.solver_card_id).then((result) => setPreview(result.data))}>Preview</button><button className="button secondary" type="button" onClick={() => void download(card).catch((cause: unknown) => setError(errorMessage(cause)))}>Download</button>{onNavigate ? <a className="text-button" href={`/materials/${state.material_id}/cards`} onClick={(event) => { event.preventDefault(); onNavigate(`/materials/${state.material_id}/cards`); }}>Open Material CAE Cards</a> : null}</div></article>)}
      {preview ? <pre className="solver-card-preview">{preview}</pre> : null}
    </section>
  );
}

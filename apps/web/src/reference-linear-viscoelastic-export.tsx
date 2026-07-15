import { useEffect, useState } from "react";

import {
  type ApiConfig,
  createLinearViscoelasticSolverCard,
  downloadLinearViscoelasticSolverCard,
  listLinearViscoelasticSolverCards,
  preflightLinearViscoelasticMapping,
  previewLinearViscoelasticSolverCard,
} from "./api";
import type {
  LinearViscoelasticCardResponse,
  LinearViscoelasticMappingReport,
  LinearViscoelasticModelResponse,
} from "./types";

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "The Abaqus card workflow failed.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

export function ReferenceLinearViscoelasticExport({
  config,
  model,
}: {
  config: ApiConfig;
  model: LinearViscoelasticModelResponse;
}) {
  const [report, setReport] = useState<LinearViscoelasticMappingReport | null>(null);
  const [cards, setCards] = useState<LinearViscoelasticCardResponse[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [materialName, setMaterialName] = useState("POLYMER_REFERENCE");
  const [solverMaterialId, setSolverMaterialId] = useState("201");
  const [changeReason, setChangeReason] = useState("Generate Abaqus linear Prony card");
  const [action, setAction] = useState<"preflight" | "create" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload(): Promise<void> {
    const result = await listLinearViscoelasticSolverCards(config, model.material_model_id);
    setCards(result.data.items);
  }

  useEffect(() => {
    setReport(null);
    setPreview(null);
    setError(null);
    void reload().catch((cause: unknown) => setError(errorMessage(cause)));
  }, [config.baseUrl, config.accessToken, model.material_model_id]);

  async function runPreflight(): Promise<void> {
    setAction("preflight");
    setError(null);
    try {
      const result = await preflightLinearViscoelasticMapping(
        config,
        model.material_model_id,
        model.current_revision.id,
      );
      setReport(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setAction(null);
    }
  }

  async function createCard(): Promise<void> {
    if (!report) return;
    setAction("create");
    setError(null);
    try {
      const result = await createLinearViscoelasticSolverCard(config, model.material_model_id, {
        material_model_revision_id: model.current_revision.id,
        expected_mapping_report_sha256: report.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        material_name: materialName,
        change_reason: changeReason,
      });
      await reload();
      const text = await previewLinearViscoelasticSolverCard(
        config,
        result.data.card.solver_card_id,
      );
      setPreview(text.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setAction(null);
    }
  }

  async function download(card: LinearViscoelasticCardResponse): Promise<void> {
    setAction("download");
    setError(null);
    try {
      const result = await downloadLinearViscoelasticSolverCard(config, card.solver_card_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="workflow-stack" aria-label="Abaqus linear Prony card workflow">
      <div className="workflow-step">
        <div className="section-heading compact-heading">
          <div>
            <p className="eyebrow">IR-to-card vertical slice</p>
            <h4>Abaqus 2025 linear Prony card</h4>
          </div>
          <span className="reference-chip">Reference / non-production</span>
        </div>
        <p className="form-hint">
          The immutable IR maps to *DENSITY, instantaneous *ELASTIC, and time-domain
          *VISCOELASTIC Prony data in consistent kg-m-s units.
        </p>
        <button
          className="button secondary"
          type="button"
          disabled={action !== null}
          onClick={() => void runPreflight()}
        >
          {action === "preflight" ? "Checking mapping…" : "Run Abaqus mapping preflight"}
        </button>
        {report ? (
          <section className="mapping-report" aria-label="Abaqus linear Prony mapping report">
            <div className="mapping-report-heading">
              <strong>{report.exportable ? "Exportable mapping" : "Mapping blocked"}</strong>
              <span className="mapping-status exact">Abaqus 2025</span>
            </div>
            <small>Report {shortId(report.mapping_report_sha256)}</small>
            <ul className="mapping-list">
              {report.items.map((item) => (
                <li key={item.name}>
                  <span className={`mapping-status ${item.status}`}>
                    {item.status.replaceAll("_", " ")}
                  </span>
                  <div>
                    <strong>{item.name.replaceAll("_", " ")}</strong>
                    <small>{item.detail}</small>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      {report ? (
        <div className="workflow-step">
          <strong>Generate an immutable .inp card</strong>
          <div className="form-grid">
            <label>
              Material name
              <input
                value={materialName}
                pattern="[A-Za-z][A-Za-z0-9_-]{0,79}"
                onChange={(event) => setMaterialName(event.target.value)}
              />
            </label>
            <label>
              Platform solver material ID
              <input
                type="number"
                min="1"
                max="9999999999"
                value={solverMaterialId}
                onChange={(event) => setSolverMaterialId(event.target.value)}
              />
            </label>
          </div>
          <label>
            Change reason
            <input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} />
          </label>
          <button
            className="button primary"
            type="button"
            disabled={!report.exportable || action !== null}
            onClick={() => void createCard()}
          >
            {action === "create" ? "Generating card…" : "Generate Abaqus .inp"}
          </button>
        </div>
      ) : null}

      {error ? <p className="error-notice" role="alert">{error}</p> : null}
      {cards.map((card) => (
        <article className="solver-card-item" key={card.solver_card_id}>
          <div>
            <strong>*MATERIAL / *VISCOELASTIC</strong>
            <small>{card.material_name} · {shortId(card.current_revision.id)}</small>
          </div>
          <div className="card-actions">
            <button
              className="text-button"
              type="button"
              onClick={() =>
                void previewLinearViscoelasticSolverCard(config, card.solver_card_id)
                  .then((result) => setPreview(result.data))
                  .catch((cause: unknown) => setError(errorMessage(cause)))
              }
            >
              Preview
            </button>
            <button
              className="button secondary"
              type="button"
              disabled={action === "download"}
              onClick={() => void download(card)}
            >
              Download .inp
            </button>
          </div>
        </article>
      ))}
      {preview ? <pre className="solver-card-preview">{preview}</pre> : null}
    </section>
  );
}

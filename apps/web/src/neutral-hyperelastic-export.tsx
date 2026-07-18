import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createNeutralHyperelasticSolverCard,
  downloadNeutralHyperelasticMappingReport,
  downloadNeutralHyperelasticSolverCard,
  preflightNeutralHyperelasticSolverCard,
  previewNeutralHyperelasticSolverCard,
} from "./api";
import type {
  ExportTarget,
  NeutralHyperelasticMappingReport,
  NeutralHyperelasticSolverCardResponse,
  NeutralMaterialResponse,
} from "./types";
import { DomainWorkflowLinks } from "./domain-workflow-links";

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) {
    return cause.message;
  }
  return cause instanceof Error ? cause.message : "Solver card generation failed.";
}

function save(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function NeutralSolverExport({
  config,
  neutralMaterial,
}: {
  config: ApiConfig;
  neutralMaterial: NeutralMaterialResponse;
}) {
  const [solver, setSolver] = useState<"abaqus" | "openradioss">("abaqus");
  const [solverMaterialId, setSolverMaterialId] = useState("301");
  const [materialName, setMaterialName] = useState("ELASTOMER_REFERENCE");
  const [changeReason, setChangeReason] = useState(
    "Create reviewed native card from the exact Neutral Material revision",
  );
  const [report, setReport] = useState<NeutralHyperelasticMappingReport | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [card, setCard] = useState<NeutralHyperelasticSolverCardResponse | null>(null);
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const target: ExportTarget = useMemo(
    () => ({ solver, version: "2025", unit_system: "kg_m_s" }),
    [solver],
  );
  const reviewRequired = report?.report.items.some(
    (item) => item.status === "approximated" || item.status === "ignored",
  ) ?? false;

  useEffect(() => {
    const modelFamily = neutralMaterial.document?.material_model_ir?.model_family;
    setMaterialName(
      modelFamily === "isotropic_tabulated_plasticity"
        ? "METAL_REFERENCE"
        : modelFamily === "generalized_maxwell"
          ? "POLYMER_REFERENCE"
          : "ELASTOMER_REFERENCE",
    );
    setReport(null);
    setAcknowledged(false);
    setCard(null);
    setPreview("");
  }, [solver, neutralMaterial.neutral_material_revision_id]);

  async function preflight(): Promise<void> {
    setBusy("preflight");
    setError(null);
    setCard(null);
    setPreview("");
    try {
      const result = await preflightNeutralHyperelasticSolverCard(
        config,
        neutralMaterial.neutral_material_id,
        {
          neutral_material_revision_id: neutralMaterial.neutral_material_revision_id,
          target,
        },
      );
      setReport(result.data);
      setAcknowledged(false);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function create(): Promise<void> {
    if (!report) return;
    setBusy("create");
    setError(null);
    try {
      const result = await createNeutralHyperelasticSolverCard(
        config,
        neutralMaterial.neutral_material_id,
        {
          neutral_material_revision_id: neutralMaterial.neutral_material_revision_id,
          target,
          expected_mapping_report_sha256: report.mapping_report_sha256,
          solver_material_id: Number(solverMaterialId),
          material_name: materialName.trim(),
          change_reason: changeReason.trim(),
        },
      );
      setCard(result.data);
      const rendered = await previewNeutralHyperelasticSolverCard(
        config,
        result.data.solver_card_id,
      );
      setPreview(rendered.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function downloadCard(): Promise<void> {
    if (!card) return;
    setBusy("download");
    setError(null);
    try {
      const result = await downloadNeutralHyperelasticSolverCard(config, card.solver_card_id);
      save(result.data.blob, result.data.filename);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function downloadReport(): Promise<void> {
    if (!card) return;
    setBusy("report");
    setError(null);
    try {
      const result = await downloadNeutralHyperelasticMappingReport(config, card.solver_card_id);
      save(result.data.blob, result.data.filename);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="workflow-step neutral-solver-export" aria-label="Neutral Material solver card generation">
      <DomainWorkflowLinks
        config={config}
        target={{
          kind: "neutral_material",
          objectId: neutralMaterial.neutral_material_id,
          revisionId: neutralMaterial.neutral_material_revision_id,
          label: `Neutral Material JSON r${neutralMaterial.revision_no}`,
        }}
      />
      <div className="curve-heading">
        <div>
          <p className="eyebrow">T-64 · family-neutral solver mapping</p>
          <h5>Generate a native solver card from this exact Neutral revision</h5>
        </div>
        <span className="reference-chip">reference / non-production</span>
      </div>
      <p className="form-hint">
        Select a declared 2025 target, inspect every mapping state, then acknowledge any
        approximation before creating immutable ASCII output.
      </p>
      <div className="form-grid compact-grid">
        <label>
          Solver target
          <select value={solver} onChange={(event) => setSolver(event.target.value as typeof solver)}>
            <option value="abaqus">Abaqus 2025</option>
            <option value="openradioss">OpenRadioss 2025</option>
          </select>
        </label>
        <label>
          Solver material ID
          <input
            type="number"
            min="1"
            max="9999999999"
            value={solverMaterialId}
            onChange={(event) => setSolverMaterialId(event.target.value)}
          />
        </label>
        <label>
          Material name
          <input value={materialName} onChange={(event) => setMaterialName(event.target.value)} />
        </label>
      </div>
      <label>
        Card creation reason
        <input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} />
      </label>
      <button className="button secondary" type="button" disabled={busy !== null} onClick={() => void preflight()}>
        {busy === "preflight" ? "Checking mapping…" : "Run mapping preflight"}
      </button>
      {report ? (
        <section className="mapping-report" aria-label="Neutral Material solver mapping report">
          <div className="mapping-report-heading">
            <div>
              <strong>{report.report.family.replaceAll("_", " ")} → {solver}</strong>
              <small>Report SHA-256 {report.mapping_report_sha256.slice(0, 16)}…</small>
            </div>
            <span className={report.exportable ? "status-chip success" : "status-chip warning"}>
              {report.exportable ? "exportable" : "blocked"}
            </span>
          </div>
          <ul className="mapping-list" aria-label="Mapping items">
            {report.report.items.map((item) => (
              <li key={item.name}>
                <span className={`mapping-status ${item.status}`}>{item.status}</span>
                <div>
                  <strong>{item.name.replaceAll("_", " ")} · {item.target_representation ?? "sidecar only"}</strong>
                  <small>{item.detail}</small>
                </div>
              </li>
            ))}
          </ul>
          {report.report.exporter.documentation_url ? (
            <a href={report.report.exporter.documentation_url} target="_blank" rel="noreferrer">
              Official keyword reference used by this exporter
            </a>
          ) : null}
          {reviewRequired ? (
            <label className="acknowledgement-control">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              I reviewed every approximated or ignored mapping state.
            </label>
          ) : null}
          <button
            className="button primary"
            type="button"
            disabled={
              busy !== null ||
              !report.exportable ||
              (reviewRequired && !acknowledged) ||
              !materialName.trim() ||
              !changeReason.trim() ||
              Number(solverMaterialId) < 1
            }
            onClick={() => void create()}
          >
            {busy === "create" ? "Creating immutable card…" : "Create solver card"}
          </button>
        </section>
      ) : null}
      {card ? (
        <div className="promotion-confirmation" aria-live="polite">
          <strong>{card.target.solver} card r{card.current_revision.revision_no} created</strong>
          <small>Card SHA-256 {card.current_revision.content.card_sha256.slice(0, 16)}…</small>
          <small>Exact Neutral revision {neutralMaterial.revision_no} remains unchanged.</small>
          <div className="button-row">
            <button className="button secondary" type="button" disabled={busy !== null} onClick={() => void downloadCard()}>
              {busy === "download" ? "Preparing card…" : "Download native ASCII card"}
            </button>
            <button className="button secondary" type="button" disabled={busy !== null} onClick={() => void downloadReport()}>
              {busy === "report" ? "Preparing report…" : "Download mapping report JSON"}
            </button>
          </div>
          {preview ? <pre className="solver-card-preview" aria-label="Solver card preview">{preview}</pre> : null}
        </div>
      ) : null}
      {error ? <p className="error-banner">{error}</p> : null}
    </section>
  );
}

// T-57 compatibility export for the existing hyperelastic workbench and external imports.
export const NeutralHyperelasticExport = NeutralSolverExport;

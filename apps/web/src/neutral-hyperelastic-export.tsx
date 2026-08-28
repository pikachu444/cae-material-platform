import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  createNeutralHyperelasticSolverCard,
  downloadNeutralMaterial,
  downloadNeutralHyperelasticMappingReport,
  downloadNeutralHyperelasticSolverCard,
  preflightNeutralHyperelasticSolverCard,
  previewNeutralHyperelasticSolverCard,
} from "./features/modeling";
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
  onNavigate,
}: {
  config: ApiConfig;
  neutralMaterial: NeutralMaterialResponse;
  onNavigate?: (path: string) => void;
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
  const [showReview, setShowReview] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const target: ExportTarget = useMemo(
    () => ({ solver, version: "2025", unit_system: "kg_m_s" }),
    [solver],
  );
  const reviewRequired = report?.report.items.some(
    (item) => item.status === "approximated" || item.status === "ignored",
  ) ?? false;
  const source = neutralMaterial.document.sources ?? { datasets: [] };
  const model = neutralMaterial.document.material_model_ir;
  const selection = neutralMaterial.document.candidate_selection;
  const materialLaw = model?.model_family === "isotropic_tabulated_plasticity"
    ? solver === "abaqus" ? "Isotropic *PLASTIC" : "/MAT/LAW36 + /FUNCT"
    : model?.model_family === "generalized_maxwell"
      ? solver === "abaqus" ? "TIME=PRONY" : "/VISC/LPRONY"
      : solver === "abaqus" ? "Hyperelastic + TIME=PRONY" : "/MAT/LAW62 + /VISC/PRONY";
  const reviewedEvidenceCount = [
    source.material,
    source.material_state,
    source.property_set,
    ...(source.datasets ?? []),
    selection?.processing_output,
    model?.model,
  ].filter(Boolean).length;

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
    setShowReview(true);
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
      setShowReview(true);
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
        result.data.current_revision.id,
      );
      setPreview(rendered.data);
      setShowReview(false);
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
      const result = await downloadNeutralHyperelasticSolverCard(
        config,
        card.solver_card_id,
        card.current_revision.id,
      );
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
      const result = await downloadNeutralHyperelasticMappingReport(
        config,
        card.solver_card_id,
        card.current_revision.id,
      );
      save(result.data.blob, result.data.filename);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function downloadNeutralJson(): Promise<void> {
    setBusy("neutral");
    setError(null);
    try {
      const result = await downloadNeutralMaterial(config, neutralMaterial.neutral_material_id);
      save(result.data.blob, result.data.filename);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={`workflow-step neutral-solver-export reviewed-delivery ${card ? "has-card" : ""}`} aria-label="Reviewed Neutral Material and solver card delivery">
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
          <p className="eyebrow">Final step · reviewed delivery</p>
          <h5>Neutral Material JSON → verified mapping → native solver card</h5>
        </div>
        <span className="reference-chip">reference / non-production</span>
      </div>
      <p className="form-hint">
        This panel pins the selected result and its exact evidence. Review the neutral model,
        inspect every solver mapping state, then download the native ASCII card without leaving
        the modeling workspace.
      </p>
      <ol className="delivery-progress" aria-label="Reviewed delivery progress">
        <li className="complete"><span>1</span><strong>Evidence reviewed</strong><small>{reviewedEvidenceCount} exact references</small></li>
        <li className="complete"><span>2</span><strong>Neutral JSON</strong><small>r{neutralMaterial.revision_no} · {(neutralMaterial.document.content_sha256 ?? neutralMaterial.content_hash).slice(0, 10)}…</small></li>
        <li className={report ? "complete" : "current"}><span>3</span><strong>Solver mapping</strong><small>{report ? `${report.report.items.length} states checked` : "Preflight required"}</small></li>
        <li className={card ? "complete" : report ? "current" : "pending"}><span>4</span><strong>Native card</strong><small>{card ? `${card.target.solver} r${card.current_revision.revision_no}` : "Preview and download"}</small></li>
      </ol>
      {!card || showReview ? <section className="delivery-evidence" aria-label="Exact reviewed evidence">
        <div className="delivery-evidence-heading">
          <div>
            <strong>Selected model result</strong>
            <small>{model?.constitutive_model.family.replaceAll("_", " ") ?? "canonical material model"} · {model?.maturity ?? "exact revision"}</small>
          </div>
          <span className="status-chip success">exact revisions</span>
        </div>
        <dl>
          <div><dt>Selection reason</dt><dd>{selection?.reason ?? "Canonical Neutral revision selected"}</dd></div>
          <div><dt>Model revision</dt><dd>Exact model revision pinned in Neutral JSON</dd></div>
          {selection?.processing_output ? <div><dt>Processing Output</dt><dd>Exact reviewed output revision pinned</dd></div> : null}
          <div><dt>Input datasets</dt><dd>{source.datasets?.length ?? 0} pinned revision{source.datasets?.length === 1 ? "" : "s"}</dd></div>
          <div><dt>Curve stages</dt><dd>{neutralMaterial.document.curve_stages?.length ?? 0} preserved stages</dd></div>
          <div><dt>Applicability</dt><dd>{Object.keys(neutralMaterial.document.applicability ?? {})[0]?.replaceAll("_", " ") ?? "declared in document"}</dd></div>
        </dl>
        {selection?.warnings?.length ? (
          <ul className="delivery-warnings">{selection.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        ) : <p className="success-notice">No candidate warning was recorded in this exact Neutral revision.</p>}
        <div className="button-row">
          <button className="button secondary" type="button" disabled={busy !== null} onClick={() => void downloadNeutralJson()}>
            {busy === "neutral" ? "Preparing Neutral JSON…" : "Download exact Neutral JSON"}
          </button>
          {source.material && onNavigate ? (
            <button className="text-button" type="button" onClick={() => onNavigate(`/materials/${source.material!.id}/models`)}>
              Return to Material datasheet
            </button>
          ) : null}
        </div>
      </section> : null}
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
        <div className="delivery-readonly-field"><span>Target tuple</span><strong>{solver} 2025</strong><small>kg·m·s (SI) · exact supported unit system</small></div>
        <div className="delivery-readonly-field"><span>Material law</span><strong>{materialLaw}</strong><small>Declared by the exporter capability manifest</small></div>
      </div>
      <label>
        Card creation reason
        <input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} />
      </label>
      <button className="button secondary" type="button" disabled={busy !== null} onClick={() => void preflight()}>
        {busy === "preflight" ? "Checking mapping…" : "Run mapping preflight"}
      </button>
      {report && (!card || showReview) ? (
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
          <div className="mapping-status-legend" aria-label="All solver mapping status meanings">{(["exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"] as const).map((status) => <span className={`mapping-status ${status}`} key={status}>{status.replace("_", " ")}</span>)}</div>
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
            {onNavigate ? (
              <button className="text-button" type="button" onClick={() => onNavigate("/exports")}>
                Add exact files to a bulk package
              </button>
            ) : null}
            {source.material && onNavigate ? (
              <a className="text-button" href={`/materials/${source.material.id}/cards`} onClick={(event) => {
                event.preventDefault();
                onNavigate(`/materials/${source.material!.id}/cards`);
              }}>
                Open Material CAE Cards
              </a>
            ) : null}
            <button className="text-button" type="button" onClick={() => setShowReview((value) => !value)}>
              {showReview ? "Hide evidence and mapping" : "Review exact evidence and mapping"}
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

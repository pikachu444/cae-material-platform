import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  createNeutralHyperelasticSolverCard,
  preflightNeutralHyperelasticSolverCard,
  type ApiConfig,
} from "./api";
import type { MappingStatus, NeutralHyperelasticMappingReport } from "./types";
import {
  downloadSolverCardArtifact,
  loadSolverCardEvidence,
  mappingDisposition,
  recordDeliveryActivity,
  type SolverCardEvidence,
  type SolverCardSummary,
} from "./solver-card-delivery";

interface MaterialActivityContext {
  materialId: string;
  materialRevisionId: string;
  materialLabel: string;
}

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "Solver delivery could not be completed.";
}

function save(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function activityFor(
  action: "preview" | "download",
  material: MaterialActivityContext,
  card: SolverCardSummary,
) {
  recordDeliveryActivity({
    action,
    ...material,
    cardId: card.id,
    cardRevisionId: card.revisionId,
    cardLabel: card.label,
    solver: card.solver,
    extension: card.extension,
  });
}

/**
 * Keep exporter vocabulary in the evidence model while showing the consequence
 * a normal user needs to act on. The raw status remains available in Advanced
 * mapping evidence.
 */
export function deliveryStatusLabel(status: MappingStatus): string {
  switch (status) {
    case "exact":
      return "Values unchanged";
    case "transformed":
      return "Converted";
    case "approximated":
    case "ignored":
      return "Review required";
    case "unsupported":
      return "Not supported";
    case "not_applicable":
      return "Context only";
    default:
      return "Check compatibility";
  }
}

function deliveryDetailLabel(status: MappingStatus, name: string): string {
  switch (status) {
    case "exact":
      return "Included without value changes.";
    case "transformed":
      return "Rendered in the solver's native format.";
    case "approximated":
    case "ignored":
      if (name === "post_necking_extension") return "The selected curve continues beyond the measured range.";
      return "Check this delivery note before downloading.";
    case "unsupported":
      return "This source value is not available for this solver.";
    case "not_applicable":
      return "No action is needed for this card.";
    default:
      return "Check compatibility before continuing.";
  }
}

export function SolverCardAction({
  config,
  card,
  material,
  onNavigate,
  directClassName = "ux-button primary",
  reviewClassName = "ux-button primary",
  includePreview = false,
}: {
  config: ApiConfig;
  card: SolverCardSummary;
  material: MaterialActivityContext;
  onNavigate: (path: string) => void;
  directClassName?: string;
  reviewClassName?: string;
  includePreview?: boolean;
}) {
  const [evidence, setEvidence] = useState<SolverCardEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void loadSolverCardEvidence(config, card).then((result) => {
      if (!active) return;
      setEvidence(result);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [card, config]);

  async function download(): Promise<void> {
    setDownloading(true);
    setError(null);
    try {
      const result = await downloadSolverCardArtifact(config, card);
      save(result.data.blob, result.data.filename);
      activityFor("download", material, card);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setDownloading(false);
    }
  }

  if (loading) return <button className="ux-button" type="button" disabled title="Delivery checks are loading.">Checking…</button>;
  if (!evidence || error) {
    return <span className="delivery-action-stack"><button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${material.materialId}/cards/${card.id}`)}>Preview card</button>{error ? <small role="alert">{error} Review the card evidence.</small> : null}</span>;
  }
  if (evidence.disposition === "blocked") {
    const blockers = evidence.mappingItems.filter((item) => item.status === "unsupported").map((item) => item.name.replaceAll("_", " ")).join(", ");
    return <>{includePreview ? <button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${material.materialId}/cards/${card.id}`)}>Preview</button> : null}<span className="delivery-blocked-command" role="status">Not supported: {blockers || "some source values"}</span></>;
  }
  if (evidence.disposition === "review") {
    return <button className={reviewClassName} type="button" onClick={() => onNavigate(`/materials/${material.materialId}/cards/${card.id}`)}>Preview card</button>;
  }
  return <>{includePreview ? <button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${material.materialId}/cards/${card.id}`)}>Preview</button> : null}<button className={directClassName} type="button" disabled={downloading} onClick={() => void download()}>{downloading ? "Preparing…" : `Download ${card.extension}`}</button></>;
}

export function MappingStatusList({
  items,
  reviewAcknowledgement,
}: {
  items: SolverCardEvidence["mappingItems"];
  reviewAcknowledgement?: ReactNode;
}) {
  const reviewIndex = items.findIndex((item) => item.status === "approximated" || item.status === "ignored");
  return <ul className="delivery-mapping-list" aria-label="Delivery checks">
    {items.map((item, index) => <li className={`delivery-mapping-row${item.status === "approximated" || item.status === "ignored" ? " delivery-mapping-row-review" : ""}`} key={`${item.name}:${item.ir_path}`}>
      <span className="delivery-mapping-copy"><strong>{item.name.replaceAll("_", " ")}</strong><small>{deliveryDetailLabel(item.status, item.name)}</small></span>
      <span className={`mapping-status ${item.status}`}>{deliveryStatusLabel(item.status)}</span>
      {reviewAcknowledgement && index === reviewIndex ? reviewAcknowledgement : null}
    </li>)}
  </ul>;
}

export function NeutralCardCreationPanel({
  config,
  neutralMaterialId,
  neutralMaterialRevisionId,
  materialName,
  materialCode,
  existingCards,
  onCreated,
}: {
  config: ApiConfig;
  neutralMaterialId: string;
  neutralMaterialRevisionId: string;
  materialName: string;
  materialCode: string | null;
  existingCards: SolverCardSummary[];
  onCreated: (card: SolverCardSummary) => void;
}) {
  const availableTargets = useMemo(() => {
    const existingSolvers = new Set(existingCards.map((card) => card.solver));
    return (["abaqus", "openradioss"] as const).filter(
      (solver) => !existingSolvers.has(solver === "abaqus" ? "Abaqus" : "OpenRadioss"),
    );
  }, [existingCards]);
  const [solver, setSolver] = useState<"abaqus" | "openradioss">(availableTargets[0] ?? "abaqus");
  const [solverMaterialId, setSolverMaterialId] = useState("301");
  const [cardName, setCardName] = useState((materialCode || materialName).toUpperCase().replace(/[^A-Z0-9_]+/g, "_"));
  const [report, setReport] = useState<NeutralHyperelasticMappingReport | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState<"preflight" | "create" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const target = useMemo(() => ({ solver, version: "2025", unit_system: "kg_m_s" }), [solver]);

  useEffect(() => {
    if (!availableTargets.includes(solver)) setSolver(availableTargets[0] ?? "abaqus");
  }, [availableTargets, solver]);

  useEffect(() => {
    if (!availableTargets.length) return;
    let active = true;
    setBusy("preflight");
    setError(null);
    setReport(null);
    setAcknowledged(false);
    void preflightNeutralHyperelasticSolverCard(config, neutralMaterialId, {
      neutral_material_revision_id: neutralMaterialRevisionId,
      target,
    }).then((result) => {
      if (!active) return;
      setReport(result.data);
      setBusy(null);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setBusy(null);
    });
    return () => { active = false; };
  }, [availableTargets.length, config, neutralMaterialId, neutralMaterialRevisionId, target]);

  if (!availableTargets.length) return null;
  const disposition = report ? (report.exportable ? mappingDisposition(report.report.items) : "blocked") : null;
  const reviewRequired = disposition === "review";

  async function create(): Promise<void> {
    if (!report || disposition === "blocked") return;
    setBusy("create");
    setError(null);
    try {
      const result = await createNeutralHyperelasticSolverCard(config, neutralMaterialId, {
        neutral_material_revision_id: neutralMaterialRevisionId,
        target,
        expected_mapping_report_sha256: report.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        material_name: cardName.trim(),
        change_reason: "Create governed native solver card from the Material CAE Cards workspace",
      });
      const created = result.data;
      onCreated({
        id: created.solver_card_id,
        revisionId: created.current_revision.id,
        kind: "neutral_solver_card",
        label: `${materialName} ${solver === "abaqus" ? "Abaqus" : "OpenRadioss"} native material card`,
        solver: solver === "abaqus" ? "Abaqus" : "OpenRadioss",
        extension: solver === "abaqus" ? ".inp" : ".rad",
      });
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  return <section className="neutral-card-creation" aria-label="Create solver card from selected source data">
    <header><div><h3>Create card</h3><p>Use the selected source data, check compatibility, then save a native card.</p></div><span>Reference / non-production</span></header>
    <div className="delivery-property-grid">
      <label>Solver<select name="solver-target" autoComplete="off" value={solver} onChange={(event) => setSolver(event.target.value as typeof solver)}>{availableTargets.map((item) => <option key={item} value={item}>{item === "abaqus" ? "Abaqus" : "OpenRadioss"}</option>)}</select></label>
      <div><span>Version</span><strong>2025</strong></div>
      <div><span>Unit system</span><strong>kg · m · s</strong></div>
      <label>Solver material ID<input name="solver-material-id" autoComplete="off" type="number" min="1" max="9999999999" value={solverMaterialId} onChange={(event) => setSolverMaterialId(event.target.value)}/></label>
      <label>Material name<input name="solver-material-name" autoComplete="off" value={cardName} onChange={(event) => setCardName(event.target.value)}/></label>
    </div>
    {busy === "preflight" ? <p className="delivery-progress-line" role="status">Checking compatibility…</p> : null}
    {report ? <MappingStatusList items={report.report.items} reviewAcknowledgement={reviewRequired ? <label className="delivery-acknowledgement"><input name="mapping-creation-acknowledgement" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)}/>I reviewed the delivery notes before saving this card.</label> : undefined}/>: null}
    {disposition === "blocked" ? <p className="ux-notice error" role="alert">This card cannot be saved because some source values are not supported by the selected solver.</p> : null}
    {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
    <button className="ux-button primary" type="button" disabled={!report || busy !== null || disposition === "blocked" || (reviewRequired && !acknowledged) || !cardName.trim() || !Number.isInteger(Number(solverMaterialId)) || Number(solverMaterialId) < 1 || Number(solverMaterialId) > 9999999999} onClick={() => void create()}>{busy === "create" ? "Saving card…" : "Create card"}</button>
  </section>;
}

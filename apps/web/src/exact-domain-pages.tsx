import { useEffect, useMemo, useState } from "react";

import {
  downloadSelectedModelNeutralMaterial,
  getCatalogWorkflowGraph,
  getMaterialModel,
  getNeutralMaterial,
  getNeutralSolverCard,
  getSolverCard,
  resolveCatalogDomainRevision,
  type ApiConfig,
} from "./api";
import type { CatalogWorkflowGraphResponse, DomainBindingKind, DomainRevisionBinding } from "./types";
import {
  downloadSolverCardArtifact,
  loadSolverCardEvidence,
  previewSolverCardText,
  type SolverCardSummary,
} from "./solver-card-delivery";
import { ReviewRequestAction } from "./review-request-action";

function messageFor(cause: unknown): string {
  return cause instanceof Error ? cause.message : "The exact governed object could not be loaded.";
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function graphBindings(graph: CatalogWorkflowGraphResponse): DomainRevisionBinding[] {
  const bindings = [graph.root, ...graph.nodes].flatMap((node) => {
    const all = node.domain_bindings?.length
      ? node.domain_bindings
      : node.domain_binding
        ? [node.domain_binding]
        : [];
    return all.map((binding) => ({
      ...binding,
      record_id: node.record_id,
      record_revision_id: node.record_revision_id,
    }));
  });
  const seen = new Set<string>();
  return bindings.filter((binding) => {
    const key = `${binding.record_id}:${binding.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function requirePublishedBinding(
  config: ApiConfig,
  kind: DomainBindingKind,
  objectId: string,
  revisionId: string,
): Promise<{ binding: DomainRevisionBinding; graph: CatalogWorkflowGraphResponse }> {
  const resolved = await resolveCatalogDomainRevision(config, kind, objectId, revisionId);
  const binding = resolved.data;
  if (!binding || binding.object_id !== objectId || binding.revision_id !== revisionId) {
    throw new Error("This exact revision is not an approved Materials subject.");
  }
  const graph = (await getCatalogWorkflowGraph(
    config,
    binding.record_id,
    binding.record_revision_id,
    6,
    true,
  )).data;
  const approved = graphBindings(graph).some((candidate) =>
    candidate.kind === kind
    && candidate.object_id === objectId
    && candidate.revision_id === revisionId
    && candidate.record_id === binding.record_id
    && candidate.record_revision_id === binding.record_revision_id,
  );
  if (!approved) throw new Error("This exact revision is not approved in the current Materials graph.");
  return { binding, graph };
}

function ExactFailure({ message, onBack }: { message: string; onBack: () => void }) {
  return <div className="ux-page"><div className="ux-notice error" role="alert">{message}</div><button className="ux-button" type="button" onClick={onBack}>Back to Materials</button></div>;
}

export function ExactMaterialModelPage({ config, materialModelId, revisionId, onNavigate }: { config: ApiConfig; materialModelId: string; revisionId: string; onNavigate: (path: string) => void }) {
  const [model, setModel] = useState<Awaited<ReturnType<typeof getMaterialModel>>["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setModel(null);
    setError(null);
    void getMaterialModel(config, materialModelId).then(async (result) => {
      if (!active) return;
      if (result.data.current_revision.id !== revisionId) throw new Error("This Material Model revision is no longer the current published revision.");
      await requirePublishedBinding(config, "material_model", materialModelId, revisionId);
      if (!active) return;
      setModel(result.data);
    }).catch((cause: unknown) => active && setError(messageFor(cause)));
    return () => { active = false; };
  }, [config, materialModelId, revisionId]);
  if (error) return <ExactFailure message={error} onBack={() => onNavigate("/materials")} />;
  if (!model) return <div className="ux-page"><p role="status">Loading exact Material Model…</p></div>;
  const content = model.current_revision.content;
  return <div className="ux-page exact-domain-page"><header className="page-heading"><div><p className="ux-kicker">Modeling</p><h1>Material Model</h1><p>Current exact revision linked from the published Materials workflow.</p></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate("/materials")}>Back to Materials</button></header><section className="exact-domain-section"><dl className="evidence-grid"><div><dt>Revision</dt><dd>r{model.current_revision.revision_no}</dd></div><div><dt>Density</dt><dd>{content.density_kg_per_m3} kg/m³</dd></div><div><dt>Young’s modulus</dt><dd>{content.youngs_modulus_pa} Pa</dd></div><div><dt>Poisson ratio</dt><dd>{content.poisson_ratio}</dd></div><div><dt>Material State</dt><dd>Approved exact state input</dd></div></dl><details className="ux-disclosure"><summary>Advanced identity</summary><dl className="evidence-grid"><div><dt>Material State ID</dt><dd>{content.material_state_id}</dd></div><div><dt>Material State revision</dt><dd>{content.material_state_revision_id}</dd></div><div><dt>Model content hash</dt><dd>{model.current_revision.content_hash}</dd></div></dl></details></section></div>;
}

export function ExactNeutralMaterialPage({ config, neutralMaterialId, revisionId, onNavigate }: { config: ApiConfig; neutralMaterialId: string; revisionId: string; onNavigate: (path: string) => void }) {
  const [material, setMaterial] = useState<Awaited<ReturnType<typeof getNeutralMaterial>>["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  useEffect(() => {
    let active = true;
    setMaterial(null);
    setError(null);
    void getNeutralMaterial(config, neutralMaterialId).then(async (result) => {
      if (!active) return;
      if (result.data.neutral_material_revision_id !== revisionId) throw new Error("This Neutral Material revision is no longer the current published revision.");
      await requirePublishedBinding(config, "neutral_material", neutralMaterialId, revisionId);
      if (!active) return;
      setMaterial(result.data);
    }).catch((cause: unknown) => active && setError(messageFor(cause)));
    return () => { active = false; };
  }, [config, neutralMaterialId, revisionId]);
  async function download(): Promise<void> {
    if (downloading || !material) return;
    setDownloading(true);
    try {
      const result = await downloadSelectedModelNeutralMaterial(config, neutralMaterialId, revisionId);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setDownloading(false);
    }
  }
  if (error) return <ExactFailure message={error} onBack={() => onNavigate("/materials")} />;
  if (!material) return <div className="ux-page"><p role="status">Loading exact Neutral Material…</p></div>;
  return <div className="ux-page exact-domain-page"><header className="page-heading"><div><p className="ux-kicker">Modeling</p><h1>Neutral Material</h1><p>Current exact revision linked from the published Materials workflow.</p></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate("/materials")}>Back to Materials</button></header><section className="exact-domain-section"><dl className="evidence-grid"><div><dt>Revision</dt><dd>r{material.revision_no}</dd></div><div><dt>Model family</dt><dd>{material.document.material_model_ir.model_family ?? material.document.material_model_ir.constitutive_model.family}</dd></div><div><dt>Validation</dt><dd>{material.document.validation.status}</dd></div></dl><button className="ux-button primary" type="button" disabled={downloading} onClick={() => void download()}>{downloading ? "Preparing…" : "Download Neutral JSON"}</button><details className="ux-disclosure"><summary>Advanced identity</summary><dl className="evidence-grid"><div><dt>Source model</dt><dd>{material.document.material_model_ir.model.id} · {material.document.material_model_ir.model.revision_id}</dd></div><div><dt>Neutral content hash</dt><dd>{material.content_hash}</dd></div><div><dt>Document artifact SHA-256</dt><dd>{material.document_artifact.sha256}</dd></div></dl></details></section></div>;
}

export function ExactSolverCardPage({ config, cardId, revisionId, kind, onNavigate }: { config: ApiConfig; cardId: string; revisionId: string; kind: "solver_card" | "neutral_solver_card"; onNavigate: (path: string) => void }) {
  const [card, setCard] = useState<SolverCardSummary | null>(null);
  const [evidence, setEvidence] = useState<Awaited<ReturnType<typeof loadSolverCardEvidence>> | null>(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  useEffect(() => {
    let active = true;
    setCard(null);
    setEvidence(null);
    setPreview("");
    setError(null);
    void (kind === "neutral_solver_card" ? getNeutralSolverCard(config, cardId, revisionId) : getSolverCard(config, cardId, revisionId)).then(async (result) => {
      const current = result.data.current_revision;
      if (current.id !== revisionId) throw new Error("This solver card revision is no longer the current published revision.");
      await requirePublishedBinding(config, kind, cardId, revisionId);
      const target = "target" in result.data ? result.data.target : current.content.target;
      const solver = target.solver.toLowerCase() === "abaqus" ? "Abaqus" : target.solver.toLowerCase() === "openradioss" ? "OpenRadioss" : "Solver";
      const label = "material_name" in current.content ? current.content.material_name : "card_title" in current.content ? current.content.card_title : "Solver card";
      const summary: SolverCardSummary = { id: cardId, revisionId, kind, label, solver, extension: solver === "Abaqus" ? ".inp" : solver === "OpenRadioss" ? ".rad" : ".txt" };
      const [loadedEvidence, previewResult] = await Promise.all([loadSolverCardEvidence(config, summary), previewSolverCardText(config, summary)]);
      if (!active) return;
      setCard(summary);
      setEvidence(loadedEvidence);
      setPreview(previewResult.data);
    }).catch((cause: unknown) => active && setError(messageFor(cause)));
    return () => { active = false; };
  }, [cardId, config, kind, revisionId]);
  async function download(): Promise<void> {
    if (!card || downloading) return;
    setDownloading(true);
    try {
      const result = await downloadSolverCardArtifact(config, card);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setDownloading(false);
    }
  }
  const reviewSubject = useMemo(() => evidence ? { aggregateType: evidence.reviewAggregateType, aggregateId: cardId, revisionId: evidence.reviewRevisionId, manifestSha256: evidence.reviewContentHash, classification: evidence.reviewClassification, lifecycleState: evidence.lifecycleState } : null, [cardId, evidence]);
  if (error) return <ExactFailure message={error} onBack={() => onNavigate("/materials")} />;
  if (!card || !evidence) return <div className="ux-page"><p role="status">Loading exact solver card…</p></div>;
  const blocked = evidence.disposition === "blocked";
  return <div className="ux-page"><div className="card-preview-shell"><header className="card-preview-header"><div><button className="ux-button tertiary" type="button" onClick={() => onNavigate("/materials")}>Back to Materials</button><p className="ux-kicker">{card.solver} · Native ASCII</p><h1>{card.label}</h1><p>Exact published card revision.</p></div><div className="card-action-row"><ReviewRequestAction config={config} subject={reviewSubject} /></div></header><div className="card-preview-content"><section className="native-preview" aria-label="Native solver card preview"><pre>{preview}</pre></section><aside className="card-preview-actions"><h2>Delivery</h2><p>{blocked ? "Download blocked for this mapping." : "Published exact card is ready to download."}</p><button className="ux-button primary" type="button" disabled={blocked || downloading} onClick={() => void download()}>{downloading ? "Preparing…" : `Download ${card.extension}`}</button><details className="ux-disclosure"><summary>Mapping details</summary><ul>{evidence.mappingItems.map((item) => <li key={`${item.name}:${item.status}`}>{item.name} · {item.status}</li>)}</ul></details></aside></div></div></div>;
}

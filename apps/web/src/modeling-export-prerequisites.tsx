import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  promoteModelToNeutralMaterial,
  promoteProcessingOutputToTabulatedPlasticity,
} from "./features/modeling";
import { ReviewRequestAction } from "./review-request-action";
import type {
  CommonProcessingOutputResponse,
  ExportPrerequisite,
  ModelingSessionEvent,
  ModelingSessionSummary,
} from "./features/modeling";
import type { PropertySetResponse } from "./features/materials/contracts";

interface UpstreamModelRef {
  id: string;
  revisionId: string;
  revisionNo: number;
  manifestSha256?: string;
  classification?: import("./shared/model/core-contracts").DataClassification;
  lifecycleState?: "draft" | "published";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "The exact metal model chain could not be prepared.";
}

function sourcePrerequisitesCurrent(prerequisites: ExportPrerequisite[]): boolean {
  return prerequisites
    .filter((item) => !["Material Model IR", "Neutral representation", "Ephemeral target preview producer"].includes(item.label))
    .every((item) => item.status === "current");
}

function currentPropertySet(
  session: ModelingSessionSummary | null | undefined,
  propertySet: PropertySetResponse | undefined,
): boolean {
  return Boolean(session?.materialState && propertySet
    && propertySet.material_state_id === session.materialState.id
    && propertySet.current_revision.content.material_state_revision_id === session.materialState.revisionId);
}

function exactPromotionMatches(
  session: ModelingSessionSummary,
  output: CommonProcessingOutputResponse,
  propertySet: PropertySetResponse,
  model: Awaited<ReturnType<typeof promoteProcessingOutputToTabulatedPlasticity>>["data"],
): boolean {
  const content = model.current_revision.content;
  const projection = content.processing_projection;
  return content.material_id === session.material?.id
    && content.material_revision_id === session.material?.revisionId
    && content.material_state_id === session.materialState?.id
    && content.material_state_revision_id === session.materialState?.revisionId
    && content.property_set_id === propertySet.property_set_id
    && content.property_set_revision_id === propertySet.current_revision.id
    && projection?.output_id === output.processing_output_id
    && projection?.output_revision_id === output.current_revision.id
    && projection?.output_sha256 === `sha256:${output.output_sha256}`;
}

function ModelingMetalExportRecovery({
  config, session, output, propertySet, onSessionEvent,
}: {
  config: ApiConfig;
  session: ModelingSessionSummary;
  output: CommonProcessingOutputResponse;
  propertySet: PropertySetResponse;
  onSessionEvent?: (event: ModelingSessionEvent) => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promotedModel, setPromotedModel] = useState<UpstreamModelRef | null>(null);
  const exactSourceKey = useMemo(() => [
    session.material?.id,
    session.material?.revisionId,
    session.materialState?.id,
    session.materialState?.revisionId,
    output.processing_output_id,
    output.current_revision.id,
    propertySet.property_set_id,
    propertySet.current_revision.id,
  ].join("/"), [output.current_revision.id, output.processing_output_id, propertySet.current_revision.id, propertySet.property_set_id, session.material?.id, session.material?.revisionId, session.materialState?.id, session.materialState?.revisionId]);
  useEffect(() => {
    setPromotedModel(null);
    setError(null);
  }, [exactSourceKey]);
  const existingModel = session.materialModelIr ? {
    id: session.materialModelIr.id,
    revisionId: session.materialModelIr.revisionId,
    revisionNo: session.materialModelIr.revisionNo,
    manifestSha256: session.materialModelIr.manifestSha256,
    classification: session.materialModelIr.classification,
    lifecycleState: session.materialModelIr.lifecycleState,
  } : null;
  const modelForNeutral = promotedModel ?? existingModel;
  const canPrepare = (modelForNeutral !== null || acknowledged) && reason.trim().length > 0 && !busy;

  function pinModel(model: UpstreamModelRef): void {
    setPromotedModel(model);
    onSessionEvent?.({ type: "SET_CURRENT", key: "materialModelIr", value: {
      id: model.id,
      revisionId: model.revisionId,
      label: "Selected metal tabulated-plasticity model",
      revisionNo: model.revisionNo,
      manifestSha256: model.manifestSha256,
      classification: model.classification,
      lifecycleState: model.lifecycleState,
    } });
  }

  async function promoteNeutral(model: UpstreamModelRef): Promise<void> {
    if (!session.material || !session.materialState) return;
    const neutral = await promoteModelToNeutralMaterial(config, "metal", {
      material_model_id: model.id,
      material_model_revision_id: model.revisionId,
      selection_reason: "Promote this exact selected hardening model for reference target preview.",
      change_reason: reason.trim(),
    });
    const embeddedIr = neutral.data.document.material_model_ir.model;
    const neutralSelection = neutral.data.document.candidate_selection.processing_output;
    if (embeddedIr.id !== neutral.data.neutral_material_id
      || embeddedIr.revision_id !== neutral.data.neutral_material_revision_id
      || neutral.data.document.sources.material?.id !== session.material.id
      || neutral.data.document.sources.material?.revision_id !== session.material.revisionId
      || neutral.data.document.sources.material_state?.id !== session.materialState.id
      || neutral.data.document.sources.material_state?.revision_id !== session.materialState.revisionId
      || neutralSelection?.id !== output.processing_output_id
      || neutralSelection?.revision_id !== output.current_revision.id) {
      throw new Error("The Neutral document does not prove the current exact model chain.");
    }
    // Keep the upstream model pointer distinct from Neutral's embedded IR.
    // The server resolves that embedded IR from the exact Neutral revision.
    onSessionEvent?.({ type: "SET_CURRENT", key: "neutralModel", value: {
      id: neutral.data.neutral_material_id,
      revisionId: neutral.data.neutral_material_revision_id,
      label: "Neutral Material with embedded canonical IR",
      revisionNo: neutral.data.revision_no,
    } });
  }

  async function prepare(): Promise<void> {
    if (!canPrepare || !session.material || !session.materialState) return;
    setBusy(true);
    setError(null);
    try {
      let model = modelForNeutral;
      if (!model) {
        const created = await promoteProcessingOutputToTabulatedPlasticity(config, output.processing_output_id, {
          material_state_id: session.materialState.id,
          property_set_revision_id: propertySet.current_revision.id,
          processing_output_revision_id: output.current_revision.id,
          acknowledge_bounded_extrapolation: true,
          change_reason: reason.trim(),
        });
        if (!exactPromotionMatches(session, output, propertySet, created.data)) {
          throw new Error("The promoted model does not match the current exact Output, Material, State, and Property Set revisions.");
        }
        model = {
          id: created.data.material_model_id,
          revisionId: created.data.current_revision.id,
          revisionNo: created.data.current_revision.revision_no,
          manifestSha256: created.data.current_revision.content_hash,
          classification: created.data.current_revision.classification,
          lifecycleState: created.data.current_revision.lifecycle_state,
        };
        // Preserve the successful immutable model even if Neutral promotion
        // fails. The next action retries Neutral only; it never creates a
        // duplicate model revision.
        pinModel(model);
      }
      await promoteNeutral(model);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return <section className="modeling-export-recovery" aria-label="Prepare selected model for Export">
    <h3>Prepare selected model</h3>
    <label><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /> I reviewed the extrapolated range used by this model.</label>
    <label>Reason for preparing model<input aria-label="Reason for preparing model" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
    {modelForNeutral ? <p className="ux-notice" role="status">The model is ready. Retry Export preparation.</p> : null}
    <button className="ux-button primary" type="button" disabled={!canPrepare} onClick={() => void prepare()}>{busy ? "Preparing model…" : modelForNeutral ? "Retry preparation" : "Prepare selected model"}</button>
    {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
  </section>;
}

export function ModelingExportPrerequisites({
  config,
  session,
  output,
  propertySet,
  prerequisites,
  onSessionEvent,
  onNavigate,
}: {
  config?: ApiConfig;
  session?: ModelingSessionSummary | null;
  output?: CommonProcessingOutputResponse;
  propertySet?: PropertySetResponse;
  prerequisites: ExportPrerequisite[];
  onSessionEvent?: (event: ModelingSessionEvent) => void;
  onNavigate?: (path: string) => void;
}) {
  const outputStatus = prerequisites.find((item) => item.label === "Processing Output")?.status;
  const modelStatus = prerequisites.find((item) => item.label === "Material Model IR")?.status;
  const neutralStatus = prerequisites.find((item) => item.label === "Neutral representation")?.status;
  const sourceReady = sourcePrerequisitesCurrent(prerequisites);
  const canPrepareMetal = session?.materialFamily === "metal"
    && sourceReady
    && Boolean(config && session && output && propertySet && currentPropertySet(session, propertySet));
  return (
    <section className="modeling-export-blocked export-workspace" aria-label="Export prerequisites">
      <header className="export-workspace-header">
        <div><h2>Create solver card</h2></div>
        <span className="status-chip warning">Cannot create</span>
      </header>
      <div className="export-workspace-grid">
        <aside className="export-properties" aria-label="Export setup">
          <div className="export-pane-heading"><h3>Export setup</h3></div>
          <div className="export-subsection-heading">Selected model</div>
          <div className="export-property-row"><span>Model</span><strong>{session?.materialModelIr?.label ?? "Not selected"}</strong></div>
          {config
            && session?.materialModelIr?.manifestSha256
            && session.materialModelIr.classification
            && session.materialModelIr.lifecycleState
            && session.neutralModel
            && neutralStatus === "current"
            ? <ReviewRequestAction
                config={config}
                subject={{
                  aggregateType: "modeling.material_model",
                  aggregateId: session.materialModelIr.id,
                  revisionId: session.materialModelIr.revisionId,
                  manifestSha256: session.materialModelIr.manifestSha256,
                  classification: session.materialModelIr.classification,
                  lifecycleState: session.materialModelIr.lifecycleState,
                }}
              />
            : null}
          {onNavigate ? <button type="button" className="text-button" onClick={() => onNavigate("/modeling?stage=fit")}>Back to Fit</button> : null}
          <div className="export-check" aria-label="Export check">
            <div className="export-pane-heading"><p className="workspace-caption">Export check</p><h3 className="visually-hidden">Exact target preview is gated</h3><strong className="export-status export-status-cannot-create">Cannot create</strong></div>
            <p className="ux-notice" role="status">{sourceReady ? "Review the extrapolated range and prepare the selected model." : "Return to Fit and save a model before Export."}</p>
          </div>
          {canPrepareMetal && config && session && output && propertySet
            ? <ModelingMetalExportRecovery config={config} session={session} output={output} propertySet={propertySet} onSessionEvent={onSessionEvent} />
            : session?.materialFamily !== "metal"
              ? <p className="ux-notice" role="status">This model type cannot be prepared for Export.</p>
              : null}
          <details className="export-advanced export-prerequisite-evidence">
            <summary>Advanced · prerequisite evidence</summary>
            <ul className="modeling-export-prerequisite-list" aria-label="Exact Export prerequisite checklist">
              {prerequisites.map((item) => (
                <li key={item.label}>
                  <span className={`mapping-status ${item.status}`}>{item.status.replaceAll("-", " ")}</span>
                  <span><strong>{item.label}</strong><small>{item.detail}</small></span>
                </li>
              ))}
            </ul>
            <section className="modeling-export-lineage" aria-label="Exact Export lineage">
              <strong>Required lineage</strong>
              <ol>
                <li className={outputStatus === "current" ? "current" : outputStatus === "stale" ? "stale" : "missing"}>Processing Output</li>
                <li className={modelStatus === "current" ? "current" : modelStatus === "stale" ? "stale" : "missing"}>Material Model IR</li>
                <li className={neutralStatus === "current" ? "current" : neutralStatus === "stale" ? "stale" : "missing"}>Neutral representation</li>
                <li className="missing">Target mapping preflight and preview_only</li>
                <li className="missing">Create Solver Card after current preview and required acknowledgement</li>
              </ol>
              <small>Preview is <strong>preview_only</strong>. Creating a Solver Card is a separate action that becomes available only after a current preview and any required acknowledgement.</small>
            </section>
          </details>
        </aside>
        <main className="export-main" aria-label="Native preview workspace">
          <div className="export-pane-heading"><h3>Solver card preview</h3><span>Model required</span></div>
          <div className="export-native-preview-shell"><div className="native-preview export-preview-blocked" tabIndex={0} aria-label="Native preview unavailable"><span>No preview</span><small>Prepare a selected model first.</small></div></div>
        </main>
        <aside className="export-result" aria-label="Export result context">
          <section className="mapping-sheet" aria-label="Mapping details"><div className="export-context-heading"><h3>Mapping details</h3></div><div className="mapping-scroll export-mapping-placeholder"><p><strong>No mapping available</strong><span>Model required</span></p><span className="mapping-status blocked">Blocked</span></div></section>
          <section className="export-fit-source" aria-label="Fit source"><div className="export-context-heading"><h3>Fit curve</h3></div><p className="muted">{session?.materialModelIr?.label ?? "No selected model"}</p><div className="fit-source-plot export-fit-source-blocked" role="img" aria-label="Fit source unavailable"><span>Unavailable</span></div></section>
        </aside>
      </div>
    </section>
  );
}
